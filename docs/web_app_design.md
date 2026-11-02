# Design: the web application (FastAPI + React)

Status: design note, 22 Oct 2026 (to-do item 3). The Streamlit app (`app.py`) is replaced by a FastAPI backend over the run API in `compliance_agent/graph.py` and a React (Next.js) front end. The graph, agents, gate, retrieval, checkpointer, store, memory, export, auth and tests are reused unchanged; `app.py` is the reference for what each page must do. Streamlit stays until the React pages cover the demo run sheet (stages 0 to 9) end to end.

Decisions taken with Aishwarya on 22 Oct: the live graph and the trace keep being interpreted on the server (`viz.TraceTracker`, `trace.TraceBuilder`, both tested), the front end only draws; both halves live in this repository, the backend in `api/` and the front end in `web/` (one repository, one git history, one `docker compose up` for the hand-over); authentication is a JWT session over the seeded accounts, with OIDC designed here and built later.

## 1. Shape

```
Compliance_Assesment_Agent/              this repository
  compliance_agent/                      unchanged (two small additive methods, section 4)
  api/                                   FastAPI, imports compliance_agent, shares config/, tests/, .env
  web/                                   Next.js (App Router, TypeScript), its own package.json; node_modules/ and .next/ git-ignored
```

Two processes in development: `uvicorn api.main:app --reload --port 8000` from the project root and `npm run dev` inside `web/` on port 3000. Next.js proxies `/api/*` to the backend (`rewrites` in `next.config.ts`), so the browser talks to one origin, the session cookie is first-party and there is no CORS. `--reload` watches `compliance_agent/` too, so the "restart Streamlit after a change in the package" rule goes away. One API process (no `--workers`): the run registry of section 3 is in memory, as the compiled graph already is (`get_graph()` is cached per process); the demo and a Render instance are single-process anyway.

The backend is one module per API area, which is what the project review's "split `app.py`" asked for:

```
api/main.py        app factory, lifespan (get_graph() once, schema check), routers, GET /api/healthz
api/deps.py        current_user() from the cookie, require_role(...)
api/auth.py        POST login / logout, GET me; the OIDC hooks (section 6)
api/sessions.py    the JWT cookie (make / read token)
api/runs.py        the run registry, the view builder, GET /api/runs/{id}/events (SSE)
api/threads.py     POST threads, GET thread, resume, feedback
api/reviews.py     queue, memory candidates, decision history, keep as example
api/register.py    list, history, PDF
api/memory.py      the three namespaces
api/meta.py        models per node, graph layout, tracing status
api/schemas.py     the pydantic models of the contract below
```

Added to `requirements.txt`: `fastapi`, `uvicorn[standard]`, `pyjwt` (the SSE stream is a plain `StreamingResponse`, thirty lines, no extra dependency). `streamlit` stays until step 6.

## 2. Runs are owned by the server

In Streamlit the page that pressed the button consumes the generator; if the tab is closed the run goes on but nobody sees it, and the other role's page can only poll the database (`run_in_progress`, the heuristic in `app.py`). The API keeps that from happening by owning every run:

- `POST /api/threads`, `POST /api/threads/{id}/resume` and `POST /api/threads/{id}/feedback` do not stream. Each starts the generator (`run_turn`, `resume_turn`, `send_feedback`) in a worker thread, registers it under a `run_id`, and answers `202 {"run_id", "thread_id"}` at once. The generator is synchronous (psycopg, blocking model calls), so the thread is the right place for it; the compiled graph and the connection pool already serve several threads (two Streamlit sessions do exactly this).
- `GET /api/runs/{run_id}/events` is the Server-Sent Events stream of that run. The registry buffers the run's events in memory; a subscriber that connects late gets the buffer first and then the live tail, and the standard `Last-Event-ID` header resumes a dropped connection without a gap. A reloaded page therefore re-attaches to its running assessment instead of losing it.
- The registry knows which thread has a run executing. `GET /api/threads/{id}` reports it as `running_run_id`, so the product manager's page, which polls while the thread waits for the DPO, does not just learn that the DPO has decided: it subscribes to the DPO's run and shows that run's trace and graph live. Today's "resumed by the DPO" block, which `app.py` reconstructs from the database afterwards, becomes the real trace.
- One run per thread at a time: a second `POST` on a thread with a running run is refused with `409`. Feedback on a paused thread is refused with `409` and the reason from `send_feedback` (the thread is at `interrupt()`), instead of a run that only says "deferred".
- The buffers are per process and are dropped when the process restarts, as a Streamlit session's traces are. A finished run's last view is kept per thread for the life of the process, so `GET /api/threads/{id}` can hand a reloaded page the trace of the last run (`last_view`); after a restart only the thread's values come back, as today.

