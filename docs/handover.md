# Handover brief — Compliance Assistant (22 Oct 2026)

For a new Claude thread that continues this project: first the UI migration (to-do item 3), then the evaluation (section B). Everything below is what the previous thread knew that is not obvious from the code. Read this, then `docs/todo.md`, then the document for the piece of work at hand (README.md, TECHNICAL.md, UI.md, TOOLS.md, AGENTWORKER.md, EVALUATION.md, `docs/revision_design_v2.md`).

## 1. The project in one paragraph

A Streamlit + LangGraph app for an EU company: a product manager (`lena.k`) describes a planned feature in plain words; the worker agent searches the GDPR and the EU AI Act (agentic RAG over Postgres/pgvector), drafts a structured assessment (verdict, findings tagged Blocker / Required / Covered with verified citations, next steps, DPIA and high-risk-AI flags); the output guardrail verifies every citation against the corpus and sends the draft back once if needed; the thread then pauses (`interrupt()` inside the tool gate) until the Data Protection Officer (`m.weber`) approves, requests changes or rejects. Approval writes the processing register (the goal); *request changes* pauses the same run a second time for the product manager, whose revision runs a second agent, the reviser, producing v2 linked to v1. Long-term memory (org facts, DPO lessons, per-user preferences) is role-gated and read by every assessment. Course: Turing College capstone (Sprint 3 brief in `135.md`, architecture document of 7 Oct in `compliance_assistant_project_summary.pdf`). Owner: Aishwarya Muralikrishnan.

## 2. Stack and layout

Python 3.12 (global interpreter, **no virtual environments**), Streamlit, LangGraph + LangChain 1.x (`create_agent` with middleware), Postgres 16 + pgvector in Docker (`docker-compose.yml`), models through OpenRouter with one key (`OPENROUTER_API_KEY` **from the environment only**, never in files), reportlab for the PDF export. Windows machine, VS Code, project at `C:\Users\aishv\Compliance_Assesment_Agent`.

```
app.py                     Streamlit UI (login, assistant, review queue, register, memory) — the part the migration replaces
compliance_agent/
  graph.py                 the orchestrator and the run API (section 4 below)
  state.py                 GraphState, Assessment / Finding / StatusReply / ChangeNote, UserContext
  nodes/                   validate_input, route, direct_answer, worker (+ reviser, both create_agent), middleware
                           (RoleToolsMiddleware, ToolGateMiddleware, TracedSummarizationMiddleware, ToolBudgetMiddleware,
                           repair_tool_pairs), guardrail, memory_write, pm_revision, reviser (prompt + brief)
  tools/                   search_regulation, get_article, lookup_register, request_dpo_review
  retrieval/               hybrid search (vector + full text + identifiers), RRF, reranker, grader, rewrite, loop
  repo.py db.py auth.py memory.py export.py retention.py models.py config.py viz.py trace.py tracing.py
config/models.yaml         model slots and prices;  config/roles.yaml  permissions and memory policy
scripts/admin.py           register / memory / reset / prune-threads;  scripts/draw_graph.py  compiled graph as Mermaid
tests/                     34 pytest tests on a scratch database (compliance_test) with a scripted model; tests/fakes.py
docs/                      todo.md (the plan), demo_run_sheet.html (the demo, 9 stages), revision_design.md (v1), revision_design_v2.md (built), images/
```

Running and testing (see TECHNICAL.md): `docker compose up -d`, `streamlit run app.py`; tests `pytest tests -q`. Streamlit caches the compiled graph with `st.cache_resource`, so **a change in `compliance_agent/` needs a Streamlit restart**, not just a reload.

## 3. State of play

Built and working in the demo (run sheet: `docs/demo_run_sheet.html`, published artifact "Demo Run Sheet", version 15): everything in section 1, plus three-state citation verification (verified / unknown / unreachable), visible memory failures, the Mistral message-order safety net (`repair_tool_pairs`, unusable-output settlement), the tool budget that ignores the structured-output call, the PDF register export, the live graph with both pauses drawn (pseudo-nodes with dashed borders), checkpoint retention (`prune-threads`), the summariser that pins the request, cached-token accounting in the run stats.

