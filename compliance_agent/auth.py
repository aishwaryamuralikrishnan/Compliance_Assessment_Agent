"""Login and the permission matrix (config/roles.yaml).

    verify_login(username, password) -> UserContext | None     bcrypt check against users table
    allowed_tools(role) -> set[str]                            tools bound for the role
    tool_kind(name) -> read | write | ui
    denied_message(role, name) -> str                          what the model is told
"""
from __future__ import annotations

from functools import lru_cache

from . import config, db
from .state import UserContext

APPROVER_ROLES = {"dpo"}


def verify_login(username: str, password: str) -> UserContext | None:
    import bcrypt

    with db.connection() as conn:
        row = conn.execute(
            "SELECT username, display_name, role, password_hash FROM users WHERE username = %s", (username.strip(),)
        ).fetchone()
    if not row:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return None
    return UserContext(user_id=row["username"], role=row["role"], display_name=row["display_name"])


@lru_cache(maxsize=1)
def _roles() -> dict:
    return config.roles_config()


def known_roles() -> list[str]:
    return list(_roles()["roles"].keys())


def allowed_tools(role: str) -> set[str]:
    spec = _roles()["roles"].get(role)
    if spec is None:
        return set()
    return set(spec.get("allowed", []))


def tool_kind(name: str) -> str:
    return _roles()["tools"].get(name, {}).get("kind", "read")


def is_allowed(role: str, name: str) -> bool:
    return name in allowed_tools(role)


def denied_message(role: str, name: str) -> str:
    spec = _roles()["roles"].get(role, {})
    custom = (spec.get("denied_message") or {}).get(name)
    if custom:
        return f"Not permitted: {custom}"
    return f"Not permitted: the tool '{name}' is not available to the role '{role}'."


def can_approve(role: str) -> bool:
    return role in APPROVER_ROLES


def memory_write_scopes(role: str) -> set[str]:
    return set((_roles().get("memory_writes") or {}).get(role, []))
