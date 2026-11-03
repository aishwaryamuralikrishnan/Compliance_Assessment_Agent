"""`python scripts/admin.py forget <user>` (the privacy notice's deletion request): the account, the person's
conversations with their saved state, their assessments, review tasks and own memory namespace go; register entries
and memory items that are the organisation's record stay with the name replaced by 'deleted user'."""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

from tests.fakes import fake_retrieval
from tests.test_api import api_users  # noqa: F401  (fixture used by name)


def _admin():
    spec = importlib.util.spec_from_file_location("admin", Path(__file__).resolve().parents[1] / "scripts" / "admin.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["admin"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_forget_removes_the_person_and_pseudonymises_the_records(api_users, monkeypatch, capsys):
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from langgraph.store.postgres import PostgresStore

    from compliance_agent import auth, config, db, memory

    fake_retrieval(monkeypatch)            # the Store's index embeds on put: the fake embedding keeps the test offline
    admin = _admin()
    with db.connection() as conn:          # the scratch database is shared: start clean whatever an earlier run left
        conn.execute("DELETE FROM register WHERE assessment_id = 'A-9001'")
        conn.execute("DELETE FROM review_tasks WHERE thread_id IN ('t-pat', 't-lena')")
        conn.execute("DELETE FROM assessments WHERE thread_id IN ('t-pat', 't-lena')")
        conn.execute("DELETE FROM users WHERE username = 'pat@example.com'")
    pat = auth.user_for_oidc(subject="g-9", email="pat@example.com", display_name="Pat", dpo_emails=set(), default_role="product_manager")
    assert pat is not None and pat.user_id == "pat@example.com"
    with db.connection() as conn:
        conn.execute("INSERT INTO assessments (assessment_id, thread_id, title, status, assessment, created_by) VALUES ('A-9001', 't-pat', 'Pat feature', 'approved', '{}', 'pat@example.com')")
        conn.execute("INSERT INTO assessments (assessment_id, thread_id, title, status, assessment, created_by) VALUES ('A-9002', 't-lena', 'Lena feature', 'approved', '{}', 'lena.k')")
        conn.execute("INSERT INTO review_tasks (thread_id, assessment_id, title, requested_by, status, assessment) VALUES ('t-pat', 'A-9001', 'Pat feature', 'pat@example.com', 'pending', '{}')")
        conn.execute("INSERT INTO register (assessment_id, thread_id, title, verdict, risk_level, assessment, requested_by, approved_by) "
                     "VALUES ('A-9001', 't-pat', 'Pat feature', 'Proceed', 'low', '{}', 'pat@example.com', 'm.weber')")
        conn.execute("INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata) VALUES ('t-pat', '', 'c1', 'json', '{}', '{}') ON CONFLICT DO NOTHING")
    with PostgresStore.from_conn_string(config.database_url(), index=db.store_index_config()) as store:
        store.setup()
        store.put(memory.user_prefs_namespace("pat@example.com"), "answer-length", {"text": "short answers", "user": "pat@example.com", "source": "learned", "author": "pat@example.com"})
        store.put(memory.ORG_LESSONS, "lesson-pat", {"text": "browsing history is a no-go", "source": "learned", "author": "pat@example.com"})
        store.put(memory.ORG_LESSONS, "lesson-lena", {"text": "another lesson", "source": "learned", "author": "lena.k"})

    admin.cmd_forget(argparse.Namespace(user="Pat@Example.com", yes=True))
    out = capsys.readouterr().out
    assert "1 conversation(s)" in out and "done:" in out

    with db.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users WHERE username = 'pat@example.com'").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM assessments WHERE thread_id = 't-pat'").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM assessments WHERE thread_id = 't-lena'").fetchone()["n"] == 1   # someone else's stays
        assert conn.execute("SELECT count(*) AS n FROM review_tasks WHERE thread_id = 't-pat'").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM checkpoints WHERE thread_id = 't-pat'").fetchone()["n"] == 0
        reg = conn.execute("SELECT requested_by, approved_by FROM register WHERE assessment_id = 'A-9001'").fetchone()
        assert reg == {"requested_by": "deleted user", "approved_by": "m.weber"}            # the record stays, the name goes
    with PostgresStore.from_conn_string(config.database_url(), index=db.store_index_config()) as store:
        assert memory.list_namespace(store, memory.user_prefs_namespace("pat@example.com")) == []
        lessons = {it["key"]: it for it in memory.list_namespace(store, memory.ORG_LESSONS, limit=100)}
        assert lessons["lesson-pat"]["author"] == "deleted user" and lessons["lesson-pat"]["text"] == "browsing history is a no-go"
        assert lessons["lesson-lena"]["author"] == "lena.k"
        # clean up the scratch store for the other tests
        for k in ("lesson-pat", "lesson-lena"):
            store.delete(memory.ORG_LESSONS, k)
    with db.connection() as conn:
        conn.execute("DELETE FROM register WHERE assessment_id = 'A-9001'")
        conn.execute("DELETE FROM assessments WHERE thread_id = 't-lena'")