Models (`config/models.yaml`): `worker_full` / `worker_quick` = `mistralai/mistral-large-4-0` ($1.36 / $4.18 per 1M, cached $0.14; the EU endpoint 10% more); `cheap` = `openai/gpt-6-luna`; `judge` = `anthropic/claude-haiku-5.5` (evaluation only, never the app); embeddings `openai/text-embedding-3-small` (never change without re-indexing); reranker `cohere/rerank-4-fast`; router `typesafe/jev-router` with an LLM fallback. A full assessment costs about **$0.18 on the gateway's activity page** (the run-stats estimate sees only the worker's calls). Budget: about $15 of OpenRouter credit in total; a full evaluation run ≈ $4.20 on Mistral, ≈ $0.25 with the small model in the worker slots (debug there, run the real models once).

Decisions already taken (do not reopen): no DPO Assistant page (separation of duties: the DPO never generates what she approves); the review request is automatic after every verified assessment; the register is written only by the gate on approval, no tool writes it; the DPO's three decisions approve / request changes / reject; memory writes gated by role (a PM writes only her own preferences); the router is a classifier, not an LLM; models and tools are fixed by configuration, no user-facing model switch; no LangSmith in the demo (built, off); the revision is a pause for the PM inside the same run (design v2), the PM's second input is screened deterministically (no model), only the requester may resume her thread; a refused revision stays paused (no give-up path); the specialist-agent split, `draft_dpia`, extra corpora and the German corpus are dropped. The retrieval grader is a chat slot of its own on GPT-6 Luna, the worker's model, chosen by measurement (`scripts/probe_grader.py`, 23 Oct): a grader that is the worker's own model would be a problem if it judged the worker's text, but this one judges database passages against a ten-word query and never sees an assessment; the independence that matters is the evaluation judge's (Claude Haiku stays out of the app). Jev as a grader is dropped (a label classifier cannot name a missing provision).

## 4. The run API the backend will wrap (`compliance_agent/graph.py`)

- `UserContext(user_id, role, display_name)` from `auth.verify_login(username, password)` (bcrypt, users table). Identity reaches the graph **only** through `config["configurable"] = {thread_id, user_id, role, run_id}` (`run_config`), never through the prompt.
- `run_turn(user, message, thread_id=None, *, graph=None)` → generator of events, ending with `{"kind": "final", "state": thread_state, "run_id"}`. Events: `{"kind": "custom", "ns": (...), "node": ..., "event": ..., ...}` (progress from `get_stream_writer()`; the trace panel and the live graph are built from these), `{"kind": "update", "ns", "node", "data"}` (node results, incl. messages with `usage_metadata` for the cost), `{"kind": "interrupt", "ns", "value"}`.
- `resume_turn(user, thread_id, payload)` for both pauses: the DPO's `{"decision": "approve"|"request_changes"|"reject", "comment", "assessment" (amended, optional), "memory_items"}`; the PM's `{"description", "responses": [{"status": "done"|"not_possible", "note"}, ...]}`.
- `send_feedback(user, thread_id, comment=None, *, keep_example=False, run_id=None)` on a completed thread only.
- `thread_state(thread_id)` → `{"thread_id", "values", "pending_interrupt", "next"}`; `pending_kind(state)` → `"dpo"` | `"pm"` | `None`. The interrupt payloads: `dpo_review` {task_id, assessment_id, title, requested_by, thread_id, assessment}; `pm_revision` {revises, title, requests, comment, requested_by, requester, previous_description, error}.
- Mid-run detection (a resume still executing in another session): `app.run_in_progress(state)` — no interrupt pending, task decided, decision not yet written (or `changes_requested` and not yet paused). The checkpoint's `next` is empty mid-run and cannot be used for this.
- Data: `repo` (assessments, review tasks, register, history), `memory` (recall, list_namespace, write_items), `export.register_pdf(rows, generated_by=...)`, `models.node_models()` / `resolved_model_ids()` / `pricing()`, `viz` (layout + `TraceTracker` + `to_svg`), `trace.TraceBuilder` (events → HTML sections).
- Everything the Streamlit pages do is a thin use of the above; `app.py` is the reference for the behaviour each React page must reproduce (polling box, revision form, review form with amend / memory checkboxes / three buttons, "Keep as a good example", register history expander, PDF button, models-per-node sidebar).

## 5. Conventions and ways of working

- Aishwarya tests every build step herself in the running app and reports back; build in steps she can test; keep the demo robust; no unnecessary features.
- She edits README.md, UI.md and EVALUATION.md by hand: before changing those, compare checksums with her copy and edit in place rather than overwriting. The previous thread synced files to her machine with md5 verification after every change; a fresh staging path per commit (a reused path once delivered a stale copy).
- Prose documentation, concise; `docs/todo.md` is the plan and is kept current (items ticked with the date). Design notes before building anything with an architectural choice (`docs/revision_design_v2.md` is the model).
- TECHNICAL.md "Conventions" are the engineering rules: no fallback invents data or hides an error; balanced message histories; a condensed thread never loses its request; prompt caching is the provider's job.
- Reviewer comments from the project review (addressed or on the list): hidden failures (done), version history before approval (done as the revision loop), split `app.py` (absorbed by the migration), test coverage (after the migration), OAuth (with the backend), embedding-swap test (dropped with the German corpus).

