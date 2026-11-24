"""Settings API routes."""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config.settings import settings
from api.auth import verify_api_key


logger = logging.getLogger(__name__)
router = APIRouter()


class AnalysisLevelRequest(BaseModel):
    """Analysis level request."""
    level: str  # "fast", "balanced", "deep"


class SettingsResponse(BaseModel):
    """Settings response."""
    success: bool
    app_name: str
    app_version: str
    debug: bool
    llm_provider: str
    analysis_level: str
    features: dict


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    api_key: str = Depends(verify_api_key),
):
    """Get current settings."""
    return SettingsResponse(
        success=True,
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        debug=settings.DEBUG,
        llm_provider=settings.LLM_PROVIDER,
        analysis_level=settings.ANALYSIS_LEVEL,
        features={
            "search": settings.ENABLE_SEARCH,
            "filesystem": settings.ENABLE_FILESYSTEM,
            "document_reader": settings.ENABLE_DOCUMENT_READER,
            "image_analysis": settings.ENABLE_IMAGE_ANALYSIS,
            "translation": settings.ENABLE_TRANSLATION,
        }
    )


@router.post("/analysis-level")
async def set_analysis_level(
    request: AnalysisLevelRequest,
    api_key: str = Depends(verify_api_key),
):
    """Update analysis level."""
    if request.level not in ["fast", "balanced", "deep"]:
        raise HTTPException(status_code=400, detail="Invalid analysis level")
    
    settings.ANALYSIS_LEVEL = request.level
    
    return {
        "success": True,
        "analysis_level": request.level,
        "message": f"Analysis level set to {request.level}",
    }


@router.get("/llm-providers")
async def get_llm_providers(
    api_key: str = Depends(verify_api_key),
):
    """List only providers explicitly allowed in the private backend config."""
    allowed = {name.lower() for name in settings.ALLOWED_LLM_PROVIDERS}
    provider_info = {
        "ollama": {"name": "Ollama", "description": "Modelo local", "configured": True},
        "groq": {"name": "Groq", "description": "API externa configurada por el usuario", "configured": bool(settings.GROQ_API_KEY)},
        "google": {"name": "Google Gemini", "description": "API externa configurada por el usuario", "configured": bool(settings.GOOGLE_API_KEY)},
    }
    return {
        "success": True,
        "current": settings.LLM_PROVIDER,
        "available": [
            {"value": key, **value}
            for key, value in provider_info.items()
            if key in allowed
        ],
    }


@router.post("/llm-provider")
async def set_llm_provider(
    provider: str,
    api_key: str = Depends(verify_api_key),
):
    """Set LLM provider."""
    valid_providers = {name.lower() for name in settings.ALLOWED_LLM_PROVIDERS}
    
    provider = provider.lower()
    if provider not in valid_providers:
        raise HTTPException(status_code=403, detail="Proveedor no autorizado en el backend")
    if provider == "groq" and not settings.GROQ_API_KEY:
        raise HTTPException(status_code=409, detail="Configura GROQ_API_KEY en el backend")
    if provider == "google" and not settings.GOOGLE_API_KEY:
        raise HTTPException(status_code=409, detail="Configura GOOGLE_API_KEY en el backend")
    
    settings.LLM_PROVIDER = provider
    
    return {
        "success": True,
        "llm_provider": provider,
        "message": f"LLM provider set to {provider}",
        "note": "El modelo de los nuevos mensajes usará este proveedor; no se hará fallback automático.",
    }


@router.get("/health")
async def health_check(
    api_key: str = Depends(verify_api_key),
):
    """Health check endpoint."""
    return {
        "success": True,
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
