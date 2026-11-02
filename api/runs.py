"""Runs are owned by the server (design note §2 and §3).

A run is one consumption of a `run_turn` / `resume_turn` / `send_feedback` generator in a worker thread. The
registry keeps, per run, the events already produced (each with a sequence number), so a subscriber that connects
late, reconnects (`Last-Event-ID`) or watches another user's run (the product manager following the DPO's
decision) gets the same stream. The server interprets the graph's events (`TraceTracker.observe`,
`TraceBuilder.add`) and streams the resulting *view*, not the raw events:

    event: view        {seq, title, graph, stats, trace}
    event: interrupt   {kind: "dpo" | "pm", value}
    event: final       {thread, run_id, title}
    event: error       {message}

The buffers live in this process and go with it (one uvicorn worker). A finished run's last view is kept per
thread for the life of the process, so a reloaded page gets the trace of the last run back.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from compliance_agent import trace, viz
from compliance_agent.graph import pending_kind
from compliance_agent.models import pricing, resolved_model_ids
from compliance_agent.state import UserContext

from .deps import current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["runs"])

PING_SECONDS = 15          # a comment line keeps proxies from closing a stream that waits at the gate for minutes
POLL_SECONDS = 0.2         # the stream's reader polls the buffer; events arrive from a worker thread

TITLES = {"turn": "Running assessment…", "revision": "Running revision…", "decision": "Applying the DPO's decision…",
          "feedback": "Updating memory…"}


@dataclass
class Run:
    run_id: str
    thread_id: str
    kind: str                                  # turn | decision | revision | feedback
    user_id: str
    started: float = field(default_factory=time.time)
    events: list[tuple[int, str, dict[str, Any]]] = field(default_factory=list)   # (seq, name, payload)
    done: bool = False
    error: str | None = None
    graph_run_id: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, name: str, payload: dict[str, Any]) -> None:
        with self.lock:
            self.events.append((len(self.events) + 1, name, payload))

    def since(self, seq: int) -> list[tuple[int, str, dict[str, Any]]]:
        with self.lock:
            return [e for e in self.events if e[0] > seq]

    @property
    def last_view(self) -> dict[str, Any] | None:
        with self.lock:
            for _, name, payload in reversed(self.events):
                if name == "view":
                    return payload
        return None


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._last_by_thread: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def running_for(self, thread_id: str) -> str | None:
        with self._lock:
            for r in self._runs.values():
                if r.thread_id == thread_id and not r.done:
                    return r.run_id
        return None

    def last_view_for(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            rid = self._last_by_thread.get(thread_id)
        run = self.get(rid) if rid else None
        return run.last_view if run else None

    def views_for(self, thread_id: str) -> list[dict[str, Any]]:
        """The latest view of every run this process executed on the thread, in start order: the page draws the
        union of their paths and stacks their traces."""
        with self._lock:
            runs = sorted((r for r in self._runs.values() if r.thread_id == thread_id), key=lambda r: r.started)
        return [{"run_id": r.run_id, "kind": r.kind, "user_id": r.user_id, "done": r.done, "error": r.error, "view": r.last_view}
                for r in runs if r.last_view is not None]

    def start(self, *, kind: str, user: UserContext, thread_id: str, make_gen: Callable[[], Iterator[dict[str, Any]]],
              graph, thread_body: Callable[[str, Any], dict[str, Any] | None], resumed: bool) -> Run:
        """Refuses a second run on a thread that has one executing (409); otherwise consumes `make_gen()` in a
        thread and returns at once."""
        with self._lock:
            for r in self._runs.values():
                if r.thread_id == thread_id and not r.done:
                    raise HTTPException(409, f"a run is already executing on this thread (run {r.run_id})")
            run = Run(run_id=str(uuid.uuid4()), thread_id=thread_id, kind=kind, user_id=user.user_id)
            self._runs[run.run_id] = run
            self._last_by_thread[thread_id] = run.run_id
        t = threading.Thread(target=self._consume, args=(run, make_gen, graph, thread_body, resumed), name=f"run-{run.run_id[:8]}", daemon=True)
        t.start()
        return run

    # ---------------------------------------------------------------------------------
    def _consume(self, run: Run, make_gen, graph, thread_body, resumed: bool) -> None:
        tracker = viz.TraceTracker(active=None, resumed=True) if resumed else viz.TraceTracker()
        builder = trace.TraceBuilder(worker_model=resolved_model_ids().get("worker_full", ""))
        prices = pricing()
        title = TITLES.get(run.kind, "Running…")
        try:
            run.append("view", self._view(run, tracker, builder, title))
            for e in make_gen():
                if e["kind"] == "final":
                    run.graph_run_id = str(e.get("run_id") or "")
                    final_state = e["state"]
                    break
                tracker.observe(e, prices)
                builder.add(e)
                if e["kind"] == "interrupt":
                    value = e.get("value") if isinstance(e.get("value"), dict) else {}
                    run.append("interrupt", {"kind": _interrupt_kind(value), "value": value})
                run.append("view", self._view(run, tracker, builder, title))
            else:
                final_state = None
            kind = pending_kind(final_state) if final_state else None
            if kind == "dpo":
                tracker.paused = True
                title = "Assessment ready · waiting for DPO approval (paused)"
            elif kind == "pm":
                tracker.paused = True; tracker.pm_paused = True
                title = "Changes requested · waiting for the product manager's revision (paused)"
            else:
                tracker.finish()
                title = "Run complete"
            run.append("view", self._view(run, tracker, builder, title))
            body = thread_body(run.thread_id, graph)
            run.append("final", {"thread": body, "run_id": run.run_id, "graph_run_id": run.graph_run_id, "title": title})
        except Exception as exc:                       # reported, never hidden (TECHNICAL.md conventions)
            log.exception("run %s on thread %s failed", run.run_id, run.thread_id)
            run.error = f"{type(exc).__name__}: {exc}"
            run.append("error", {"message": run.error})
        finally:
            run.done = True

    @staticmethod
    def _view(run: Run, tracker: viz.TraceTracker, builder: trace.TraceBuilder, title: str) -> dict[str, Any]:
        rs = builder.retrieval_stats
        return {
            "title": title,
            "graph": tracker.snapshot(),
            "stats": {"step": tracker.step_label, "searches": rs.get("calls", 0), "retrieve_passes": tracker.retrievals,
                      "rewrites": rs.get("rewrites", 0), "tool_calls": tracker.tool_calls, "tokens_in": tracker.tokens_in,
                      "tokens_out": tracker.tokens_out, "cached": tracker.tokens_cached, "cost": round(tracker.cost, 6),
                      "elapsed": round(time.time() - run.started, 1), "thread": run.thread_id[:8]},
            "trace": builder.sections_json(),
        }


def _interrupt_kind(value: dict[str, Any]) -> str | None:
    return pending_kind({"pending_interrupt": value})


REGISTRY = RunRegistry()


# --------------------------------------------------------------------------------------
# GET /api/runs/{run_id}/events
# --------------------------------------------------------------------------------------

def _sse(seq: int, name: str, payload: dict[str, Any]) -> str:
    try:
        data = json.dumps(jsonable_encoder({"seq": seq, **payload}), ensure_ascii=False)
    except Exception as exc:                           # a message the stream cannot carry must not kill the stream
        log.exception("run event %s #%s could not be serialised", name, seq)
        data = json.dumps({"seq": seq, "message": f"event {name} could not be sent: {type(exc).__name__}: {exc}"})
        name = "error"
    return f"id: {seq}\nevent: {name}\ndata: {data}\n\n"


@router.get("/{run_id}/events")
async def run_events(run_id: str, request: Request, user: UserContext = Depends(current_user)) -> StreamingResponse:
    """Server-Sent Events of one run: the buffered events first, then the live tail until the run is done.
    `Last-Event-ID` (sent by the browser on reconnect) resumes after that sequence number."""
    run = REGISTRY.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    try:
        last = int(request.headers.get("last-event-id") or 0)
    except ValueError:
        last = 0

    async def stream():
        sent = last
        last_ping = time.time()
        while True:
            for seq, name, payload in run.since(sent):
                yield _sse(seq, name, payload)
                sent = seq
                last_ping = time.time()
            if run.done and not run.since(sent):
                return
            if await request.is_disconnected():
                return
            if time.time() - last_ping >= PING_SECONDS:
                yield ": ping\n\n"
                last_ping = time.time()
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
