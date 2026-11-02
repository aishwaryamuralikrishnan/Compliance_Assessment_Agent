"""Threads (design note §5): GET /api/threads/{id}, POST /api/threads, POST /api/threads/{id}/resume,
POST /api/threads/{id}/feedback. The three POSTs start a run in the registry (api/runs.py) and answer 202 with
its id; the run's events are read from GET /api/runs/{id}/events."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from compliance_agent import auth, repo
from compliance_agent.graph import new_thread_id, pending_kind, resume_turn, run_turn, send_feedback, thread_state
from compliance_agent.state import UserContext

from .deps import current_user, get_graph, require_product_manager
from .runs import REGISTRY
from .schemas import FeedbackRequest, ResumeRequest, RunStarted, TurnRequest

router = APIRouter(prefix="/api/threads", tags=["threads"])

# the thread's values a page shows; `messages` (the whole LangChain history) and `structured_response` are not sent
VALUE_KEYS = ("input", "validation", "route", "route_confidence", "route_reason", "assessment", "answer", "sources",
              "guardrail", "regenerations", "decision", "revision", "revision_error", "feedback", "review_requested")

STATUS_TEXT = {"draft": "Draft — not yet reviewed.", "pending_review": "Sent to the DPO; waiting for the decision.",
               "rejected": "Rejected by the DPO.",
               "changes_requested": "The DPO requested changes to the feature; revise it and run a revision.",
               "approved": "Approved by the DPO.", "recorded": "Recorded in the processing register."}

DECISIONS = ("approve", "request_changes", "reject")


def run_in_progress(state: dict[str, Any]) -> bool:
    """True while a resume of this thread that this process does not own (another API process, or one that died
    mid-run) is still executing: no interrupt pending, the review task already decided, and the decision not yet
    written into the thread's state by the guardrail. The checkpoint's `next` is empty mid-run, so it cannot be
    used for this. The registry answers it for runs this process owns (`running_run_id`)."""
    if state.get("pending_interrupt"):
        return False
    v = state.get("values") or {}
    if v.get("decision") == "changes_requested":
        # the guardrail has written the decision but the run is still on its way through memory_write into
        # pm_revision; it is finished only once that node has paused (an interrupt is pending, handled above)
        return True
    if v.get("decision") or v.get("answer"):
        return False
    task = repo.review_task_for_thread(state.get("thread_id") or "")
    return bool(task) and task.get("status") not in (None, "pending")


def thread_body(thread_id: str, graph) -> dict[str, Any] | None:
    """The body of GET /threads/{id} and of the stream's `final` event; None for an unknown thread."""
    state = thread_state(thread_id, graph=graph)
    values = state.get("values") or {}
    pending = state.get("pending_interrupt")
    if not values and not pending:
        return None
    a = values.get("assessment") or None
    row = repo.get_assessment(a["assessment_id"]) if a and a.get("assessment_id") else None
    status = row["status"] if row else ("draft" if a else None)
    return {
        "thread_id": thread_id,
        "pending": {"kind": pending_kind(state), "value": pending},
        "running_run_id": REGISTRY.running_for(thread_id),
        "run_in_progress": run_in_progress(state),
        "status": status,
        "status_text": STATUS_TEXT.get(status, status) if status else None,
        "review_task": repo.review_task_for_thread(thread_id),
        "values": {k: values.get(k) for k in VALUE_KEYS if k in values},
        "last_view": REGISTRY.last_view_for(thread_id),
        "views": REGISTRY.views_for(thread_id),
    }


@router.get("/{thread_id}")
def get_thread(thread_id: str, user: UserContext = Depends(current_user), graph=Depends(get_graph)) -> dict[str, Any]:
    """State of a thread plus its pending interrupt. Any logged-in user may
    read a thread: the DPO reads the product manager's. `running_run_id` names a run this process is executing on
    it (subscribe to its events); `views` are the latest views of every run this process executed on the thread
    (`last_view` the last of them), so a reloaded page, or the requester's page after the DPO decided, has the
    traces and the accumulated graph without having caught the runs live."""
    body = thread_body(thread_id, graph)
    if body is None:
        raise HTTPException(404, "unknown thread")
    return body


def _started(run) -> RunStarted:
    return RunStarted(run_id=run.run_id, thread_id=run.thread_id)


