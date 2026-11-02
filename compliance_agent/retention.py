"""Checkpoint retention: remove the saved state of conversations that are over.

The checkpointer keeps the full graph state after every node of every thread, which is what makes interrupt and
resume possible, but it grows forever. This prunes the checkpoints of threads that are finished and older than a
cut-off. It never touches the assessments, review tasks, register or long-term memory: those are the records; the
checkpoints are only the working state of a conversation.

A thread is kept, whatever its age, while anything is still open on it:
  - it is paused at an interrupt (waiting for the DPO at the gate, or for the product manager in pm_revision);
  - it still has nodes scheduled (a run that stopped half-way, for instance after an error);
  - a review task on it is pending, or its latest assessment is waiting for changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db


@dataclass
class ThreadInfo:
    thread_id: str
    last_activity: datetime
    checkpoints: int
    open_reasons: list[str] = field(default_factory=list)      # empty = finished, safe to prune

    @property
    def finished(self) -> bool:
        return not self.open_reasons


def _threads_older_than(cutoff: datetime) -> list[tuple[str, datetime, int]]:
    """Every thread whose newest checkpoint is older than the cut-off, with that time and its checkpoint count."""
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT thread_id, max((checkpoint->>'ts')::timestamptz) AS last_ts, count(*) AS n
               FROM checkpoints GROUP BY thread_id
               HAVING max((checkpoint->>'ts')::timestamptz) < %s ORDER BY last_ts""",
            (cutoff,),
        ).fetchall()
    return [(r["thread_id"], r["last_ts"], int(r["n"])) for r in rows]


def _open_reasons(thread_id: str, graph) -> list[str]:
    reasons: list[str] = []
    try:
        snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    except Exception as exc:
        # a thread whose state cannot be read is never deleted on a guess (for instance stale pending writes left by
        # an interrupted feedback update); it is reported so it can be looked at
        return [f"state could not be read ({type(exc).__name__})"]
    if any(getattr(t, "interrupts", None) for t in (getattr(snap, "tasks", ()) or ())):
        reasons.append("paused at an interrupt")
    elif snap.next:
        reasons.append(f"nodes still scheduled ({', '.join(snap.next)})")
    with db.connection() as conn:
        pending = conn.execute("SELECT count(*) AS n FROM review_tasks WHERE thread_id = %s AND status = 'pending'", (thread_id,)).fetchone()["n"]
        waiting = conn.execute(
            """SELECT status FROM assessments WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1""", (thread_id,)
        ).fetchone()
    if pending:
        reasons.append("a review task is pending")
    if waiting and waiting["status"] == "changes_requested":
        reasons.append("the latest assessment is waiting for changes")
    return reasons


def candidates(days: int, *, graph=None, now: datetime | None = None) -> list[ThreadInfo]:
    """Threads whose last activity is older than `days`, each marked finished or with the reasons it is still open."""
    from .graph import get_graph

    graph = graph or get_graph()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out: list[ThreadInfo] = []
    for thread_id, last_ts, n in _threads_older_than(cutoff):
        out.append(ThreadInfo(thread_id, last_ts, n, _open_reasons(thread_id, graph)))
    return out


def prune(days: int, *, graph=None, dry_run: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """Delete the checkpoints of finished threads older than `days`. Returns what was (or would be) done."""
    from .graph import get_graph

    graph = graph or get_graph()
    found = candidates(days, graph=graph, now=now)
    pruned = [t for t in found if t.finished]
    kept = [t for t in found if not t.finished]
    if not dry_run:
        saver = graph.checkpointer
        for t in pruned:
            saver.delete_thread(t.thread_id)
    return {"days": days, "dry_run": dry_run, "pruned": pruned, "kept": kept,
            "checkpoints_removed": sum(t.checkpoints for t in pruned)}
