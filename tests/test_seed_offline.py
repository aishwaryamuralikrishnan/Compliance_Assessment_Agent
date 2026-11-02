"""End-to-end seed run against a real Postgres, without model calls.

Runs against the scratch database (tests/conftest.py): the test REPLACES the GDPR rows with a
4-chunk fixture, so it must never run against the real corpus database. Uses the chunker fixture
as a stand-in for the EUR-Lex download and fake embeddings.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

import pytest

@pytest.fixture()
def fake_models(monkeypatch, tmp_path, scratch_db):
    os.environ.setdefault("SEED_PM_PASSWORD", "pm")
    os.environ.setdefault("SEED_DPO_PASSWORD", "dpo")
    from compliance_agent import db
    import compliance_agent.models as models
    from ingest import eurlex

    def fake_embed(texts):
        return [[random.random() for _ in range(models.embedding_dims())] for _ in texts]

    class FakeEmb:
        def embed_documents(self, texts):
            return fake_embed(texts)

        def embed_query(self, t):
            return fake_embed([t])[0]

    monkeypatch.setattr(db, "_store_embed", fake_embed)
    monkeypatch.setattr(models, "embeddings", lambda: FakeEmb())
    monkeypatch.setattr(eurlex, "RAW_DIR", tmp_path)

    from tests.test_chunker import CONSOLIDATED_HTML, OJ_HTML

    for celex, html in [("02016R0679-20160504", CONSOLIDATED_HTML), ("32016R0679", OJ_HTML)]:
        (tmp_path / f"{celex}.html").write_text(html, encoding="utf-8")
        (tmp_path / f"{celex}.meta.json").write_text(
            json.dumps({"celex": celex, "url": f"https://example/{celex}",
                        "retrieved_at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )


def test_seed_pipeline(fake_models):
    from compliance_agent import db
    from ingest import seed

    seed.main(["schema"])
    seed.main(["corpus", "--regulation", "GDPR", "--offline", "--replace"])
    seed.main(["users"])
    seed.main(["memory"])

    with db.connect_plain() as conn:
        rows = conn.execute(
            "SELECT chunk_key, embedding IS NOT NULL AS has_vec FROM legal_chunks WHERE regulation = 'GDPR' ORDER BY 1"
        ).fetchall()
        assert {r["chunk_key"] for r in rows} == {"GDPR:art1", "GDPR:art2", "GDPR:rec1", "GDPR:rec2"}
        assert all(r["has_vec"] for r in rows)
        users = conn.execute("SELECT username, role FROM users ORDER BY 1").fetchall()
        assert [(u["username"], u["role"]) for u in users] == [("lena.k", "product_manager"), ("m.weber", "dpo")]
        n = conn.execute("SELECT count(*) AS n FROM store WHERE prefix = 'org.facts' AND value->>'source' = 'seed'").fetchone()["n"]
        assert n == 3            # learned facts from the graph tests may sit next to the seeded ones
        # hybrid-search building blocks work: full-text + vector ordering
        hit = conn.execute(
            "SELECT chunk_key FROM legal_chunks WHERE regulation = 'GDPR' "
            "AND tsv @@ plainto_tsquery('english', 'material scope') LIMIT 1"
        ).fetchone()
        assert hit["chunk_key"] == "GDPR:art2"
