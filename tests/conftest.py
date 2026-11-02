"""Shared fixtures.

`scratch_db` points the whole `compliance_agent.db` module at a scratch database for the duration of a
test, so graph tests never write assessments, review tasks, register entries or memory items into the
real one. The URL is TEST_DATABASE_URL if set, otherwise DATABASE_URL with the database name replaced
by `compliance_test`; the database is created on the same server if it does not exist yet.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

import compliance_agent.config  # noqa: F401  (loads .env into os.environ before the URL is read)

SCRATCH_DB_NAME = "compliance_test"


def scratch_db_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    parts = urlsplit(base)
    return urlunsplit(parts._replace(path=f"/{SCRATCH_DB_NAME}"))


def ensure_database(url: str) -> bool:
    """Create the scratch database if missing. Returns False when the server is unreachable."""
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    try:
        with psycopg.connect(url, connect_timeout=5):
            return True
    except psycopg.OperationalError as exc:
        if "does not exist" not in str(exc):
            return False
    admin = urlunsplit(parts._replace(path="/postgres"))
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=5) as conn:
            conn.execute(f'CREATE DATABASE "{name}"')
        return True
    except Exception:
        return False


@pytest.fixture()
def scratch_db(monkeypatch):
    url = scratch_db_url()
    if not url or not ensure_database(url):
        pytest.skip("no Postgres for a scratch database (set DATABASE_URL or TEST_DATABASE_URL)")
    monkeypatch.setenv("DATABASE_URL", url)
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from compliance_agent import db
    from compliance_agent import graph as G

    db.close_pool()                      # pools created for the real DB must not be reused
    G.get_graph.cache_clear()
    with db.connect_plain() as conn:
        db.create_schema(conn, 1536)
    db.setup_langgraph_tables(1536)      # checkpoints + store tables (the seed script does this for the real DB)
    yield url
    db.close_pool()
    G.get_graph.cache_clear()


@pytest.fixture()
def graph_with_scripted_worker(monkeypatch, scratch_db):
    """A compiled graph on the scratch database whose worker and reviser run a scripted model (tests/fakes.py); retrieval,
    corpus and the input screens are canned. Shared by test_graph.py and test_api.py."""
    from tests.fakes import fake_corpus, fake_retrieval, fake_screens, ScriptedChatModel

    import compliance_agent.nodes.worker as W
    from compliance_agent import db, graph as G

    fake_retrieval(monkeypatch)
    fake_corpus(monkeypatch)
    fake_screens(monkeypatch, tier="full")

    def make(script):
        model = ScriptedChatModel(script=script)
        monkeypatch.setattr(W.models, "chat", lambda slot: model)
        W.build_worker.cache_clear(); W.build_reviser.cache_clear()
        return G.build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())

    return make