@router.post("", response_model=RunStarted, status_code=202)
def start_turn(body: TurnRequest, user: UserContext = Depends(require_product_manager), graph=Depends(get_graph)) -> RunStarted:
    """Run a turn: a feature description or a question. A new thread when `thread_id` is absent. Refused (409) while
    the thread is paused at an interrupt (resume it instead) or has a run executing."""
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "the message is empty")
    thread_id = body.thread_id or new_thread_id()
    if body.thread_id and pending_kind(thread_state(thread_id, graph=graph)):
        raise HTTPException(409, "the thread is paused at an interrupt; resume it instead of sending a new turn")
    run = REGISTRY.start(kind="turn", user=user, thread_id=thread_id, graph=graph, thread_body=thread_body, resumed=False,
                         make_gen=lambda: run_turn(user, message, thread_id, graph=graph))
    return _started(run)


@router.post("/{thread_id}/resume", response_model=RunStarted, status_code=202)
def resume(thread_id: str, body: ResumeRequest, user: UserContext = Depends(current_user), graph=Depends(get_graph)) -> RunStarted:
    """Resume a paused thread. At the DPO's pause: `{decision, comment, assessment?, memory_items}` (DPO only; a
    reason is required for request_changes and reject). At the product manager's pause: `{description, responses}`
    (the thread's requester only; one response per requested change). 409 when nothing is pending."""
    state = thread_state(thread_id, graph=graph)
    kind = pending_kind(state)
    pending = state.get("pending_interrupt") or {}
    if kind == "dpo":
        if not auth.can_approve(user.role):
            raise HTTPException(403, "only the DPO decides on a review request")
        if body.decision not in DECISIONS:
            raise HTTPException(400, f"decision must be one of {', '.join(DECISIONS)}")
        comment = (body.comment or "").strip()
        if body.decision != "approve" and not comment:
            raise HTTPException(400, "request_changes and reject need a reason in the comment")
        payload: dict[str, Any] = {"decision": body.decision, "comment": comment, "memory_items": body.memory_items or []}
        if body.decision == "approve":
            payload["assessment"] = body.assessment             # the amended assessment, or None
        run_kind = "decision"
    elif kind == "pm":
        if user.role != "product_manager" or user.user_id != pending.get("requester"):
            raise HTTPException(403, f"only the requester ({pending.get('requester')}) can revise this feature")
        description = (body.description or "").strip()
        if not description:
            raise HTTPException(400, "the revised description is empty")
        payload = {"description": description, "responses": body.responses or []}
        run_kind = "revision"
    else:
        raise HTTPException(409, "the thread is not paused at an interrupt")
    run = REGISTRY.start(kind=run_kind, user=user, thread_id=thread_id, graph=graph, thread_body=thread_body, resumed=True,
                         make_gen=lambda: resume_turn(user, thread_id, payload, graph=graph))
    return _started(run)


@router.post("/{thread_id}/feedback", response_model=RunStarted, status_code=202)
def feedback(thread_id: str, body: FeedbackRequest, user: UserContext = Depends(current_user), graph=Depends(get_graph)) -> RunStarted:
    """Feedback on a completed thread: a preference note (stored as the author's own preference) and / or the DPO's
    *Keep as a good example*. 409 while the thread is paused (nothing may touch a thread at interrupt())."""
    comment = (body.comment or "").strip()
    if not comment and not body.keep_example:
        raise HTTPException(400, "nothing to store: give a comment or keep_example")
    if body.keep_example and not auth.can_approve(user.role):
        raise HTTPException(403, "only the DPO keeps an assessment as a good example")
    state = thread_state(thread_id, graph=graph)
    if not state.get("values") and not state.get("pending_interrupt"):
        raise HTTPException(404, "unknown thread")
    if pending_kind(state):
        raise HTTPException(409, "the thread is paused at interrupt(); feedback opens once it has completed")
    run = REGISTRY.start(kind="feedback", user=user, thread_id=thread_id, graph=graph, thread_body=thread_body, resumed=True,
                         make_gen=lambda: send_feedback(user, thread_id, comment or None, keep_example=body.keep_example,
                                                        run_id=body.run_id, graph=graph))
    return _started(run)
