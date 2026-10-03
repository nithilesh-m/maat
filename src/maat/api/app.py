from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from maat import __version__
from maat.api.auth import load_users
from maat.api.settings import ApiSettings
from maat.api.store import RunStore
from maat.api.worker import Worker


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    app = FastAPI(title="MAAT API", version="1.0.0")
    app.state.settings = settings
    app.state.users = load_users(settings.users_file)
    app.state.store = RunStore(settings.runs_dir / "runs.db")
    app.state.store.fail_incomplete("server restarted while the run was in progress")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.worker = Worker(settings, app.state.store)

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    from maat.api.routers import evidence, mutations, runs  # noqa: PLC0415

    for r in (runs.router, evidence.router, mutations.router):
        app.include_router(r, prefix="/api/v1")
    return app
