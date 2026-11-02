"""GET /api/register · GET /api/register.pdf · GET /api/assessments/{id} · GET /api/assessments/{id}.md"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse

from compliance_agent import auth, repo
from compliance_agent.export import assessment_markdown, register_pdf
from compliance_agent.state import UserContext

from .deps import current_user

router = APIRouter(prefix="/api", tags=["register"])


@router.get("/register")
def list_register(user: UserContext = Depends(current_user)) -> dict[str, Any]:
    """Every recorded entry (`repo.list_register`), with the v1 → v2 history for entries that revise an earlier
    assessment, and whether this user may export."""
    rows = repo.list_register()
    for r in rows:
        r["history"] = repo.assessment_history(r["assessment_id"]) if r.get("revises") else []
    return {"entries": rows, "can_export": auth.is_allowed(user.role, "export_register")}


class PDFResponse(Response):
    media_type = "application/pdf"          # advertised in the OpenAPI document, so /docs offers a download link


@router.get("/register.pdf", response_class=PDFResponse)
def register_as_pdf(user: UserContext = Depends(current_user)) -> Response:
    """The overview table and every recorded assessment in full, for audits (DPO only: roles.yaml `export_register`)."""
    if not auth.is_allowed(user.role, "export_register"):
        raise HTTPException(403, "Export is available to the DPO.")
    pdf = register_pdf(repo.list_register(), generated_by=user.user_id)
    name = f"processing_register_{datetime.now():%Y-%m-%d}.pdf"
    return PDFResponse(content=pdf, headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _assessment_or_404(assessment_id: str) -> dict[str, Any]:
    row = repo.get_assessment(assessment_id)
    if row is None:
        raise HTTPException(404, "unknown assessment")
    return row


@router.get("/assessments/{assessment_id}.md", response_class=PlainTextResponse)
def assessment_as_markdown(assessment_id: str, user: UserContext = Depends(current_user)) -> PlainTextResponse:
    """The *Download (Markdown)* button."""
    row = _assessment_or_404(assessment_id)
    return PlainTextResponse(assessment_markdown(row["assessment"]), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{assessment_id}.md"'})


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, user: UserContext = Depends(current_user)) -> dict[str, Any]:
    """The assessment row: status, the assessment, who created it, what it revises, its version."""
    return _assessment_or_404(assessment_id)