## 6. The two pieces of work ahead

**UI migration (item 3).** FastAPI backend over section 4 + React (Next.js) front end; design note first (API contract, SSE event format, page list, what is reused). Suggested layout: the backend as `api/` **inside this project** (it imports `compliance_agent` and shares the tests and config), the front end in a separate folder (e.g. `compliance-ui/` next to the project) connected to the thread as a second folder. Authentication: sessions with JWT, OIDC login later. Streamlit stays until the React pages cover the demo run sheet end to end. Dockerfiles and deployment come after the evaluation (to-do sections C and D).

**Evaluation (section B).** The plan is EVALUATION.md (seven sets E1–E7; E6 = 20 feature cases, E5 = 15 quick answers; judge on a third vendor; expert review by Stela, who runs FairAudit and is also working on evals; a call is planned for the week of 27 Oct; she suggested the Hugging Face dataset `nguha/legal-eval`, 9.8k samples across 202 legal tasks, no GDPR / AI Act content, useful as a format reference only). Safeguards for generated cases, grader calibration and LangSmith-on-for-eval are in the to-do (items 5–11). Do not quote the old "$0.06 per assessment": the measured figure is $0.18.

## 7. Known quirks

- Interrupt-and-resume: a resumed run executes under the resumer's identity; the gate's replayed "pause" event carries `resumed_by`. The PM page's polling must keep polling while the DPO's run executes (see `run_in_progress`).
- Mistral rejects unbalanced tool histories (400 "Not the same number of function calls and responses"); the middleware repairs and reports. Mistral occasionally writes the assessment as prose until the 8,192-token output cap; the guardrail sends it back once (costs ~half an assessment).
- The compiled graph can be drawn with `python scripts/draw_graph.py` (Mermaid; PNG needs internet via mermaid.ink). The live-graph layout is pinned to the compiled graph by a test; the tool gate and the two interrupt boxes are pseudo-nodes.
- SVGs written to the machine through the Claude desktop bridge gain a C2PA metadata block; harmless.
- `_to_delete/` in the project and `revision_walkthrough.svg` in "Claude outputs" are leftovers to delete (to-do item 19).

## 8. Addendum, 23 Oct 2026 (end of the day)

State: to-do items 3 and 4 are done. The app is the React front end in `web/` over the FastAPI backend in `api/`; `app.py` and Streamlit are gone (`_to_delete/`), UI.md is rewritten for the web app with screenshots `docs/images/web_*.png` (taken from the scripted model; real captures can overwrite them under the same names), README §5 and TECHNICAL.md follow. Tests: 70, 92 % line coverage with the seeded corpus (89 % without); `pytest.ini` silences one third-party warning. The demo run sheet is at version 18 (two windows, no promised rewrite, the previous version folded above a v2 on the review page). Models: `worker_full` / `worker_quick` = GPT-6 Luna (Mistral Large 4 kept as comments, the showcase setting), `cheap` = Gemini 3.1 Flash Lite, `grader` = a chat slot of its own on GPT-6 Luna, chosen with `scripts/probe_grader.py` (the measurement and the independence argument are in `config/models.yaml` and TECHNICAL.md), `judge` = Claude Haiku 5.5, evaluation only. The worker prompt asks for every data source the description names as its own finding where the law treats it differently. The progress stepper shows a resumed run's own steps.

Next: section B of `docs/todo.md`, rewritten on 23 Oct in the agreed order, starting with item 5 (structure, domains, metrics, report format, the RAGAs dependency check) before any golden content; Stela's round 1 shapes the remaining E6 cases. EVALUATION.md is intentionally left as written; its §1, §7 step 4 and §8 predate the Luna setting and are corrected by hand when the results section is written. After the capstone: items 17, 21 (model and embedding swaps) and 22 (E9, the reviser's judgement).

Ways of working that held today and should continue: the API reads `config/models.yaml` once at start (restart it after a config change; the Model box in the progress card shows what the running process loaded); the scratch database persists across test runs, so a test that stores memory must use unique text; files synced to the project are verified by md5 on both sides, from a fresh staging path each time.
