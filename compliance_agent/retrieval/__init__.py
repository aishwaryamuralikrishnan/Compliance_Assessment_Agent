"""Agentic retrieval over the legal corpus.

    identifiers.py  "Article 22(1)", "Recital 71", "Annex III point 5(b)" -> metadata filters
    search.py       vector + full-text + identifier lookups, reciprocal rank fusion
    rerank.py       cross-encoder reranker (Rerank 4 Fast) with LLM fallback
    grader.py       grade(query, chunks) -> (sufficient, confidence, relevant_chunk_ids)
    rewrite.py      query rewrite on a grader miss
    loop.py         retrieve -> rerank -> grade -> (rewrite -> retry) x <= 3
"""
from .loop import RetrievalResult, search_with_loop  # noqa: F401
from .search import RetrievedChunk, hybrid_search, fetch_by_reference  # noqa: F401
