"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import agents, announcements, auth, dashboard, day_off_requests, demand, me, offices, schedules, skills
from app.core.config import get_settings
from app.core.exceptions import DependencyUnavailableError
from app.core.firebase import initialize_firebase

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_firebase()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(offices.router, prefix=settings.api_v1_prefix)
app.include_router(skills.router, prefix=settings.api_v1_prefix)
app.include_router(agents.router, prefix=settings.api_v1_prefix)
app.include_router(demand.router, prefix=settings.api_v1_prefix)
app.include_router(schedules.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(me.router, prefix=settings.api_v1_prefix)
app.include_router(announcements.router, prefix=settings.api_v1_prefix)
app.include_router(day_off_requests.me_router, prefix=settings.api_v1_prefix)
app.include_router(day_off_requests.admin_router, prefix=settings.api_v1_prefix)

react_dist_candidates = [
    Path(__file__).resolve().parents[3] / "react-app" / "dist",
    Path(__file__).resolve().parents[2] / "react-app" / "dist",
]
react_dist_dir = next((candidate for candidate in react_dist_candidates if candidate.exists()), react_dist_candidates[0])
react_assets_dir = react_dist_dir / "assets"

if react_assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=react_assets_dir), name="react-assets")


@app.exception_handler(DependencyUnavailableError)
async def dependency_error_handler(_: Request, exc: DependencyUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "dependency": exc.dependency,
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def serve_index() -> FileResponse:
    return serve_react_app()


@app.get("/dashboard")
def serve_dashboard() -> FileResponse:
    return serve_react_app()


@app.get("/admin")
def serve_admin() -> FileResponse:
    return serve_react_app()


def serve_react_app() -> FileResponse:
    index_file = react_dist_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "React frontend build not found. Run `npm run build` in react-app "
                "or use the Vite dev server at http://localhost:5173."
            ),
        )
    return FileResponse(index_file)
