"""Factory for creating LLM instances based on configuration."""

import logging
from typing import Any

from langchain_core.language_models import BaseLanguageModel

from config.settings import settings


logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM instances with automatic fallback cascade."""

    _failed_providers: set[str] = set()

    @staticmethod
    def _prefer_local() -> bool:
        """
        True = priorizar Ollama (uso en PC).
        production / cloud = APIs primero, Ollama al final.
        """
        env = str(getattr(settings, "ENVIRONMENT", "local") or "local").lower()
        prefer = getattr(settings, "PREFER_OLLAMA", None)
        if prefer is not None:
            return bool(prefer)
        # Por defecto en PC: local
        return env not in ("production", "prod", "cloud", "render")

    @staticmethod
    def create_llm() -> BaseLanguageModel:
        return LLMFactory.create_llm_for_task("normal")

    @staticmethod
    def create_llm_for_task(task_type: str = "normal") -> BaseLanguageModel:
        """
        Cascada:

        LOCAL (PC):
          1. Ollama (qwen2.5:7b)
          2. Groq / Google / OpenAI / Anthropic / Grok (si hay keys)

        PRODUCTION (más adelante en Render):
          1. APIs
          2. Ollama (solo si existiera en ese entorno)
        """
        api_providers = []

        if getattr(settings, "GROQ_API_KEY", None):
            api_providers.append(("Groq", LLMFactory._create_groq))

        if getattr(settings, "GOOGLE_API_KEY", None):
            api_providers.append(("Google", LLMFactory._create_google))

        if getattr(settings, "OPENAI_API_KEY", None):
            api_providers.append(("OpenAI", LLMFactory._create_openai))

        if getattr(settings, "ANTHROPIC_API_KEY", None):
            api_providers.append(("Anthropic", LLMFactory._create_anthropic))

        if getattr(settings, "GROK_API_KEY", None):
            api_providers.append(("Grok", LLMFactory._create_grok))

        if LLMFactory._prefer_local():
            providers = [("Ollama", LLMFactory._create_ollama)] + api_providers
            logger.info("Modo LOCAL: Ollama tiene prioridad")
        else:
            providers = api_providers + [("Ollama", LLMFactory._create_ollama)]
            logger.info("Modo PRODUCTION: APIs tienen prioridad")

        last_error = None
        for name, creator in providers:
            if name in LLMFactory._failed_providers:
                logger.info(f"Saltando {name} (ya falló en esta sesión)")
                continue

            try:
                logger.info(f"Intentando {name}...")
                llm = creator()
                logger.info(f"✅ Usando modelo: {name}")
                return llm
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {name} falló al crear: {e}")
                LLMFactory._failed_providers.add(name)
                continue

        logger.error(f"Todos los proveedores fallaron. Último error: {last_error}")
        return LLMFactory._create_dummy()

    @staticmethod
    def mark_failed(provider_name: str):
        LLMFactory._failed_providers.add(provider_name)
        logger.warning(f"Proveedor marcado como fallido: {provider_name}")

    @staticmethod
    def reset_failed():
        LLMFactory._failed_providers.clear()
        logger.info("Lista de proveedores fallidos reiniciada")

    @staticmethod
    def _create_openai() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=8192,
        )

    @staticmethod
    def _create_anthropic() -> BaseLanguageModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model="claude-3-5-sonnet-20241022",
            temperature=0.5,
            max_tokens=8192,
        )

    @staticmethod
    def _create_google() -> BaseLanguageModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            api_key=settings.GOOGLE_API_KEY,
            model="gemini-2.5-flash",
            temperature=0.5,
        )

    @staticmethod
    def _create_groq() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        # Modelo actualizado (llama-3.1-8b-instant ya no estaba disponible)
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            model=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            base_url="https://api.groq.com/openai/v1",
            temperature=0.5,
            max_tokens=8192,
        )

    @staticmethod
    def _create_grok() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.GROK_API_KEY,
            model="grok-3",
            base_url="https://api.x.ai/v1",
            temperature=0.5,
            max_tokens=8192,
        )

    @staticmethod
    def _create_ollama() -> BaseLanguageModel:
        model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b")
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        timeout = getattr(settings, "OLLAMA_TIMEOUT", 120)

        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=base_url,
                model=model,
                temperature=0.5,
                num_ctx=8192,
                timeout=timeout,
            )
        except ImportError:
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                base_url=base_url,
                model=model,
                temperature=0.5,
            )

    @staticmethod
    def _create_dummy() -> BaseLanguageModel:
        from langchain_core.language_models import LLM

        class DummyLLM(LLM):
            @property
            def _llm_type(self) -> str:
                return "dummy"

            def _call(self, prompt: str, stop: list[str] | None = None, **kwargs: Any) -> str:
                return (
                    "Hola, soy Aiko en modo de emergencia. "
                    "Ningún modelo de IA está disponible ahora mismo. "
                    "Revisa que Ollama esté corriendo (`ollama serve`) "
                    "y que tengas el modelo qwen2.5:7b."
                )

        return DummyLLM()