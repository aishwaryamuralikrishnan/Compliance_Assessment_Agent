"""Review tool: request_dpo_review (write, pauses the thread)."""
from __future__ import annotations

from langchain_core.tools import tool


@tool(response_format="content_and_artifact")
def request_dpo_review(assessment_id: str) -> tuple[str, dict]:
    """Send a verified assessment to the Data Protection Officer for approval.

    Creates a review task in the DPO's queue and pauses this conversation until the DPO
    approves, requests changes or rejects. Use the assessment id shown with the assessment
    ("A-0012"). Only call it when the user asks for DPO review / approval / recording.
    """
    # The tool gate performs the real work (creates the task, pauses, applies the DPO's
    # decision). If this body runs, the gate was bypassed - say so rather than pretend.
    return (
        f"request_dpo_review({assessment_id}) was not routed through the tool gate; no review task was created.",
        {"error": "gate bypassed"},
    )
