"""Cross-encoder reranking of the fused top-20 down to top-5.

Primary, when `reranker.method` in config/models.yaml is `api`: the `reranker` slot (Rerank 4 Fast) through the
gateway's POST /rerank, which reads query and chunk together. With `method: llm` (the setting since 3 Nov: the
reranker has no zero-data-retention endpoint, so the account's data policy refuses it) the listwise rerank by the
cheap model with structured output is the first choice; it is otherwise the fallback when the call fails. Last
resort: keep the fused order. The result says which path ran so the trace is honest about it.
"""
from __future__ import annotations

from typing import Any

import requests
from langsmith import traceable
from pydantic import BaseModel, Field

from .. import config, models
from .search import RetrievedChunk


class _Listwise(BaseModel):
    """Indices of the most relevant passages, best first."""

    ranked_indices: list[int] = Field(description="0-based indices of the passages, most relevant first")


def _doc_text(c: RetrievedChunk, max_chars: int = 2000) -> str:
    return f"{c.heading}\n{c.text}"[:max_chars]


def _rerank_provider() -> dict[str, Any]:
    """The provider policy of config/models.yaml for the rerank call, without `zdr`: the reranker has no
    zero-data-retention endpoint on the gateway (probe 2 Nov, scripts/probe_provider.py), so with it every rerank
    would fail over to the LLM fallback; the rest of the policy (data_collection: deny) is sent."""
    return {k: v for k, v in models._provider_routing().items() if k != "zdr"}


def _rerank_api(query: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]:
    spec = models.slot_spec("reranker")
    url = f"{config.openrouter_base_url()}{spec.get('endpoint', '/rerank')}"
    body: dict[str, Any] = {"model": spec["model"], "query": query, "documents": [_doc_text(c) for c in chunks], "top_n": top_n}
    provider = _rerank_provider()
    if provider:
        body["provider"] = provider
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {config.openrouter_api_key()}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    results = body.get("results") or body.get("data") or []
    if not results:
        raise RuntimeError(f"rerank endpoint returned no results: {str(body)[:200]}")
    out: list[RetrievedChunk] = []
    for r in results[:top_n]:
        idx = int(r["index"])
        c = chunks[idx]
        c.rerank_score = float(r.get("relevance_score", r.get("score", 0.0)))
        out.append(c)
    return out


def _rerank_llm(query: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]:
    numbered = "\n\n".join(f"[{i}] {_doc_text(c, 900)}" for i, c in enumerate(chunks))
    msgs = [
        ("system", "You rank legal passages by how directly they answer the question. Return the indices of the most relevant passages, best first."),
        ("human", f"Question: {query}\n\nPassages:\n{numbered}\n\nReturn the {top_n} most relevant passage indices."),
    ]
    result = models.invoke_structured("cheap", _Listwise, msgs)
    out: list[RetrievedChunk] = []
    for pos, idx in enumerate(result.ranked_indices):
        if 0 <= idx < len(chunks) and chunks[idx] not in out:
            chunks[idx].rerank_score = round(1.0 - pos / max(len(result.ranked_indices), 1), 3)
            out.append(chunks[idx])
        if len(out) >= top_n:
            break
    if not out:
        raise RuntimeError("LLM rerank returned no valid indices")
    return out


@traceable(name="rerank", run_type="chain")
def rerank(query: str, chunks: list[RetrievedChunk], top_n: int | None = None) -> tuple[list[RetrievedChunk], dict[str, Any]]:
    """Returns (top-n chunks in rerank order, trace)."""
    if not chunks:
        return [], {"method": "none", "n_in": 0}
    spec = models.slot_spec("reranker")
    top_n = top_n or int(spec.get("top_n", 5))
    errors: list[str] = []
    if spec.get("method", "api") == "api":            # method: llm skips the gateway's reranker (no zero-retention endpoint, 3 Nov)
        try:
            ranked = _rerank_api(query, chunks, top_n)
            return ranked, {"method": "rerank_api", "model": spec["model"], "n_in": len(chunks),
                            "top": [(c.citation, c.rerank_score) for c in ranked]}
        except Exception as exc:
            errors.append(f"rerank_api: {exc}")
    try:
        ranked = _rerank_llm(query, chunks, top_n)
        return ranked, {"method": "llm_listwise", "n_in": len(chunks), "errors": errors,
                        "top": [(c.citation, c.rerank_score) for c in ranked]}
    except Exception as exc:
        errors.append(f"llm_listwise: {exc}")
    ranked = chunks[:top_n]
    return ranked, {"method": "fused_order", "n_in": len(chunks), "errors": errors, "top": [(c.citation, None) for c in ranked]}
