"""Identity API — Agent Identity Lab."""

import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.common.settings import settings

# Structured logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": settings.log_level,
    },
    "loggers": {
        "identity_api": {"level": settings.log_level, "propagate": False},
    },
})

logger = logging.getLogger("identity_api")

app = FastAPI(
    title="Agent Identity Lab — Identity API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow admin UI from Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "identity_api"}


# Routers registered after modules are created
# from apps.identity_api.api import blueprints, agents, sessions, delegations, authorization, audit
# app.include_router(blueprints.router)
