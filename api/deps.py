"""Request dependencies: the current user from the session cookie, role checks, the compiled graph."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from compliance_agent import auth
from compliance_agent.state import UserContext

from . import sessions


def get_graph(request: Request):
    """The compiled graph of this process (set by the app's lifespan, or injected by the tests)."""
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(503, "the graph is not ready")
    return graph


def current_user(request: Request) -> UserContext:
    token = request.cookies.get(sessions.COOKIE_NAME)
    user = sessions.read_token(token) if token else None
    if user is None:
        raise HTTPException(401, "not logged in")
    return user


def require_dpo(user: UserContext = Depends(current_user)) -> UserContext:
    if not auth.can_approve(user.role):
        raise HTTPException(403, "the review queue is the DPO's")
    return user


def require_product_manager(user: UserContext = Depends(current_user)) -> UserContext:
    """Separation of duties: the DPO never generates what she approves (handover §3)."""
    if user.role != "product_manager":
        raise HTTPException(403, "only a product manager requests assessments")
    return user
