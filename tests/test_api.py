"""The web API (docs/web_app_design.md), through HTTP with FastAPI's TestClient.

The pure tests (serialisers, layout, Markdown) need nothing; the rest run on the scratch database with two users
seeded by `api_users` and, where a thread is needed, the scripted worker of `graph_with_scripted_worker`."""
from __future__ import annotations

import json
import os

import pytest

from tests.fakes import iter_events, tool_call
from tests.test_graph import ASSESSMENT_ARGS

PM_PW, DPO_PW = "pm-test", "dpo-test"


# --------------------------------------------------------------------------------------
# serialisers (no database)
# --------------------------------------------------------------------------------------

def test_tracker_snapshot_is_plain_json_and_layout_json_matches_constants():
    import json

    from compliance_agent import viz

    t = viz.TraceTracker()
    t.observe({"kind": "custom", "ns": (), "node": "validate_input", "event": "validated"})
    t.observe({"kind": "custom", "ns": ("worker",), "node": "search_regulation", "event": "retrieve", "call": "a"})
    t.observe({"kind": "custom", "ns": ("worker",), "node": "tool_gate", "event": "pause", "tool": "request_dpo_review"})
    snap = t.snapshot()
    json.dumps(snap)                                            # nothing but lists, dicts and scalars
    assert snap["active"] == "worker" and snap["paused"] and ["tool_gate", "interrupt"] in snap["taken"]
    assert snap["substep"] == "retrieve" and snap["retrievals"] == 1 and "validate_input" in snap["visited"]
    lay = viz.layout_json()
    json.dumps(lay)
    assert set(lay["nodes"]) == set(viz.NODES) and len(lay["edges"]) == len(viz.EDGES)
    assert lay["edges"][0] == {"source": "__start__", "target": "validate_input", "points": [[180, 30], [180, 44]], "style": "solid"}


def test_trace_builder_sections_json_mirrors_sections():
    import json

    from compliance_agent import trace

    b = trace.TraceBuilder(worker_model="m")
    b.add({"kind": "custom", "node": "validate_input", "event": "validated", "ok": True, "flags": [], "chars": 50, "redactions": 0})
    b.add({"kind": "custom", "node": "search_regulation", "call": "a", "event": "retrieve", "attempt": 1, "query": "q1"})
    b.add({"kind": "custom", "node": "search_regulation", "call": "a", "event": "graded", "attempt": 1, "sufficient": True,
           "confidence": 0.9, "relevant": ["GDPR Art. 22(1)"], "top": [], "reason": "ok"})
    js = b.sections_json()
    json.dumps(js)
    assert [s["title"] for s in js] == ["validate_input", "search_regulation"]
    assert js[0]["items"][0].startswith("50 chars") and js[1]["cls"] == "tool" and js[1]["rows"][0]["label"] == "retrieve 1"
    assert "Art. 22(1)" in js[1]["rows"][0]["detail"]


def test_assessment_markdown_moved_to_export():
    from compliance_agent.export import assessment_markdown

    md = assessment_markdown({**ASSESSMENT_ARGS, "assessment_id": "A-0001", "sources": ["GDPR Art. 22"], "disclaimer": "d"})
    assert md.startswith("# A-0001 · Automated credit scoring (BNPL)") and "- **Blocker** — Add human intervention" in md


# --------------------------------------------------------------------------------------
# the API on the scratch database
# --------------------------------------------------------------------------------------

@pytest.fixture()
def api_users(scratch_db):
    import bcrypt

    from compliance_agent import db

    with db.connection() as conn:
        for name, display, role, pw in (("lena.k", "Lena K.", "product_manager", PM_PW), ("m.weber", "M. Weber", "dpo", DPO_PW)):
            conn.execute(
                """INSERT INTO users (username, display_name, role, password_hash) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (username) DO UPDATE SET display_name = EXCLUDED.display_name, role = EXCLUDED.role,
                   password_hash = EXCLUDED.password_hash""",
                (name, display, role, bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=4)).decode()))
    return scratch_db


def make_client(graph):
    from fastapi.testclient import TestClient

    from api.main import create_app

    return TestClient(create_app(graph=graph))


