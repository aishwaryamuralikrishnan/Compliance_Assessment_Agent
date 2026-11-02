"""The orchestrator: a StateGraph the project owns.

    START -> validate_input -> route -+-> direct_answer -> output_guardrail -> END
                                      +-> worker (create_agent subgraph) -> output_guardrail -> memory_write -+-> END
                                      +-> reject -> END                                                      +-> pm_revision -> reviser -> output_guardrail -> ...
    output_guardrail may send the draft back to the agent once (unknown citations / bad schema), and after a
    verified assessment it sends the agent back once more to request DPO review: the agent calls
    request_dpo_review through the tool gate, which pauses the thread with interrupt() until the DPO
    decides. The decision resumes the same run: gate -> agent -> output_guardrail -> memory_write, then END
    (approved / rejected) or pm_revision (changes requested): a second interrupt() in which the thread waits for
    the product manager's revised description; her resume runs the reviser (a second create_agent subgraph),
    whose v2 pauses for the DPO again. One run carries a feature from its description to the register entry.
    memory_write runs only after a DPO decision (it has something to store); a verified quick answer and a
    rejected input go straight to END. Feedback on a completed thread re-enters at memory_write
    (Command(goto="memory_write")), so it needs no edge.

Compiled once per process with the Postgres checkpointer (thread memory, interrupt +
resume) and the Postgres Store (long-term memory). Identity enters through
config["configurable"] = {thread_id, user_id, role}, never through the prompt.
"""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, Iterator

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from . import db, models
from .nodes.direct_answer import direct_answer
from .nodes.guardrail import output_guardrail
from .nodes.memory_write import memory_write
from .nodes.route import next_node, route
from .nodes.validate_input import validate_input
from .nodes.pm_revision import INTERRUPT_TYPE as PM_INTERRUPT, after_memory_write, after_pm_revision, pm_revision
from .nodes.worker import build_reviser, build_worker
from .state import GraphState, UserContext


def reject(state: GraphState) -> dict[str, Any]:
    text = state.get("answer") or "I can't help with that request."
    return {"answer": text, "assessment": None, "sources": [], "messages": [AIMessage(content=text)]}


def build_graph(checkpointer=None, store=None):
    g = StateGraph(GraphState)
    g.add_node("validate_input", validate_input)
    g.add_node("route", route)
    g.add_node("direct_answer", direct_answer)
    g.add_node("worker", build_worker())
    g.add_node("reviser", build_reviser())
    g.add_node("reject", reject)
    g.add_node("output_guardrail", output_guardrail, destinations=("worker", "reviser", "memory_write", END))
    g.add_node("memory_write", memory_write)
    g.add_node("pm_revision", pm_revision)

    g.add_edge(START, "validate_input")
    g.add_edge("validate_input", "route")
    g.add_conditional_edges("route", next_node, {"direct_answer": "direct_answer", "worker": "worker", "reject": "reject"})
    g.add_edge("direct_answer", "output_guardrail")
    g.add_edge("worker", "output_guardrail")
    g.add_edge("reviser", "output_guardrail")
    g.add_edge("reject", END)
    g.add_conditional_edges("memory_write", after_memory_write, {"pm_revision": "pm_revision", END: END})
    g.add_conditional_edges("pm_revision", after_pm_revision, {"pm_revision": "pm_revision", "reviser": "reviser"})
    return g.compile(checkpointer=checkpointer, store=store, name="compliance_assistant")


@lru_cache(maxsize=1)
def get_graph():
    """Process-wide compiled graph with the Postgres checkpointer and Store."""
    with db.connect_plain() as conn:          # idempotent: picks up new tables / columns after upgrades
        db.create_schema(conn, models.embedding_dims())
    return build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())


# --------------------------------------------------------------------------------------
# Running turns
# --------------------------------------------------------------------------------------

def new_thread_id() -> str:
    return str(uuid.uuid4())


