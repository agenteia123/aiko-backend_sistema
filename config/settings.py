"""Application configuration settings."""

from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # App
    APP_NAME: str = "Aiko AI Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Entorno: local = Ollama primero | production = APIs primero
    ENVIRONMENT: str = "local"
    PREFER_OLLAMA: bool = True

    # API
    API_KEY: str = "aiko-default-key-change-in-production"
    CORS_ORIGINS: list[str] = ["*"]

    # LLM Configuration
    LLM_PROVIDER: Literal["openai", "anthropic", "google", "groq", "grok", "ollama"] = "ollama"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROK_API_KEY: str = ""

    # Ollama (PC local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT: int = 120

    # Analysis Level
    ANALYSIS_LEVEL: Literal["fast", "balanced", "deep"] = "balanced"

    # Memory
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    DB_PATH: str = "./data/aiko.db"
    MEMORY_SEARCH_LIMIT: int = 5

    # Voice
    STT_PROVIDER: Literal["whisper", "google"] = "whisper"
    TTS_PROVIDER: Literal["piper", "google", "elevenlabs", "windows"] = "windows"
    PIPER_MODEL: str = "en_US-amy-medium"

    # Tools
    TAVILY_API_KEY: str = ""
    ENABLE_SEARCH: bool = True
    ENABLE_FILESYSTEM: bool = True
    ENABLE_DOCUMENT_READER: bool = True
    ENABLE_IMAGE_ANALYSIS: bool = True

    # Allowed filesystem paths
    ALLOWED_PATHS: list[str] = [
        "C:/Users/User/OneDrive/Documentos",
        "C:/Users/User/Downloads",
        "C:/Users/User/Documents",
        "./documents",
        "./uploads",
    ]

    # Translation
    ENABLE_TRANSLATION: bool = True
    DEFAULT_LANGUAGE: str = "es"

    # Security
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()