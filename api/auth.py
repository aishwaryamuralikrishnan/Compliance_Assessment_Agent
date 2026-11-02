"""POST /api/auth/login · POST /api/auth/logout · GET /api/auth/me"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from compliance_agent import auth as accounts
from compliance_agent.state import UserContext

from . import sessions
from .deps import current_user
from .schemas import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response) -> UserOut:
    """bcrypt check against the users table (`auth.verify_login`); sets the `session` cookie."""
    user = accounts.verify_login(body.username, body.password)
    if user is None:
        raise HTTPException(401, "Unknown user or wrong password.")
    response.set_cookie(sessions.COOKIE_NAME, sessions.make_token(user), max_age=sessions.TTL_SECONDS, httponly=True,
                        samesite="lax", secure=sessions.cookie_secure(), path="/")
    return UserOut(user_id=user.user_id, role=user.role, display_name=user.display_name)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(sessions.COOKIE_NAME, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: UserContext = Depends(current_user)) -> UserOut:
    return UserOut(user_id=user.user_id, role=user.role, display_name=user.display_name)
