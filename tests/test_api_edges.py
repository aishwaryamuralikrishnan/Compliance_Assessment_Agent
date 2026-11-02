"""The web API's edges (to-do item 4): the refusals and error reports that the happy-path tests in test_api.py do not
reach: an empty turn, a second run on a busy thread, feedback while a thread is paused, a run whose generator
raises (the stream ends with an `error` event, nothing hidden), a view the stream cannot serialise, a bad
`Last-Event-ID`, a forged or expired session cookie, the memory candidates endpoint, and the `run_in_progress`
heuristic for a run this process does not own."""
from __future__ import annotations

import json
import time

import pytest

from tests.fakes import tool_call
from tests.test_api import DPO_PW, PM_PW, api_users, login, make_client  # noqa: F401  (the fixture is used by name)
from tests.test_graph import ASSESSMENT_ARGS


def _events(client, run_id, timeout=30.0):
    """All SSE events of a run as (name, payload)."""
    out = []
    deadline = time.time() + timeout
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        assert r.status_code == 200
        name = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                out.append((name, json.loads(line[5:])))
            if time.time() > deadline:
                break
    return out


def test_turn_refusals_and_feedback_while_paused(api_users, graph_with_scripted_worker):
    g = graph_with_scripted_worker([
        tool_call("search_regulation", {"query": "automated decision-making", "regulation": "GDPR"}, "r1"),
        tool_call("Assessment", ASSESSMENT_ARGS, "r2"),
        tool_call("request_dpo_review", {"assessment_id": "LATEST"}, "r3"),
    ])
    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        assert c.post("/api/threads", json={"message": "   "}).status_code == 400                    # nothing to run
        started = c.post("/api/threads", json={"message": "We're adding automated credit scoring using browsing behaviour."})
        assert started.status_code == 202
        tid, rid = started.json()["thread_id"], started.json()["run_id"]
        busy = c.post("/api/threads", json={"message": "another one", "thread_id": tid})
        assert busy.status_code == 409 and ("executing" in busy.json()["detail"] or "paused" in busy.json()["detail"])
        names = [n for n, _ in _events(c, rid)]
        assert names[-1] == "final" and "interrupt" in names
        # paused at the DPO's interrupt: a new turn and a feedback are both refused, the resume is the DPO's
        assert c.post("/api/threads", json={"message": "another one", "thread_id": tid}).status_code == 409
        fb = c.post(f"/api/threads/{tid}/feedback", json={"comment": "shorter please"})
        assert fb.status_code == 409 and "paused" in fb.json()["detail"]
        assert c.post(f"/api/threads/{tid}/feedback", json={}).status_code == 400                   # nothing to store
        assert c.post("/api/threads/no-such/feedback", json={"comment": "x"}).status_code == 404
        assert c.post(f"/api/threads/{tid}/resume", json={"decision": "approve"}).status_code == 403   # the PM may not decide
        body = c.get(f"/api/threads/{tid}").json()
        assert body["pending"]["kind"] == "dpo" and body["running_run_id"] is None and body["run_in_progress"] is False
        assert [v["kind"] for v in body["views"]] == ["turn"] and body["last_view"]["title"].startswith("Assessment ready")
        assert c.get("/api/runs/no-such-run/events").status_code == 404

        login(c, "m.weber", DPO_PW)
        assert c.post(f"/api/threads/{tid}/resume", json={"decision": "maybe"}).status_code == 400
        assert c.post(f"/api/threads/{tid}/resume", json={"decision": "reject", "comment": ""}).status_code == 400   # a reason is required
        task = c.get("/api/reviews").json()["pending"][0]
        cands = c.post(f"/api/reviews/{task['id']}/memory-candidates", json={"amended": None, "comment": "No legal basis."}).json()
        assert cands["amendments"] == [] and cands["note"][0]["allowed"] and cands["note"][0]["label"] == "org/lessons"
        assert cands["on_reject"][0]["item"]["source"] == "dpo_rejection" and cands["on_changes"][0]["item"]["source"] == "dpo_change_request"
        assert c.post("/api/reviews/999999/memory-candidates", json={"comment": "x"}).status_code == 404
        assert c.get("/api/reviews/999999").status_code == 404


