"""Aiko FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware


APP_ROOT = Path(__file__).resolve().parent
load_dotenv(APP_ROOT / ".env")

from config.settings import settings  # noqa: E402


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (APP_ROOT / path).resolve()


settings.DATA_DIR = str(_project_path(settings.DATA_DIR))
settings.CHROMA_PERSIST_DIR = str(_project_path(settings.CHROMA_PERSIST_DIR))
settings.DB_PATH = str(_project_path(settings.DB_PATH))
settings.UPLOAD_DIR = str(_project_path(settings.UPLOAD_DIR))
settings.DOCUMENTS_DIR = str(_project_path(settings.DOCUMENTS_DIR))
settings.ALLOWED_PATHS = [str(_project_path(path)) for path in settings.ALLOWED_PATHS]
LOG_DIR = _project_path("./logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

file_handler = RotatingFileHandler(
    LOG_DIR / "aiko.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=4,
    encoding="utf-8",
)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), file_handler],
)
logger = logging.getLogger(__name__)

from api.routes import auth, chat, health, memory, settings as settings_routes, tools, upload, voice  # noqa: E402
from core.services import ServiceManager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create persistent directories and initialize app services."""
    logger.info("Starting Aiko backend")
    for directory in (
        settings.DATA_DIR,
        settings.CHROMA_PERSIST_DIR,
        settings.UPLOAD_DIR,
        settings.DOCUMENTS_DIR,
        str(LOG_DIR),
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)

    await ServiceManager.initialize()
    logger.info("Aiko services initialized")
    try:
        yield
    finally:
        logger.info("Shutting down Aiko backend")
        await ServiceManager.shutdown()


production = settings.ENVIRONMENT.lower() in {"production", "prod"}
docs_enabled = settings.ENABLE_API_DOCS and not production
app = FastAPI(
    title="Aiko AI Assistant Backend",
    description="Private backend for the Aiko AI companion",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if docs_enabled else None,
        "api": {
            "auth": "/api/auth/login",
            "chat": "/api/chat/message",
            "upload": "/api/upload",
            "health": "/api/health",
            "ready": "/api/ready",
        },
    }


if __name__ == "__main__":
    import uvicorn

    from voice.desktop import start_listener

    listener = start_listener()
    try:
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            reload=False,
            log_level=settings.LOG_LEVEL.lower(),
        )
    finally:
        if listener is not None and listener.poll() is None:
            listener.terminate()
