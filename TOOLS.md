# Tools

Two kinds of model-callable tool: 🟢 **read** (cheap, read-only, bound for every role that lists it) and 🟡 **write** (creates a review task and pauses the graph at `interrupt()` until the DPO decides). No tool writes the processing register: the entry is written by the tool gate itself when the DPO approves, under the DPO's identity, so the requester and the approver are always different people (separation of duties). ⚪ **utility** functions run inside nodes and are not model-callable; ⚫ **setup** is the one-off seed script.

## Tool inventory

| Tool | Kind | What it does | Runs in |
|---|---|---|---|
| `search_regulation(query, regulation?, k)` | 🟢 read | Hybrid retrieval over GDPR and AI Act chunks; reranks the fused top-20 to five, runs the grade / rewrite loop internally and returns the passages with citation labels | `worker` (tool call, through `tool_gate`); one pass without the loop in `direct_answer` |
| `get_article(regulation, article, paragraph?)` | 🟢 read | Returns the exact text of one article or paragraph; used when the model already knows the identifier | `worker` (tool call, through `tool_gate`) |
| `lookup_register(query \| id)` | 🟢 read | Finds existing processing-register entries so the agent can say "this is already registered as A-…" | `worker` (tool call, through `tool_gate`) |
| `request_dpo_review(assessment_id)` | 🟡 write | Called automatically after every verified assessment: creates a review task for the DPO and pauses the thread; the DPO's approve / amend / reject resumes it, and an approval writes the register entry (assessment, citations, high-risk flag) from inside the gate | `tool_gate` → `interrupt` (the gate does the work; the thread resumes in the worker) |
| `export_register` | 🟢 read | PDF export of the register for audits: overview table and every recorded assessment in full (`compliance_agent/export.py`, reportlab) | Register page (UI button, DPO only; not a worker tool) |
| `verify_citations` | ⚪ utility | Checks every cited label in the draft against the corpus; unknown citations send the draft back to the worker for one regeneration | `output_guardrail` |
| `pii_redact` / `pii_scan_output` | ⚪ utility | Redacts e-mails, phones, IBANs and card numbers on the way in and checks nothing leaks on the way out | `validate_input` / `output_guardrail` (plus `PIIMiddleware` inside `worker`) |
| `jev_router` / `llm_router` | ⚪ utility | Classifier behind the route node; returns a tier and a confidence | `route` |
| `grade_chunks`, `rewrite_query` | ⚪ utility | The retrieval grader and the query rewriter of the agentic RAG loop | inside `search_regulation`, i.e. `worker` |
| `seed.py`: ingest_corpus, seed_memory, create_users, reindex_corpus | ⚫ setup | One-off script run by the developer: ingests the corpus, writes the organisation facts into memory with `source: seed`, creates the two users, re-embeds after chunking changes | outside the graph |

## Who may call what

| Tool | product_manager | dpo | Note |
|---|---|---|---|
| `search_regulation` | 🟢 yes | 🟢 yes | Read-only, cheap. |
| `get_article` | 🟢 yes | 🟢 yes | Read-only, cheap. |
| `lookup_register` | 🟢 yes | 🟢 yes | Read-only. |
| `request_dpo_review` | 🟢 yes | 🔴 no | The PM's only write; called automatically after every verified assessment, creates the review task and pauses the thread. The DPO never requests a review: the DPO has no Assistant page and generates no assessments. |
| *(register write)* | 🔴 no | 🟡 by decision | Not a tool. Happens inside the tool gate when the DPO approves a paused request; the worker cannot call it for any role (a product manager's attempt gets the role's `denied_message`). |
| `export_register` | 🔴 no | 🟢 yes | Read-only PDF export for audits (UI button, not a worker tool). |

The matrix lives in `config/roles.yaml`; the model only ever sees its role's tools, and the tool gate re-checks the role on every call regardless. The DPO's read tools matter after a decision: the resumed worker runs under the DPO's identity and may still look things up while it reports the outcome. Memory writes follow the same file (`memory_writes`): a product manager may write only their own preferences; organisation facts and lessons come from DPO actions.

## The tool gate

Every tool call the worker makes passes through `ToolGateMiddleware` (`compliance_agent/nodes/middleware.py`), in this order:

1. **Doom-loop exit**: the same tool called with the same arguments a third time in one thread is refused, with a message telling the worker to use the earlier result and finish with what it has. A per-run budget of 14 real tool calls (`ToolBudgetMiddleware`, the stock limit middleware counting tools only, not the structured-output call that ends a run) caps the whole turn.
2. **Permission re-check** against the matrix above, even though the model only saw its allowed tools (defence in depth); a denied call returns the role's `denied_message` to the model.
3. **Human-in-the-loop**: after the output guardrail has verified an assessment it sends the worker back with "Please request DPO review for A-…"; `request_dpo_review` then creates the review task and calls `interrupt()`. The thread resumes under the identity in `config["configurable"]` (the DPO's), and the gate applies the decision: approve writes the register entry and stores the ticked memory items; request changes marks the assessment "changes requested" and stores the DPO's requirement as a lesson, and the run continues into a second pause, `pm_revision` (below), instead of ending; anything else is treated as a rejection. The resumed call is judged by the requester's permission (the task already exists), not the DPO's, which is why the DPO needs no write tool of its own.
4. **Allowed** calls run and the result goes back to the worker; every outcome is streamed to the trace.

## The second pause: `pm_revision`

Not a tool but the same mechanism. After the DPO's *Request changes* the run goes through `memory_write` and into the `pm_revision` node, which calls `interrupt()` with the requested changes, the DPO's comment and the previous description; the product manager's *Run revision* resumes the thread with her revised description and a done / not-possible answer per request, the node briefs the reviser agent from the thread's state, and v2 comes back through the gate to the DPO. Two checks happen on the resume, both deterministic, and a failed check pauses the thread again with the reason instead of ending the turn: only the thread's requester may resume it (the DPO cannot revise a feature on the product manager's behalf, another product manager cannot take over the thread), and the revised description must pass the same hard limits, PII redaction and injection patterns as a first input.

The second input is deliberately not sent to the small model that screens a first input. That classifier answers two questions, *is this on topic* and *is this an injection attempt*; the first is meaningless for a revision (the thread already is an assessment of this feature), and the marginal value of the second over the pattern check is small here, because the text comes from an already-screened user continuing her own thread and everything the reviser produces still passes the output guardrail (citation verification, the two revision rules, the PII scan) and then the DPO. Against that small gain, a model call inside a resume would make the pause depend on a helper model being up; the resume stays fast and deterministic instead.