`run_in_progress` stays, moved out of `app.py` into `api/threads.py` as the fallback for the transition weeks when a decision may be taken in Streamlit and is invisible to the API's registry; once Streamlit is gone it is only a safety net for a process that died mid-run.

## 3. The event stream

The server consumes the graph's events the way `run_live` in `app.py` does: `TraceTracker.observe(event, pricing)` and `TraceBuilder.add(event)` per event, and sends the result, not the raw event. Four message types, each with an `id` (the sequence number, for `Last-Event-ID`) and a JSON body; a comment line `: ping` every 15 s keeps proxies from closing an idle stream (the DPO's decision can sit at the gate for minutes).

```
id: 12
event: view
data: {"seq": 12, "title": "Running assessment…",
       "graph": {"active": "worker", "visited": ["__start__", "validate_input", "route"],
                 "taken": [["__start__", "validate_input"], ["validate_input", "route"], ["route", "worker"]],
                 "paused": false, "pm_paused": false, "resumed": false, "substep": "grade", "substeps_done": ["retrieve"],
                 "rewrote": false, "da_state": null, "gate_state": "allowed", "finished": false},
       "stats": {"step": "worker", "searches": 1, "retrieve_passes": 2, "rewrites": 1, "tool_calls": 1,
                 "tokens_in": 9120, "tokens_out": 340, "cached": 6200, "cost": 0.0041, "elapsed": 12.4, "thread": "3f2a9c1e"},
       "trace": [{"key": "validate_input", "title": "validate_input", "cls": "", "subtitle": "", "items": ["412 chars · no injection · …"], "rows": []},
                 {"key": "search:1", "title": "search_regulation", "cls": "tool", "subtitle": "query=\"credit scoring…\"", "items": [],
                  "rows": [{"label": "retrieve 1", "detail": "2 weak hits · grade: insufficient · certainty 0.31", "attempt": 1, "tip": "…"}]}]}

event: interrupt      data: {"kind": "dpo" | "pm", "value": <the interrupt payload: dpo_review or pm_revision>}
event: final          data: {"thread": <GET /api/threads/{id} body>, "run_id": "…", "title": "Assessment ready · waiting for DPO approval (paused)"}
event: error          data: {"message": "…"}     (the generator raised; the run is closed; the thread's state is whatever the checkpointer holds)
```

