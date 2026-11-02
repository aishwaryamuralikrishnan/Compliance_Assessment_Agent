"""Smoke test for the local setup: env vars, database, pgvector, one tiny model call.

    python scripts/check_env.py
    python scripts/check_env.py --no-model   # skip the OpenRouter calls
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compliance_agent import config, db  # noqa: E402


def main() -> None:
    skip_model = "--no-model" in sys.argv
    ok = True

    try:
        key = config.openrouter_api_key()
        print(f"OPENROUTER_API_KEY: set ({key[:7]}...{key[-4:]})")
    except config.ConfigError as exc:
        print(f"OPENROUTER_API_KEY: MISSING - {exc}")
        ok = False
    print(f"OPENROUTER_BASE_URL: {config.openrouter_base_url()}")
    print(f"DATABASE_URL: {config.database_url()}")

    try:
        with db.connect_plain() as conn:
            v = conn.execute("SELECT version()").fetchone()["version"]
            print(f"postgres: {v.split(',')[0]}")
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            ext = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
            print(f"pgvector: {ext['extversion'] if ext else 'NOT INSTALLED'}")
            n = conn.execute(
                "SELECT count(*) AS n FROM information_schema.tables WHERE table_name = 'legal_chunks'"
            ).fetchone()["n"]
            if n:
                rows = conn.execute(
                    "SELECT regulation, count(*) AS n, count(embedding) AS embedded FROM legal_chunks GROUP BY 1 ORDER BY 1"
                ).fetchall()
                print("legal_chunks:", ", ".join(f"{r['regulation']}={r['n']} ({r['embedded']} embedded)" for r in rows) or "empty")
            else:
                print("legal_chunks: table not created yet (run `python -m ingest.seed schema`)")
    except Exception as exc:
        print(f"database: FAILED - {exc}")
        print("  -> is the container running? `docker compose up -d` then `docker compose ps`")
        ok = False

    if not skip_model and ok:
        from compliance_agent.models import chat, embeddings, resolved_model_ids

        print("model slots:", resolved_model_ids())
        try:
            r = chat("cheap").invoke("Reply with the single word OK.")
            print(f"chat('cheap'): {r.content!r}")
        except Exception as exc:
            print(f"chat('cheap'): FAILED - {exc}")
            print("  -> check the model id in config/models.yaml with `python scripts/list_models.py`")
            ok = False
        try:
            v = embeddings().embed_query("automated decision-making")
            print(f"embeddings: ok ({len(v)} dims)")
        except Exception as exc:
            print(f"embeddings: FAILED - {exc}")
            ok = False

    # LangSmith is optional: report, never fail on it
    if config.langsmith_enabled():
        project = config.env("LANGSMITH_PROJECT", "default")
        key = config.env("LANGSMITH_API_KEY") or ""
        endpoint = config.env("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com (default)"
        print(f"langsmith: key {key[:8] + '...' + key[-4:] if len(key) > 14 else 'MISSING or malformed'} · endpoint {endpoint} · project '{project}'")
        try:
            from langsmith import Client

            c = Client()
            c.read_project(project_name=project) if project else None
            print(f"langsmith: tracing ON · project '{project}' reachable")
        except Exception as exc:
            msg = str(exc)
            if "not found" in msg.lower() or "404" in msg:
                print(f"langsmith: tracing ON · project '{project}' will be created on the first run")
            else:
                print(f"langsmith: tracing ON but the API refused or is unreachable - {msg[:120]}")
                print("  -> 403 Forbidden = the key is not accepted: regenerate it (Settings -> API keys) in the workspace you look at,")
                print("     paste it without quotes or spaces, and if your account is in the EU region also set")
                print("     LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com. The app keeps working; traces are just dropped.")
    else:
        print("langsmith: tracing off (set LANGSMITH_TRACING=true, LANGSMITH_API_KEY and LANGSMITH_PROJECT in .env to enable)")

    print("\nALL GOOD" if ok else "\nSOMETHING IS MISSING - see above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
