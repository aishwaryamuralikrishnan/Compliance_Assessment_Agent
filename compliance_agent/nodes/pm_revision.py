"""pm_revision: the second human pause of a thread, for the product manager.

After the DPO's "Request changes" the run does not end: memory_write (which stores the DPO's requirement as a
lesson) continues here, and this node calls interrupt() with everything the product manager's page needs. Her
"Run revision" resumes the thread with {"description": ..., "responses": [...]}; the node screens the revised
description deterministically (limits, PII redaction, the injection regex: no model call, see TOOLS.md), writes the
revision into the state, puts the reviser's brief into the messages, and the graph proceeds to the reviser.

A text that fails the screen, or a resume by anyone but the thread's requester, does not end the turn: the node
records the reason in `revision_error` and the conditional edge runs it again, which is a fresh interrupt() whose
payload carries the reason, so the page shows it above the form. (A loop of interrupt() calls inside one node is
avoided on purpose: on replay the identity in the config is the latest resumer's, not the one who sent each
earlier answer.) A refused thread simply stays paused, like a review the DPO has not decided yet.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.config import get_config, get_stream_writer
from langgraph.types import interrupt

from .. import repo, tracing
from ..state import GraphState
from .reviser import revision_brief
from .validate_input import MAX_CHARS, MIN_CHARS, _INJECTION_HINTS, redact_pii

INTERRUPT_TYPE = "pm_revision"


def screen_revision(raw: str) -> tuple[str, list[str], str | None]:
    """Deterministic screen of the revised description: (redacted text, flags, reason or None)."""
    text = (raw or "").strip()
    flags: list[str] = []
    if len(text) < MIN_CHARS:
        return text, ["too_short"], "The revised description is too short. Describe the feature as it will be built."
    if len(text) > MAX_CHARS:
        return text, ["too_long"], f"The revised description is longer than {MAX_CHARS} characters. Shorten it."
    text, n = redact_pii(text)
    if n:
        flags.append("pii_redacted")
    if _INJECTION_HINTS.search(text):
        return text, flags + ["injection"], ("The revised description contains instructions to the assistant rather than a description "
                                             "of the feature. Describe what will be built; the assistant decides what it means.")
    return text, flags, None


def _refuse(reason: str, attempts: int, by: str, **extra) -> dict[str, Any]:
    say = get_stream_writer()
    say({"node": "pm_revision", "event": "refused", "by": by, "reason": reason, "attempt": attempts + 1, **extra})
    tracing.tag_run("pm_revision:refused", refused_user=by, reason=reason[:120])
    return {"revision_error": reason, "revision_attempts": attempts + 1}


def pm_revision(state: GraphState) -> dict[str, Any]:
    say = get_stream_writer()
    cfg = get_config().get("configurable", {})
    thread_id = cfg.get("thread_id", "")
    attempts = int(state.get("revision_attempts") or 0)
    cr = repo.change_request_for_thread(thread_id)                    # idempotent: re-read when the node re-executes
    if not cr:
        # memory_write routes here only after a "request changes" decision, so an open request must exist; if it does
        # not, the database and the thread disagree and the run must not continue silently.
        raise RuntimeError(f"pm_revision reached on thread {thread_id} without an open change request")
    v1, task = cr["assessment"], cr["task"] or {}
    requester = v1.get("created_by")
    payload: dict[str, Any] = {
        "type": INTERRUPT_TYPE, "thread_id": thread_id, "revises": v1["assessment_id"], "title": v1.get("title"),
        "requests": cr["requests"], "comment": task.get("dpo_comment") or "", "requested_by": task.get("resolved_by"),
        "requester": requester, "previous_description": v1.get("description") or "", "error": state.get("revision_error"),
    }
    say({"node": "pm_revision", "event": "pause", "revises": v1["assessment_id"], "requests": len(cr["requests"]),
         "requester": requester, "error": state.get("revision_error")})
    tracing.tag_run("pm_revision:interrupt", interrupt_type=INTERRUPT_TYPE, revises=v1["assessment_id"])

    answer = interrupt(payload) or {}
    resumer = get_config().get("configurable", {})                      # whoever resumed the thread
    r_id, r_role = resumer.get("user_id", "unknown"), resumer.get("role", "unknown")
    if r_id != requester or r_role != "product_manager":
        return _refuse(f"Only the requester ({requester}) can revise this feature; it stays waiting.", attempts, r_id)
    text, flags, reason = screen_revision(str(answer.get("description") or ""))
    if reason:
        return _refuse(reason, attempts, r_id, flags=flags)

    responses = [{"status": "not_possible" if str((r or {}).get("status", "done")).startswith("not") else "done",
                  "note": str((r or {}).get("note") or "").strip()} for r in (answer.get("responses") or [])]
    responses += [{"status": "done", "note": ""}] * max(0, len(cr["requests"]) - len(responses))
    revision = {
        "revises": v1["assessment_id"], "requests": cr["requests"], "responses": responses[: len(cr["requests"])],
        "comment": task.get("dpo_comment") or "", "requested_by": task.get("resolved_by"),
        "previous_description": v1.get("description") or "", "v1": v1["assessment"],
    }
    say({"node": "pm_revision", "event": "received", "by": r_id, "chars": len(text), "flags": flags,
         "responses": [r["status"] for r in revision["responses"]], "revises": v1["assessment_id"]})
    tracing.tag_run("pm_revision:received", "route:revise", *[f"input:{f}" for f in flags], revises=v1["assessment_id"])
    return {
        "messages": [HumanMessage(content=revision_brief(revision, text), additional_kwargs={"kind": "request"})],
        "input": text, "validation": {"ok": True, "reason": "revision screened deterministically", "flags": flags, "redactions": flags.count("pii_redacted")},
        "revision": revision, "route": "revise", "route_confidence": 1.0,
        "route_reason": f"revision of {v1['assessment_id']} after the DPO requested changes",
        "assessment": None, "answer": None, "sources": [], "guardrail": {}, "structured_response": None,
        "review_requested": False, "regenerations": 0, "decision": None, "feedback": None,
        "revision_error": None, "revision_attempts": 0,
    }


def after_pm_revision(state: GraphState) -> str:
    """pm_revision → itself while a resume was refused (a fresh pause with the reason), → reviser once the revision is in the state."""
    return "pm_revision" if state.get("revision_error") else "reviser"


def after_memory_write(state: GraphState) -> str:
    """memory_write → pm_revision after a 'request changes' decision, → END otherwise."""
    return "pm_revision" if state.get("decision") == "changes_requested" else "__end__"
