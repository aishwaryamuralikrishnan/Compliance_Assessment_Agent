"""memory_write: runs after every DPO decision and on feedback (step 6); the last node of a run unless the decision
was "request changes", in which case the run continues into pm_revision (see graph.py).

Two triggers, both human actions:
  - a DPO decision that resumed this thread (the review task carries the items the DPO ticked);
  - a feedback event (a user's note, or the DPO's "keep as a good example") delivered with
    `Command(update={"feedback": ...}, goto="memory_write")` by `graph.send_feedback`.

Candidates come from `memory.propose_*` (deterministic) or from the ticked checkboxes; items based on a
free-text comment go through `memory.reflect` (cheap model, verbatim fallback). The write itself is
gated by the role in config["configurable"] - the person whose action triggered this run - via
roles.yaml `memory_writes`: a product manager can only ever write their own preferences.
A run with neither trigger writes nothing and says so.
"""
from __future__ import annotations

from typing import Any

from langgraph.config import get_config, get_stream_writer
from langgraph.runtime import Runtime

from .. import auth, memory, repo, tracing
from ..state import GraphState


def memory_write(state: GraphState, runtime: Runtime) -> dict[str, Any]:
    say = get_stream_writer()
    cfg = get_config()
    c = cfg.get("configurable", {})
    thread_id, user_id, role = c.get("thread_id", ""), c.get("user_id", ""), c.get("role", "")
    run_id = c.get("run_id") or (str(cfg.get("run_id")) if cfg.get("run_id") else None)   # root run id (configurable), for provenance
    feedback = state.get("feedback") or None
    decision = repo.decision_awaiting_memory(thread_id, user_id) if (thread_id and auth.can_approve(role)) else None

    candidates: list[dict[str, Any]] = []
    triggers: list[str] = []
    assessment_id = None
    if decision:
        triggers.append(f"dpo_{decision['status']}")
        assessment_id = decision["assessment_id"]
        ticked = decision.get("memory_items") or []
        if ticked:
            candidates += ticked
        else:   # decided without the UI (CLI): propose from the stored decision
            kind = {"approved": "approve", "changes_requested": "request_changes"}.get(decision["status"], "reject")
            candidates += memory.propose_from_decision(decision["assessment"], None, kind,
                                                       decision.get("dpo_comment") or "", requested_by=decision["requested_by"])
    if feedback:
        triggers.append("feedback")
        a = state.get("assessment")
        row = repo.get_assessment(a["assessment_id"]) if a else (repo.latest_assessment_for_thread(thread_id) if thread_id else None)
        if a is None and row:                 # the thread moved on (e.g. a status turn): the vote is about its assessment
            a = row["assessment"]
        assessment_id = assessment_id or (a or {}).get("assessment_id")
        dpo_involved = bool(row) and row.get("status") in ("approved", "recorded")
        candidates += memory.propose_from_feedback(feedback.get("comment"), keep_example=bool(feedback.get("example")), assessment=a,
                                                   answer=state.get("answer"), user_id=user_id, dpo_involved=dpo_involved)

    if not triggers:
        say({"node": "memory_write", "event": "skipped", "triggers": [], "role": role})
        return {"memory_items": [], "feedback": None}

    say({"node": "memory_write", "event": "reflecting", "triggers": triggers, "role": role, "candidates": len(candidates),
         "to_reflect": sum(1 for x in candidates if x.get("reflect"))})
    items = memory.reflect(candidates) if candidates else []
    written: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    if runtime.store is not None and items:
        written, dropped = memory.write_items(runtime.store, items, role=role, author=user_id, thread_id=thread_id,
                                              run_id=run_id, assessment_id=assessment_id)
    elif items:
        dropped = [{"type": x.get("type"), "text": x.get("text"), "why": "no store attached"} for x in items]
    if decision:
        repo.mark_memory_written(decision["id"])
    tracing.tag_run(*[f"memory:{w['type']}" for w in written], *[f"trigger:{t}" for t in triggers],
                    memory_written=[w["ns"] + " ← " + w["text"][:80] for w in written], memory_dropped=[d.get("why") for d in dropped])
    say({"node": "memory_write", "event": "written", "triggers": triggers, "role": role, "by": user_id,
         "written": written, "dropped": dropped, "feedback_example": (feedback or {}).get("example"),
         "langsmith": (feedback or {}).get("langsmith")})
    return {"memory_items": written, "feedback": None}
