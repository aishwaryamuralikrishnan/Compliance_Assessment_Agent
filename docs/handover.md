# Handover brief · Compliance Assistant (3 November 2026)

For the next working session. The project is Aishwarya Murali Krishnan's Turing College capstone: a GDPR / EU AI Act compliance assistant (LangGraph + FastAPI + Next.js) with a human in the loop. The code, the data and the documents live in `C:\Users\aishv\Compliance_Assesment_Agent` on her laptop; `docs/todo.md` is the single list of what is done and what is open, `docs/links.txt` has every address.

## 1. State of the project

- **App**: live on Render (free tier) since 2 Nov: web `https://compliance-web-qo1l.onrender.com`, API `https://compliance-api-tt5r.onrender.com`; Postgres on Neon (Frankfurt), seeded once from the laptop; Google sign-in (product manager by default, DPO from `DPO_EMAILS`); a nightly GitHub Actions job prunes threads older than 30 days. 78 automated tests (75 pass, 3 skip without Postgres).
- **Evaluation**: done and reported (runs of 27 Oct, retrieval re-run 3 Nov after the reranker switch); the report is public at `/evaluation` and as `eval/report/evaluation.pdf`; `eval/REPORT.md` and `EVALUATION.md` are the prose records.
- **Compliance of the app itself**: own OpenRouter key, zero data retention on the account and on every request, reranking by the cheap model (Cohere has no ZDR endpoint), privacy notice at `/privacy`, notice lines on the login page and the assistant, `python scripts/admin.py forget <user>` for deletion requests, evidence under `docs/compliance/`.
- **Website**: designed on a Claude Design canvas (`https://claude.ai/artifact/EBdrFG1BwQFc8GV3858Nzo`, private unless shared), written as a static page `site/index.html` and deployed on Vercel from the public repository: `https://complianceassessmentagent-site.vercel.app` (root directory `site`, redeploys on every push to `main`).
- **Repositories**: `origin` = public portfolio and deploy source `https://github.com/aishwaryamuralikrishnan/Compliance_Assessment_Agent`; `turing` = `https://github.com/TuringCollegeSubmissions/amural-AE.CAP.AFA.1.1` (keeps its own `AE.CAP_afa.md`). Aishwarya commits and pushes herself: `git push origin main` and `git push turing main`. Uncommitted at handover: `docs/links.txt`, `docs/todo.md`, this file.

## 2. Open work (numbers are `docs/todo.md` items)

1. **Item 7, Stela's expert review** — waiting on her; her answers replace Gemini's preliminary ones in `eval/data/` (`reviewed_by` fields). If she never replies, close with a line in the report that the expectations were reviewed by a stand-in model, not a domain expert (the evaluation page already says this).
2. **Item 10, second full-route run** — a small golden set written by Aishwarya from Jaunius' (in hand) and Stela's (pending until the weekend of 8–9 Nov) feature descriptions; expected verdict and key findings with severities only; run once with a stronger worker model set in `config/models.yaml` for the run; reported as its own section beside E6. Never run the harness against the demo database; never tune against the golden set.
3. **Item 14, README for the review** — reviewer-facing README; the website address goes at the top next to the demo; section 9 (compliance, marked as a draft) is reviewed and unmarked here (that closes item 26); section 8 is outdated. README.md, UI.md and EVALUATION.md are Aishwarya's to edit by hand unless she asks.
4. **Item 15, requirements check** — go through `AE.CAP_afa.md` point by point, note where each requirement is met (file or page) and turn gaps into tasks.
5. **Item 16, showcase** — slides or a live walkthrough from the demo run sheet (stages 0 to 9), two-window demo on the hosted version, a recorded fallback; the website link on the slides.
6. **Section F, housekeeping** — 19 deletions (`_to_delete/`, the empty `web/app/(app)/evaluation/`, unreferenced `docs/images/ui_*.png`, old rehearsal result folders of 26 Oct, optionally `eval/results/E3_20261103-1057`), 20 one full rehearsal on a reset database before the showcase, 30 the repository files review (keep / update / delete for every file in both repositories).
7. **A known inaccuracy to fix** — the privacy notice (`web/app/privacy/page.tsx`, section "What you enter, and where it goes") and README section 9 say the redaction covers "names". The code (`compliance_agent/nodes/validate_input.py`) masks e-mail addresses, phone numbers, IBANs and card numbers only. The website already states it correctly. Fix both texts, push, Render redeploys.

Parked after the capstone (section E): quick-path escalation (17), model and embedding swap evaluation (21), the revision evaluation E9 (22), EU-only processing on OpenRouter's Business plan (25).

## 3. How we work (standing rules)

- `OPENROUTER_API_KEY` never in a file that is committed; it is in `.env` (git-ignored) and in Render's environment. `config.py` loads `.env` with override off, so an OS variable wins (the old Turing College key was removed from the Windows environment). Credits: top up on openrouter.ai when a 402 appears; a run of the whole evaluation costs about $1.
- Python 3.12 global interpreter, no virtual environments. Tests: `python -m pytest -q` with the Docker database up (`docker compose up -d db`); the container run in the cloud used `DATABASE_URL=postgresql://compliance@localhost:5432/compliance_test OPENROUTER_API_KEY=test-key`.
- Claude edits files on the laptop through the device link: stage from `C:\Users\aishv\Compliance_Assesment_Agent\...`, edit, write back, and verify the md5 on both sides after every write; before overwriting, check the laptop copy still equals the version that was read. Edits inside a document Aishwarya owns (README.md, UI.md, EVALUATION.md, `config/models.yaml`) are exact-match replacements of a sentence she has approved, nothing more.
- The device link cannot write into `.github/` (such files go to `docs/` and she moves them) and cannot delete; moves and deletions are hers.
- No new app functionality unless she approves it first; the website and the privacy texts are text-only changes.
- Design canvas: revise `project/Main.dc.html` only after re-reading it (she edits on the canvas too); do not change any wording on the website without her say-so; the static copy `site/index.html` must be regenerated from the canvas page when the design changes (replace `{{accent}}` with `#4F8BFF` and the two `/_blob/...` image addresses with `images/assessment_card.png` and `images/live_graph.gif`; add the `<head>` metadata and the small responsive block).
- When a session's cloud workspace is new, nothing of the project is in it: stage what is needed from the laptop first. The screenshots used on the website were taken from the app's test stack (`devserver.py` with the scripted worker); the originals under `docs/images/` are older.

## 4. Where things are

- Design and decision notes: `docs/web_app_design.md`, `docs/containers_design.md`, `docs/deployment_design.md`, `docs/expert_round1.md`, `docs/expert_round2.md`, `docs/compliance/` (OpenRouter terms, privacy policy, data-policy screenshots, probe output).
- Evaluation: `eval/README.md` (method), `eval/REPORT.md` (results), `eval/harness/` (code; `report.py` builds the report JSON), `eval/report/notes.json` (hand-written texts of the report), `eval/results/` (runs; the `real/` ones are the reported ones on the Render image), `scripts/eval_pdf.py` (the PDF).
- Compliance tooling: `scripts/probe_provider.py` (does every call carry the data policy), `scripts/admin.py` (`prune-threads`, `forget`).
- Website: `site/index.html`, `site/images/`, the canvas link above; the canvas also holds the five exploration boards (A–C, D–E, backgrounds, slabs, What-it-does options) and an empty Page 2, all deletable.
- Demo accounts for a walkthrough: `lena.k` (product manager) and `m.weber` (DPO); Google sign-in for everyone else.
