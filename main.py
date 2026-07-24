"""
Aiko Backend - AI Assistant FastAPI Server
A complete backend for the Aiko AI companion with LangGraph, memory, tools, and voice support.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware as GZIPMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routes and services
from api.routes import chat, voice, tools, memory, settings, health
from core.services import ServiceManager


# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    logger.info("🚀 Starting Aiko Backend...")
    
    # Initialize services
    await ServiceManager.initialize()
    logger.info("✅ Services initialized")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Aiko Backend...")
    await ServiceManager.shutdown()
    logger.info("✅ Cleanup completed")


# Create FastAPI app
app = FastAPI(
    title="Aiko AI Assistant Backend",
    description="Professional AI assistant backend with LangGraph, memory, tools, and voice",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Add compression middleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Include routes
logger.info("📌 Registering API routes...")
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])

# Root endpoint
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
            "health": "/api/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
