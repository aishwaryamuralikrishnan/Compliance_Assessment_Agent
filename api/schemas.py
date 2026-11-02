"""Request and response models of the contract (docs/web_app_design.md §5). Database rows and the assessment
itself are free-form JSON and are returned as dicts; the models here are the bodies the client sends and the
small fixed-shape replies."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(examples=["lena.k"])
    password: str


class UserOut(BaseModel):
    user_id: str
    role: str
    display_name: str = ""


class HealthOut(BaseModel):
    ok: bool
    db: bool
    detail: str | None = None


class TurnRequest(BaseModel):
    message: str = Field(examples=["We're adding automated credit scoring to our checkout …"])
    thread_id: str | None = Field(default=None, description="Continue this thread; a new one when absent.")


class ResumeRequest(BaseModel):
    """Either the DPO's decision (`decision`, `comment`, `assessment`, `memory_items`) or the product manager's
    revision (`description`, `responses`); which one is decided by the pause the thread is at."""

    decision: str | None = Field(default=None, examples=["approve"], description="approve | request_changes | reject")
    comment: str | None = None
    assessment: dict[str, Any] | None = Field(default=None, description="The amended assessment (approve only), if edited.")
    memory_items: list[dict[str, Any]] | None = Field(default=None, description="The ticked memory candidates.")
    description: str | None = Field(default=None, description="The revised feature description (pm pause).")
    responses: list[dict[str, Any]] | None = Field(default=None, description='[{"status": "done" | "not_possible", "note": "…"}, …], one per requested change.')


class FeedbackRequest(BaseModel):
    comment: str | None = None
    keep_example: bool = False
    run_id: str | None = Field(default=None, description="The graph run to score in LangSmith, if tracing is on.")


class RunStarted(BaseModel):
    run_id: str
    thread_id: str


class MemoryCandidatesRequest(BaseModel):
    """What the DPO has typed and amended so far; the reply is the deterministic memory candidates for each
    possible decision (the review page's 'What the assistant will remember')."""

    amended: dict[str, Any] | None = Field(default=None, description="The assessment with the DPO's edits, if any.")
    comment: str = ""


class MemoryCandidate(BaseModel):
    item: dict[str, Any]
    label: str = Field(description="The namespace the item would be written to, e.g. 'org/lessons'.")
    allowed: bool = Field(description="Whether this role may write that namespace (roles.yaml memory_writes).")


class MemoryCandidatesOut(BaseModel):
    """Compose per decision: approve = ticked amendments + ticked note;
    request_changes = ticked amendments + on_changes; reject = ticked amendments + on_reject.
    `on_changes` and `on_reject` depend on the decision itself and are shown but cannot be unticked."""

    amendments: list[MemoryCandidate]
    note: list[MemoryCandidate]
    on_changes: list[MemoryCandidate]
    on_reject: list[MemoryCandidate]