def login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_me_logout_and_role_refusals(api_users, monkeypatch):
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    graph = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(graph) as c:
        assert c.get("/api/auth/me").status_code == 401                       # no session
        assert c.post("/api/auth/login", json={"username": "lena.k", "password": "wrong"}).status_code == 401
        me = login(c, "lena.k", PM_PW)
        assert me == {"user_id": "lena.k", "role": "product_manager", "display_name": "Lena K."}
        assert "session" in c.cookies
        assert c.get("/api/auth/me").json()["user_id"] == "lena.k"
        assert c.get("/api/reviews").status_code == 403                       # the queue is the DPO's
        assert c.get("/api/register.pdf").status_code == 403                  # export_register is DPO-only
        assert c.get("/api/threads/no-such-thread").status_code == 404
        reg = c.get("/api/register").json()                                   # the scratch database keeps rows from earlier tests
        assert set(reg) == {"entries", "can_export"} and reg["can_export"] is False
        mem = c.get("/api/memory").json()
        assert [s["namespace"] for s in mem["sections"]] == ["org/facts", "org/lessons", "user/lena_k/prefs"]
        assert mem["can_add"] == ["user/lena_k/prefs"]
        meta = c.get("/api/meta").json()
        assert "worker" in meta["models"] and "worker_full" in meta["pricing"] and meta["langsmith"]["enabled"] is False
        from compliance_agent import viz
        assert c.get("/api/meta/graph-layout").json() == viz.layout_json()
        assert c.get("/api/healthz").json() == {"ok": True, "db": True, "detail": None}
        assert c.post("/api/auth/logout").status_code == 204
        assert c.get("/api/auth/me").status_code == 401

        login(c, "m.weber", DPO_PW)
        assert set(c.get("/api/reviews").json()) == {"pending", "decided"}
        pdf = c.get("/api/register.pdf")
        assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf") and pdf.content[:4] == b"%PDF"
        assert c.get("/api/register").json()["can_export"] is True
        assert c.get("/api/memory").json()["can_add"] == ["org/facts", "org/lessons", "user/m_weber/prefs"]


def test_thread_and_review_read_side_after_a_scripted_assessment(api_users, graph_with_scripted_worker):
    from compliance_agent.graph import run_turn
    from compliance_agent.state import UserContext

    script = [
        tool_call("search_regulation", {"query": "automated individual decision-making profiling credit", "regulation": "GDPR"}, "c2"),
        tool_call("Assessment", ASSESSMENT_ARGS, "c4"),
        tool_call("request_dpo_review", {"assessment_id": "LATEST"}, "c5"),
    ]
    g = graph_with_scripted_worker(script)
    _, state = iter_events(run_turn(UserContext("lena.k", "product_manager"), "We're adding automated credit scoring to our checkout.", graph=g))
    thread_id, aid = state["thread_id"], state["values"]["assessment"]["assessment_id"]

    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        body = c.get(f"/api/threads/{thread_id}").json()
        assert body["pending"]["kind"] == "dpo" and body["pending"]["value"]["assessment_id"] == aid
        assert body["status"] == "pending_review" and body["status_text"].startswith("Sent to the DPO")
        assert body["review_task"]["status"] == "pending" and body["run_in_progress"] is False
        assert body["values"]["assessment"]["assessment_id"] == aid and body["values"]["route"] == "full"
        assert "messages" not in body["values"]
        md = c.get(f"/api/assessments/{aid}.md")
        assert md.status_code == 200 and md.text.startswith(f"# {aid} ·")
        assert c.get(f"/api/assessments/{aid}").json()["status"] == "pending_review"

        login(c, "m.weber", DPO_PW)
        queue = c.get("/api/reviews").json()
        mine = [t for t in queue["pending"] if t["assessment_id"] == aid]      # earlier tests may have left tasks pending
        assert len(mine) == 1 and mine[0]["thread_id"] == thread_id
        task_id = mine[0]["id"]
        rv = c.get(f"/api/reviews/{task_id}").json()
        assert rv["assessment"]["assessment"]["title"] == ASSESSMENT_ARGS["title"] and rv["previous"] is None
        assert c.get("/api/reviews/999999").status_code == 404

        amended = {**rv["assessment"]["assessment"]}
        amended["findings"] = [dict(f) for f in amended["findings"]]
        amended["findings"][1]["severity"] = "Blocker"
        cands = c.post(f"/api/reviews/{task_id}/memory-candidates", json={"amended": amended, "comment": "Always name the DPIA deadline."}).json()
        assert len(cands["amendments"]) == 1 and cands["amendments"][0]["label"] == "org/lessons" and cands["amendments"][0]["allowed"] is True
        assert "Blocker" in cands["amendments"][0]["item"]["text"]
        assert len(cands["note"]) == 1 and cands["note"][0]["item"]["source"] == "dpo_comment"
        assert cands["on_reject"][0]["item"]["source"] == "dpo_rejection" and cands["on_changes"][0]["item"]["source"] == "dpo_change_request"


# --------------------------------------------------------------------------------------
# runs and the event stream (step 2)
# --------------------------------------------------------------------------------------

def read_stream(client, run_id: str, last_event_id: int | None = None) -> list[dict]:
    """Consume GET /api/runs/{id}/events to its end; returns [{"id", "event", "data"}, ...] (ping comments dropped)."""
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id is not None else {}
    out, cur = [], {}
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line == "":
                if cur.get("event"):
                    out.append({"id": int(cur["id"]), "event": cur["event"], "data": json.loads(cur["data"])})
                cur = {}
            elif line.startswith(":"):
                continue
            else:
                k, _, v = line.partition(":")
                cur[k] = v.strip()
    return out


