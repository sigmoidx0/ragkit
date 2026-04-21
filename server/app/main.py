"""FastAPI app."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, health, search, services
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.bootstrap import bootstrap_admin
from app.db.session import SessionLocal, create_tables
from app.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    create_tables()
    with SessionLocal() as db:
        bootstrap_admin(db)
    try:
        get_vectorstore().ensure_collection()
    except Exception:
        logger.exception("could not prepare Qdrant collection; continuing")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ragkit", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(services.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    return app


app = create_app()
