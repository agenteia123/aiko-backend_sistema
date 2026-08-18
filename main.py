"""
Aiko Backend - AI Assistant FastAPI Server
A complete backend for the Aiko AI companion with LangGraph, memory, tools, and voice support.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware as GZIPMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import routes and services
from api.routes import chat, voice, tools, memory, settings, health, upload
from core.services import ServiceManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    logger.info("🚀 Starting Aiko Backend...")

    # Asegurar carpetas necesarias
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    Path("data/chroma").mkdir(parents=True, exist_ok=True)
    Path("data/documents").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    await ServiceManager.initialize()
    logger.info("✅ Services initialized")

    yield

    logger.info("🛑 Shutting down Aiko Backend...")
    await ServiceManager.shutdown()
    logger.info("✅ Cleanup completed")


app = FastAPI(
    title="Aiko AI Assistant Backend",
    description="Professional AI assistant backend with LangGraph, memory, tools, and voice",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Compression
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Routes
logger.info("📌 Registering API routes...")
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
# Upload de imágenes/archivos para el chat
app.include_router(upload.router, prefix="/api", tags=["Upload"])

# Servir archivos subidos (previews opcionales)
uploads_dir = Path("data/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Aiko AI Assistant Backend",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api": {
            "chat": "/api/chat",
            "voice": "/api/voice",
            "tools": "/api/tools",
            "memory": "/api/memory",
            "settings": "/api/settings",
            "health": "/api/health",
            "upload": "/api/upload",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )