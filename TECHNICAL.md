# Technical notes

Python 3.12 · FastAPI + React (Next.js) · LangGraph + LangChain 1.x · OpenRouter (one key, any vendor) · Postgres 16 + pgvector in Docker (checkpointer, long-term store, RAG corpus).

## Project layout

```
api/                        the web API (FastAPI) over graph.py: auth (JWT cookie), oidc (sign in with Google), threads, reviews, register, memory, meta, evaluation (the public report); docs/web_app_design.md
web/                        the React (Next.js) front end: login, assistant, review queue, register, memory; the public /evaluation pages; lib/ (API client, hooks), components/ (EvalReport + EvalCharts: the report's sections and inline SVG figures)
compliance_agent/           the agent package (knows nothing of the UI)
  config.py                 env + YAML loading (OPENROUTER_API_KEY from the environment)
  models.py                 model registry: slot -> init_chat_model via OpenRouter
  db.py                     psycopg pool + schema (legal_chunks, users, assessments, review_tasks, register)
  memory.py                 Store namespaces, candidate proposals, reflect, role-gated writes
  auth.py                   bcrypt login, roles.yaml permission helpers
  repo.py                   assessments, review tasks, register data access
  export.py                 PDF export of the register (reportlab), assessment as Markdown
  retention.py              checkpoint retention: prune the saved state of finished threads (admin.py prune-threads)
  state.py                  GraphState, Assessment / Finding / StatusReply, UserContext
  graph.py                  StateGraph wiring, run_turn / resume_turn / send_feedback / thread_state
  tracing.py                LangSmith tagging (no-op while tracing is off)
  viz.py, trace.py          live-graph layout + tracker and the trace sections, both served as JSON by the API
  retrieval/                identifiers, hybrid search + RRF, reranker, grader, rewrite, loop
  tools/                    search_regulation, get_article, lookup_register, request_dpo_review
  nodes/                    validate_input, route, direct_answer, worker + reviser (+ middleware), guardrail, memory_write, pm_revision
ingest/                     EUR-Lex download / manual-save adoption, legal-structure chunker, seed script
config/                     models.yaml (slots + prices), roles.yaml (permissions, memory policy), corpus.yaml
scripts/                    check_env, list_models, probe_models, probe_slot, probe_grader, probe_provider (the gateway's data policy per call), search, chat, admin, draw_graph (the compiled graph as Mermaid), expert_round2 (the reviewer's pack), eval_pdf (the Evaluation page as PDF), container_start (what the api container runs)
eval/                       the evaluation harness (eval/README.md): data/ golden sets, harness/ runners + report.py, prompts/ judge, report/ notes.json + evaluation.pdf, results/ (not versioned)
tests/                      pytest; graph flows run on a scratch database with a canned corpus
docker-compose.yml          three containers: db (pgvector/pgvector:pg16 on a named volume), api (Dockerfile.api), web (web/Dockerfile); docs/containers_design.md
```

## Setup (once)

```powershell
python -m pip install -r requirements.txt
copy .env.example .env            # DB defaults are fine; keep OPENROUTER_API_KEY in the OS environment
```

## Start the database

Docker Desktop must be running.

```powershell
docker compose up -d db
docker compose ps                 # wait until compliance_db is "healthy"
```

(`docker compose up -d` without `db` also builds and starts the API and the front end as containers; see *Run everything in containers* below.)

## Check the environment (smoke test)

```powershell
python scripts/check_env.py       # key, Postgres + pgvector, corpus counts, one model call, one embedding
```

First time only: `python -m ingest.seed all` (schema, corpus from `data/corpus/raw/`, users, seeded memory). EUR-Lex pages must be saved manually from a browser under the names printed by `python -m ingest.seed urls`.

## Run

```powershell
uvicorn api.main:app --reload --port 8000       # the web API, http://localhost:8000/docs (docs/web_app_design.md)
cd web; npm install; npm run dev               # the React front end, http://localhost:3000 (Node.js 20+; proxies /api to :8000)
```

Accounts: `lena.k` (product manager), `m.weber` (DPO); passwords from `.env`. **Sign in with Google** (`api/oidc.py`, OpenID Connect with PKCE) appears on the login page when `OIDC_CLIENT_ID` is set: a first sign-in creates a product manager from the verified e-mail address, the addresses in `DPO_EMAILS` sign in as DPO, and `OIDC_DEFAULT_ROLE=deny` admits only accounts the table already knows; the role is decided by the `users` table at every sign-in, never by the provider. The callback runs through the front end's `/api` proxy so the session cookie stays first-party; the redirect URI to register is `PUBLIC_BASE_URL` + `/api/auth/oidc/callback` (`docs/deployment_design.md`).

## Run everything in containers

The alternative to the two commands above, for a hand-over or a reviewer: the API and the front end as containers next to the database (`docs/containers_design.md`).

```powershell
docker compose up --build         # first time: a few minutes while the corpus is downloaded, chunked and embedded
docker compose logs -f api        # "first start: ...", then "serving the API on port 8000"
```

Then http://localhost:3000 (the app), http://localhost:8000/docs (the API), http://localhost:3000/evaluation (the report, reading `eval/results/` from the project folder). The `api` container waits for the database, runs the schema statements and seeds on first start (`scripts/container_start.py`): an empty corpus table is filled through the gateway (`OPENROUTER_API_KEY` must be in `.env` or the environment; the EUR-Lex pages come from `data/corpus/raw/`, bind-mounted, or are downloaded), an empty users table gets the two accounts from `SEED_PM_PASSWORD` / `SEED_DPO_PASSWORD` and the seeded memory. A restart never re-embeds or overwrites memory; `SEED_ON_START=0` skips seeding altogether. The front end image bakes in the address it proxies `/api/*` to (build argument `API_URL`, default `http://api:8000`). `docker compose down -v` wipes the database and the next start seeds again.

## Models

Every node asks the model registry for a *slot*; `config/models.yaml` maps each slot to an OpenRouter model id, a display name and a price. Changing a model is one line there, no code change; the README's node table and the app's sidebar (*Models per node*) read the names from this file.

| Graph node | Model type | Model | Slot in `config/models.yaml` |
|---|---|---|---|
| validate_input | small LLM (injection / topic classifier, structured output) + regex | Gemini 3.1 Flash Lite | `cheap` |
| route | classifier (returns a tier and a confidence); LLM fallback on `cheap` | TypeSafe Jev Router | `router` |
| direct_answer | heavy LLM (quick answer, one retrieval pass) | GPT-6 Luna | `worker_quick` |
| direct_answer · retrieval | embeddings + cross-encoder reranker | Text Embedding 3 Small, Rerank 4 Fast | `embeddings`, `reranker` |
| worker | heavy LLM (plans, calls tools, drafts the assessment) | GPT-6 Luna | `worker_full` |
| reviser | heavy LLM (v2 after the DPO requested changes; same tools and gate) | GPT-6 Luna | `worker_full` |
| pm_revision | none (pause for the product manager; deterministic screen of the revised description) | - | - |
| worker · search_regulation | embeddings + reranker; an LLM grades the passages (structured output); a small LLM rewrites the query after a miss | Text Embedding 3 Small, Rerank 4 Fast, GPT-6 Luna (grader), Gemini 3.1 Flash Lite (rewrite) | `embeddings`, `reranker`, `grader`, `cheap` |
| worker · summariser | small LLM (long threads only) | Gemini 3.1 Flash Lite | `cheap` |
| tool_gate, interrupt | none (deterministic) | – | – |
| output_guardrail | none (deterministic checks; a regeneration goes back to the worker) | – | – |
| memory_write · reflect | small LLM (rephrases free text into one reusable sentence) | Gemini 3.1 Flash Lite | `cheap` |
| *(evaluation only)* judge | small LLM from a third vendor, scores outputs against the rubric | Claude Haiku 5.5 | `judge` |

Setting of 23 Oct 2026 (development; the showcase lines for Mistral Large 4 are kept as comments in `config/models.yaml`): GPT-6 Luna ($0.10 / $0.50 per 1M tokens, cached input $0.01) in the two worker slots and as the retrieval grader, Gemini 3.1 Flash Lite ($0.25 / $1.50) for the small helper calls (input screen, query rewrite, summariser, reflect), and Claude Haiku 5.5 as the evaluation judge, from a third vendor so that no model scores its own family's output. A full assessment on this setting costs a few cents (the $0.18 figure in EVALUATION.md was measured on Mistral Large 4, 22 Oct; the run-stats estimate covers the worker's calls only, see UI.md). Alternatives for the workers are noted in `config/models.yaml` (DeepSeek V4.1 Flash cheaper; GPT-6 Sol and Claude Sonnet 5.5 at the frontier tier); `python scripts/list_models.py <word>` lists the ids your key can use. The embeddings slot must not change after the corpus is indexed (re-index with `python -m ingest.seed reindex` if it does).

**The grader is a slot of its own, and it may be the worker's model.** Grading is a small reasoning job: the grader must name the provision the retrieved passages lack, so that the rewrite can go to it, and `python scripts/probe_grader.py` (ten queries, six in plain English) showed that the cheapest models cannot do that: Gemini 3.1 Flash Lite asked for judgements the law does not state and left three of the six unresolved, GPT-5.4 mini resolved three at eight times Luna's price, GPT-6 Luna named the article every time and resolved five; the figures are in `config/models.yaml`. A grader that is the worker's own model would be a problem if it judged the worker's text; this grader doesn't. It judges passages that come from the database through the embeddings and the reranker, against a ten-word query, and it never sees an assessment. The independence that matters in this project is the evaluation judge's, which is why Claude Haiku stays out of the app. The slot can still be pointed at any other model with one config line; the probe is the way to compare candidates.

## Tests

```powershell
pytest tests -q                                                  # 75 tests, about 2 min (bcrypt and the Postgres round trips)
pytest tests -q --cov=compliance_agent --cov=api --cov-report=term-missing    # with line coverage (pytest-cov, requirements-eval.txt)
```

Writing tests run on a scratch database (`compliance_test`, created automatically next to the real one), so the register and memory are never touched by a test run. No test calls a model or the gateway: the worker and the reviser run a scripted model, retrieval, corpus and the input screens are canned (`tests/fakes.py`), and the unit tests of the retrieval loop, the grader, the rewrite, the reranker, the router, the input screen and the memory proposals replace the model call with a stub that answers what the test needs.

Line coverage on 23 Oct 2026: **92 %** of `compliance_agent/` and `api/` (3,178 statements, 257 missed) on a machine with the seeded corpus, 89 % without it (the three database tests of `tests/test_retrieval.py` then skip), up from 82 % with the 41 tests before to-do item 4. What the tests cover, by file: `tests/test_graph.py` the graph's flows (reject, full assessment through the DPO's three decisions, the revision loop, the guardrail's rules, retention, tracing tags, the live-graph layout); `tests/test_api.py` the web API through HTTP including the event stream and its replay; `tests/test_api_edges.py` its refusals and error reports (busy or paused thread, a run that raises, a view the stream cannot serialise, forged and expired cookies); `tests/test_oidc.py` the Google sign-in with the provider stubbed (first sign-in, the DPO allowlist, refusals, invitation-only mode); `tests/test_quick_path.py` the quick path (a question routed `quick`, the empty answer reported rather than hidden, a preference note on a quick thread); `tests/test_retrieval_loop.py` every branch of the agentic RAG loop and the grader's decision rule; `tests/test_rerank_and_tools.py` the reranker's three paths and the tools' own refusals; `tests/test_screens_and_memory.py` the input screen, the router's fallback order, the memory proposals and the role-gated store write; `tests/test_retrieval.py` identifiers and rank fusion (its database tests need a seeded corpus and are skipped otherwise); `tests/test_chunker.py` and `tests/test_seed_offline.py` the ingestion. The one file still below 80 %: `tracing.py` (74 %: the LangSmith branches, off in the tests); `retrieval/search.py` is at 98 % with the seeded corpus and 47 % without, because the SQL of the hybrid search runs only against it. Coverage measures the code, not the agent's output quality, which is EVALUATION.md.

## Conventions

- **No fallback invents data or hides an error.** When something the agent depends on fails (the corpus lookup behind citation verification, the memory store, the DPO-comment lookup in the PDF export), the code logs the real exception with `logging` and reports the state to the user through the trace or the UI; it never substitutes an empty or made-up result silently. Citation verification therefore has three states (`verified`, `unknown`, `unreachable`), and only `unknown` triggers regeneration or removal. The API prints warnings to the terminal it was started from, and a run that fails ends its event stream with an `error` event the page shows.
- **A condensed thread never loses its request.** The summariser pins the latest request message (feature description or revision brief) in front of the summary verbatim and lets the cheap model see it when writing the summary; see AGENTWORKER.md.
- **Prompt caching is the provider's job.** Mistral caches prompt prefixes implicitly (64-token blocks, cached tokens at 10% of the input rate); the gateway reports cached tokens and the run-stats strip shows and prices them (`cached_input` in `config/models.yaml`). Nothing is sent to enable it, so a provider without caching simply reports zero.
- **The message history sent to a model is always balanced.** Mistral (and other strict providers) reject a request unless every assistant tool call is answered by exactly one tool message, in order. Two places guarantee that: a model output that cannot be used (a tool call whose JSON is malformed or cut off at `max_tokens`) is answered at once with an error tool message by `RoleToolsMiddleware`, and the trace shows *model output unusable*; and before every model call `repair_tool_pairs` checks the history it is about to send (unanswered calls, orphan tool messages, repeated ids) and reports any repair in the trace. If a provider still rejects a request, the trace and the log show the shape of the history that was sent (role, tool call ids, answered ids), which is enough to see why.

## Register, memory and thread clean-up

`scripts/admin.py` lists and prunes what testing leaves behind; every delete asks for confirmation (`--yes` skips it).

```powershell
python scripts/admin.py register                 # list
python scripts/admin.py register --dedupe        # keep the newest entry per title
python scripts/admin.py memory                   # list every item with key, source, author
python scripts/admin.py memory --clear-learned   # back to the seeded memory
python scripts/admin.py reset                    # fresh demo state: no assessments, tasks, register entries,
                                                 # threads or learned memory; corpus, users, seeded memory stay
python scripts/admin.py prune-threads --days 30  # checkpoint retention: remove the saved state of finished
                                                 # conversations with no activity for 30 days (--dry-run lists only)
```

Restart the API after a `reset` (the run registry and the compiled graph live in the process).

**Checkpoint retention.** The checkpointer saves the whole graph state after every node of every thread (that is what makes interrupt and resume work), so it grows without bound. `prune-threads` deletes the checkpoints of threads that are *finished* and older than the cut-off, and nothing else: assessments, review tasks, the register and long-term memory are records and stay. A thread is kept whatever its age while anything is open on it: paused at an interrupt (waiting for the DPO or for the product manager), nodes still scheduled (a run that stopped half-way), a pending review task, or a latest assessment waiting for changes; a thread whose state cannot be read is kept and reported rather than deleted on a guess. A pruned thread's conversation page is gone, its register entry and decision history are not. Run it from a scheduled task once the app is hosted (`compliance_agent/retention.py` is the module behind the command).

## Stop

```powershell
docker compose down               # stops the containers, keeps the data
docker compose down -v            # also wipes the data (the next start seeds again)
```
