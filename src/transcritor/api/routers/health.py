import redis
from fastapi import APIRouter, HTTPException

from transcritor.api.schemas import HealthResponse, ReadyResponse
from transcritor.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url)
        client.ping()
        return ReadyResponse(status="ok", redis="ok")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {e}")
