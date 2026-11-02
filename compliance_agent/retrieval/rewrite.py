"""Rewrite the retrieval query after a grader miss (cheap slot)."""
from __future__ import annotations

from langsmith import traceable
from pydantic import BaseModel, Field

from .. import models


class _Rewrite(BaseModel):
    """A better search query for the legal corpus."""

    query: str = Field(description="Rewritten search query using the regulation's own vocabulary")
    rationale: str = Field(default="", description="One sentence on what changed and why")


_SYSTEM = (
    "You rewrite search queries over the GDPR and the EU AI Act. The previous query did not retrieve the "
    "provisions needed. Rewrite it in the vocabulary the regulations use (e.g. 'automated individual "
    "decision-making', 'profiling', 'data protection impact assessment', 'high-risk AI system', 'deployer', "
    "'provider', 'legal basis', 'legitimate interests'). Name the likely article or annex if you know it. "
    "Keep it under 25 words and do not repeat an earlier query."
)


@traceable(name="rewrite_query", run_type="chain")
def rewrite_query(original: str, previous_queries: list[str], missing: str) -> tuple[str, str]:
    """Returns (new_query, rationale). Falls back to the original with a generic suffix on error."""
    history = "\n".join(f"- {q}" for q in previous_queries)
    msgs = [
        ("system", _SYSTEM),
        ("human", f"Original question: {original}\n\nQueries tried so far:\n{history}\n\nWhat was missing: {missing or 'unclear'}"),
    ]
    try:
        r = models.invoke_structured("cheap", _Rewrite, msgs)
        new_q = r.query.strip()
        if not new_q or new_q.lower() in {q.lower() for q in previous_queries}:
            raise ValueError("rewrite repeated an earlier query")
        return new_q, r.rationale
    except Exception as exc:
        return f"{original} {missing}".strip(), f"rewrite fallback ({exc})"
