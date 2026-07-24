"""Health check routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from config.settings import settings


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check (no auth required)."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/detailed")
async def detailed_health_check(
    api_key: str = Depends(verify_api_key),
):
    """Detailed health check with service status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": {
            "llm": {
                "provider": settings.LLM_PROVIDER,
                "status": "configured",
            },
            "memory": {
                "db_path": settings.DB_PATH,
                "chroma_path": settings.CHROMA_PERSIST_DIR,
                "status": "initialized",
            },
            "voice": {
                "stt": settings.STT_PROVIDER,
                "tts": settings.TTS_PROVIDER,
                "status": "ready",
            },
            "tools": {
                "search": settings.ENABLE_SEARCH,
                "filesystem": settings.ENABLE_FILESYSTEM,
                "document_reader": settings.ENABLE_DOCUMENT_READER,
                "image_analysis": settings.ENABLE_IMAGE_ANALYSIS,
            },
        }
    }


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    return {
        "ready": True,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {
        "live": True,
        "timestamp": datetime.now().isoformat(),
    }