- `view` is sent after every event that changes the picture (what `builder.add()` returning True and the tracker's node changes mean today), with the whole view each time: the trace of a full assessment is a few kilobytes, and sending the whole view keeps the client stateless (a late subscriber needs only the last `view`). Deltas can come later if a trace ever grows large.
- `graph` is the tracker's fields; the client draws the SVG from the layout (section 4) and these fields exactly as `viz.to_svg` does. `stats` are the ten tiles of the run-stats strip as values. `trace` is the builder's `Section` list; `items` and `detail` are HTML snippets as the builder produces them (escaped on the server with `trace.esc`, with the small `<span class="ok|warn|bad">` and `<pre class="small">` markup), rendered by the client as HTML, with the same CSS.
- `title` is the trace heading `run_live` computes ("Running assessment…", "Running revision…", then "Assessment ready · waiting for DPO approval (paused)", "Changes requested · waiting for the product manager's revision (paused)", "Run complete"); the server computes it from `pending_kind` as today.
- A resumed run (a decision, a revision) starts its tracker with `resumed=True` as today, so START, validate_input and route stay grey and the path continues out of the pause.

## 4. What changes in `compliance_agent/`

Two additive methods, no behavioural change, both covered by one test each:

- `viz.TraceTracker.snapshot() -> dict`: the fields above (sets and tuples as lists). `to_svg` stays for Streamlit until step 6 and for `scripts/`.
- `trace.TraceBuilder.sections_json() -> list[dict]`: the `Section` and `Row` dataclasses as dicts. `sections_html` stays.
- `viz.NODES`, `SUBSTEPS`, `SUBSTEP_EDGES`, `SUBSTEP_LABELS`, `DA_SUBSTEP`, `EDGES` are served as JSON by `GET /api/meta/graph-layout`, so the layout has one source and `test_live_graph_layout_matches_compiled_graph` keeps guarding it. The React component reads the layout once and draws it (section 7).

`run_in_progress` and `assessment_markdown` leave `app.py` (the first to `api/threads.py`, the second to `export.py` as `assessment_markdown(a)`, served as a download). Everything else in the package, `config/`, `scripts/`, `ingest/`, `tests/` and the Postgres service in `docker-compose.yml` is untouched. Identity still enters the graph only through `config["configurable"]` via `run_config(user, thread_id)`; the API builds the `UserContext` from the session cookie and passes it to `run_turn` / `resume_turn` / `send_feedback`, nothing else.

## 5. The API contract

All paths under `/api`; JSON in and out; errors as `{"detail": "…"}` with 400 (bad payload), 401 (no session), 403 (wrong role or not the requester), 404, 409 (run in progress, paused thread). Role checks use `auth.can_approve`, `auth.is_allowed` and the thread's requester, in the API as the first line and in the graph as the second (the gate and `pm_revision` re-check, as today).

| Method, path | Who | Request | Response |
|---|---|---|---|
| `POST /auth/login` | anyone | `{username, password}` | `200 {user_id, role, display_name}` + the session cookie; `401` otherwise |
| `POST /auth/logout` | session | | `204`, cookie cleared |
| `GET /auth/me` | session | | `{user_id, role, display_name}` |
| `POST /threads` | product manager | `{message, thread_id?}` (a new id when absent, `graph.new_thread_id()`) | `202 {run_id, thread_id}` |
| `GET /threads/{id}` | session | | the thread body below |
| `POST /threads/{id}/resume` | DPO for a `dpo` pause, the requester for a `pm` pause | the `resume_turn` payload: `{decision, comment, assessment?, memory_items}` or `{description, responses}` | `202 {run_id, thread_id}`; `409` if nothing is pending or a run is executing; `403` for the wrong person |
| `POST /threads/{id}/feedback` | session | `{comment?, keep_example?, run_id?}` | `202 {run_id}`; `409` while the thread is paused (reason from `send_feedback`) |
| `GET /runs/{id}/events` | session | header `Last-Event-ID?` | `text/event-stream`, section 3; `404` for an unknown run |
| `GET /reviews` | DPO | | `{pending: [task + title…], decided: [...]}` (`repo.pending_reviews`, `repo.decided_reviews(20)`) |
| `GET /reviews/{task_id}` | DPO | | the task, its assessment (`repo.get_assessment`), and for a revision the previous version and the DPO's requested changes (`repo.assessment_history`), i.e. what `review_form` looks up |
| `POST /reviews/{task_id}/memory-candidates` | DPO | `{amended?, comment}` | `{amendments, note, on_changes, on_reject}`, each a list of `{item, label, allowed}` from `memory.propose_from_decision`; the client composes them per decision as `memory_checkboxes` does (the decision itself goes through `POST /threads/{id}/resume`) |
| `GET /assessments/{id}` | session | | `repo.get_assessment` (status, assessment, created_by, revises) |
| `GET /assessments/{id}.md` | session | | the Markdown download |
| `GET /register` | session | | `repo.list_register()` rows; `history` per entry that revises (`repo.assessment_history`) |
| `GET /register.pdf` | DPO (`is_allowed(role, "export_register")`) | | `application/pdf`, `export.register_pdf(rows, generated_by=user)` |
| `GET /memory` | session | | the three sections of the Memory page with the labels and visibility text, `memory.list_namespace` per namespace, `allowed_types(role)` |
| `GET /meta` | session | | `{models: node_models(), model_ids: resolved_model_ids(), pricing: pricing(), langsmith: {enabled, project}}` |
| `GET /meta/graph-layout` | session | | the layout constants of `viz.py` |
| `GET /healthz` | anyone | | `{ok, db}` |

The thread body (`GET /threads/{id}` and `final`):

```
{"thread_id": "…",
 "pending": {"kind": "dpo" | "pm" | null, "value": {…}},        pending_kind(state), state["pending_interrupt"]
 "running_run_id": "…" | null,                                  the registry (section 2)
 "run_in_progress": false,                                      the database fallback
 "status_text": "Sent to the DPO; waiting for the decision.",   STATUS_TEXT of app.py from the assessment row
 "review_task": {id, status, resolved_by, dpo_comment, …} | null,
 "values": {input, validation, route, assessment, answer, sources, guardrail, decision, revision, feedback},
 "last_view": {…} | null,                                      the last `view` of the last run in this process
 "views": [{run_id, kind, user_id, done, error, view}, …]}      every run of this process on the thread, in order: the page draws the union of their paths and stacks their traces
```

`values` is `thread_state(...)["values"]` without `messages` (LangChain objects, the whole history; nothing on a page shows them) and without `structured_response` (already dropped by `thread_state`).

## 6. Authentication

- `POST /auth/login` calls `auth.verify_login` (bcrypt, the `users` table, the two seeded accounts) and sets `session`: a JWT (HS256, `SESSION_SECRET` from the environment, 8 h) with `sub` = username, `role`, `name`; cookie `HttpOnly`, `SameSite=Lax`, `Secure` outside development. The front end never sees the token; `EventSource` sends the cookie by itself, which is why the stream is a `GET` on a separate URL rather than the body of the `POST`.
- `deps.current_user()` decodes the cookie into `UserContext(user_id, role, display_name)` and is the only place identity is read; `deps.require_role("dpo")` wraps the DPO-only routes. The role comes from the token, which was built from the `users` table, never from the request.
- OIDC later, without touching the pages: `GET /auth/oidc/start` (Authorization Code with PKCE, `authlib`) and `GET /auth/oidc/callback`, which maps the provider's `sub` or verified e-mail to a row of the `users` table (new columns `oidc_subject`, `email`) and issues the same cookie. The role stays in our table, not in the provider's claims: an identity the table does not know is refused, so the DPO cannot appear by signing up. The register's `approved_by`, the review task's `resolved_by` and memory authorship keep `user_id` = username as the key.

## 7. The front end (`web/`)

Next.js, App Router, TypeScript, plain CSS (`app/globals.css`), every page a client component behind `/login`. The first cut reproduced the Streamlit look; on 22 Oct Aishwarya chose a fresh design instead, approved on the canvas "Compliance Assistant redesign" (Claude artifact): a navy icon rail, a top bar whose right end always says what the agent is doing, the result as the hero (a verdict card), and the agent's work one click away in a "Behind the scenes" panel (Graph / Trace / Stats, plus Previous on the review page for a v2) that opens by itself while a run streams and folds to a status strip when the result is there; while it works, a horizontal progress stepper stands in for the graph. Theme E "Frost": light blue-grey ground `#EAF0F8`, white cards, rail `#1B2A4A`, accent `#1D6FE0`, status colours deep red / amber / green on pale tints (chosen over the dark options because dark UIs band in GIFs, wash out on projectors and read as black rectangles in a LinkedIn feed). Inter for the UI, JetBrains Mono for the agent's voice (trace, ids, citations); tool blocks in the trace sit on a light grey so they stand apart from node lines.

Routes and what each reproduces from `app.py`:

- `/login`: the form, the seeded-accounts note; a DPO lands on `/review`, a product manager on `/assistant` (separation of duties: no Assistant page for the DPO).
- Layout for every page: the live graph pinned on the left with its legend; the sidebar with the user, the pages for the role, *Models per node* and the tracing line from `GET /meta`, *Log out*; the run-stats strip and the page content on the right.
- `/assistant` (product manager): the request box (first screen), the progress card while the agent works, then the verdict card or the short answer; *New conversation*, one request per conversation; the request, the trace, the assessment card or the short answer with its sources; the status line and *Download (Markdown)*; the waiting banner while the thread is pending for the DPO; the revision mode when the thread is paused for this user (`pending.kind == "pm"` and `value.requester` = me): the DPO's requests with done / not possible and a note each, the box pre-filled with the previous description, the error line from `value.error`, *Run revision* → `resume`; "only the requester can" when it is someone else's; the preference note once the thread has completed (→ `feedback`). The current `thread_id` lives in `sessionStorage` per tab, so two tabs are two conversations as in Streamlit, and a reload restores the thread from `GET /threads/{id}`.
- `/review` (DPO): the pending list, the restored thread banner, the editable assessment (severity and wording per finding), the previous version and the requested changes for a v2, the comment box, the memory checkboxes (re-fetched from `memory-candidates` when the comment or an amendment changes, debounced), the three buttons with the "needs a reason" warnings; the decision → `resume`, the resumed run live on the left and in the trace; "Decisions in this session" with the outcome line, *Keep as a good example* (→ `feedback` with `keep_example`) and the assessment as recorded; the decision history.
- `/register`: the table, the explanatory captions, *Export register (PDF)* for the DPO, each entry's full assessment and, for a revision, its history.
- `/memory`: the three sections with provenance, seeded grey and learned blue.

Components: `LiveGraph` (draws `GET /meta/graph-layout` as SVG and applies the `graph` fields of a view: node classes active / visited / paused / pseudo, edges taken, substeps on / done, `da_state`, `gate_state`, the same rules as `viz.to_svg`), `RunStats`, `TracePanel` (sections as HTML), `AssessmentCard` (read-only and editable), `ChangesSinceV1`, `ReviewForm`, `MemoryCandidates`, `RevisionForm`, `RegisterTable`, `History`, `MemoryList`, `Banner`. One hook, `useRun(runId)`, wraps `EventSource` and exposes the latest view, the interrupt, the final body and the error; a second, `useThread(threadId)`, holds the thread body, polls it every 4 s while `pending.kind == "dpo"` or `run_in_progress`, and switches to `useRun(running_run_id)` the moment a run appears, which is what makes the DPO's decision play live in the product manager's window. The five-minute "the DPO's run did not finish" warning stays in `useThread`.

Not built, deliberately: a list of earlier conversations (Streamlit has none; the thread id in the tab is the same scope), editing in the register, any model switch, a DPO Assistant page.

## 8. Tests

`tests/test_api.py`, with FastAPI's `TestClient` on the scratch database and the existing `graph_with_scripted_worker` fixture (moved from `test_graph.py` into `conftest.py` so both files share it): the app factory takes the graph (`create_app(graph=...)`) so the tests inject the scripted one, as `run_turn(..., graph=...)` does today. The flows mirror `test_graph.py` through HTTP: login as the product manager → `POST /threads` → read the stream to `interrupt` (`dpo`) → login as the DPO → `GET /reviews` → `memory-candidates` → `resume` with approve → `final` with the register entry; request changes → the product manager's `resume` with a revised description → v2 pending for the DPO; the refusals (a product manager on `GET /reviews` and `register.pdf`, the DPO on `POST /threads`, another user resuming a `pm` pause, a second run on a running thread, feedback on a paused thread: 403 / 409); a late subscriber with `Last-Event-ID` gets the rest without a gap; `register.pdf` is a PDF; `graph-layout` equals the constants in `viz.py`. These are the API tests item 4 asks for and replace the Streamlit smokes; `pytest --cov` comes with item 4.

## 9. Build order, each step testable by Aishwarya

1. ~~**API skeleton and read side**~~ done 22 Oct (half a day): `api/` with lifespan, auth, `GET /threads/{id}`, `/reviews`, `/register`, `/register.pdf`, `/memory`, `/meta`, the two serialisers in `viz.py` / `trace.py`. Test: `uvicorn api.main:app --reload`, log in from FastAPI's `/docs` page, read a thread run in Streamlit, download the PDF. Streamlit untouched.
2. ~~**Runs and the stream**~~ done 22 Oct (half a day): the registry, `POST /threads`, `resume`, `feedback`, `GET /runs/{id}/events`. Test: start an assessment from `/docs`, watch `curl -N http://localhost:8000/api/runs/<id>/events` print the views, decide in Streamlit's review queue, see the decision's run appear in the thread body.
3. ~~**Front end, product manager**~~ done 22 Oct (one day): the `web/` scaffold (`create-next-app`, `.gitignore` entries for `node_modules/` and `.next/`), login, layout, `LiveGraph`, `RunStats`, `TracePanel`, the Assistant page through a full assessment to the DPO pause. Test: run sheet stages 0 to 3 with the DPO still in Streamlit.
4. ~~**Front end, DPO**~~ done 22 Oct (one day): the review queue with amendments, memory checkboxes and the three decisions; Lena's window following the DPO's run. Test: stages 4 and 5, both windows on React.
5. ~~**The rest of the demo**~~ done 22 Oct, on the redesigned pages (one day): register, memory, PDF, preference note, keep as example, the revision loop. Test: stages 6 to 8c; the full rehearsal of to-do item 20 on React.
6. ~~**Close**~~ done 23 Oct, after the full rehearsal on React: `tests/test_api.py`; UI.md rewritten for the React app with new screenshots (`docs/images/web_*.png`), TECHNICAL.md, README section 5, `roles.yaml` (the `ui` kind: the API endpoint checks the role), the run sheet; `app.py` moved to `_to_delete/`, `streamlit` dropped from `requirements.txt`, the Streamlit-only renderers (`viz.to_svg`, `trace.sections_html`, both CSS blocks) removed, so `viz.py` and `trace.py` produce JSON only.

About four and a half days. Containers for the two processes and the deployment are to-do items 12 and 13 and come after the evaluation.

## 10. Open points, not blocking

- Deltas instead of full views if a trace ever grows beyond a few tens of kilobytes (not in the demo's traces).
- A per-account usage cap for the public demo (to-do 13): the registry is the natural place to count runs per user per day.
- Persisting the last view per thread in Postgres so a trace survives a restart; not needed for the demo, where a restart is a reset anyway.