def run_config(user: UserContext, thread_id: str, *, extra_tags: list[str] | None = None, run_name: str = "compliance_turn") -> dict[str, Any]:
    """One LangSmith root run per call; its id is fixed here so feedback can be attached to it later."""
    rid = uuid.uuid4()
    return {
        "run_id": rid,
        "configurable": {"thread_id": thread_id, "user_id": user.user_id, "role": user.role, "run_id": str(rid)},
        "tags": ["compliance-assistant", f"role:{user.role}", f"user:{user.user_id}", *(extra_tags or [])],
        "metadata": {"user_id": user.user_id, "role": user.role, "thread_id": thread_id, "models": models.resolved_model_ids()},
        "run_name": run_name,
    }


def _normalise(item) -> dict[str, Any]:
    """graph.stream(..., subgraphs=True) yields (namespace, mode, payload)."""
    if isinstance(item, tuple) and len(item) == 3:
        ns, mode, payload = item
    elif isinstance(item, tuple) and len(item) == 2:
        ns, (mode, payload) = (), item
    else:
        ns, mode, payload = (), "updates", item
    ns = tuple(str(n).split(":")[0] for n in (ns or ()))
    if mode == "custom":
        body = payload if isinstance(payload, dict) else {"data": payload}
        return {**body, "kind": "custom", "ns": ns}
    if mode == "updates" and isinstance(payload, dict):
        if "__interrupt__" in payload:
            intr = payload["__interrupt__"]
            value = intr[0].value if isinstance(intr, (list, tuple)) and intr else getattr(intr, "value", intr)
            return {"kind": "interrupt", "ns": ns, "value": value}
        node = next(iter(payload.keys()), "?")
        return {"kind": "update", "ns": ns, "node": node, "data": payload[node]}
    return {"kind": mode, "ns": ns, "data": payload}


def _stream(graph, inp, config) -> Iterator[dict[str, Any]]:
    last_interrupt = None
    for item in graph.stream(inp, config, stream_mode=["updates", "custom"], subgraphs=True):
        ev = _normalise(item)
        if ev["kind"] == "interrupt":           # surfaces once per namespace level; report it once
            if ev["value"] == last_interrupt:
                continue
            last_interrupt = ev["value"]
        yield ev
    yield {"kind": "final", "state": thread_state(config["configurable"]["thread_id"], graph=graph), "run_id": str(config.get("run_id") or "")}


def run_turn(user: UserContext, message: str, thread_id: str | None = None, *, graph=None) -> Iterator[dict[str, Any]]:
    """One user turn. Yields events (custom progress, node updates, interrupt) and a final
    {"kind": "final", "state": {...}}. The thread_id is in the final state."""
    graph = graph or get_graph()
    thread_id = thread_id or new_thread_id()
    config = run_config(user, thread_id)
    inp: dict[str, Any] = {
        "messages": [HumanMessage(content=message, additional_kwargs={"kind": "request"})], "input": message,
        "regenerations": 0, "answer": None, "assessment": None, "sources": [], "guardrail": {}, "feedback": None,
        "structured_response": None, "review_requested": False, "revision": None, "decision": None,
        "revision_error": None, "revision_attempts": 0,
    }
    yield from _stream(graph, inp, config)


PENDING_FOR_DPO = ("dpo_review",)
PENDING_FOR_PM = (PM_INTERRUPT,)


def pending_kind(state: dict[str, Any]) -> str | None:
    """'dpo' while the thread waits at the tool gate for the DPO's decision, 'pm' while it waits in pm_revision for
    the product manager's revision, else None."""
    t = (state.get("pending_interrupt") or {}).get("type")
    if t in PENDING_FOR_DPO:
        return "dpo"
    if t in PENDING_FOR_PM:
        return "pm"
    return None


def resume_turn(user: UserContext, thread_id: str, payload: dict[str, Any], *, graph=None) -> Iterator[dict[str, Any]]:
    """Resume a thread paused at interrupt() under `user`'s identity. Two pauses exist:

    - the DPO's review (tool gate): payload = {"decision": "approve" | "request_changes" | "reject", "comment": str,
      "assessment": <amended assessment dict, optional>, "memory_items": [...]};
    - the product manager's revision (pm_revision): payload = {"description": str,
      "responses": [{"status": "done" | "not_possible", "note": str}, ...]} (one per requested change, in order).
    """
    graph = graph or get_graph()
    _purge_stale_feedback_writes(thread_id)
    config = run_config(user, thread_id, extra_tags=["resume"])
    yield from _stream(graph, Command(resume=payload), config)


