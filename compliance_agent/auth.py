"""Login and the permission matrix (config/roles.yaml).

    verify_login(username, password) -> UserContext | None     bcrypt check against users table
    user_for_oidc(subject=, email=, ...) -> UserContext | None  the row for a verified OpenID identity (created on first sign-in)
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
    if not row or not row["password_hash"]:          # unknown, or an OIDC-only account without a password
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return None
    return UserContext(user_id=row["username"], role=row["role"], display_name=row["display_name"])


def user_for_oidc(*, subject: str, email: str, display_name: str, dpo_emails: set[str], default_role: str) -> UserContext | None:
    """The users row for a verified OpenID identity, created on first sign-in (deployment note, OIDC).

    Matched by the provider's subject first, then by e-mail (a seeded or earlier row that carries one). The role is
    decided at every sign-in: an e-mail on the DPO allowlist is a DPO, any other OIDC user is `default_role`
    (`product_manager` for the public demo; `deny` admits nobody the table does not know, the original design).
    The username of a created row is the e-mail address, so everything keyed on user_id keeps working."""
    email = email.strip().lower()
    role = "dpo" if email in dpo_emails else default_role
    with db.connection() as conn:
        row = conn.execute("SELECT username, display_name, role FROM users WHERE oidc_subject = %s", (subject,)).fetchone() \
            or conn.execute("SELECT username, display_name, role FROM users WHERE email = %s", (email,)).fetchone()
        if row is None:
            if role == "deny":
                return None
            conn.execute(
                "INSERT INTO users (username, display_name, role, password_hash, email, oidc_subject) VALUES (%s, %s, %s, NULL, %s, %s)",
                (email, display_name or email, role, email, subject))
            return UserContext(user_id=email, role=role, display_name=display_name or email)
        new_role = row["role"] if role == "deny" else role
        conn.execute("UPDATE users SET oidc_subject = %s, email = COALESCE(email, %s), role = %s WHERE username = %s",
                     (subject, email, new_role, row["username"]))
        return UserContext(user_id=row["username"], role=new_role, display_name=row["display_name"])


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
