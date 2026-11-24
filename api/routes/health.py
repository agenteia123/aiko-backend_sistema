"""Health endpoints for local supervision and status displays."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import verify_api_key
from config.settings import settings


logger = logging.getLogger(__name__)
router = APIRouter()


def _check_sqlite() -> bool:
    database = Path(settings.DB_PATH)
    if not database.is_file():
        return False
    try:
        # Path.as_uri() handles Windows drive letters and spaces correctly.
        with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=1) as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


@router.get("/health")
async def health_check():
    """Liveness only; does not claim that the model or database is ready."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/detailed")
async def detailed_health_check(
    authenticated_user_id: str = Depends(verify_api_key),
):
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "checks": {
            "memory_database": _check_sqlite(),
            "provider": settings.LLM_PROVIDER,
            "voice": {"stt": settings.STT_PROVIDER, "tts": settings.TTS_PROVIDER},
        },
    }


@router.get("/ready")
async def readiness_check():
    """Readiness includes persistent memory and the selected provider setup."""
    checks: dict[str, bool] = {"memory_database": _check_sqlite()}
    provider = settings.LLM_PROVIDER

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if response.status_code == 200:
                available = {
                    item.get("name", "")
                    for item in response.json().get("models", [])
                    if isinstance(item, dict)
                }
                checks["llm_provider"] = settings.OLLAMA_MODEL in available
            else:
                checks["llm_provider"] = False
        except Exception:
            checks["llm_provider"] = False
    elif provider == "google":
        checks["llm_provider"] = bool(settings.GOOGLE_API_KEY)
    elif provider == "groq":
        checks["llm_provider"] = bool(settings.GROQ_API_KEY)
    else:
        checks["llm_provider"] = False

    ready = all(checks.values())
    payload = {
        "ready": ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@router.get("/live")
async def liveness_check():
    return {"live": True, "timestamp": datetime.now(timezone.utc).isoformat()}
