"""output_guardrail: verify citations, scan for PII, check the schema, append the disclaimer,
persist the verified draft.

verify_citations is a string check against the corpus metadata, not a model call: every
citation label in the output ("GDPR Art. 22(1)", "AI Act Annex III point 5") must resolve to
a chunk. An unknown citation sends the draft back to the worker for ONE regeneration; after
that, unknown citations are removed and the output is flagged.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.config import get_config, get_stream_writer
from langgraph.graph import END
from langgraph.types import Command
from pydantic import ValidationError

from .. import repo, tracing
from ..retrieval.identifiers import parse_identifiers
from ..retrieval.search import fetch_by_reference
from ..state import Assessment, GraphState, StatusReply
from .validate_input import redact_pii

log = logging.getLogger(__name__)

DISCLAIMER = ("This is an automated first assessment based on the text of the GDPR and the EU AI Act, "
              "not legal advice. It becomes an organisational record only after the DPO approves it.")

RE_CITATION = re.compile(
    r"\b(GDPR|AI Act)\s+(?:Art\.?\s*\d{1,3}[a-z]?(?:\(\d{1,2}[a-z]?\))?(?:\([a-z]{1,2}\))?"
    r"|Rec\.?\s*\d{1,3}"
    r"|Annex\s+[IVXLC]+(?:\s*,?\s*(?:point\s*)?\d{1,2}(?:\([a-z]{1,2}\))?)?)",
)

_verified_cache: dict[str, str] = {}

VERIFIED, UNKNOWN, UNREACHABLE = "verified", "unknown", "unreachable"


def verify_citation(label: str) -> str:
    """Three states, never a guess: VERIFIED (the label resolves to a chunk, and to the paragraph when one is
    named), UNKNOWN (the corpus has no such provision: a hallucinated or malformed label), UNREACHABLE (the
    corpus could not be queried: database down, pool exhausted). Only UNKNOWN may trigger a regeneration or the
    removal of a citation; UNREACHABLE is logged with the real error and reported, and the citation is kept.
    Results are cached per process except UNREACHABLE, which is retried on the next call."""
    if label in _verified_cache:
        return _verified_cache[label]
    parsed = parse_identifiers(label)
    reg = parsed.single_regulation
    if not (reg and parsed.identifiers):
        _verified_cache[label] = UNKNOWN
        return UNKNOWN
    ident = parsed.identifiers[0]
    try:
        chunks = fetch_by_reference(reg, label)
    except Exception as exc:
        log.warning("citation lookup failed for %r (corpus unreachable): %s: %s", label, type(exc).__name__, exc)
        return UNREACHABLE
    state = UNKNOWN
    if chunks:
        state = VERIFIED
        if ident.kind == "article" and ident.paragraph is not None and all(c.paragraph is None for c in chunks):
            marker = re.compile(rf"(?:^|\n)\s*{ident.paragraph}{ident.paragraph_letter or ''}\.\s")
            state = VERIFIED if any(marker.search(c.text) for c in chunks) else UNKNOWN
    _verified_cache[label] = state
    return state


def citation_exists(label: str) -> bool:
    """Backwards-compatible boolean view of verify_citation (an unreachable corpus counts as not verified here;
    the guardrail itself uses verify_citation so it can tell the two apart)."""
    return verify_citation(label) == VERIFIED


def _check_labels(labels: list[str]) -> tuple[list[str], list[str]]:
    """(unknown labels, unreachable labels) for a list of citation labels."""
    states = {l: verify_citation(l) for l in labels}
    return [l for l, st in states.items() if st == UNKNOWN], [l for l, st in states.items() if st == UNREACHABLE]


def extract_citations(*texts: str) -> list[str]:
    found: list[str] = []
    for t in texts:
        for m in RE_CITATION.finditer(t or ""):
            label = re.sub(r"\s+", " ", m.group(0)).strip()
            if label not in found:
                found.append(label)
    return found


def collect_sources(messages: list) -> list[dict[str, Any]]:
    """Chunks retrieved in the current turn: tool artifacts after the last HumanMessage."""
    start = 0
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            start = i
    seen: dict[str, dict] = {}
    for m in messages[start:]:
        if isinstance(m, ToolMessage) and getattr(m, "artifact", None):
            art = m.artifact if isinstance(m.artifact, dict) else {}
            for c in art.get("chunks", []):
                seen.setdefault(c.get("citation") or c.get("chunk_key"), c)
    return list(seen.values())


def _assessment_texts(a: dict) -> list[str]:
    texts = [a.get("summary", ""), *a.get("next_steps", [])]
    for f in a.get("findings", []):
        texts.append(f.get("text", ""))
        texts.extend(f.get("citations", []))
    return texts


def _render_assessment(a: dict) -> str:
    lines = [f"Assessment {a.get('assessment_id', '')} · {a.get('title')} · {a.get('risk_level', '').upper()} risk",
             f"{a.get('verdict')}. {a.get('summary')}", ""]
    if a.get("revises"):
        lines.append(f"Revises {a['revises']}. Changes since v1:")
        for c in a.get("changes_since_v1") or []:
            lines.append(f"- {c.get('request')} → PM: {c.get('pm_response')} → {c.get('outcome')}: {c.get('explanation')}")
        lines.append("")
    for f in a.get("findings", []):
        lines.append(f"[{f['severity']}] {f['text']} ({', '.join(f.get('citations', [])) or 'no citation'})")
    if a.get("next_steps"):
        lines.append("")
        lines.append("Next steps: " + " ".join(f"{i}. {s}" for i, s in enumerate(a["next_steps"], 1)))
    lines.append("")
    lines.append(a.get("disclaimer", DISCLAIMER))
    return "\n".join(lines)


_REGISTER_ID = re.compile(r"\bA-\d{4}\b")


def _names_register_entry(text: str) -> bool:
    """True when the reply points at an assessment that really is in the register ("already recorded as A-0012")."""
    for aid in set(_REGISTER_ID.findall(text or "")):
        try:
            if repo.search_register(aid):
                return True
        except Exception:
            continue
    return False


def _unusable_output(messages: list) -> str | None:
    """Why the agent's last model output produced no structured response, when that is visible on the message:
    the output was cut off at the token limit (finish_reason "length") or a tool call's JSON was malformed. Returns
    a short reason or None."""
    for m in reversed(messages or []):
        if isinstance(m, AIMessage):
            fr = (getattr(m, "response_metadata", None) or {}).get("finish_reason")
            invalid = list(getattr(m, "invalid_tool_calls", None) or [])
            if fr == "length":
                return "the output was cut off at the model's token limit"
            if invalid:
                err = (invalid[0].get("error") or "malformed JSON")
                return f"the {invalid[0].get('name') or 'structured'} tool call was malformed ({str(err)[:120]})"
            return None
    return None


def _last_decision(thread_id: str) -> str | None:
    """The DPO's latest decision on this thread (approved | changes_requested | rejected), read from the review task the
    gate resolved; None while nothing is decided. memory_write's outgoing edge uses it to continue into pm_revision."""
    try:
        task = repo.review_task_for_thread(thread_id)
    except Exception as exc:
        log.warning("could not read the last decision on thread %s: %s: %s", thread_id, type(exc).__name__, exc)
        return None
    status = (task or {}).get("status")
    return status if status in ("approved", "changes_requested", "rejected") else None


