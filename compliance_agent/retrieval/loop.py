"""The agentic RAG loop behind search_regulation.

    attempt = 1
    loop:
        fused   = hybrid_search(query)          # vector + full-text + identifiers, RRF
        top5    = rerank(query, fused)          # Rerank 4 Fast
        verdict = grade(query, top5)            # sufficient? confidence? which chunks?
        if verdict.sufficient or attempt == max_attempts: stop
        query   = rewrite_query(...)            # cheap model
        attempt += 1

The tool returns the chunks the grader marked relevant (union over attempts, best first),
or the final top-5 if the grader never accepted. Every attempt is recorded in
`RetrievalResult.attempts` and optionally streamed through `emit(event)` so the UI can
show "retrieve, attempt 2: ... grader says insufficient" in real time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from langsmith import traceable

from .grader import GradeResult, grade
from .rerank import rerank
from .rewrite import rewrite_query
from .search import RetrievedChunk, hybrid_search

Emit = Callable[[dict[str, Any]], None] | None


@dataclass
class Attempt:
    number: int
    query: str
    search_trace: dict[str, Any]
    rerank_trace: dict[str, Any]
    grade: GradeResult
    rewrite_rationale: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.number, "query": self.query, "identifiers": self.search_trace.get("identifiers", []),
            "fused_top": self.search_trace.get("fused_top", []), "rerank_method": self.rerank_trace.get("method"),
            "reranked": self.rerank_trace.get("top", []), "grade": self.grade.as_dict(),
            "rewrite_rationale": self.rewrite_rationale,
        }


@dataclass
class RetrievalResult:
    original_query: str
    chunks: list[RetrievedChunk]
    sufficient: bool
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def queries(self) -> list[str]:
        return [a.query for a in self.attempts]

    def as_dict(self) -> dict[str, Any]:
        return {"query": self.original_query, "sufficient": self.sufficient, "attempts": [a.as_dict() for a in self.attempts],
                "chunks": [c.as_dict() for c in self.chunks]}


@traceable(name="search_regulation_loop", run_type="chain")
def search_with_loop(
    query: str,
    regulation: str | None = None,
    k: int = 5,
    max_attempts: int = 3,
    emit: Emit = None,
    use_grader: bool = True,
) -> RetrievalResult:
    def say(event: dict[str, Any]) -> None:
        if emit:
            emit({"node": "search_regulation", **event})

    attempts: list[Attempt] = []
    accepted: dict[int, RetrievedChunk] = {}
    current = query
    last_top: list[RetrievedChunk] = []
    sufficient = False

    for n in range(1, max_attempts + 1):
        say({"event": "retrieve", "attempt": n, "query": current})
        fused, s_trace = hybrid_search(current, regulation=regulation, k=20)
        top, r_trace = rerank(current, fused, top_n=k)
        last_top = top
        if use_grader:
            verdict = grade(query, top)   # grade against the ORIGINAL question, not the rewrite
        else:
            verdict = GradeResult(True, 1.0, [c.id for c in top], "grader disabled", "none")
        attempt = Attempt(n, current, s_trace, r_trace, verdict)
        attempts.append(attempt)
        say({"event": "graded", "attempt": n, "sufficient": verdict.sufficient, "confidence": round(verdict.confidence, 2),
             "relevant": [c.citation for c in top if c.id in verdict.relevant_chunk_ids],
             "top": [c.citation for c in top], "reason": verdict.reason})

        for c in top:
            if c.id in verdict.relevant_chunk_ids and c.id not in accepted:
                accepted[c.id] = c
        if verdict.sufficient:
            sufficient = True
            break
        # Diminishing returns: after a rewrite, if the grader still marks most passages relevant
        # and only side topics are missing, stop rather than burn the last attempt.
        if n >= 2 and len(verdict.relevant_chunk_ids) >= 3:
            say({"event": "graded", "attempt": n, "sufficient": True, "confidence": round(verdict.confidence, 2),
                 "relevant": [c.citation for c in top if c.id in verdict.relevant_chunk_ids],
                 "reason": "accepted: most passages relevant after a rewrite; remaining gaps need a separate search"})
            sufficient = True
            break
        if n < max_attempts:
            new_q, why = rewrite_query(query, [a.query for a in attempts], verdict.reason)
            attempt.rewrite_rationale = why
            say({"event": "rewrite", "attempt": n, "new_query": new_q, "why": why})
            current = new_q

    # Grader-relevant chunks first (best rerank score first); then fill up to k with the
    # remaining reranked passages of the last attempt, flagged as supporting context.
    chunks = sorted(accepted.values(), key=lambda c: -(c.rerank_score or 0.0))[:k]
    for c in chunks:
        c.grader_relevant = True
    for c in last_top:
        if len(chunks) >= k:
            break
        if c.id not in accepted:
            c.grader_relevant = False
            chunks.append(c)
    say({"event": "done", "attempts": len(attempts), "sufficient": sufficient, "chunks": [c.citation for c in chunks]})
    return RetrievalResult(query, chunks, sufficient, attempts)
