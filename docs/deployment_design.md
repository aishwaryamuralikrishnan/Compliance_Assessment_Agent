# Deployment (to-do item 13), design note

2 Nov 2026. Decided with the author: no hosting cost, the platform's own addresses, Google sign-in with the DPO
role by allowlist, deployment from the public repository
`https://github.com/aishwaryamuralikrishnan/Compliance_Assessment_Agent` (the Turing College capstone repository
receives the same commits and is not deployed from). The compliance items that go live with the deployment are
listed at the end (23, 26, 27, 28; 24 is done).

## The pieces

| piece | where | plan | notes |
|---|---|---|---|
| database | **Neon** (Postgres 16, `vector` extension) | free, permanent | about 1 GB; suspends after 5 minutes idle and resumes in under a second; the whole database is tens of MB |
| API | **Render** web service, Docker, `Dockerfile.api` | free | spins down after 15 minutes without requests, about a minute to wake; health check `/api/healthz` |
| front end | **Render** web service, Docker, `web/Dockerfile` | free | same spin-down; proxies `/api/*` to the API service (build argument `API_URL`) |
| retention job | **GitHub Actions** schedule in the public repository | free | runs `python scripts/admin.py prune-threads --days 30` against Neon once a day; Render has no free cron jobs |
| sign-in | **Google** (OpenID Connect) through the API | free | a Google Cloud OAuth client; see *OIDC* below |

Render's free Postgres is not used: it expires 30 days after creation and is deleted two weeks later. The two
free web services share 750 instance hours a month; a sleeping service consumes none, so a demo that is opened
now and then stays well inside the budget. When both services are asleep, the first visit takes up to two
minutes (each wakes on its first request); the login page is static and appears first, the API call behind it
waits. The showcase runs with both services woken a few minutes in advance.

## Order of work

1. **Neon.** Create a project (region: Frankfurt, EU), database `compliance`; copy the connection string
   (`postgresql://…neon.tech/compliance?sslmode=require`). Nothing else: the schema is created by the seed.
2. **Seed from the laptop, once.** `DATABASE_URL=<neon string> python -m ingest.seed all` (schema, corpus from
   `data/corpus/raw/`, the two demo accounts from `SEED_PM_PASSWORD` / `SEED_DPO_PASSWORD`, the seeded memory).
   A few cents of embedding on the author's own OpenRouter key. The Render service never seeds (`SEED_ON_START=0`),
   because EUR-Lex refuses direct downloads and the HTML cache lives on the laptop.
