"""The reranker's three paths (to-do item 4) with the gateway and the cheap model replaced: the /rerank endpoint,
the listwise fallback on the cheap model when the endpoint fails, and the fused order as the last resort, each
named in the trace so the UI is honest about what ran. Then the tools' own refusals: search_regulation reporting
a failed retrieval instead of inventing passages, and get_article's reference handling."""
from __future__ import annotations

import pytest

import compliance_agent.retrieval.rerank as RR
import compliance_agent.tools.regulation as TR
from compliance_agent.retrieval.search import RetrievedChunk


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(RR.models, "slot_spec", lambda name: {"model": "cohere/rerank-4-fast", "endpoint": "/rerank", "top_n": 3})


def _chunks(n: int) -> list[RetrievedChunk]:
    return [RetrievedChunk(id=i, chunk_key=f"k{i}", regulation="GDPR", unit_type="article", heading=f"Article {i}", text=f"t{i}", article=i) for i in range(n)]


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def test_rerank_api_path(monkeypatch):
    sent = {}

    def post(url, headers=None, json=None, timeout=None):
        sent.update(url=url, json=json)
        return _Resp({"results": [{"index": 3, "relevance_score": 0.91}, {"index": 0, "relevance_score": 0.4}, {"index": 4, "score": 0.2}]})

    monkeypatch.setattr(RR.requests, "post", post)
    ranked, trace = RR.rerank("q", _chunks(5))
    assert sent["url"].endswith("/rerank") and sent["json"]["model"] == "cohere/rerank-4-fast" and sent["json"]["top_n"] == 3
    assert sent["json"]["documents"][1].startswith("Article 1\n")
    # the provider policy travels with the rerank call too, minus zdr (the reranker has no zero-retention endpoint)
    assert sent["json"]["provider"] == {"data_collection": "deny"} and "zdr" not in sent["json"]["provider"]
    assert [c.id for c in ranked] == [3, 0, 4] and [c.rerank_score for c in ranked] == [0.91, 0.4, 0.2]
    assert trace["method"] == "rerank_api" and trace["n_in"] == 5 and trace["top"][0] == ("GDPR Art. 3", 0.91)
    assert RR.rerank("q", []) == ([], {"method": "none", "n_in": 0})


def test_rerank_falls_back_to_the_cheap_model_then_to_the_fused_order(monkeypatch):
    monkeypatch.setattr(RR.requests, "post", lambda *a, **k: _Resp({"error": "no permitted endpoint"}, status=502))
    monkeypatch.setattr(RR.models, "invoke_structured", lambda slot, schema, msgs: RR._Listwise(ranked_indices=[2, 2, 9, 0]))
    ranked, trace = RR.rerank("q", _chunks(4), top_n=2)
    assert [c.id for c in ranked] == [2, 0] and trace["method"] == "llm_listwise"      # a repeated or out-of-range index is ignored
    assert trace["errors"] == ["rerank_api: HTTP 502"] and ranked[0].rerank_score == 1.0

    monkeypatch.setattr(RR.requests, "post", lambda *a, **k: _Resp({"results": []}))
    monkeypatch.setattr(RR.models, "invoke_structured", lambda slot, schema, msgs: RR._Listwise(ranked_indices=[]))
    ranked, trace = RR.rerank("q", _chunks(4), top_n=2)
    assert [c.id for c in ranked] == [0, 1] and trace["method"] == "fused_order"
    assert trace["errors"][0].startswith("rerank_api: rerank endpoint returned no results") and trace["errors"][1] == "llm_listwise: LLM rerank returned no valid indices"
    assert trace["top"] == [("GDPR Art. 0", None), ("GDPR Art. 1", None)]


def test_search_tool_reports_a_failed_retrieval_and_an_unconfirmed_one(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(TR, "search_with_loop", boom)
    text, artifact = TR.search_regulation.func("q", regulation="GDPR")
    assert text.startswith("search_regulation failed: database unavailable") and artifact == {"error": "database unavailable"}

    from compliance_agent.retrieval.grader import GradeResult
    from compliance_agent.retrieval.loop import Attempt, RetrievalResult
    chunks = _chunks(2)
    weak = RetrievalResult("q", chunks, False, [Attempt(1, "q", {}, {}, GradeResult(False, 0.9, [], "missing Art. 22"))])
    monkeypatch.setattr(TR, "search_with_loop", lambda *a, **k: weak)
    text, artifact = TR.search_regulation.func("q", k=20)
    assert "[GDPR Art. 0]" in text and text.rstrip().endswith("cite them carefully and say what is uncertain.)")
    assert artifact["sufficient"] is False and artifact["attempts"][0]["grade"]["reason"] == "missing Art. 22"


def test_get_article_reference_forms(monkeypatch):
    seen = []

    def fetch(regulation, ref):
        seen.append((regulation, ref))
        return _chunks(1) if "22" in ref else []

    monkeypatch.setattr(TR, "fetch_by_reference", fetch)
    text, art = TR.get_article.func("GDPR", "22", "1")
    assert seen[-1] == ("GDPR", "Article 22(1)") and "[GDPR Art. 0]" in text and len(art["chunks"]) == 1
    TR.get_article.func("AI_ACT", "75a")
    assert seen[-1] == ("AI_ACT", "Article 75a")
    TR.get_article.func("GDPR", "Recital 71")
    assert seen[-1] == ("GDPR", "Recital 71")                                          # passed through as written
    text, art = TR.get_article.func("GDPR", "Annex III point 5")
    assert text.startswith("No provision matches 'Annex III point 5' in GDPR") and art == {"chunks": []}

    def boom(regulation, ref):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(TR, "fetch_by_reference", boom)
    text, art = TR.get_article.func("GDPR", "22")
    assert text == "get_article failed: database unavailable" and art == {"error": "database unavailable"}


def test_embeddings_carry_the_provider_policy_in_the_request_body(monkeypatch):
    """The provider block rides in extra_body (the OpenAI SDK merges it into the JSON); a bare keyword is rejected by
    the SDK, which is how the Neon seed failed on 2 Nov."""
    from compliance_agent import models

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    models.embeddings.cache_clear()
    emb = models.embeddings()
    params = emb._invocation_params
    assert "provider" not in params and params["extra_body"]["provider"]["data_collection"] == "deny"
    seen = {}

    class _Resp:
        @staticmethod
        def model_dump():
            return {"data": [{"embedding": [0.0] * 3, "index": 0}], "usage": None}

    emb.client = type("C", (), {"create": staticmethod(lambda **kw: (seen.update(kw), _Resp())[1])})()
    emb.embed_documents(["x"])
    assert seen["extra_body"] == {"provider": models._provider_routing()}   # whatever config/models.yaml says (data_collection, zdr)
    models.embeddings.cache_clear()


def test_method_llm_skips_the_gateway_reranker(monkeypatch):
    """`reranker.method: llm` (3 Nov): the cheap model ranks first, the /rerank endpoint is never called."""
    monkeypatch.setattr(RR.models, "slot_spec", lambda name: {"model": "cohere/rerank-4-fast", "endpoint": "/rerank", "top_n": 2, "method": "llm"})
    monkeypatch.setattr(RR.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("the gateway reranker must not be called")))
    monkeypatch.setattr(RR.models, "invoke_structured", lambda slot, schema, msgs: RR._Listwise(ranked_indices=[2, 0]))
    ranked, trace = RR.rerank("q", _chunks(4))
    assert [c.id for c in ranked] == [2, 0] and trace["method"] == "llm_listwise" and trace["errors"] == []
