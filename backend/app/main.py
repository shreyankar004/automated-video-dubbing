from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.workers.job_manager import get_job_manager

configure_logging()

settings = get_settings()

app = FastAPI(
    title="DubFlow API",
    description="Automated YouTube-to-English video dubbing pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.on_event("startup")
async def bind_manager_loop() -> None:
    get_job_manager(settings).bind_loop(asyncio.get_running_loop())
