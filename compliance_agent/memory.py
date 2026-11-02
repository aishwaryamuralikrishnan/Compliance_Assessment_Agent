"""Long-term memory (LangGraph Store).

    ("org", "facts")               organisation profile, vendor transfer status (seeded)
    ("org", "lessons")             DPO corrections, notes, rejections and kept examples (few-shot examples)
    ("user", <user_ns>, "prefs")   answer-style preferences, recurring context, per user

Recorded assessments live in the processing register only (lookup_register reads it); an approval
writes no memory item of its own.

Store namespace labels may not contain '.', so usernames like "lena.k" are mapped with
`user_prefs_namespace()`. Reading is `recall`; writing is the memory_write node, which
calls `write_items` after the deterministic role gate (`allowed_types`).

What gets written (step 6):
  - candidates are proposed deterministically from the triggering event (`propose_from_decision`
    for a DPO decision, `propose_from_feedback` for a user's note or the DPO's "keep as a good example")
    and shown to the person before the write - the DPO's checkboxes, or the note itself;
  - a free-text comment is turned into one reusable sentence by the cheap model (`reflect`);
    if that call fails the comment is stored verbatim;
  - the rule that decides what is written is the role of the person whose action triggered the
    run (config/roles.yaml `memory_writes`), never the model and never the requester's role.
Every item carries provenance: type, source, author, thread_id, run_id, assessment_id, created_at.
Conversation turns and feature descriptions are never stored.
"""
from __future__ import annotations

import logging

import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from . import config

TYPE_TO_POLICY = {"org_fact": "org_facts", "lesson": "org_lessons", "pref": "user_prefs"}

ORG_FACTS = ("org", "facts")
ORG_LESSONS = ("org", "lessons")


log = logging.getLogger(__name__)

def user_ns_label(username: str) -> str:
    return username.replace(".", "_").replace("/", "_")


def user_prefs_namespace(username: str) -> tuple[str, str, str]:
    return ("user", user_ns_label(username), "prefs")


def _items(results) -> list[dict[str, Any]]:
    out = []
    for it in results:
        v = dict(it.value)
        v.setdefault("key", it.key)
        out.append(v)
    return out


def recall(store: BaseStore, user_id: str, query: str, *, facts_k: int = 6, lessons_k: int = 3, prefs_k: int = 5) -> dict[str, list[dict[str, Any]]]:
    """Memories for one turn: all org facts relevant to the query, a few lessons as examples,
    and only this user's preferences. Semantic search over the Store index; falls back to a
    plain listing if the index is unavailable."""
    def search(ns: tuple, k: int):
        try:
            return _items(store.search(ns, query=query, limit=k))
        except Exception as exc:
            # Semantic search needs the embeddings slot; if that fails, fall back to a plain listing but say so.
            log.warning("semantic memory search failed for %s (%s: %s); falling back to a plain listing", "/".join(ns), type(exc).__name__, exc)
            return _items(store.search(ns, limit=k))

    return {
        "org_facts": search(ORG_FACTS, facts_k),
        "lessons": search(ORG_LESSONS, lessons_k),
        "prefs": search(user_prefs_namespace(user_id), prefs_k),
    }


def format_for_prompt(mem: dict[str, list[dict[str, Any]]]) -> str:
    """Compact block placed in the worker prompt ahead of the retrieved legal text."""
    lines: list[str] = []
    if mem.get("org_facts"):
        lines.append("Organisation facts (long-term memory; source in brackets):")
        for f in mem["org_facts"]:
            lines.append(f"- {f.get('text')} [{f.get('source', '?')}]")
    if mem.get("lessons"):
        lines.append("Standing positions from earlier DPO decisions (apply as requirements):")
        for l in mem["lessons"]:
            lines.append(f"- {l.get('text')}")
    if mem.get("prefs"):
        lines.append("This user's preferences:")
        for p in mem["prefs"]:
            lines.append(f"- {p.get('text')}")
    return "\n".join(lines) if lines else "No long-term memory items yet."


# --------------------------------------------------------------------------------------
# Writing (step 6)
# --------------------------------------------------------------------------------------

