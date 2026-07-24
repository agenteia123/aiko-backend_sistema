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
    """Get available LLM providers."""
    return {
        "success": True,
        "current": settings.LLM_PROVIDER,
        "available": [
            {
                "name": "Ollama",
                "value": "ollama",
                "description": "Local/offline model",
                "configured": True,
            },
            {
                "name": "OpenAI",
                "value": "openai",
                "description": "GPT-4 and GPT-3.5",
                "configured": bool(settings.OPENAI_API_KEY),
            },
            {
                "name": "Anthropic Claude",
                "value": "anthropic",
                "description": "Claude models",
                "configured": bool(settings.ANTHROPIC_API_KEY),
            },
            {
                "name": "Google Gemini",
                "value": "google",
                "description": "Google AI models",
                "configured": bool(settings.GOOGLE_API_KEY),
            },
            {
                "name": "Grok",
                "value": "grok",
                "description": "X.AI Grok model",
                "configured": bool(settings.GROK_API_KEY),
            },
        ]
    }


@router.post("/llm-provider")
async def set_llm_provider(
    provider: str,
    api_key: str = Depends(verify_api_key),
):
    """Set LLM provider."""
    valid_providers = ["ollama", "openai", "anthropic", "google", "grok"]
    
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail="Invalid LLM provider")
    
    settings.LLM_PROVIDER = provider
    
    return {
        "success": True,
        "llm_provider": provider,
        "message": f"LLM provider set to {provider}",
        "note": "Backend restart may be required for changes to take effect",
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
