"""The app factory. `app` is what uvicorn serves; `create_app(graph=...)` lets the tests inject the scripted graph.

    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from compliance_agent import db

from . import auth, evaluation, memory, meta, register, reviews, runs, threads
from .schemas import HealthOut

log = logging.getLogger(__name__)


def create_app(*, graph=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if graph is not None:
            app.state.graph = graph
        else:
            from compliance_agent.graph import get_graph
            app.state.graph = get_graph()         # compiled once per process, with the Postgres checkpointer and Store
        yield
        db.close_pool()

    app = FastAPI(title="Compliance Assistant API", version="0.1", lifespan=lifespan,
                  description="GDPR · EU AI Act · article-cited first assessment · not legal advice. "
                              "Log in with POST /api/auth/login; the session is a cookie, so the browser and this page keep it.")
    for r in (auth, threads, runs, reviews, register, memory, meta, evaluation):
        app.include_router(r.router)

    @app.get("/api/healthz", response_model=HealthOut, tags=["meta"], responses={503: {"model": HealthOut}})
    def healthz():
        try:
            with db.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return HealthOut(ok=True, db=True)
        except Exception as exc:
            log.exception("healthz: database unreachable")
            body = HealthOut(ok=False, db=False, detail=f"{type(exc).__name__}: {exc}")
            return JSONResponse(status_code=503, content=body.model_dump())

    return app


app = create_app()
