"""Sign in with Google (api/oidc.py): the provider is stubbed (discovery, code exchange, ID-token verification), the
rest runs for real — the state cookie, the users row created or matched, the role from the DPO allowlist or the
default, the session cookie, the refusals. docs/deployment_design.md, section OIDC."""
from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_api import api_users, make_client  # noqa: F401  (fixture used by name)

ISSUER = "https://accounts.google.com"
DISC = {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth", "token_endpoint": "https://oauth2.googleapis.com/token", "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs"}


@pytest.fixture()
def oidc(monkeypatch):
    """Google configured; the three network calls replaced. `claims` is what the ID token will say."""
    from api import oidc as O

    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-123")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "shh")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://web.test")
    monkeypatch.setenv("DPO_EMAILS", "Aishwarya@Example.com")
    monkeypatch.delenv("OIDC_DEFAULT_ROLE", raising=False)
    box = {"claims": {}, "exchange": []}
    monkeypatch.setattr(O, "discovery", lambda issuer: DISC)
    monkeypatch.setattr(O, "exchange_code", lambda endpoint, **kw: (box["exchange"].append(kw), {"id_token": "signed-by-google"})[1])
    monkeypatch.setattr(O, "verify_id_token", lambda token, **kw: dict(box["claims"]))
    yield box
    # the scratch database is shared by the API tests: remove the rows these tests created or marked
    from compliance_agent import db

    with db.connection() as conn:
        conn.execute("DELETE FROM users WHERE oidc_subject IS NOT NULL AND password_hash IS NULL")
        conn.execute("UPDATE users SET email = NULL, oidc_subject = NULL")


def _sign_in(c, box, claims):
    """Follow the two redirects by hand: start sets the state cookie, the callback consumes it."""
    box["claims"] = claims
    r = c.get("/api/auth/oidc/start", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["client_id"] == ["client-123"] and q["redirect_uri"] == ["http://web.test/api/auth/oidc/callback"] and q["code_challenge_method"] == ["S256"]
    return c.get(f"/api/auth/oidc/callback?code=abc&state={q['state'][0]}", follow_redirects=False)


def test_first_sign_in_creates_a_product_manager_and_the_allowlist_makes_a_dpo(api_users, oidc):
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    graph = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(graph) as c:
        assert c.get("/api/auth/providers").json() == {"oidc": True, "name": "Google"}
        # a colleague: not on the list -> product manager, row created with the e-mail as username, no password
        r = _sign_in(c, oidc, {"sub": "g-1", "email": "Pat@Example.com", "email_verified": True, "name": "Pat"})
        assert r.status_code == 302 and r.headers["location"] == "/assistant" and "session=" in r.headers["set-cookie"]
        assert c.get("/api/auth/me").json() == {"user_id": "pat@example.com", "role": "product_manager", "display_name": "Pat"}
        assert oidc["exchange"][-1]["redirect_uri"] == "http://web.test/api/auth/oidc/callback" and oidc["exchange"][-1]["verifier"]
        with db.connection() as conn:
            row = conn.execute("SELECT username, email, oidc_subject, password_hash FROM users WHERE oidc_subject = 'g-1'").fetchone()
        assert row == {"username": "pat@example.com", "email": "pat@example.com", "oidc_subject": "g-1", "password_hash": None}
        # a password login against that row is refused (no password), the seeded accounts are untouched
        assert c.post("/api/auth/login", json={"username": "pat@example.com", "password": "x"}).status_code == 401
        c.post("/api/auth/logout")
        # the author: on the allowlist (case-insensitive) -> DPO, lands on the review queue
        r = _sign_in(c, oidc, {"sub": "g-2", "email": "aishwarya@example.com", "email_verified": True, "name": "Aishwarya"})
        assert r.headers["location"] == "/review" and c.get("/api/auth/me").json()["role"] == "dpo"
        # the same subject again: matched, not duplicated; the role is read again at sign-in
        c.post("/api/auth/logout")
        _sign_in(c, oidc, {"sub": "g-2", "email": "aishwarya@example.com", "email_verified": True, "name": "Aishwarya M."})
        with db.connection() as conn:
            assert conn.execute("SELECT count(*) AS n FROM users WHERE email = 'aishwarya@example.com'").fetchone()["n"] == 1


def test_refusals_and_the_invitation_only_mode(api_users, oidc, monkeypatch):
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    graph = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(graph) as c:
        # an unverified e-mail is refused and sent back to the login page with a reason
        r = _sign_in(c, oidc, {"sub": "g-3", "email": "x@example.com", "email_verified": False})
        assert r.status_code == 302 and r.headers["location"] == "/login?error=email-unverified" and "session=" not in r.headers.get("set-cookie", "")
        # a callback without the state cookie, or with another state, is refused
        assert c.get("/api/auth/callback-missing", follow_redirects=False).status_code == 404
        oidc["claims"] = {"sub": "g-4", "email": "y@example.com", "email_verified": True}
        c.get("/api/auth/oidc/start", follow_redirects=False)
        assert c.get("/api/auth/oidc/callback?code=abc&state=forged", follow_redirects=False).headers["location"] == "/login?error=state-mismatch"
        # the provider reporting an error
        assert c.get("/api/auth/oidc/callback?error=access_denied", follow_redirects=False).headers["location"] == "/login?error=provider-access_denied"
        # invitation only: an unknown identity is refused, a known one (by e-mail) still signs in with its table role
        monkeypatch.setenv("OIDC_DEFAULT_ROLE", "deny")
        r = _sign_in(c, oidc, {"sub": "g-5", "email": "stranger@example.com", "email_verified": True})
        assert r.headers["location"] == "/login?error=not-invited"
        with db.connection() as conn:
            conn.execute("UPDATE users SET email = 'lena@example.com' WHERE username = 'lena.k'")
        r = _sign_in(c, oidc, {"sub": "g-6", "email": "lena@example.com", "email_verified": True, "name": "Lena"})
        assert r.headers["location"] == "/assistant" and c.get("/api/auth/me").json() == {"user_id": "lena.k", "role": "product_manager", "display_name": "Lena K."}


def test_providers_reports_off_when_not_configured(api_users, monkeypatch):
    from compliance_agent import db
    from compliance_agent.graph import build_graph

    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
    graph = build_graph(checkpointer=db.langgraph_checkpointer(), store=db.langgraph_store())
    with make_client(graph) as c:
        assert c.get("/api/auth/providers").json() == {"oidc": False, "name": None}
        assert c.get("/api/auth/oidc/start", follow_redirects=False).status_code == 404
