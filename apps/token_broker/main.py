"""Token Broker — issues downstream credentials without exposing raw secrets."""

import logging
import logging.config

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import get_db
from apps.token_broker.providers.mock_oauth import MockOAuthProvider
from apps.token_broker.providers.static_secret import StaticSecretProvider
from apps.token_broker.services.exchange_service import ExchangeService
from packages.common.settings import settings

logging.config.dictConfig(
    {
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
    }
)

logger = logging.getLogger("token_broker")

app = FastAPI(title="Agent Identity Lab — Token Broker", version="0.1.0")

providers = {
    "mock_oauth": MockOAuthProvider(),
    "static_secret": StaticSecretProvider(),
}
db_session = Depends(get_db)


class TokenExchangeRequest(BaseModel):
    tool_id: str
    scopes: list[str] = Field(default_factory=list)
    session_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "token_broker"}


@app.post("/v1/token-exchange")
async def token_exchange(
    data: TokenExchangeRequest,
    db: AsyncSession = db_session,
) -> dict[str, str]:
    service = ExchangeService(db, providers)
    try:
        return await service.exchange(data.tool_id, data.scopes, data.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
