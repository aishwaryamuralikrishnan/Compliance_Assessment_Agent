"""Postgres access and schema.

One database, several jobs:
    legal_chunks     RAG corpus (vector + full-text + legal metadata)   -- owned here
    users            logins and roles                                    -- owned here
    register         the processing register (goal of the agent)        -- owned here
    review_tasks     DPO approval queue                                  -- owned here
    corpus_versions  provenance of each ingestion run                    -- owned here
    checkpoints*     LangGraph PostgresSaver (thread memory)             -- created by .setup()
    store*           LangGraph PostgresStore (long-term memory)          -- created by .setup()
"""
from __future__ import annotations

import atexit
from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None
CONNECT_TIMEOUT = 5  # seconds; a stopped Docker Desktop otherwise makes connects hang on Windows


def _ensure_vector(conn: psycopg.Connection) -> None:
    """Create the pgvector extension if needed, then register the `vector` type adapter.

    Must run before register_vector(): on a fresh database the type does not exist yet and
    pgvector raises "vector type not found in the database".
    """
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if not conn.autocommit:
        conn.commit()
    register_vector(conn)


def _configure(conn: psycopg.Connection) -> None:
    _ensure_vector(conn)


def close_pool() -> None:
    global _pool, _lg_pool
    for name in ("_pool", "_lg_pool"):
        p = globals()[name]
        if p is not None:
            try:
                p.close()
            except Exception:
                pass
            globals()[name] = None


atexit.register(close_pool)


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=config.database_url(),
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "autocommit": True, "connect_timeout": CONNECT_TIMEOUT},
            configure=_configure,
            open=True,
            timeout=CONNECT_TIMEOUT * 2,
        )
    return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


def connect_plain(autocommit: bool = True) -> psycopg.Connection:
    """A standalone connection (used by seed.py and by LangGraph saver/store setup)."""
    try:
        conn = psycopg.connect(
            config.database_url(), autocommit=autocommit, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT
        )
    except psycopg.OperationalError as exc:
        raise ConnectionError(
            f"Cannot reach Postgres at {config.database_url()} ({exc}). "
            f"Is Docker Desktop running and the container up? Try: docker compose up -d && docker compose ps"
        ) from exc
    _ensure_vector(conn)
    return conn


# --------------------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------------------

def schema_sql(embedding_dims: int) -> str:
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('product_manager', 'dpo')),
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OIDC sign-in (2 Nov): a Google identity maps to a users row by subject or verified e-mail; such a row has no password
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oidc_subject TEXT UNIQUE;
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

CREATE TABLE IF NOT EXISTS legal_chunks (
    id             SERIAL PRIMARY KEY,
    chunk_key      TEXT UNIQUE NOT NULL,         -- e.g. GDPR:art22:p1, AI_ACT:rec71, AI_ACT:anxIII:5
    regulation     TEXT NOT NULL,                -- GDPR | AI_ACT
    unit_type      TEXT NOT NULL,                -- article | article_paragraph | recital | annex_point | annex
    chapter        TEXT,                         -- e.g. "III"
    chapter_title  TEXT,
    section        TEXT,
    section_title  TEXT,
    article        INTEGER,
    article_letter TEXT,                         -- "a" for inserted articles ("Article 75a")
    article_title  TEXT,
    paragraph      INTEGER,
    paragraph_letter TEXT,                       -- "a" for inserted paragraphs ("Article 5(1a)")
    recital        INTEGER,
    annex          TEXT,                         -- e.g. "III"
    annex_title    TEXT,
    point          TEXT,                         -- e.g. "5"
    heading        TEXT NOT NULL,                -- human citation, e.g. "GDPR Article 22(1) — Automated individual decision-making"
    text           TEXT NOT NULL,                -- verbatim legal text of the unit
    cross_refs     INTEGER[] NOT NULL DEFAULT '{{}}',
    word_count     INTEGER NOT NULL,
    -- provenance
    celex          TEXT NOT NULL,
    source_url     TEXT NOT NULL,
    retrieved_at   TIMESTAMPTZ NOT NULL,
    embed_model    TEXT,
    chunk_version  INTEGER NOT NULL,
    -- search columns
    tsv            tsvector GENERATED ALWAYS AS (
                       setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
                       setweight(to_tsvector('english', coalesce(text, '')), 'B')
                   ) STORED,
    embedding      vector({embedding_dims})
);
-- migrations for tables created by earlier versions of this file
ALTER TABLE legal_chunks ADD COLUMN IF NOT EXISTS article_letter TEXT;
ALTER TABLE legal_chunks ADD COLUMN IF NOT EXISTS paragraph_letter TEXT;
DROP INDEX IF EXISTS legal_chunks_meta_idx;

CREATE INDEX IF NOT EXISTS legal_chunks_tsv_idx       ON legal_chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS legal_chunks_embedding_idx ON legal_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS legal_chunks_meta_idx      ON legal_chunks (regulation, article, article_letter, paragraph, paragraph_letter);
CREATE INDEX IF NOT EXISTS legal_chunks_recital_idx   ON legal_chunks (regulation, recital);
CREATE INDEX IF NOT EXISTS legal_chunks_annex_idx     ON legal_chunks (regulation, annex, point);