def namespace_for(item_type: str, user_id: str) -> tuple:
    if item_type == "org_fact":
        return ORG_FACTS
    if item_type == "lesson":
        return ORG_LESSONS
    return user_prefs_namespace(user_id)


def ns_label(item_type: str, user_id: str) -> str:
    return "/".join(namespace_for(item_type, user_id))


def allowed_types(role: str) -> set[str]:
    """Item types this role's actions may write (roles.yaml -> memory_writes)."""
    policy = set((config.roles_config().get("memory_writes") or {}).get(role, []))
    return {t for t, p in TYPE_TO_POLICY.items() if p in policy}


def _item(item_type: str, text: str, *, source: str, reflect: bool = False, detail: str = "", **extra) -> dict[str, Any]:
    return {"type": item_type, "text": text.strip(), "source": source, "reflect": reflect, "detail": detail, **extra}


def _clean(text: str) -> str:
    """Whitespace-normalised, whole text: a lesson keeps the entire finding or comment."""
    return " ".join(str(text).split())


def _short(text: str, n: int = 110) -> str:
    text = _clean(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def propose_from_decision(original: dict[str, Any], amended: dict[str, Any] | None, decision: str, comment: str,
                          *, requested_by: str) -> list[dict[str, Any]]:
    """Deterministic candidates for a DPO decision, shown as checkboxes before the decision is sent."""
    items: list[dict[str, Any]] = []
    title, aid = original.get("title", ""), original.get("assessment_id", "")
    if amended and amended != original:
        for f, g in zip(original.get("findings", []), amended.get("findings", [])):
            if f.get("severity") != g.get("severity"):
                items.append(_item("lesson", f"DPO treats this as {g['severity']} (assistant said {f['severity']}): {_clean(g.get('text', ''))}",
                                   source="dpo_amendment", detail=f"{title} ({aid})"))
            elif f.get("text") != g.get("text"):
                items.append(_item("lesson", f"DPO rewording of a {g.get('severity')} finding: {_clean(g.get('text', ''))}",
                                   source="dpo_amendment", detail=f"{title} ({aid})"))
    if decision == "reject":
        # one lesson for a rejection: the reason is the lesson (rephrased into a standing position; the original is kept)
        items.append(_item("lesson", f"DPO rejected '{title}'" + (f": {comment.strip()}" if comment.strip() else "."),
                           source="dpo_rejection", reflect=bool(comment.strip()), detail=f"{title} ({aid})"))
    elif decision == "request_changes":
        # one lesson for a change request: what the DPO requires of such a feature
        items.append(_item("lesson", f"DPO requires, before '{title}' can be approved: {comment.strip()}",
                           source="dpo_change_request", reflect=True, detail=f"{title} ({aid})"))
    elif comment.strip():
        items.append(_item("lesson", f"DPO note on '{title}': {comment.strip()}", source="dpo_comment", reflect=True,
                           detail=f"{title} ({aid})"))
    return items[:5]


def propose_from_feedback(comment: str | None, *, keep_example: bool, assessment: dict[str, Any] | None, answer: str | None,
                          user_id: str, dpo_involved: bool) -> list[dict[str, Any]]:
    """Candidates for feedback on a completed thread: a note becomes the author's own preference; "keep as a
    good example" on a DPO-approved assessment becomes a lesson (the role gate limits that to the DPO)."""
    items: list[dict[str, Any]] = []
    title = (assessment or {}).get("title") or _short(answer or "", 60)
    if comment and comment.strip():
        items.append(_item("pref", f"{user_id} on '{title}': {comment.strip()}", source="feedback_comment", reflect=True))
    if keep_example and dpo_involved and assessment:
        heads = "; ".join(f"{f.get('severity')}: {_clean(f.get('text', ''))}" for f in assessment.get("findings", [])[:3])
        items.append(_item("lesson", f"Good example (DPO-approved, rated up by {user_id}): '{title}' - {assessment.get('verdict')}. {heads}",
                           source="top_rated_example", detail=assessment.get("assessment_id", "")))
    return items


class _Reflection(BaseModel):
    text: str = Field(description="One sentence, reusable in future assessments, no personal names or contact details.")


_REFLECT_PROMPT = """You maintain the long-term memory of a GDPR / AI Act compliance assistant.
Rewrite the note below as ONE sentence the assistant can apply to future assessments: a standing position,
rule of thumb or preference. Keep concrete legal references and the stance; drop case-specific
narrative, personal names and contact details. If the note is only a preference about answer style
(length, format, tone), phrase it as 'Prefers ...'."""


def reflect(items: list[dict[str, Any]], *, model_slot: str = "cheap") -> list[dict[str, Any]]:
    """Rephrase comment-based items into one reusable sentence (cheap model). Verbatim fallback."""
    from . import models

    out = []
    for it in items:
        it = dict(it)
        if it.get("reflect"):
            try:
                r = models.invoke_structured(model_slot, _Reflection, [("system", _REFLECT_PROMPT), ("human", it["text"])])
                if r.text.strip():
                    it["original"] = it["text"]
                    it["detail"] = (it.get("detail", "") + f" · original: {it['text']}").strip(" ·")
                    it["text"], it["reflected"] = r.text.strip(), True
            except Exception as exc:          # model unavailable: store the comment as written
                it["reflected"], it["reflect_error"] = False, str(exc)[:120]
        out.append(it)
    return out


NEAR_DUPLICATE = 0.92     # cosine similarity above which two items are the same memory


def _exists(store: BaseStore, ns: tuple, text: str, original: str | None = None) -> str | None:
    """Why this text is already stored, or None. Three checks: the same text verbatim, the same
    source note verbatim (a rephrase of it is not new), and a near-identical embedding (a note
    with one word changed, or the cheap model's slightly different wording of it)."""
    try:
        if store.search(ns, filter={"text": text}, limit=1):
            return "already stored"
        if original and store.search(ns, filter={"original": original}, limit=1):
            return "already stored (same note)"
        for hit in store.search(ns, query=text, limit=1):
            score = getattr(hit, "score", None)
            if score is not None and score >= NEAR_DUPLICATE:
                return f"near-duplicate of an existing item (similarity {score:.2f})"
    except Exception:
        return None
    return None


def write_items(store: BaseStore, items: list[dict[str, Any]], *, role: str, author: str, thread_id: str,
                run_id: str | None, assessment_id: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The deterministic gate: write what `role` may write, drop the rest. Returns (written, dropped)."""
    allowed = allowed_types(role)
    written, dropped = [], []
    for it in items:
        t = it.get("type", "pref")
        text = " ".join(str(it.get("text", "")).split())
        if not text:
            continue
        rec = {"ns": ns_label(t, author), "type": t, "text": text, "source": it.get("source", "")}
        if t not in allowed:
            dropped.append({**rec, "why": f"{role} may not write {TYPE_TO_POLICY.get(t, t)}"})
            continue
        ns = namespace_for(t, author)
        why = _exists(store, ns, text, it.get("original"))
        if why:
            dropped.append({**rec, "why": why})
            continue
        key = f"{it.get('source', 'learned')}-{uuid.uuid4().hex[:10]}"
        try:
            store.put(ns, key, {
                "text": text, "kind": t, "source": it.get("source", "learned"), "author": author, "thread_id": thread_id,
                "run_id": run_id, "assessment_id": assessment_id or it.get("assessment_id"), "detail": it.get("detail", ""),
                "reflected": bool(it.get("reflected")), "original": it.get("original") or text,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
        except Exception as exc:              # e.g. the embedding call for the index failed: report, do not crash the run
            dropped.append({**rec, "why": f"store write failed: {str(exc)[:100]}"})
            continue
        written.append({**rec, "key": key})
    return written, dropped


def list_namespace(store: BaseStore, ns: tuple, limit: int = 50) -> list[dict[str, Any]]:
    items = _items(store.search(ns, limit=limit))
    return sorted(items, key=lambda v: str(v.get("created_at") or ""), reverse=True)