3. **Render, API service.** New web service from the public repository, language Docker, Dockerfile path
   `Dockerfile.api`, instance type Free, health check path `/api/healthz`, auto-deploy on push to `main`.
   Environment variables: `DATABASE_URL` (Neon), `OPENROUTER_API_KEY` (the author's own key, item 23),
   `OPENROUTER_BASE_URL`, `SESSION_SECRET` (a long random string: logins survive restarts), `SESSION_COOKIE_SECURE=true`,
   `SEED_ON_START=0`, `LANGSMITH_TRACING=false`, `EVAL_RESULTS_DIR=/app/eval/results`, and the OIDC variables below.
   Note the service's address, `https://<api-name>.onrender.com`.
4. **Render, front end.** Second web service, root directory `web`, Dockerfile path `web/Dockerfile`, Free,
   build argument `API_URL=https://<api-name>.onrender.com`. Its address, `https://<web-name>.onrender.com`,
   is the demo link (items 16 and 29).
5. **Google OAuth client** (console.cloud.google.com, APIs & Services → Credentials): a Web application client
   with the authorised redirect URI `https://<web-name>.onrender.com/api/auth/oidc/callback`, plus
   `http://localhost:3000/api/auth/oidc/callback` for local runs; the OAuth consent screen set to External with
   the app's name and the author as contact. Client id and secret go to the API service as `OIDC_CLIENT_ID`,
   `OIDC_CLIENT_SECRET`.
6. **GitHub Actions.** `.github/workflows/prune.yml` (in the repository) runs daily; the repository secret
   `DATABASE_URL` holds the Neon string. The first run can be started by hand from the Actions tab to check it.
7. **Smoke test** on the hosted addresses: `/evaluation` (public), Google sign-in as product manager, the seeded
   DPO account, one full assessment through to the DPO pause, the register PDF.

## OIDC with Google

The design document (`docs/web_app_design.md`, section 6) sketched the flow; two things change by the author's
decision for a public demo: a Google identity the table does not know is **admitted as a product manager**
rather than refused, and the **DPO role is given by an allowlist of e-mail addresses** (`DPO_EMAILS`, the
author's address for now). The two seeded accounts keep working, for the showcase and for the containers.

Flow (Authorization Code with PKCE, `authlib`):

- `GET /api/auth/oidc/start` builds the Google authorisation URL from `OIDC_ISSUER`
  (`https://accounts.google.com`, discovery document) and redirects; state and the PKCE verifier are kept in a
  short-lived signed cookie.
- `GET /api/auth/oidc/callback` exchanges the code, verifies the ID token (issuer, audience, signature, expiry,
  `email_verified`), finds or creates the `users` row by e-mail, decides the role (`DPO_EMAILS` → `dpo`, else
  `OIDC_DEFAULT_ROLE`, `product_manager`), issues the **same session cookie** as the password login and
  redirects to `/assistant`.
- Both URLs are reached **through the front end's proxy** (`/api/*` on the web origin), so the redirect URI
  Google calls is on the web address and the cookie is first-party, exactly as the password login's is. The
  API builds the redirect URI from `PUBLIC_BASE_URL` (`https://<web-name>.onrender.com`, or
  `http://localhost:3000`), never from the request's `Host`.
- `users` gains `email TEXT UNIQUE` and `oidc_subject TEXT UNIQUE`, and `password_hash` becomes nullable
  (an OIDC user has none); `username` for an OIDC user is the e-mail address, `display_name` the Google name.
  Everything keyed on `user_id` = username (register `approved_by`, review tasks, memory authorship) is untouched.
- The login page gets a **Sign in with Google** button above the existing form; the API advertises whether OIDC
  is configured (`GET /api/meta` or a small `GET /api/auth/providers`), so a local run without the Google
  variables shows the form only.
- A role is read at sign-in; changing `DPO_EMAILS` changes the role at the person's next sign-in. An existing
  user who signs in with Google for the first time is matched by e-mail if the row has one, otherwise a new row.

Environment: `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `PUBLIC_BASE_URL`, `DPO_EMAILS`
(comma-separated), `OIDC_DEFAULT_ROLE` (`product_manager`; `deny` restores the original design, invitation only).

Cost control for a public sign-in: anyone with a Google account can run assessments on the author's key. Two
measures, neither in code: a **credit limit on the OpenRouter key** (the key's own setting; the gateway refuses
calls above it and the app shows the gateway's error), and `OIDC_DEFAULT_ROLE=deny` plus an allowlist if the
demo is ever abused. A per-user daily cap in the API would be a feature and is left out.

Tests: the callback with a stubbed token exchange and ID-token verification (new user → product manager row;
allowlisted e-mail → dpo; unverified e-mail → 401; `deny` → 403); the existing login tests unchanged.

## Changes to the repository for this item

- `Dockerfile.api` copies `eval/results/` into the image and `.dockerignore` stops excluding it, so the hosted
  `/evaluation` reads the runs from the image (locally the bind mount still overrides it). `eval/report/evaluation.pdf`
  is not in the image; the page's *Print view* is.
- `.github/workflows/prune.yml`, the retention schedule.
- OIDC: `api/oidc.py` (router), `api/sessions.py` (the state cookie), `compliance_agent/db.py` (the two columns,
  nullable password), `compliance_agent/auth.py` (`user_for_oidc`), `web/app/login/page.tsx` (the button),
  `requirements.txt` (`authlib`), tests, `.env.example`, `docker-compose.yml` (the OIDC variables passed through).
- The notices (item 27): one line on the login page and in the assistant's header, and a public `/privacy`
  page with the recipients (OpenRouter and the model providers as sub-processors under its DPA and SCCs, data
  collection denied, zero data retention where the provider offers it, the reranker excepted), what never
  leaves (the database, the register, the users), the 30-day retention of finished conversations, and the
  request not to enter real personal data.

## Compliance items that go live with this (section G of the to-do)

- **23**: on the author's own OpenRouter account, logging off and zero data retention on; `probe_provider.py`
  already shows the key answers under the policy; the DPA and the sub-processor list saved under `docs/compliance/`.
- **26**: the README paragraph on what leaves the app, to whom, under what, and what never leaves (the author
  writes it; the facts are in the to-do's section G and in item 24's result).
- **27**: the notices above.
- **28**: the GitHub Actions schedule and the retention period stated in the notice.
- **25** (EU-only processing through OpenRouter's EU domain) stays a decision for after the capstone; the
  notice says processing may happen outside the EU under SCCs.