def output_guardrail(state: GraphState):
    say = get_stream_writer()
    cfg = get_config().get("configurable", {})
    thread_id, user_id = cfg.get("thread_id", ""), cfg.get("user_id", "unknown")
    agent = "reviser" if state.get("route") == "revise" else "worker"      # who produced the draft and who is sent back
    sources = collect_sources(state.get("messages", [])) or list(state.get("sources", []))
    regenerations = int(state.get("regenerations", 0) or 0)
    sr = state.get("structured_response")
    answer = state.get("answer")
    report: dict[str, Any] = {"citations_checked": 0, "invalid": [], "pii_redactions": 0, "regenerated": regenerations}

    # ---- status reply / quick answer ------------------------------------------------
    if isinstance(sr, StatusReply):
        answer = sr.message
    elif isinstance(sr, dict) and "message" in sr and "findings" not in sr:
        answer = sr["message"]

    if not isinstance(sr, Assessment) and not (isinstance(sr, dict) and "findings" in sr):
        text = answer or ""
        # A feature description must end in an Assessment. If the worker returned a status reply on the full path
        # without any assessment behind it (a summary, an acknowledgement, a clarification), send it back once.
        # The one legitimate status reply here points at an existing register entry.
        if (state.get("route") in ("full", "revise") and not state.get("review_requested") and not state.get("assessment")
                and regenerations < 1 and not _names_register_entry(text)):
            cut_off = _unusable_output(state.get("messages", []))
            reason = cut_off or "status reply instead of an assessment"
            say({"node": "output_guardrail", "event": "regenerate", "reason": reason})
            tracing.tag_run("guardrail:regenerated", regenerated_for="unusable_output" if cut_off else "no_assessment")
            if cut_off:
                ask = (f"Your Assessment could not be used: {cut_off}. Produce the Assessment structured output again, "
                       "shorter: at most eight findings, two or three sentences each, next_steps as short items. "
                       "Keep every citation label exactly as the tools returned it.")
            else:
                ask = ("That is not the deliverable. The request was a feature description" + (" revision" if agent == "reviser" else "") + ", so produce the Assessment "
                       "structured output now (verdict, severity-tagged findings with the citation labels the tools returned, "
                       "next steps, DPIA and high-risk-AI flags). Use the passages you already retrieved; do not ask for "
                       "more detail - put open questions into next_steps.")
            return Command(goto=agent, update={
                "regenerations": regenerations + 1, "guardrail": report,
                "messages": [HumanMessage(content=ask)],
            })
        labels = extract_citations(text)
        invalid, unreachable = _check_labels(labels)
        for l in invalid:
            text = text.replace(l, f"{l} [unverified]")
        text, n = redact_pii(text)
        report.update(citations_checked=len(labels), invalid=invalid, unreachable=unreachable, pii_redactions=n)
        if unreachable:
            say({"node": "output_guardrail", "event": "source_unreachable", "labels": unreachable})
        say({"node": "output_guardrail", "event": "checked", "kind": "answer", **{k: v for k, v in report.items()}})
        # a status reply that closes a review (approved / rejected) keeps the assessment it is about on the thread
        # and continues to memory_write (there is a DPO decision to store); a quick answer is finished here
        closing_review = bool(state.get("review_requested"))
        update = {"answer": text, "sources": sources, "guardrail": report,
                  "assessment": state.get("assessment") if closing_review else None,
                  "decision": _last_decision(thread_id) if closing_review else None}
        if text and not state.get("messages") or (state.get("messages") and not isinstance(state["messages"][-1], AIMessage)):
            update["messages"] = [AIMessage(content=text)]
        return Command(goto="memory_write" if closing_review else END, update=update)

    # ---- assessment -----------------------------------------------------------------
    a = sr.model_dump() if isinstance(sr, Assessment) else dict(sr)
    labels = extract_citations(*_assessment_texts(a))
    invalid, unreachable = _check_labels(labels)
    report.update(citations_checked=len(labels), invalid=invalid, unreachable=unreachable)
    if unreachable:
        # The corpus could not be queried for these labels. This is not a hallucination: nothing is regenerated or
        # removed; the labels are kept, reported in the trace and marked in the stored draft.
        say({"node": "output_guardrail", "event": "source_unreachable", "labels": unreachable})
        tracing.tag_run("guardrail:source_unreachable", unreachable=unreachable)

    if invalid and regenerations < 1:
        say({"node": "output_guardrail", "event": "regenerate", "invalid": invalid})
        tracing.tag_run("guardrail:regenerated", regenerated_for=invalid)
        return Command(
            goto=agent,
            update={
                "regenerations": regenerations + 1,
                "guardrail": report,
                "messages": [HumanMessage(content=(
                    "Citation check failed. These citation labels do not exist in the corpus: "
                    + ", ".join(invalid)
                    + ". Regenerate the Assessment using only citation labels returned by the tools "
                      "(call get_article to verify a provision if needed). Keep everything else."
                ))],
            },
        )

    if invalid:
        for f in a.get("findings", []):
            f["citations"] = [c for c in f.get("citations", []) if c not in invalid]
        for key in ("summary",):
            for l in invalid:
                a[key] = a.get(key, "").replace(l, f"{l} [unverified]")
        a["next_steps"] = [re.sub("|".join(re.escape(l) for l in invalid), lambda m: f"{m.group(0)} [unverified]", s) for s in a.get("next_steps", [])]

    n_total = 0
    for key in ("title", "summary"):
        a[key], n = redact_pii(a.get(key, "")); n_total += n
    for f in a.get("findings", []):
        f["text"], n = redact_pii(f.get("text", "")); n_total += n
    steps = []
    for s in a.get("next_steps", []):
        s2, n = redact_pii(s); n_total += n; steps.append(s2)
    a["next_steps"] = steps
    report["pii_redactions"] = n_total

    try:
        a = Assessment.model_validate(a).model_dump()
    except ValidationError as exc:
        if regenerations < 1:
            say({"node": "output_guardrail", "event": "regenerate", "schema_error": str(exc)[:300]})
            tracing.tag_run("guardrail:regenerated", schema_error=str(exc)[:200])
            return Command(goto=agent, update={
                "regenerations": regenerations + 1, "guardrail": report,
                "messages": [HumanMessage(content=f"The assessment did not match the required schema ({str(exc)[:300]}). Produce it again.")],
            })
        report["schema_error"] = str(exc)[:300]

    rev = state.get("revision") if state.get("route") == "revise" else None
    if rev:
        # Revision rules, enforced here rather than trusted to the prompt.
        problem = None
        if not a.get("changes_since_v1"):
            problem = "a revision must contain changes_since_v1, one entry per requested change, and revises = the v1 id"
        elif any(r.get("status") == "not_possible" for r in (rev.get("responses") or [])) and a.get("verdict") == "Proceed":
            problem = ("a requested change was marked 'not possible', so its finding stays open and the verdict cannot be "
                       "'Proceed'; keep the finding and its severity and set the verdict accordingly")
        if problem and regenerations < 1:
            say({"node": "output_guardrail", "event": "regenerate", "reason": f"revision rule: {problem}"})
            tracing.tag_run("guardrail:regenerated", regenerated_for="revision_rule")
            return Command(goto=agent, update={
                "regenerations": regenerations + 1, "guardrail": report,
                "messages": [HumanMessage(content=f"Revision rule not met: {problem}. Produce the Assessment again.")],
            })
        a["revises"] = rev.get("revises")
        report["revision_rule"] = problem                   # None when met; recorded if a second attempt still fails
        if problem:
            a["revision_rule_violation"] = problem          # shown to the DPO on the card
    a["findings"] = sorted(a["findings"], key=lambda f: {"Blocker": 0, "Required": 1, "Covered": 2}.get(f["severity"], 3))
    a["sources"] = [c.get("citation") for c in sources]
    a["verified_citations"] = [l for l in labels if l not in invalid and l not in unreachable]
    if unreachable:
        a["unverified_citations"] = unreachable          # kept, could not be checked against the corpus this time
    a["disclaimer"] = DISCLAIMER
    row = repo.create_assessment(thread_id, a["title"][:200], a, user_id, description=state.get("input") or None,
                                 revises=(rev or {}).get("revises"))
    a["assessment_id"] = row["assessment_id"]
    tracing.tag_run("output:assessment", *(["guardrail:citations_removed"] if report["invalid"] else []),
                    assessment_id=a["assessment_id"], citations_checked=report["citations_checked"], citations_invalid=report["invalid"])
    say({"node": "output_guardrail", "event": "checked", "kind": "assessment", "assessment_id": a["assessment_id"],
         "citations_checked": len(labels), "invalid": invalid, "unreachable": unreachable, "pii_redactions": n_total, "sources": len(sources)})
    if state.get("review_requested"):
        # a second assessment in the same run (the worker re-assessed instead of requesting review): stop here
        return Command(goto="memory_write", update={
            "assessment": a, "answer": None, "sources": sources, "guardrail": report, "decision": _last_decision(thread_id),
            "messages": [AIMessage(content=_render_assessment(a))],
        })
    # An assessment is not the end of the thread. The verified, stored draft is shown to the requester and the
    # worker is sent back once to request DPO review: it calls request_dpo_review through the tool gate, which
    # pauses the thread with interrupt() until the DPO decides.
    request = f"Please request DPO review for {a['assessment_id']}."
    say({"node": "output_guardrail", "event": "request_review", "assessment_id": a["assessment_id"], "agent": agent,
         "revises": a.get("revises")})
    return Command(goto=agent, update={
        "assessment": a, "answer": None, "sources": sources, "guardrail": report, "review_requested": True,
        "structured_response": None,
        "messages": [AIMessage(content=_render_assessment(a)), HumanMessage(content=request)],
    })