CREATE TABLE IF NOT EXISTS corpus_versions (
    id            SERIAL PRIMARY KEY,
    regulation    TEXT NOT NULL,
    celex         TEXT NOT NULL,
    source_url    TEXT NOT NULL,
    retrieved_at  TIMESTAMPTZ NOT NULL,
    embed_model   TEXT,
    embed_dims    INTEGER,
    chunk_version INTEGER NOT NULL,
    n_chunks      INTEGER NOT NULL,
    stats         JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE TABLE IF NOT EXISTS register (
    id             SERIAL PRIMARY KEY,
    assessment_id  TEXT UNIQUE NOT NULL,
    thread_id      TEXT,
    title          TEXT NOT NULL,
    verdict        TEXT NOT NULL,               -- e.g. "Do not build as described" / "Proceed with conditions" / "Proceed"
    risk_level     TEXT NOT NULL,               -- low | medium | high
    high_risk_ai   BOOLEAN NOT NULL DEFAULT FALSE,
    dpia_required  BOOLEAN NOT NULL DEFAULT FALSE,
    assessment     JSONB NOT NULL,              -- full structured Assessment
    citations      TEXT[] NOT NULL DEFAULT '{{}}',
    requested_by   TEXT NOT NULL,               -- username of the product manager
    approved_by    TEXT NOT NULL,               -- username of the DPO
    approved_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE register ADD COLUMN IF NOT EXISTS revises TEXT;                 -- the entry supersedes this earlier assessment (history)

CREATE TABLE IF NOT EXISTS assessments (
    id             SERIAL PRIMARY KEY,
    assessment_id  TEXT UNIQUE NOT NULL,        -- "A-0001"
    thread_id      TEXT NOT NULL,
    title          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'pending_review', 'rejected', 'approved', 'recorded')),
    assessment     JSONB NOT NULL,              -- verified Assessment (+ sources, disclaimer)
    dpia_draft     TEXT,
    created_by     TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assessments_thread_idx ON assessments (thread_id, created_at);
-- Revisions ("Request changes"): v2 is a new row that points at v1; nothing is overwritten.
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS description TEXT;          -- the feature description this version assessed
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS revises TEXT;              -- previous assessment id, NULL for v1
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE assessments DROP CONSTRAINT IF EXISTS assessments_status_check;
ALTER TABLE assessments ADD CONSTRAINT assessments_status_check
    CHECK (status IN ('draft', 'pending_review', 'changes_requested', 'rejected', 'approved', 'recorded'));

CREATE TABLE IF NOT EXISTS review_tasks (
    id             SERIAL PRIMARY KEY,
    thread_id      TEXT NOT NULL,
    assessment_id  TEXT NOT NULL,
    title          TEXT NOT NULL,
    requested_by   TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'approved', 'rejected')),
    assessment     JSONB NOT NULL,
    dpo_comment    TEXT,
    resolved_by    TEXT,
    resolved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE review_tasks DROP CONSTRAINT IF EXISTS review_tasks_status_check;
ALTER TABLE review_tasks ADD CONSTRAINT review_tasks_status_check
    CHECK (status IN ('pending', 'approved', 'changes_requested', 'rejected'));
ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS memory_items JSONB;        -- what the DPO ticked at decision time
ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS memory_written_at TIMESTAMPTZ; -- set once memory_write processed the decision
CREATE INDEX IF NOT EXISTS review_tasks_status_idx ON review_tasks (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS review_tasks_pending_uniq
    ON review_tasks (assessment_id) WHERE status = 'pending';
"""


def create_schema(conn: psycopg.Connection, embedding_dims: int) -> None:
    conn.execute(schema_sql(embedding_dims))


def existing_embedding_dims(conn: psycopg.Connection) -> int | None:
    """Dimension of legal_chunks.embedding if the table exists, else None."""
    row = conn.execute(
        """
        SELECT a.atttypmod AS dims
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = 'legal_chunks' AND a.attname = 'embedding'
        """
    ).fetchone()
    return int(row["dims"]) if row and row["dims"] and row["dims"] > 0 else None


def setup_langgraph_tables(embedding_dims: int) -> None:
    """Create the checkpointer and Store tables (idempotent)."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore

    with PostgresSaver.from_conn_string(config.database_url()) as saver:
        saver.setup()
    with PostgresStore.from_conn_string(
        config.database_url(),
        index={"dims": embedding_dims, "embed": _store_embed, "fields": ["text"]},
    ) as store:
        store.setup()


_lg_pool: ConnectionPool | None = None


def langgraph_pool() -> ConnectionPool:
    """Pool for the LangGraph checkpointer and Store (they need autocommit + dict rows and
    no prepared statements). Long-lived: created once per process."""
    global _lg_pool
    if _lg_pool is None:
        _lg_pool = ConnectionPool(
            conninfo=config.database_url(),
            min_size=1,
            max_size=8,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row, "connect_timeout": CONNECT_TIMEOUT},
            open=True,
            timeout=CONNECT_TIMEOUT * 2,
        )
    return _lg_pool


def langgraph_checkpointer():
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    # The worker's structured output (a Pydantic Assessment / StatusReply) is checkpointed.
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("compliance_agent.state", "Assessment"),
                                                        ("compliance_agent.state", "StatusReply")])
    return PostgresSaver(langgraph_pool(), serde=serde)


def langgraph_store():
    from langgraph.store.postgres import PostgresStore

    return PostgresStore(langgraph_pool(), index=store_index_config())


def _store_embed(texts: list[str]) -> list[list[float]]:
    from .models import embeddings

    return embeddings().embed_documents(texts)


def store_index_config() -> dict:
    """Index config shared by seed.py and graph.py so the Store is always opened the same way."""
    from .models import embedding_dims

    return {"dims": embedding_dims(), "embed": _store_embed, "fields": ["text"]}