_NULL_TASK = "00000000-0000-0000-0000-000000000000"


def _purge_stale_feedback_writes(thread_id: str) -> int:
    """A feedback update sent while a thread was paused leaves its `Command(update=..., goto=...)` writes
    pending on the interrupted checkpoint; a second one makes the resume fail with "can receive only one
    value per step". Feedback is refused on paused threads now (`send_feedback`), and this removes any
    such leftovers so an already-affected thread can still be resumed."""
    try:
        with db.connection() as conn:
            return conn.execute(
                """DELETE FROM checkpoint_writes WHERE thread_id = %s AND task_id = %s
                          AND (channel = 'feedback' OR channel LIKE 'branch:to:%%')""",
                (thread_id, _NULL_TASK),
            ).rowcount
    except Exception:
        return 0


def send_feedback(user: UserContext, thread_id: str, comment: str | None = None, *, keep_example: bool = False,
                  run_id: str | None = None, graph=None) -> Iterator[dict[str, Any]]:
    """Feedback on a finished thread: a note (stored as the author's own preference) and / or the DPO's "keep as a
    good example". Scores the LangSmith run if tracing is on, then runs only the memory_write node of this thread
    with the feedback in state, under the author's identity."""
    graph = graph or get_graph()
    fb: dict[str, Any] = {"comment": (comment or "").strip() or None, "example": bool(keep_example), "run_id": run_id, "langsmith": None}
    current = thread_state(thread_id, graph=graph)
    kind = pending_kind(current)
    if kind is not None:
        # Feedback is for completed work: while an assessment waits for the requester's button or for the DPO, the
        # thread is paused at interrupt() and nothing may touch it (an update parked on the paused checkpoint breaks
        # the resume). The UI shows the thumbs only once the thread has completed.
        yield {"kind": "custom", "ns": (), "node": "feedback", "event": "deferred", "example": fb["example"], "comment": fb["comment"],
               "reason": "thread paused at interrupt() for the DPO; feedback opens once the DPO has decided"}
        yield {"kind": "final", "state": current, "run_id": ""}
        return
    fb["langsmith"] = _langsmith_feedback(run_id, 1 if fb["example"] else None, fb["comment"])
    yield {"kind": "custom", "ns": (), "node": "feedback", "event": "received", "example": fb["example"], "comment": fb["comment"],
           "langsmith": fb["langsmith"], "run_id": run_id}
    _purge_stale_feedback_writes(thread_id)
    config = run_config(user, thread_id, extra_tags=["feedback"] + (["good_example"] if fb["example"] else []), run_name="compliance_feedback")
    yield from _stream(graph, Command(update={"feedback": fb}, goto="memory_write"), config)


def _langsmith_feedback(run_id: str | None, score: int | None, comment: str | None) -> str:
    """Attach the score to the traced run. Returns a short status for the trace; never raises."""
    from . import config as cfg

    if not cfg.langsmith_enabled():
        return "tracing off"
    if not run_id:
        return "no run id"
    try:
        from langsmith import Client

        Client().create_feedback(run_id=run_id, key="user_feedback", score=None if score is None else float(score), comment=comment,
                                 source_info={"app": "compliance-assistant"})
        return f"feedback on run {run_id[:8]}"
    except Exception as exc:
        return f"failed: {str(exc)[:80]}"


def thread_state(thread_id: str, *, graph=None) -> dict[str, Any]:
    """Current values of a thread plus any pending interrupt (for the UI and for polling)."""
    graph = graph or get_graph()
    snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    pending = None
    for task in getattr(snap, "tasks", ()) or ():
        for intr in getattr(task, "interrupts", ()) or ():
            pending = intr.value
    values = dict(snap.values or {})
    values.pop("structured_response", None)
    return {"thread_id": thread_id, "values": values, "pending_interrupt": pending, "next": list(snap.next or ())}
