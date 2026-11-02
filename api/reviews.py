"""The DPO's queue: GET /api/reviews · GET /api/reviews/{task_id} · POST /api/reviews/{task_id}/memory-candidates.
The decision itself is a resume of the thread (POST /api/threads/{id}/resume, step 2), as in the graph."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from compliance_agent import memory, repo
from compliance_agent.state import UserContext

from .deps import require_dpo
from .schemas import MemoryCandidate, MemoryCandidatesOut, MemoryCandidatesRequest

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("")
def list_reviews(user: UserContext = Depends(require_dpo)) -> dict[str, Any]:
    """Pending requests (oldest first) and the last 20 decisions."""
    return {"pending": repo.pending_reviews(), "decided": repo.decided_reviews(limit=20)}


def _task_or_404(task_id: int) -> dict[str, Any]:
    task = repo.get_review_task(task_id)
    if task is None:
        raise HTTPException(404, "unknown review task")
    return task


@router.get("/{task_id}")
def get_review(task_id: int, user: UserContext = Depends(require_dpo)) -> dict[str, Any]:
    """The task with its assessment row; for a revision also the previous version and what the DPO asked for
    (what the review form shows)."""
    task = _task_or_404(task_id)
    row = repo.get_assessment(task["assessment_id"])
    if row is None:
        raise HTTPException(404, "the task's assessment is gone")
    a = row["assessment"]
    previous, requested_changes = None, None
    if a.get("revises"):
        previous = repo.get_assessment(a["revises"])
        hist = [h for h in repo.assessment_history(a["assessment_id"]) if h["assessment_id"] == a["revises"]]
        requested_changes = (hist[0].get("decision") or {}).get("dpo_comment") if hist else None
    return {"task": task, "assessment": row, "previous": previous, "requested_changes": requested_changes}


@router.post("/{task_id}/memory-candidates", response_model=MemoryCandidatesOut)
def memory_candidates(task_id: int, body: MemoryCandidatesRequest, user: UserContext = Depends(require_dpo)) -> MemoryCandidatesOut:
    """'What the assistant will remember': the deterministic candidates `memory_write` would store for each
    decision, computed from the DPO's amendments and comment as typed (`memory.propose_from_decision`)."""
    task = _task_or_404(task_id)
    row = repo.get_assessment(task["assessment_id"])
    if row is None:
        raise HTTPException(404, "the task's assessment is gone")
    a = row["assessment"]
    allowed = memory.allowed_types(user.role)

    def wrap(items: list[dict[str, Any]]) -> list[MemoryCandidate]:
        return [MemoryCandidate(item=it, label=memory.ns_label(it["type"], user.user_id), allowed=it["type"] in allowed) for it in items]

    on_approve = memory.propose_from_decision(a, body.amended, "approve", body.comment, requested_by=task["requested_by"])
    on_reject = memory.propose_from_decision(a, None, "reject", body.comment, requested_by=task["requested_by"])
    on_changes = memory.propose_from_decision(a, None, "request_changes", body.comment, requested_by=task["requested_by"])
    return MemoryCandidatesOut(
        amendments=wrap([it for it in on_approve if it["source"] == "dpo_amendment"]),
        note=wrap([it for it in on_approve if it["source"] == "dpo_comment"]),
        on_changes=wrap([it for it in on_changes if it["source"] == "dpo_change_request"]),
        on_reject=wrap([it for it in on_reject if it["source"] == "dpo_rejection"]),
    )