def start(client, method: str, url: str, body: dict) -> str:
    r = client.post(url, json=body)
    assert r.status_code == 202, r.text
    return r.json()["run_id"]


def test_run_stream_pm_assessment_dpo_approval_feedback_and_refusals(api_users, graph_with_scripted_worker):
    from compliance_agent import repo

    script = [
        tool_call("search_regulation", {"query": "automated individual decision-making profiling credit", "regulation": "GDPR"}, "c2"),
        tool_call("Assessment", ASSESSMENT_ARGS, "c4"),
        tool_call("request_dpo_review", {"assessment_id": "LATEST"}, "c5"),
        tool_call("StatusReply", {"message": "The DPO approved and recorded the assessment."}, "c6"),
    ]
    g = graph_with_scripted_worker(script)
    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        r = c.post("/api/threads", json={"message": "We're adding automated credit scoring to our checkout."})
        assert r.status_code == 202
        run_id, thread_id = r.json()["run_id"], r.json()["thread_id"]
        assert c.get("/api/runs/no-such-run/events").status_code == 404

        evs = read_stream(c, run_id)
        names = [e["event"] for e in evs]
        assert names[0] == "view" and names[-1] == "final" and "interrupt" in names and "error" not in names
        assert [e["id"] for e in evs] == list(range(1, len(evs) + 1))                   # sequence numbers, for Last-Event-ID
        assert evs[0]["data"]["title"] == "Running assessment…"
        intr = next(e for e in evs if e["event"] == "interrupt")
        assert intr["data"]["kind"] == "dpo" and intr["data"]["value"]["type"] == "dpo_review"
        last_view = [e for e in evs if e["event"] == "view"][-1]["data"]
        assert last_view["title"].startswith("Assessment ready") and last_view["graph"]["paused"] is True
        assert last_view["stats"]["searches"] >= 1 and last_view["stats"]["tool_calls"] >= 1 and last_view["stats"]["thread"] == thread_id[:8]
        assert [s["title"] for s in last_view["trace"]][:2] == ["validate_input", "route"]
        final = evs[-1]["data"]
        assert final["thread"]["pending"]["kind"] == "dpo" and final["thread"]["status"] == "pending_review" and final["run_id"] == run_id
        aid = final["thread"]["values"]["assessment"]["assessment_id"]

        # a late subscriber with Last-Event-ID gets only the rest
        tail = read_stream(c, run_id, last_event_id=len(evs) - 2)
        assert [e["id"] for e in tail] == [len(evs) - 1, len(evs)] and tail[-1]["event"] == "final"

        body = c.get(f"/api/threads/{thread_id}").json()
        assert body["running_run_id"] is None and body["last_view"]["title"] == last_view["title"]

        # refusals while the thread waits for the DPO
        assert c.post(f"/api/threads/{thread_id}/resume", json={"decision": "approve"}).status_code == 403     # a PM cannot decide
        assert c.post("/api/threads", json={"message": "again", "thread_id": thread_id}).status_code == 409       # paused: resume, don't restart
        assert c.post(f"/api/threads/{thread_id}/feedback", json={"comment": "nice"}).status_code == 409          # nothing touches a paused thread
        assert c.post(f"/api/threads/{thread_id}/feedback", json={"keep_example": True}).status_code == 403      # DPO only
        assert c.post(f"/api/threads/{thread_id}/feedback", json={}).status_code == 400

        login(c, "m.weber", DPO_PW)
        assert c.post("/api/threads", json={"message": "x"}).status_code == 403                                    # the DPO never generates
        assert c.post(f"/api/threads/{thread_id}/resume", json={"decision": "reject", "comment": ""}).status_code == 400   # needs a reason
        assert c.post(f"/api/threads/{thread_id}/resume", json={"decision": "maybe"}).status_code == 400
        task = next(t for t in c.get("/api/reviews").json()["pending"] if t["assessment_id"] == aid)
        cands = c.post(f"/api/reviews/{task['id']}/memory-candidates", json={"comment": "Browsing data is a blocker."}).json()
        rid = start(c, "post", f"/api/threads/{thread_id}/resume",
                    {"decision": "approve", "comment": "Browsing data is a blocker.", "memory_items": [x["item"] for x in cands["note"]]})
        evs = read_stream(c, rid)
        assert evs[0]["data"]["title"] == "Applying the DPO's decision…" and evs[0]["data"]["graph"]["resumed"] is True
        final = evs[-1]["data"]
        assert evs[-1]["event"] == "final" and final["title"] == "Run complete"
        assert final["thread"]["pending"]["kind"] is None and final["thread"]["values"]["decision"] == "approved"
        assert final["thread"]["status"] == "recorded" and final["thread"]["review_task"]["status"] == "approved"
        views = final["thread"]["views"]                                     # both runs of this process, in order
        assert [v["kind"] for v in views] == ["turn", "decision"] and views[1]["view"]["graph"]["resumed"] is True
        assert views[0]["view"]["title"].startswith("Assessment ready") and views[0]["done"] is True
        assert any(e["assessment_id"] == aid for e in c.get("/api/register").json()["entries"])
        assert c.post(f"/api/threads/{thread_id}/resume", json={"decision": "approve"}).status_code == 409        # nothing pending now
        assert repo.get_assessment(aid)["status"] == "recorded"

        # feedback: the DPO keeps the example, the PM leaves a note; both run only memory_write
        evs = read_stream(c, start(c, "post", f"/api/threads/{thread_id}/feedback", {"keep_example": True}))
        assert evs[-1]["event"] == "final" and any(s["title"] == "memory_write" for s in evs[-2]["data"]["trace"])
        login(c, "lena.k", PM_PW)
        evs = read_stream(c, start(c, "post", f"/api/threads/{thread_id}/feedback", {"comment": f"shorter findings please ({thread_id[:6]})"}))
        assert evs[-1]["event"] == "final" and "error" not in [e["event"] for e in evs]
        assert c.get("/api/memory").json()["sections"][2]["items"], "the PM's note should be in her preferences"


