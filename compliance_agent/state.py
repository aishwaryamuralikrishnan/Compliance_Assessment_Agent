"""Typed state of the orchestrator graph and the structured outputs it carries.

Identity (user_id, role, thread_id) is NOT state: it travels in config["configurable"]
so a thread can be resumed by a different user (the DPO approving a product manager's
request) without rewriting state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Role = Literal["product_manager", "dpo"]
Route = Literal["quick", "full", "revise", "reject"]


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str
    display_name: str = ""


# --------------------------------------------------------------------------------------
# Structured outputs of the worker
# --------------------------------------------------------------------------------------

class Finding(BaseModel):
    """One finding of the compliance assessment, tied to the provisions it rests on."""

    severity: Literal["Blocker", "Required", "Covered"] = Field(
        description="Blocker: must change before build. Required: an obligation to fulfil. Covered: already handled (e.g. by an organisation fact)."
    )
    text: str = Field(description="One or two sentences: what the issue is and what to do about it.")
    citations: list[str] = Field(
        default_factory=list,
        description="Citation labels exactly as returned by the tools, e.g. 'GDPR Art. 22(1)', 'GDPR Rec. 71', 'AI Act Annex III point 5', 'AI Act Art. 6(2)'.",
    )


class ChangeNote(BaseModel):
    """One line of 'Changes since v1' in a revised assessment: what the DPO asked, what the PM did, the consequence."""

    request: str = Field(description="The DPO's requested change, as given.")
    pm_response: str = Field(description="What the product manager did about it: 'done: ...' or 'not possible: ...'.")
    outcome: Literal["closed", "narrowed", "kept", "new"] = Field(
        description="closed: the finding no longer applies; narrowed: still applies with smaller scope or lower severity; "
                    "kept: unchanged (say why); new: the change introduced an issue v1 did not have.")
    finding: str = Field(description="The finding concerned, by its topic or first words; 'none' if no finding is affected.")
    explanation: str = Field(description="One or two sentences on the legal consequence, with the citation labels that back it.")


class Assessment(BaseModel):
    """A structured GDPR / EU AI Act compliance assessment of a planned feature."""

    title: str = Field(description="Short title of the feature or processing activity, e.g. 'Automated credit scoring (BNPL)'.")
    verdict: Literal["Do not build as described", "Proceed with conditions", "Proceed"] = Field(
        description="Headline verdict."
    )
    risk_level: Literal["low", "medium", "high"]
    summary: str = Field(description="Two or three sentences explaining the verdict, citing the decisive provisions.")
    high_risk_ai: bool = Field(description="True if the activity is (or contains) a high-risk AI system under the AI Act.")
    dpia_required: bool = Field(description="True if a data protection impact assessment is required (GDPR Art. 35).")
    findings: list[Finding] = Field(description="Severity-tagged findings, blockers first.")
    next_steps: list[str] = Field(description="Concrete, ordered actions for the product team.")
    revises: str | None = Field(default=None, description="Revision only: the id of the assessment this one revises, e.g. 'A-0038'.")
    changes_since_v1: list[ChangeNote] | None = Field(
        default=None, description="Revision only: one entry per change the DPO requested, in the DPO's order.")


class StatusReply(BaseModel):
    """A short non-assessment reply: a status update, confirmation, clarification request or
    the outcome of a register / review action."""

    message: str = Field(description="The reply to the user, with citation labels where provisions are mentioned.")


# --------------------------------------------------------------------------------------
# Graph state
# --------------------------------------------------------------------------------------

class GraphState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    input: str                       # the user's text for this turn (after validation / redaction)
    validation: dict[str, Any]       # {ok, reason, flags: [...], redactions: n}
    route: Route
    route_confidence: float
    route_reason: str
    structured_response: Any         # filled by the worker subgraph (Assessment | StatusReply)
    assessment: dict[str, Any] | None   # verified assessment incl. assessment_id, sources, disclaimer
    answer: str | None               # plain-text answer for quick / reject / status turns
    sources: list[dict[str, Any]]    # chunks retrieved in this turn (from tool artifacts)
    guardrail: dict[str, Any]        # {citations_checked, invalid, pii_redactions, regenerated}
    regenerations: int
    feedback: dict[str, Any] | None  # {score, comment, run_id} from the UI (step 6)
    review_requested: bool           # output_guardrail already sent the worker to request DPO review for this assessment
    revision: dict[str, Any] | None  # revision run only: {revises, requests, responses, previous_description, v1}
    decision: str | None             # the DPO's last decision on this thread (approved | changes_requested | rejected); drives memory_write → pm_revision
    revision_error: str | None       # pm_revision: why the last resume was refused (the node runs again and shows it)
    revision_attempts: int
    memory_items: list[dict[str, Any]]
