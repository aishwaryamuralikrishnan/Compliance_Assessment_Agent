"""The agentic RAG loop as a unit (to-do item 4): search_with_loop with hybrid search, reranker, grader and rewrite
replaced by stubs, so every branch of the loop is exercised without a database or a model: accept on the first pass,
rewrite then accept, three misses, the diminishing-returns stop, the grader switched off. Then the grader's own
decision rule (threshold, no relevant passages, a failed call) and the rewrite's fallbacks."""
from __future__ import annotations

import pytest

import compliance_agent.retrieval.grader as GR
import compliance_agent.retrieval.loop as L
import compliance_agent.retrieval.rewrite as RW
from compliance_agent.retrieval.grader import GradeResult
from compliance_agent.retrieval.search import RetrievedChunk


def _chunk(i: int, article: int) -> RetrievedChunk:
    return RetrievedChunk(id=i, chunk_key=f"k{i}", regulation="GDPR", unit_type="article", heading=f"Article {article}",
                          text=f"text of article {article}", article=article)


def _stubs(monkeypatch, verdicts: list[GradeResult], per_query: dict[str, list[int]] | None = None):
    """hybrid search returns chunks by query (ids), the reranker keeps the order, the grader answers from `verdicts`
    in turn, the rewrite appends ' v2' / ' v3'. Returns the list of (event) the loop emitted."""
    calls = {"grade": 0, "rewrite": 0}

    def hybrid(q, regulation=None, k=20):
        ids = (per_query or {}).get(q, [1, 2, 3, 4, 5])
        return [_chunk(i, 20 + i) for i in ids], {"identifiers": [], "fused_top": [f"Art. {20 + i}" for i in ids]}

    def rerank(q, chunks, top_n=5):
        for n, c in enumerate(chunks[:top_n]):
            c.rerank_score = 1.0 - n / 10
        return chunks[:top_n], {"method": "stub", "top": [(c.citation, c.rerank_score) for c in chunks[:top_n]]}

    def grade(q, chunks):
        v = verdicts[min(calls["grade"], len(verdicts) - 1)]
        calls["grade"] += 1
        return v

    def rewrite(original, previous, missing):
        calls["rewrite"] += 1
        return f"{original} v{calls['rewrite'] + 1}", f"added {missing}"

    monkeypatch.setattr(L, "hybrid_search", hybrid)
    monkeypatch.setattr(L, "rerank", rerank)
    monkeypatch.setattr(L, "grade", grade)
    monkeypatch.setattr(L, "rewrite_query", rewrite)
    return calls


def test_first_pass_sufficient(monkeypatch):
    calls = _stubs(monkeypatch, [GradeResult(True, 0.9, [3, 1], "passages cover the question")])
    events: list[dict] = []
    r = L.search_with_loop("q", k=5, emit=events.append)
    assert r.sufficient and len(r.attempts) == 1 and calls["rewrite"] == 0
    assert [c.id for c in r.chunks] == [1, 3, 2, 4, 5]                  # grader-relevant first (best rerank score first), then the rest
    assert [c.grader_relevant for c in r.chunks] == [True, True, False, False, False]
    assert [e["event"] for e in events] == ["retrieve", "graded", "done"]
    assert events[1]["relevant"] == ["GDPR Art. 21", "GDPR Art. 23"] and events[1]["sufficient"] is True
    assert r.as_dict()["attempts"][0]["grade"]["relevant_chunk_ids"] == [3, 1]


def test_miss_then_rewrite_then_accept(monkeypatch):
    calls = _stubs(monkeypatch, [GradeResult(False, 0.9, [], "Article 22 is missing"), GradeResult(True, 0.95, [6, 7], "ok")],
                   per_query={"q": [1, 2, 3, 4, 5], "q v2": [6, 7, 8, 9, 10]})
    events: list[dict] = []
    r = L.search_with_loop("q", k=5, emit=events.append)
    assert r.sufficient and r.queries == ["q", "q v2"] and calls["rewrite"] == 1
    assert [e["event"] for e in events] == ["retrieve", "graded", "rewrite", "retrieve", "graded", "done"]
    assert events[2]["new_query"] == "q v2" and events[2]["why"] == "added Article 22 is missing"
    assert r.attempts[0].rewrite_rationale == "added Article 22 is missing" and r.attempts[1].rewrite_rationale is None
    assert [c.id for c in r.chunks][:2] == [6, 7]                      # the accepted passages come from the second pass


def test_three_misses_return_the_last_top_five_as_context(monkeypatch):
    calls = _stubs(monkeypatch, [GradeResult(False, 0.8, [], "missing")])
    r = L.search_with_loop("q", k=5, max_attempts=3, emit=None)
    assert not r.sufficient and len(r.attempts) == 3 and calls["rewrite"] == 2    # no rewrite after the last attempt
    assert r.queries == ["q", "q v2", "q v3"]
    assert len(r.chunks) == 5 and all(c.grader_relevant is False for c in r.chunks)
    assert r.as_dict()["sufficient"] is False


