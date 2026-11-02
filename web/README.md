# Compliance Assistant — web front end

Next.js (App Router, TypeScript) over the FastAPI backend in `../api` (see `../docs/web_app_design.md`).

    npm install
    npm run dev          # http://localhost:3000; the API must run on :8000 (uvicorn api.main:app --reload --port 8000)

`/api/*` is proxied to the backend (`next.config.ts`), so the session cookie is first-party. `API_URL` points the
proxy elsewhere.
