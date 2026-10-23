"""Application composition only: environment, lifecycle, middleware and route groups."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load configuration before importing domain modules that resolve data paths.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import store
from .routes import articles, assets, delivery, generation, preview, research, settings
from .tasks import recover


@asynccontextmanager
async def lifespan(app):
    recover()
    yield


def create_app(serve_frontend=True):
    application = FastAPI(
        title="Signal Studio · WeChatRewritingAssistant", version="0.1.0", lifespan=lifespan
    )
    origins = os.getenv(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,https://18582088138.github.io"
    ).split(",")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.get("/api/health")
    def health():
        return {"ok": True, "version": "0.1.0", "requires_token": bool(os.getenv("APP_TOKEN"))}

    for module in (articles, generation, assets, preview, settings, delivery, research):
        application.include_router(module.router)

    if serve_frontend:
        application.mount(
            "/", StaticFiles(directory=str(store.ROOT / "web"), html=True), name="frontend"
        )
    return application


app = create_app(serve_frontend=os.getenv("SERVE_FRONTEND", "true").lower() == "true")
