"""The quick path (to-do item 4): a question routed `quick` runs direct_answer on the quick model over one retrieval
pass, the guardrail checks the citations, the run ends without a review task, and a preference note on the thread
stores the author's own preference. The scripted model stands in for the quick model; retrieval, corpus and the
input screens are canned (tests/fakes.py)."""
from __future__ import annotations

from langchain_core.messages import AIMessage

from compliance_agent import trace
from tests.fakes import iter_events


def _quick(monkeypatch):
    import compliance_agent.nodes.route as R

    monkeypatch.setattr(R, "decide", lambda text: (R.RouteDecision(tier="quick", confidence=0.91, reason="a short question"), "stub"))


def test_quick_answer_runs_direct_answer_and_ends_without_a_review(graph_with_scripted_worker, monkeypatch):
    from compliance_agent import repo
    from compliance_agent.graph import pending_kind, run_turn, thread_state
    from compliance_agent.state import UserContext

    _quick(monkeypatch)
    answer = AIMessage(content="Yes: a decision based solely on automated processing needs human intervention (GDPR Art. 22(3)); see also GDPR Art. 999.")
    g = graph_with_scripted_worker([answer])
    pm = UserContext("lena.k", "product_manager")
    events, state = iter_events(run_turn(pm, "Can a computer reject a credit application with nobody checking?", graph=g))

    updates = [e["node"] for e in events if e["kind"] == "update"]
    assert updates == ["validate_input", "route", "direct_answer", "output_guardrail"]      # no worker, no memory_write
    v = state["values"]
    assert v["route"] == "quick" and v["route_confidence"] == 0.91
    assert "GDPR Art. 22(3)" in v["answer"] and "GDPR Art. 999 [unverified]" in v["answer"]   # the unknown citation is marked, not removed
    assert v["guardrail"]["citations_checked"] == 2 and v["guardrail"]["invalid"] == ["GDPR Art. 999"]
    assert v["assessment"] is None and [s["citation"] for s in v["sources"]][:2] == ["GDPR Art. 22(1)", "GDPR Art. 22(3)"]
    assert pending_kind(state) is None and repo.review_task_for_thread(state["thread_id"]) is None

    da = [e for e in events if e["kind"] == "custom" and e.get("node") == "direct_answer"]
    assert [e["event"] for e in da] == ["model_call"] and da[0]["sources"][0] == "GDPR Art. 22(1)"
    searches = [e for e in events if e["kind"] == "custom" and e.get("node") == "search_regulation"]
    assert [e["event"] for e in searches] == ["retrieve", "graded", "done"]              # one pass, no rewrite
    guard = [e for e in events if e["kind"] == "custom" and e.get("node") == "output_guardrail"]
    assert guard[-1]["event"] == "checked" and guard[-1]["citations_checked"] == 2 and "assessment_id" not in guard[-1]

    b = trace.TraceBuilder(worker_model="x")
    for e in events:
        b.add(e)
    titles = [s["title"] for s in b.sections_json()]
    assert titles == ["validate_input", "route", "search_regulation", "direct_answer", "output_guardrail"]   # the one retrieval pass, boxed
    assert "quick model, no tools" in b.sections_json()[3]["items"][-1]
    assert thread_state(state["thread_id"], graph=g)["values"]["answer"] == v["answer"]


def test_quick_answer_that_comes_back_empty_is_reported_not_hidden(graph_with_scripted_worker, monkeypatch):
    from compliance_agent.graph import run_turn
    from compliance_agent.state import UserContext

    _quick(monkeypatch)
    empty = AIMessage(content="", usage_metadata={"input_tokens": 900, "output_tokens": 1024, "total_tokens": 1924})
    g = graph_with_scripted_worker([empty])
    events, state = iter_events(run_turn(UserContext("lena.k", "product_manager"), "Do we need consent to e-mail existing customers?", graph=g))

    assert state["values"]["answer"] == ""                                              # nothing invented in its place
    da = [e for e in events if e["kind"] == "custom" and e.get("node") == "direct_answer"]
    assert [e["event"] for e in da] == ["model_call", "empty_answer"]
    assert da[1]["tokens_out"] == 1024 and da[1]["max_tokens"]                           # the slot's max_tokens, for the diagnosis
    b = trace.TraceBuilder(worker_model="x")
    for e in events:
        b.add(e)
    items = next(s for s in b.sections_json() if s["title"] == "direct_answer")["items"]
    assert "returned no text" in items[-1] and "1024 output tokens" in items[-1]


def test_preference_note_on_a_quick_thread_is_the_authors_own(graph_with_scripted_worker, monkeypatch):
    from compliance_agent import memory
    from compliance_agent.graph import run_turn, send_feedback
    from compliance_agent.state import UserContext

    _quick(monkeypatch)
    g = graph_with_scripted_worker([AIMessage(content="In general yes, with a right to object (GDPR Art. 6(1)(f)).")])
    pm = UserContext("lena.k", "product_manager")
    _, state = iter_events(run_turn(pm, "Can we rely on legitimate interests for product analytics?", graph=g))
    tid = state["thread_id"]
    import uuid
    note = f"Keep answers to two sentences ({uuid.uuid4().hex[:6]})."      # unique: the scratch store keeps earlier runs' items

    events, state = iter_events(send_feedback(pm, tid, note, keep_example=False, graph=g))
    fb = [e for e in events if e["kind"] == "custom" and e.get("node") == "feedback"]
    assert fb and fb[0].get("comment") == note
    mem = [e for e in events if e["kind"] == "custom" and e.get("node") == "memory_write" and e.get("event") == "written"][-1]
    assert [w["ns"] for w in mem["written"]] == [memory.ns_label("pref", "lena.k")]           # her own namespace, nothing org-wide
    assert mem["written"][0]["text"].startswith("Lesson: lena.k on")                         # reflected by the (fake) cheap model
    assert mem["dropped"] == []

    # a second, identical note is not stored twice
    events, _ = iter_events(send_feedback(pm, tid, note, keep_example=False, graph=g))
    mem = [e for e in events if e["kind"] == "custom" and e.get("node") == "memory_write" and e.get("event") == "written"][-1]
    assert mem["written"] == [] and "already stored" in mem["dropped"][0]["why"]
