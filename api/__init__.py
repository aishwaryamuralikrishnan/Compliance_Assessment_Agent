"""The web API: FastAPI over the run API in `compliance_agent.graph` (docs/web_app_design.md).

    uvicorn api.main:app --reload --port 8000        then http://localhost:8000/docs

One module per API area: auth, threads, runs (step 2), reviews, register, memory, meta. Identity enters the
graph only through `config["configurable"]` via `graph.run_config`; the API reads it from the session cookie
(`deps.current_user`) and passes a `UserContext`, nothing else.
"""
