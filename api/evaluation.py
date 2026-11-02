"""GET /api/eval/report · the evaluation report (eval/README.md section 7), built from the latest run of each set
under eval/results/ (or EVAL_RESULTS_DIR) and the notes in eval/report/notes.json. Public and read-only (decided
29 Oct): the report is for whoever reviews the project, holds no personal data, and the evaluation pages are
reached from the login screen without signing in. scripts/eval_pdf.py prints their print view."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


@router.get("/report")
def report() -> dict[str, Any]:
    """The report as one document: targets with met/not met, the per-set figures, E6 per case, cost, the author's notes.
    404 when no run exists, so the page can say so rather than draw an empty chart."""
    from eval.harness.report import build, results_dir

    doc = build()
    if not doc["runs"]:
        raise HTTPException(status_code=404, detail=f"no evaluation runs under {results_dir()}; run python -m eval.run_eval first")
    return doc
