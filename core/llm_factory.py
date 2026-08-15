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
    def create_llm() -> BaseLanguageModel:
        return LLMFactory.create_llm_for_task("normal")

    @staticmethod
    def create_llm_for_task(task_type: str = "normal") -> BaseLanguageModel:
        """
        Cascada automática:
        1. Groq
        2. Google
        3. OpenAI
        4. Anthropic
        5. Grok
        6. Ollama (local)
        """
        providers = []

        if getattr(settings, "GROQ_API_KEY", None):
            providers.append(("Groq", LLMFactory._create_groq))

        if getattr(settings, "GOOGLE_API_KEY", None):
            providers.append(("Google", LLMFactory._create_google))

        if getattr(settings, "OPENAI_API_KEY", None):
            providers.append(("OpenAI", LLMFactory._create_openai))

        if getattr(settings, "ANTHROPIC_API_KEY", None):
            providers.append(("Anthropic", LLMFactory._create_anthropic))

        if getattr(settings, "GROK_API_KEY", None):
            providers.append(("Grok", LLMFactory._create_grok))

        providers.append(("Ollama", LLMFactory._create_ollama))

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
        # IMPORTANTE: gemini-2.0-flash ya no existe
        return ChatGoogleGenerativeAI(
            api_key=settings.GOOGLE_API_KEY,
            model="gemini-2.5-flash",
            temperature=0.5,
        )

    @staticmethod
    def _create_groq() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        # Modelo más liviano = menos consumo de cuota diaria
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            model="llama-3.1-8b-instant",
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
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
                model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"),
                temperature=0.5,
                num_ctx=8192,
                timeout=getattr(settings, "OLLAMA_TIMEOUT", 120),
            )
        except ImportError:
            from langchain_community.llms import Ollama
            return Ollama(
                base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
                model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b"),
                temperature=0.5,
                num_ctx=8192,
                timeout=getattr(settings, "OLLAMA_TIMEOUT", 120),
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
                    "Revisa tus API keys o que Ollama esté corriendo (`ollama serve`)."
                )

        return DummyLLM()