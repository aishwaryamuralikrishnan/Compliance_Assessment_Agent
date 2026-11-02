# Containers (to-do item 12), design note

2 Nov 2026. Three choices were put to the author and decided before the build; the files are `Dockerfile.api`,
`web/Dockerfile`, `docker-compose.yml`, `scripts/container_start.py`, the two `.dockerignore` files and one line in
`web/next.config.ts`. TECHNICAL.md has the commands.

## What `docker compose up --build` starts

| container | image | what it does | port |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` (unchanged) | Postgres 16 with the `vector` extension: checkpoints, long-term store, register, the embedded corpus; a named volume | 5432 |
| `api` | `Dockerfile.api`, `python:3.12-slim` | waits for `db`, creates the schema, seeds on first start, serves FastAPI with uvicorn | 8000 |
| `web` | `web/Dockerfile`, `node:22-alpine`, three stages | the Next.js app built once (`output: "standalone"`), served by its own Node server; `/api/*` is proxied to `api` | 3000 |

The same two images deploy to a platform as two web services next to a managed Postgres (item 13).

## The three decisions

**Seeding on first start, not as a separate command.** `scripts/container_start.py` runs the idempotent schema
statements, then looks at two tables: an empty `legal_chunks` triggers `python -m ingest.seed corpus` (download or
cached HTML, chunk, embed through the gateway, a few cents once), an empty `users` triggers `seed users` and
`seed memory` from `SEED_PM_PASSWORD` and `SEED_DPO_PASSWORD`. A filled table is left alone, so a restart never
re-embeds and never overwrites a learned memory. `SEED_ON_START=0` turns the seeding off for a hosted database
seeded by hand. One command is all a reviewer or the hand-over needs; the price is a first start of a few minutes.

**The front end in its own Node container, not static files behind the API.** It is what runs on the author's
machine today (`npm run dev` beside `uvicorn`), so the login cookie and the Server-Sent Events stream behave the
same; on the platform it is simply the second web service. The rewrite target for `/api/*` is read by
`next.config.ts` at build time, so it is a build argument (`API_URL`, default `http://api:8000`); a platform
build passes the API service's URL. `compress: false` stays, for the event stream.

**`pgvector/pgvector:pg16`, pinned.** The official image with the extension inside, the Postgres version the
project already runs on; nothing to install.

## Configuration

Everything secret or local comes from the environment; `docker compose` reads `.env` next to the compose file
(copy `.env.example`): `OPENROUTER_API_KEY` (required, the compose file refuses to start without it),
`SEED_PM_PASSWORD`, `SEED_DPO_PASSWORD`, `SESSION_SECRET`, optionally `OPENROUTER_BASE_URL`, `SEED_ON_START`, the
LangSmith variables (off by default). `DATABASE_URL` is set in the compose file to the `db` container and
overrides the localhost value of `.env`. `.env` itself never enters an image (`.dockerignore`).

Two folders of the project are bind-mounted into `api`: `data/` (the EUR-Lex HTML cache, so a re-seed does not
download again, and so a manual save of the pages works as it does today) and `eval/results/` read-only (the
runs the public evaluation report reads; the hand-written `eval/report/notes.json` and the test data are in the
image). The API runs as an unprivileged user; the health check is `GET /api/healthz`, with a two-minute grace
period for the first-start seeding.

## What is not in this item

OIDC login, the hosted Postgres, the scheduled retention job and the demo notices are deployment (items 13, 27,
28). The container runs the app exactly as `uvicorn api.main:app` does; no code path changed.

## How to test it

```powershell
docker compose up --build          # first time: a few minutes while the corpus is embedded
docker compose logs -f api         # "first start: ..." lines, then "serving the API on port 8000"
# http://localhost:3000  -> login as lena.k / m.weber with the passwords of .env
# http://localhost:8000/docs, http://localhost:3000/evaluation
docker compose down                # keeps the data;  down -v  wipes it and the next start seeds again
```
