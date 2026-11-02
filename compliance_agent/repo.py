"""Data access for the business tables: assessments (drafts), review_tasks, register.

Plain SQL through the shared pool. Every function returns dicts so tools and the UI can
serialise them without extra conversion.
"""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from . import db

# --------------------------------------------------------------------------------------
# assessments (verified drafts)
# --------------------------------------------------------------------------------------

def create_assessment(thread_id: str, title: str, assessment: dict[str, Any], created_by: str, *,
                      description: str | None = None, revises: str | None = None) -> dict[str, Any]:
    version = 1
    if revises:
        prev = get_assessment(revises)
        version = int((prev or {}).get("version") or 1) + 1
    with db.connection() as conn:
        row = conn.execute(
            """INSERT INTO assessments (assessment_id, thread_id, title, assessment, created_by, description, revises, version)
               VALUES ('pending', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (thread_id, title, Jsonb(assessment), created_by, description, revises, version),
        ).fetchone()
        assessment_id = f"A-{row['id']:04d}"
        assessment = {**assessment, "assessment_id": assessment_id}
        conn.execute(
            "UPDATE assessments SET assessment_id = %s, assessment = %s WHERE id = %s",
            (assessment_id, Jsonb(assessment), row["id"]),
        )
    return get_assessment(assessment_id)  # type: ignore[return-value]


def get_assessment(assessment_id: str) -> dict[str, Any] | None:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM assessments WHERE assessment_id = %s", (assessment_id,)).fetchone()
    return dict(row) if row else None


def change_request_for_thread(thread_id: str) -> dict[str, Any] | None:
    """The open change request on this thread: the latest assessment if its status is changes_requested, with the
    DPO's requested changes (one per line) and the comment's author. None once a revision exists or nothing is open."""
    latest = latest_assessment_for_thread(thread_id)
    if not latest or latest.get("status") != "changes_requested":
        return None
    task = None
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM review_tasks WHERE assessment_id = %s AND status = 'changes_requested' ORDER BY resolved_at DESC LIMIT 1",
            (latest["assessment_id"],),
        ).fetchone()
        task = dict(row) if row else None
    requests = [l.strip(" -•\t") for l in ((task or {}).get("dpo_comment") or "").splitlines() if l.strip(" -•\t")]
    return {"assessment": latest, "task": task, "requests": requests}


def assessment_history(assessment_id: str) -> list[dict[str, Any]]:
    """The chain v1 → v2 → … that ends in `assessment_id`, oldest first, each with the review decision taken on it."""
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cur = get_assessment(assessment_id)
    while cur and cur["assessment_id"] not in seen:
        seen.add(cur["assessment_id"])
        with db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM review_tasks WHERE assessment_id = %s AND status <> 'pending' ORDER BY resolved_at DESC LIMIT 1",
                (cur["assessment_id"],),
            ).fetchone()
        cur["decision"] = dict(row) if row else None
        chain.append(cur)
        cur = get_assessment(cur["revises"]) if cur.get("revises") else None
    chain.reverse()
    return chain


def latest_assessment_for_thread(thread_id: str) -> dict[str, Any] | None:
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1", (thread_id,)
        ).fetchone()
    return dict(row) if row else None


def update_assessment(assessment_id: str, *, assessment: dict[str, Any] | None = None, status: str | None = None,
                      dpia_draft: str | None = None) -> None:
    sets, params = [], []
    if assessment is not None:
        sets.append("assessment = %s"); params.append(Jsonb(assessment))
        sets.append("title = %s"); params.append(assessment.get("title", "")[:200])
    if status is not None:
        sets.append("status = %s"); params.append(status)
    if dpia_draft is not None:
        sets.append("dpia_draft = %s"); params.append(dpia_draft)
    if not sets:
        return
    sets.append("updated_at = now()")
    params.append(assessment_id)
    with db.connection() as conn:
        conn.execute(f"UPDATE assessments SET {', '.join(sets)} WHERE assessment_id = %s", params)


# --------------------------------------------------------------------------------------
# review_tasks (DPO queue)
# --------------------------------------------------------------------------------------

def create_review_task(thread_id: str, assessment_id: str, requested_by: str) -> dict[str, Any]:
    """Idempotent: one pending task per assessment (partial unique index)."""
    a = get_assessment(assessment_id)
    if a is None:
        raise ValueError(f"unknown assessment {assessment_id}")
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT * FROM review_tasks WHERE assessment_id = %s AND status = 'pending'", (assessment_id,)
        ).fetchone()
        if existing:
            return dict(existing)
        row = conn.execute(
            """INSERT INTO review_tasks (thread_id, assessment_id, title, requested_by, assessment)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (thread_id, assessment_id, a["title"], requested_by, Jsonb(a["assessment"])),
        ).fetchone()
        conn.execute("UPDATE assessments SET status = 'pending_review', updated_at = now() WHERE assessment_id = %s", (assessment_id,))
    return dict(row)