def test_a_failing_run_ends_its_stream_with_an_error_event(api_users, monkeypatch):
    import os
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from api import runs as RUNS
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    def exploding(*a, **k):
        yield {"kind": "custom", "node": "validate_input", "event": "validated", "ok": True, "flags": [], "chars": 40, "redactions": 0}
        raise RuntimeError("the checkpointer went away")

    from api import threads as T
    monkeypatch.setattr(T, "run_turn", exploding)
    g = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        r = c.post("/api/threads", json={"message": "We are adding automated credit scoring to the checkout."})
        assert r.status_code == 202
        ev = _events(c, r.json()["run_id"])
        assert ev[-1][0] == "error" and "RuntimeError: the checkpointer went away" in ev[-1][1]["message"]
        assert ev[0][0] == "view" and ev[0][1]["seq"] == 1
        run = RUNS.REGISTRY.get(r.json()["run_id"])
        assert run.done and run.error.startswith("RuntimeError")
        assert RUNS.REGISTRY.running_for(run.thread_id) is None


def test_stream_replays_after_last_event_id_and_survives_an_unserialisable_view(api_users, monkeypatch):
    import os
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from api import runs as RUNS
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    g = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        run = RUNS.Run(run_id="r-test", thread_id="t-test", kind="turn", user_id="lena.k")
        run.append("view", {"title": "one"})
        run.append("view", {"title": "two", "bad": object()})          # a payload json cannot carry
        run.append("final", {"thread": None, "run_id": "r-test", "title": "done"})
        run.done = True
        with RUNS.REGISTRY._lock:
            RUNS.REGISTRY._runs[run.run_id] = run
        ev = _events(c, "r-test")
        assert [n for n, _ in ev] == ["view", "error", "final"]
        assert "could not be sent" in ev[1][1]["message"] and ev[1][1]["seq"] == 2
        # Last-Event-ID resumes after the given sequence number; a malformed header starts from the beginning
        with c.stream("GET", "/api/runs/r-test/events", headers={"Last-Event-ID": "2"}) as r:
            lines = [l for l in r.iter_lines() if l.startswith("event:")]
        assert lines == ["event: final"]
        with c.stream("GET", "/api/runs/r-test/events", headers={"Last-Event-ID": "abc"}) as r:
            lines = [l for l in r.iter_lines() if l.startswith("event:")]
        assert lines == ["event: view", "event: error", "event: final"]
        assert RUNS.REGISTRY.last_view_for("t-test") is None                     # the registry's per-thread pointer is set by start(), not by hand
        assert run.last_view["title"] == "two"


def test_session_cookie_forged_or_expired_is_refused(api_users, monkeypatch):
    import os
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    import jwt

    from api import sessions as S
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    g = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(g) as c:
        c.cookies.set("session", "not-a-token")
        assert c.get("/api/auth/me").status_code == 401
        c.cookies.set("session", jwt.encode({"sub": "lena.k", "role": "product_manager", "exp": int(time.time()) - 10}, S.secret(), algorithm="HS256"))
        assert c.get("/api/auth/me").status_code == 401                                # expired
        c.cookies.set("session", jwt.encode({"sub": "lena.k", "role": "product_manager", "exp": int(time.time()) + 60}, "another-secret-that-is-long-enough-for-hs256", algorithm="HS256"))
        assert c.get("/api/auth/me").status_code == 401                                # wrong signature
        c.cookies.set("session", jwt.encode({"role": "product_manager", "exp": int(time.time()) + 60}, S.secret(), algorithm="HS256"))
        assert c.get("/api/auth/me").status_code == 401                                # no subject
        assert S.read_token("garbage") is None


def test_run_in_progress_for_a_run_this_process_does_not_own(monkeypatch):
    from api import threads as T

    assert T.run_in_progress({"pending_interrupt": {"type": "dpo_review"}, "values": {}}) is False
    assert T.run_in_progress({"pending_interrupt": None, "values": {"decision": "changes_requested"}, "thread_id": "t"}) is True   # on its way to pm_revision
    assert T.run_in_progress({"pending_interrupt": None, "values": {"decision": "approved"}, "thread_id": "t"}) is False
    assert T.run_in_progress({"pending_interrupt": None, "values": {"answer": "done"}, "thread_id": "t"}) is False
    monkeypatch.setattr(T.repo, "review_task_for_thread", lambda tid: {"status": "approved"})
    assert T.run_in_progress({"pending_interrupt": None, "values": {}, "thread_id": "t"}) is True      # decided, but the decision not yet in the state
    monkeypatch.setattr(T.repo, "review_task_for_thread", lambda tid: {"status": "pending"})
    assert T.run_in_progress({"pending_interrupt": None, "values": {}, "thread_id": "t"}) is False
    monkeypatch.setattr(T.repo, "review_task_for_thread", lambda tid: None)
    assert T.run_in_progress({"pending_interrupt": None, "values": {}, "thread_id": "t"}) is False