def test_run_stream_request_changes_then_the_requester_revises(api_users, graph_with_scripted_worker):
    from tests.test_graph import REVISED_ARGS

    script = [
        tool_call("search_regulation", {"query": "automated decision-making", "regulation": "GDPR"}, "r1"),
        tool_call("Assessment", ASSESSMENT_ARGS, "r2"),
        tool_call("request_dpo_review", {"assessment_id": "LATEST"}, "r3"),
        tool_call("StatusReply", {"message": "The DPO requested changes: drop the browsing data."}, "r4"),
        tool_call("search_regulation", {"query": "data minimisation", "regulation": "GDPR"}, "r5"),
        tool_call("Assessment", REVISED_ARGS, "r6"),
        tool_call("request_dpo_review", {"assessment_id": "LATEST"}, "r7"),
    ]
    g = graph_with_scripted_worker(script)
    with make_client(g) as c:
        login(c, "lena.k", PM_PW)
        text = "We're adding automated credit scoring using transaction history, device fingerprint and browsing behaviour."
        r = c.post("/api/threads", json={"message": text})
        run_id, thread_id = r.json()["run_id"], r.json()["thread_id"]
        final = read_stream(c, run_id)[-1]["data"]
        v1 = final["thread"]["values"]["assessment"]["assessment_id"]
        script[5].tool_calls[0]["args"]["revises"] = v1

        login(c, "m.weber", DPO_PW)
        evs = read_stream(c, start(c, "post", f"/api/threads/{thread_id}/resume", {"decision": "request_changes", "comment": "Drop the browsing data"}))
        intr = next(e for e in evs if e["event"] == "interrupt")
        assert intr["data"]["kind"] == "pm" and intr["data"]["value"]["requests"] == ["Drop the browsing data"]
        final = evs[-1]["data"]
        assert final["title"].startswith("Changes requested") and final["thread"]["pending"]["kind"] == "pm"
        assert final["thread"]["status"] == "changes_requested" and evs[-2]["data"]["graph"]["pm_paused"] is True
        # the DPO cannot revise on the PM's behalf
        assert c.post(f"/api/threads/{thread_id}/resume", json={"description": "x", "responses": []}).status_code == 403

        login(c, "lena.k", PM_PW)
        assert c.post(f"/api/threads/{thread_id}/resume", json={"description": "  ", "responses": []}).status_code == 400
        revised = "We're adding automated credit scoring using transaction history and device fingerprint."
        evs = read_stream(c, start(c, "post", f"/api/threads/{thread_id}/resume",
                                   {"description": revised, "responses": [{"status": "done", "note": "browsing behaviour removed"}]}))
        assert evs[0]["data"]["title"] == "Running revision…"
        final = evs[-1]["data"]
        v2 = final["thread"]["values"]["assessment"]
        assert v2["revises"] == v1 and final["thread"]["pending"]["kind"] == "dpo" and final["thread"]["values"]["route"] == "revise"
        titles = [s["title"] for s in evs[-2]["data"]["trace"]]
        assert "pm_revision" in titles and "reviser" in titles and "worker" not in titles
        login(c, "m.weber", DPO_PW)
        rv = c.get(f"/api/reviews/{next(t for t in c.get('/api/reviews').json()['pending'] if t['assessment_id'] == v2['assessment_id'])['id']}").json()
        assert rv["previous"]["assessment_id"] == v1 and rv["requested_changes"] == "Drop the browsing data"
