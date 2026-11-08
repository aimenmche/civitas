from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import settings
from .db import init_db
from .services.runtime import manager
from .version import __version__

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("civitas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await manager.startup()
    log.info("CIVITAS API ready with %s restored run(s)", len(manager.runtimes))
    yield
    await manager.shutdown()
    log.info("CIVITAS API stopped")


app = FastAPI(
    title="CIVITAS API",
    description="Autonomous civilization simulator: deterministic simulation, emergent societies.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    log.exception("Unhandled API error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
ASSETS_DIST = FRONTEND_DIST / "assets"
INDEX_HTML = FRONTEND_DIST / "index.html"

if ASSETS_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    root = FRONTEND_DIST.resolve()
    candidate = (FRONTEND_DIST / path).resolve()
    # Serve a real file only if it lives inside dist (no traversal out of it).
    if candidate != root and root in candidate.parents and candidate.is_file():
        return FileResponse(candidate)

    if not INDEX_HTML.is_file():
        # Happens mid-rebuild: `vite build` clears dist before writing it back.
        # Answer cleanly instead of raising FileNotFoundError and logging a 500
        # traceback for every request that lands in that window.
        return JSONResponse(
            status_code=503,
            content={"detail": "Frontend build missing. Run `npm run build` in frontend/."},
            headers={"Cache-Control": "no-store"},
        )

    # The HTML entry point must never be cached heuristically: it is the only
    # thing that points at the hashed bundle. If an old copy sticks, the
    # browser keeps loading the previous renderer no matter what was rebuilt.
    return FileResponse(
        INDEX_HTML,
        headers={"Cache-Control": "no-store, max-age=0, must-revalidate"},
    )
