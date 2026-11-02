"""Read-only legal tools: search_regulation and get_article.

Both return `content_and_artifact`: the content is what the model reads; the artifact is
the structured chunk list the graph uses for citation verification and the source panel.
Every tool catches its own errors and returns a message the model can act on.
"""
from __future__ import annotations

from typing import Literal

import uuid

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from ..retrieval.loop import search_with_loop
from ..retrieval.search import RetrievedChunk, fetch_by_reference

Regulation = Literal["GDPR", "AI_ACT"]


def format_chunks(chunks: list[RetrievedChunk], max_chars: int = 2500) -> str:
    if not chunks:
        return "No matching provisions found."
    parts = []
    for c in chunks:
        tag = " (supporting context)" if c.grader_relevant is False else ""
        parts.append(f"[{c.citation}] {c.heading}{tag}\n{c.text[:max_chars]}")
    return "\n\n".join(parts)


@tool(response_format="content_and_artifact")
def search_regulation(query: str, regulation: Regulation | None = None, k: int = 5) -> tuple[str, dict]:
    """Search the GDPR and the EU AI Act for the provisions on ONE topic.

    The query must be a single focused topic of at most ~10 words in the regulations' vocabulary,
    e.g. "automated individual decision-making profiling", "high-risk AI creditworthiness Annex III",
    "data protection impact assessment required", "legal basis legitimate interests", "storage
    limitation retention period", "transfer to third country adequacy". Do NOT bundle several topics
    into one query - call the tool once per topic instead (calls run in parallel). Optionally restrict
    to one regulation. Returns up to k passages, each prefixed with its citation such as
    [GDPR Art. 22(1)] or [AI Act Annex III point 5]; cite exactly those labels in your answer.
    """
    # Stream the loop's progress (attempt, grade, rewrite, stop) tagged with a call id, so the
    # UI can show each tool call as its own section even when calls run in parallel.
    call_id = uuid.uuid4().hex[:6]
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    def emit(event: dict) -> None:
        if writer:
            writer({**event, "call": call_id, "tool": "search_regulation"})

    try:
        result = search_with_loop(query, regulation=regulation, k=max(1, min(k, 8)), emit=emit)
    except Exception as exc:
        return f"search_regulation failed: {exc}. Try get_article with an explicit reference.", {"error": str(exc)}
    note = "" if result.sufficient else "\n\n(Note: retrieval could not confirm these passages fully cover the question; cite them carefully and say what is uncertain.)"
    return format_chunks(result.chunks) + note, result.as_dict()


@tool(response_format="content_and_artifact")
def get_article(regulation: Regulation, article: str, paragraph: str | None = None) -> tuple[str, dict]:
    """Return the exact text of one provision when you already know the identifier.

    `article` accepts "22", "75a", "Recital 71" or "Annex III point 5"; `paragraph` optionally narrows
    an article to one numbered paragraph ("1", "1a"). Use this to quote a provision verbatim or to
    check a citation before relying on it.
    """
    ref = article.strip()
    if ref.isdigit() or (ref[:-1].isdigit() and ref[-1].isalpha()):
        ref = f"Article {ref}" + (f"({paragraph})" if paragraph else "")
    try:
        chunks = fetch_by_reference(regulation, ref)
    except Exception as exc:
        return f"get_article failed: {exc}", {"error": str(exc)}
    if not chunks:
        return f"No provision matches '{ref}' in {regulation}. Check the number or use search_regulation.", {"chunks": []}
    return format_chunks(chunks, max_chars=6000), {"chunks": [c.as_dict() for c in chunks]}
