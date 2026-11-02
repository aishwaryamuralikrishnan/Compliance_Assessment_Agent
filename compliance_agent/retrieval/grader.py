"""Retrieval grader: are these chunks enough to answer the question?

grade(query, chunks) -> GradeResult(sufficient, confidence, relevant_chunk_ids, reason), answered by the `grader`
chat slot with structured output. Grading is a small reasoning job: the grader has to name the provision that is
missing so that the rewrite can go to it, and the cheapest models ask for judgements instead (scripts/probe_grader.py,
23 Oct 2026; the measurement and the choice are recorded in config/models.yaml). The slot is separate from `cheap`
(the rewrite) and may be the worker's own model: the grader never sees the worker's text, it judges passages that
come from the database through the embeddings and the reranker against a ten-word query, so the independence that
matters, the evaluation judge's, is untouched. `grader.accept_threshold` in models.yaml is what the stage-2
calibration (to-do item 8) tunes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langsmith import traceable
from pydantic import BaseModel, Field

from .. import models
from .search import RetrievedChunk

log = logging.getLogger(__name__)


@dataclass
class GradeResult:
    sufficient: bool
    confidence: float
    relevant_chunk_ids: list[int] = field(default_factory=list)
    reason: str = ""
    model: str = ""                      # the grader model id, for the trace
    model_sufficient: bool | None = None  # what the model said before the threshold; the evaluation's threshold sweep (E4) reads it

    def as_dict(self) -> dict:
        return {"sufficient": self.sufficient, "confidence": round(self.confidence, 3),
                "relevant_chunk_ids": self.relevant_chunk_ids, "reason": self.reason, "model": self.model}


class _Grade(BaseModel):
    """Judgement on whether the retrieved legal passages suffice to answer the question."""

    sufficient: bool = Field(description="True if the passages contain the provisions needed to answer the question with article citations")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the judgement, 0 to 1")
    relevant_passage_numbers: list[int] = Field(description="1-based numbers of the passages that are actually relevant")
    missing: str = Field(default="", description="If not sufficient: the one provision needed for the central question that is missing, in one sentence")


_SYSTEM = (
    "You grade retrieved passages from the GDPR and the EU AI Act for a compliance assistant. "
    "Identify the central question of the search query (if the query bundles several topics, the first or "
    "dominant one). The passages are SUFFICIENT when they contain the specific provisions that answer that central "
    "question with article citations (the obligation, condition, exception or risk classification at stake), even "
    "if side topics in the query would need a separate search. They are INSUFFICIENT when the passages are only "
    "loosely related, cover a different situation, or miss the key provision for the central question. "
    "In `missing`, name only the provision needed for the central question, not side topics."
)


def _grade_llm(query: str, chunks: list[RetrievedChunk]) -> GradeResult:
    model_id = models.resolved_model_ids().get("grader", "")
    if not chunks:
        return GradeResult(False, 1.0, [], "no passages retrieved", model_id)
    numbered = "\n\n".join(f"[{i}] {c.heading}\n{c.text[:1500]}" for i, c in enumerate(chunks, start=1))
    msgs = [("system", _SYSTEM), ("human", f"Question: {query}\n\nPassages:\n{numbered}")]
    r = models.invoke_structured("grader", _Grade, msgs)
    threshold = float(models.slot_spec("grader").get("accept_threshold", 0.6))
    ids = [chunks[n - 1].id for n in r.relevant_passage_numbers if 1 <= n <= len(chunks)]
    sufficient = bool(r.sufficient) and r.confidence >= threshold and bool(ids)
    reason = r.missing if not sufficient else "passages cover the question"
    return GradeResult(sufficient, float(r.confidence), ids, reason, model_id, bool(r.sufficient))


@traceable(name="grade_chunks", run_type="chain")
def grade(query: str, chunks: list[RetrievedChunk]) -> GradeResult:
    last: Exception | None = None
    for attempt in (1, 2):                       # one retry: a model that returns no structured output once usually does the second time
        try:
            return _grade_llm(query, chunks)
        except Exception as exc:
            last = exc
            log.warning("grader call %d failed: %s: %s", attempt, type(exc).__name__, exc)
    # A failed grader must not stall retrieval: accept what we have, with low confidence, and say so.
    return GradeResult(True, 0.0, [c.id for c in chunks], f"grader error after a retry, accepted as-is: {last}", "error")
