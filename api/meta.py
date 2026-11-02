"""GET /api/meta (models per node, prices, tracing) · GET /api/meta/graph-layout (the live graph's drawing)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from compliance_agent import config, viz
from compliance_agent.models import node_models, pricing, resolved_model_ids
from compliance_agent.state import UserContext

from .deps import current_user

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def meta(user: UserContext = Depends(current_user)) -> dict[str, Any]:
    """Display only: models are fixed in config/models.yaml, there is no user-facing switch."""
    return {"models": node_models(), "model_ids": resolved_model_ids(), "pricing": pricing(),
            "langsmith": {"enabled": config.langsmith_enabled(), "project": config.env("LANGSMITH_PROJECT", "default")}}


@router.get("/graph-layout")
def graph_layout(user: UserContext = Depends(current_user)) -> dict[str, Any]:
    """The layout constants of viz.py; the front end draws them and applies a run's `graph` snapshot."""
    return viz.layout_json()