def resolve_review_task(task_id: int, status: str, resolved_by: str, comment: str | None,
                        assessment: dict[str, Any] | None = None, memory_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    with db.connection() as conn:
        row = conn.execute(
            """UPDATE review_tasks SET status = %s, resolved_by = %s, dpo_comment = %s, resolved_at = now(),
                      assessment = COALESCE(%s, assessment), memory_items = %s
               WHERE id = %s RETURNING *""",
            (status, resolved_by, comment, Jsonb(assessment) if assessment else None, Jsonb(memory_items or []), task_id),
        ).fetchone()
    return dict(row)


def decision_awaiting_memory(thread_id: str, resolved_by: str) -> dict[str, Any] | None:
    """The decision on this thread that memory_write has not processed yet (idempotent trigger)."""
    with db.connection() as conn:
        row = conn.execute(
            """SELECT * FROM review_tasks WHERE thread_id = %s AND resolved_by = %s AND status <> 'pending'
                      AND memory_written_at IS NULL ORDER BY resolved_at DESC LIMIT 1""",
            (thread_id, resolved_by),
        ).fetchone()
    return dict(row) if row else None


def mark_memory_written(task_id: int) -> None:
    with db.connection() as conn:
        conn.execute("UPDATE review_tasks SET memory_written_at = now() WHERE id = %s", (task_id,))


def pending_reviews() -> list[dict[str, Any]]:
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM review_tasks WHERE status = 'pending' ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def decided_reviews(limit: int = 20) -> list[dict[str, Any]]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM review_tasks WHERE status <> 'pending' ORDER BY resolved_at DESC NULLS LAST LIMIT %s", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_review_task(task_id: int) -> dict[str, Any] | None:
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM review_tasks WHERE id = %s", (task_id,)).fetchone()
    return dict(row) if row else None


def review_task_for_thread(thread_id: str, status: str | None = None) -> dict[str, Any] | None:
    with db.connection() as conn:
        if status:
            row = conn.execute(
                "SELECT * FROM review_tasks WHERE thread_id = %s AND status = %s ORDER BY created_at DESC LIMIT 1",
                (thread_id, status),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM review_tasks WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1", (thread_id,)
            ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------------------
# register (the goal)
# --------------------------------------------------------------------------------------

def record_in_register(assessment_id: str, approved_by: str, requested_by: str | None = None) -> dict[str, Any]:
    a = get_assessment(assessment_id)
    if a is None:
        raise ValueError(f"unknown assessment {assessment_id}")
    body = a["assessment"]
    citations: list[str] = []
    for f in body.get("findings", []):
        citations.extend(f.get("citations", []))
    citations = sorted(set(citations))
    with db.connection() as conn:
        row = conn.execute(
            """INSERT INTO register (assessment_id, thread_id, title, verdict, risk_level, high_risk_ai, dpia_required,
                                     assessment, citations, requested_by, approved_by, revises)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (assessment_id) DO UPDATE SET
                   assessment = EXCLUDED.assessment, citations = EXCLUDED.citations, verdict = EXCLUDED.verdict,
                   risk_level = EXCLUDED.risk_level, high_risk_ai = EXCLUDED.high_risk_ai,
                   dpia_required = EXCLUDED.dpia_required, approved_by = EXCLUDED.approved_by, approved_at = now(),
                   revises = EXCLUDED.revises
               RETURNING *""",
            (assessment_id, a["thread_id"], body.get("title", a["title"]), body.get("verdict", ""),
             body.get("risk_level", "medium"), bool(body.get("high_risk_ai")), bool(body.get("dpia_required")),
             Jsonb(body), citations, requested_by or a["created_by"], approved_by, a.get("revises")),
        ).fetchone()
        conn.execute("UPDATE assessments SET status = 'recorded', updated_at = now() WHERE assessment_id = %s", (assessment_id,))
    return dict(row)


def search_register(query: str, limit: int = 5) -> list[dict[str, Any]]:
    q = query.strip()
    with db.connection() as conn:
        if q.upper().startswith("A-"):
            rows = conn.execute("SELECT * FROM register WHERE assessment_id = %s", (q.upper(),)).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM register
                   WHERE title ILIKE %s OR assessment::text ILIKE %s
                   ORDER BY approved_at DESC LIMIT %s""",
                (f"%{q}%", f"%{q}%", limit),
            ).fetchall()
    return [dict(r) for r in rows]


def list_register(limit: int = 100) -> list[dict[str, Any]]:
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM register ORDER BY approved_at DESC LIMIT %s", (limit,)).fetchall()
    return [dict(r) for r in rows]


