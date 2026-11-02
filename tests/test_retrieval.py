"""Retrieval tests.

Pure-function tests always run. Database tests run when DATABASE_URL points at a database
that already holds the seeded corpus (>= 1,000 chunks); they are read-only and use fake
query embeddings so no model is called.
"""
from __future__ import annotations

import os
import random

import pytest

from compliance_agent.retrieval.identifiers import parse_identifiers
from compliance_agent.retrieval.search import RetrievedChunk, reciprocal_rank_fusion


def test_identifiers_articles_recitals_annexes():
    p = parse_identifiers("Does Article 22(1) of the GDPR apply? See also Recital 71 and Art. 35(3)(a).")
    assert p.regulations == ["GDPR"]
    labels = {(f.kind, f.article, f.paragraph, f.recital, f.point) for f in p.identifiers}
    assert ("article", 22, 1, None, None) in labels
    assert ("recital", None, None, 71, None) in labels
    assert ("article", 35, 3, None, "a") in labels
    assert all(f.regulation == "GDPR" for f in p.identifiers)

    p = parse_identifiers("Annex III point 5(b) and Article 75a; also Art 5(1a)")
    anx = next(f for f in p.identifiers if f.kind == "annex")
    assert (anx.annex, anx.point, anx.regulation) == ("III", "5", "AI_ACT")
    a75 = next(f for f in p.identifiers if f.article == 75)
    assert a75.article_letter == "a"
    a5 = next(f for f in p.identifiers if f.article == 5)
    assert (a5.paragraph, a5.paragraph_letter) == (1, "a")

    assert parse_identifiers("do we need consent for marketing emails").identifiers == []
    assert parse_identifiers("AI Act and GDPR both").regulations == ["GDPR", "AI_ACT"]


def _chunk(i: int) -> RetrievedChunk:
    return RetrievedChunk(id=i, chunk_key=f"k{i}", regulation="GDPR", unit_type="article", heading=f"h{i}", text="t", article=i)


def test_rrf_prefers_chunks_in_both_lists_and_identifier_hits():
    a, b, c, d = _chunk(1), _chunk(2), _chunk(3), _chunk(4)
    fused = reciprocal_rank_fusion({"vector": [a, b, c], "fulltext": [c, b], "identifier": [d]})
    order = [x.id for x in fused]
    # b and c appear in two lists; d is an identifier hit (weighted double) -> all three beat a
    assert set(order[:3]) == {2, 3, 4}
    assert fused[-1].id == 1
    # an identifier-only hit outranks a vector-only hit at the same rank
    solo = reciprocal_rank_fusion({"vector": [a], "identifier": [d]})
    assert [x.id for x in solo] == [4, 1]
    assert fused[0].ranks and fused[0].fused_score > 0


def test_citation_format():
    c = RetrievedChunk(id=1, chunk_key="x", regulation="AI_ACT", unit_type="article_paragraph", heading="", text="", article=5, paragraph=1, paragraph_letter="a")
    assert c.citation == "AI Act Art. 5(1a)"
    c = RetrievedChunk(id=1, chunk_key="x", regulation="AI_ACT", unit_type="annex_point", heading="", text="", annex="III", point="5")
    assert c.citation == "AI Act Annex III point 5"
    c = RetrievedChunk(id=1, chunk_key="x", regulation="GDPR", unit_type="recital", heading="", text="", recital=71)
    assert c.citation == "GDPR Rec. 71"


# --------------------------------------------------------------------------------------
# Database-backed (read-only, needs the seeded corpus)
# --------------------------------------------------------------------------------------

def _corpus_available() -> bool:
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        from compliance_agent import db
        with db.connect_plain() as conn:
            n = conn.execute("SELECT count(*) AS n FROM legal_chunks").fetchone()["n"]
        return n >= 1000
    except Exception:
        return False


needs_corpus = pytest.mark.skipif(not _corpus_available(), reason="seeded corpus not available at DATABASE_URL")


@pytest.fixture()
def fake_query_embeddings(monkeypatch):
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    import compliance_agent.retrieval.search as S

    class FakeEmb:
        def embed_query(self, t):
            return [random.random() for _ in range(1536)]

    monkeypatch.setattr(S, "embeddings", lambda: FakeEmb())


@needs_corpus
def test_exact_lookups_against_corpus(fake_query_embeddings):
    from compliance_agent.retrieval.search import fetch_by_reference

    assert [c.citation for c in fetch_by_reference("GDPR", "Article 22")] == ["GDPR Art. 22"]
    assert [c.citation for c in fetch_by_reference("GDPR", "Recital 71")] == ["GDPR Rec. 71"]
    assert [c.citation for c in fetch_by_reference("GDPR", "Article 4(4)")] == ["GDPR Art. 4(4)"]
    assert [c.citation for c in fetch_by_reference("AI_ACT", "Annex III point 5")] == ["AI Act Annex III point 5"]
    assert [c.citation for c in fetch_by_reference("AI_ACT", "Article 5(1a)")] == ["AI Act Art. 5(1a)"]
    assert [c.citation for c in fetch_by_reference("AI_ACT", "Art. 75b")] == ["AI Act Art. 75b"]
    assert fetch_by_reference("GDPR", "Article 999") == []


@needs_corpus
def test_fulltext_and_hybrid_against_corpus(fake_query_embeddings):
    from compliance_agent.retrieval.search import fulltext_search, hybrid_search

    hits = [c.citation for c in fulltext_search("creditworthiness of natural persons credit score", k=10, regulation="AI_ACT")]
    assert "AI Act Annex III point 5" in hits
    fused, trace = hybrid_search("Does Article 22 GDPR apply to automated credit scoring using browsing behaviour?")
    assert trace["regulation_filter"] == "GDPR"
    assert trace["identifier_hits"] == ["GDPR Art. 22"]
    assert fused[0].citation == "GDPR Art. 22"          # identifier hit always surfaces
    assert any("fulltext" in c.ranks for c in fused)      # OR-semantics keyword leg contributes


@needs_corpus
def test_get_article_tool(fake_query_embeddings):
    from compliance_agent.tools import get_article

    out = get_article.invoke({"regulation": "GDPR", "article": "22", "paragraph": "1"})
    assert out.startswith("[GDPR Art. 22]")
    out = get_article.invoke({"regulation": "AI_ACT", "article": "Annex III point 5"})
    assert "creditworthiness" in out
