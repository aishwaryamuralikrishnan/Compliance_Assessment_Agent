"""GET /api/memory: the long-term store with provenance, in the three sections of the Memory page."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from compliance_agent import memory
from compliance_agent.state import UserContext

from .deps import current_user, get_graph

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("")
def list_memory(user: UserContext = Depends(current_user), graph=Depends(get_graph)) -> dict[str, Any]:
    """Org facts and the DPO's standing positions, lessons from decisions, and this user's own preferences. A
    namespace that cannot be read is reported in its section (`error`), not hidden."""
    store = graph.store
    spec = [
        ("org/facts", "Facts about the organisation and the DPO's standing positions", "visible to every user", memory.ORG_FACTS),
        ("org/lessons", "Corrections and examples taken from the DPO's decisions", "visible to every user", memory.ORG_LESSONS),
        (f"user/{memory.user_ns_label(user.user_id)}/prefs", "Your own answer-style preferences", "visible only to you",
         memory.user_prefs_namespace(user.user_id)),
    ]
    sections = []
    for ns_name, what, who, ns in spec:
        try:
            items, error = memory.list_namespace(store, ns), None
        except Exception as exc:                      # reported, never hidden (TECHNICAL.md conventions)
            log.exception("memory namespace %s unreadable", ns_name)
            items, error = [], f"{type(exc).__name__}: {exc}"
        sections.append({"namespace": ns_name, "what": what, "who": who, "items": items, "error": error})
    return {"sections": sections,
            "can_add": sorted(memory.ns_label(t, user.user_id) for t in memory.allowed_types(user.role))}
