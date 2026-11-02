"""Start the API inside its container: wait for Postgres, create the schema, seed on first start, serve.

    python scripts/container_start.py            # what the api image runs (Dockerfile.api)

First start: when `legal_chunks` is empty the corpus is downloaded, chunked and embedded (one-off embedding
calls, a few cents on the gateway; the EUR-Lex HTML is cached under data/corpus/raw, a bind mount in
docker-compose.yml); when `users` is empty the two demo accounts and the seeded memory are created from
SEED_PM_PASSWORD and SEED_DPO_PASSWORD.  Every later start finds both tables filled and only runs the schema
statements (idempotent) before serving.  SEED_ON_START=0 skips the seeding entirely (a hosted database seeded
by hand).  The schema check also refuses to serve against a corpus embedded with other dimensions than
config/models.yaml names, the same guard `python -m ingest.seed schema` applies.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from compliance_agent import config, db  # noqa: E402
from ingest import seed  # noqa: E402


def wait_for_db(timeout_s: int = 90) -> None:
    deadline = time.time() + timeout_s
    url = config.database_url()
    while True:
        try:
            with psycopg.connect(url, connect_timeout=3):
                return
        except Exception as exc:  # noqa: BLE001  -- the database is still starting
            if time.time() > deadline:
                sys.exit(f"database not reachable after {timeout_s}s: {exc}")
            print("waiting for the database ...", flush=True)
            time.sleep(2)


def _count(table: str) -> int:
    with db.connect_plain() as conn:
        row = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()   # table names are our own constants; rows are dicts
        return int(row["n"]) if row else 0


def seed_if_empty() -> None:
    if os.environ.get("SEED_ON_START", "1") in ("0", "false", "no"):
        print("SEED_ON_START=0: schema only, no seeding", flush=True)
        return
    if _count("legal_chunks") == 0:
        if not config.env("OPENROUTER_API_KEY"):
            print("corpus is empty and OPENROUTER_API_KEY is not set: the corpus cannot be embedded; set the key and restart", flush=True)
        else:
            print("first start: downloading, chunking and embedding the corpus (one-off)", flush=True)
            seed.main(["corpus"])
    else:
        print(f"corpus present: {_count('legal_chunks')} chunks", flush=True)
    if _count("users") == 0:
        if config.env("SEED_PM_PASSWORD") and config.env("SEED_DPO_PASSWORD"):
            print("first start: creating the two demo accounts and the seeded memory", flush=True)
            seed.main(["users"])
            seed.main(["memory"])
        else:
            print("no users yet and SEED_PM_PASSWORD / SEED_DPO_PASSWORD are not set: nobody can log in until they are", flush=True)
    else:
        print(f"users present: {_count('users')}", flush=True)


def main() -> None:
    wait_for_db()
    seed.main(["schema"])          # idempotent; exits if the corpus was embedded with other dimensions
    seed_if_empty()
    port = os.environ.get("PORT", "8000")
    print(f"serving the API on port {port}", flush=True)
    os.execvp("uvicorn", ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", port, "--proxy-headers", "--forwarded-allow-ips", "*"])


if __name__ == "__main__":
    main()
