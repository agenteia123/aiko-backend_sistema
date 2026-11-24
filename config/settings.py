"""Application configuration loaded from the private backend environment."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the single-user local Aiko backend."""

    APP_NAME: str = "Aiko AI Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "local"

    # Authentication: configure these in the backend's private .env file.
    AUTH_USERNAME: str = ""
    AUTH_PASSWORD: str = ""
    AUTH_USER_ID: str = "user-123"
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 12

    # Network defaults keep the API local to this computer. Add explicit LAN
    # origins and set HOST=0.0.0.0 only when another trusted device needs it.
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    ENABLE_API_DOCS: bool = True

    # The model is selected explicitly. There is no automatic provider cascade.
    LLM_PROVIDER: Literal["ollama", "groq", "google"] = "ollama"
    ALLOWED_LLM_PROVIDERS: list[str] = ["ollama", "groq", "google"]
    PREFER_OLLAMA: bool = True  # retained for compatibility with older config
    GOOGLE_API_KEY: str = ""
    GOOGLE_MODEL: str = "gemini-2.0-flash"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_API_KEY: str = ""  # used only if explicitly configured for Whisper STT
    ANTHROPIC_API_KEY: str = ""
    GROK_API_KEY: str = ""

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_KEEP_ALIVE: str = "10m"
    ANALYSIS_LEVEL: Literal["fast", "balanced", "deep"] = "balanced"

    # Relative paths are resolved from the backend project directory at startup.
    DATA_DIR: str = "./data"
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    DB_PATH: str = "./data/aiko.db"
    UPLOAD_DIR: str = "./data/uploads"
    DOCUMENTS_DIR: str = "./data/documents"
    MEMORY_SEARCH_LIMIT: int = 5

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "documents"

    # Backend transcription is disabled by default to avoid a hidden paid API call.
    STT_PROVIDER: Literal["disabled", "whisper", "google"] = "disabled"
    TTS_PROVIDER: Literal["piper", "google", "elevenlabs", "windows"] = "windows"
    PIPER_MODEL: str = "es_MX-claude-high.onnx"

    TAVILY_API_KEY: str = ""
    ENABLE_SEARCH: bool = True
    ENABLE_FILESYSTEM: bool = True
    ENABLE_DOCUMENT_READER: bool = True
    ENABLE_IMAGE_ANALYSIS: bool = True

    # Keep defaults inside Aiko's own data folders. Add user folders only by
    # explicitly configuring ALLOWED_PATHS in the private backend environment.
    ALLOWED_PATHS: list[str] = [
        "./data/documents",
        "./data/uploads",
    ]

    ENABLE_TRANSLATION: bool = True
    DEFAULT_LANGUAGE: str = "es"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