def test_diminishing_returns_stops_after_a_rewrite_with_mostly_relevant_passages(monkeypatch):
    _stubs(monkeypatch, [GradeResult(False, 0.9, [1], "A"), GradeResult(False, 0.9, [1, 2, 3], "B, a side topic")])
    events: list[dict] = []
    r = L.search_with_loop("q", k=5, emit=events.append)
    assert r.sufficient and len(r.attempts) == 2
    graded = [e for e in events if e["event"] == "graded"]
    assert graded[-1]["sufficient"] is True and graded[-1]["reason"].startswith("accepted: most passages relevant")
    assert [c.id for c in r.chunks][:3] == [1, 2, 3]


def test_grader_off_is_a_single_pass(monkeypatch):
    calls = _stubs(monkeypatch, [GradeResult(False, 0.1, [], "would have missed")])
    r = L.search_with_loop("q", k=3, max_attempts=1, use_grader=False)
    assert r.sufficient and calls["grade"] == 0 and calls["rewrite"] == 0
    assert r.attempts[0].grade.reason == "grader disabled" and [c.id for c in r.chunks] == [1, 2, 3]


# --------------------------------------------------------------------------------------
# the grader's decision rule
# --------------------------------------------------------------------------------------

def _grader_spec(monkeypatch, threshold: float):
    monkeypatch.setattr(GR.models, "slot_spec", lambda name: {"model": "x/y", "accept_threshold": threshold})
    monkeypatch.setattr(GR.models, "resolved_model_ids", lambda: {"grader": "x/y"})


def test_grader_accepts_only_above_threshold_with_relevant_passages(monkeypatch):
    chunks = [_chunk(1, 22), _chunk(2, 35)]
    answers = iter([
        GR._Grade(sufficient=True, confidence=0.9, relevant_passage_numbers=[2], missing=""),
        GR._Grade(sufficient=True, confidence=0.5, relevant_passage_numbers=[1], missing=""),       # confident enough? no
        GR._Grade(sufficient=True, confidence=0.9, relevant_passage_numbers=[], missing=""),        # nothing relevant: no
        GR._Grade(sufficient=False, confidence=0.9, relevant_passage_numbers=[1, 9], missing="Art. 6(4)"),
    ])
    monkeypatch.setattr(GR.models, "invoke_structured", lambda slot, schema, msgs: next(answers))
    _grader_spec(monkeypatch, 0.6)
    a = GR.grade("q", chunks)
    assert a.sufficient and a.relevant_chunk_ids == [2] and a.reason == "passages cover the question" and a.model == "x/y"
    b = GR.grade("q", chunks)
    assert not b.sufficient and b.confidence == 0.5
    c = GR.grade("q", chunks)
    assert not c.sufficient and c.relevant_chunk_ids == []
    d = GR.grade("q", chunks)
    assert not d.sufficient and d.relevant_chunk_ids == [1] and d.reason == "Art. 6(4)"       # passage 9 does not exist: ignored
    assert d.as_dict() == {"sufficient": False, "confidence": 0.9, "relevant_chunk_ids": [1], "reason": "Art. 6(4)", "model": "x/y"}


def test_grader_without_passages_and_with_a_failed_call(monkeypatch):
    _grader_spec(monkeypatch, 0.6)
    assert GR.grade("q", []) == GradeResult(False, 1.0, [], "no passages retrieved", "x/y")

    def boom(slot, schema, msgs):
        raise RuntimeError("gateway 502")

    monkeypatch.setattr(GR.models, "invoke_structured", boom)
    r = GR.grade("q", [_chunk(1, 22)])
    assert r.sufficient and r.confidence == 0.0 and r.relevant_chunk_ids == [1] and r.model == "error"
    assert r.reason.startswith("grader error after a retry, accepted as-is: gateway 502")         # the safety net says what happened


# --------------------------------------------------------------------------------------
# the rewrite
# --------------------------------------------------------------------------------------

def test_rewrite_uses_the_model_and_falls_back_honestly(monkeypatch):
    monkeypatch.setattr(RW.models, "invoke_structured", lambda slot, schema, msgs: RW._Rewrite(query="automated individual decision-making GDPR Art. 22", rationale="law's vocabulary"))
    q, why = RW.rewrite_query("nobody looks at the declines", ["nobody looks at the declines"], "Art. 22")
    assert q == "automated individual decision-making GDPR Art. 22" and why == "law's vocabulary"

    # a rewrite that repeats an earlier query is refused and the fallback appends what was missing
    monkeypatch.setattr(RW.models, "invoke_structured", lambda slot, schema, msgs: RW._Rewrite(query="Nobody looks at the declines", rationale=""))
    q, why = RW.rewrite_query("nobody looks at the declines", ["nobody looks at the declines"], "Art. 22")
    assert q == "nobody looks at the declines Art. 22" and "repeated an earlier query" in why

    def boom(slot, schema, msgs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(RW.models, "invoke_structured", boom)
    q, why = RW.rewrite_query("q", ["q"], "")
    assert q == "q" and why == "rewrite fallback (timeout)"


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
