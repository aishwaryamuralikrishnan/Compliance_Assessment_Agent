"""The session token: a JWT (HS256) in an httpOnly cookie, 8 hours, built from the `users` table row at login
(design note §6). The role travels in the token because the token was built from the table; nothing in a
request can change it. OIDC later issues the same token from its callback."""
from __future__ import annotations

import logging
import secrets
import time

import jwt

from compliance_agent import config
from compliance_agent.state import UserContext

log = logging.getLogger(__name__)

COOKIE_NAME = "session"
TTL_SECONDS = 8 * 3600
_ALGO = "HS256"
_secret: str | None = None


def secret() -> str:
    """SESSION_SECRET from the environment. Without it a random per-process secret is used and said so in the
    log: fine for development, but every restart logs everyone out."""
    global _secret
    if _secret is None:
        _secret = config.env("SESSION_SECRET") or ""
        if not _secret:
            _secret = secrets.token_urlsafe(32)
            log.warning("SESSION_SECRET is not set: using a random per-process secret, sessions end when the API restarts")
    return _secret


def make_token(user: UserContext) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user.user_id, "role": user.role, "name": user.display_name, "iat": now, "exp": now + TTL_SECONDS},
                      secret(), algorithm=_ALGO)


def read_token(token: str) -> UserContext | None:
    try:
        claims = jwt.decode(token, secret(), algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
    sub, role = claims.get("sub"), claims.get("role")
    if not sub or not role:
        return None
    return UserContext(user_id=sub, role=role, display_name=claims.get("name") or "")


def cookie_secure() -> bool:
    return (config.env("SESSION_COOKIE_SECURE") or "false").lower() in ("1", "true", "yes")
