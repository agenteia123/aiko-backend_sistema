"""Factory for creating LLM instances based on configuration."""

import logging
from typing import Any, List, Optional

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
        return env not in ("production", "prod", "cloud", "render")

    @staticmethod
    def create_llm() -> BaseLanguageModel:
        return LLMFactory.create_llm_for_task("normal")

    @staticmethod
    def create_llm_for_task(task_type: str = "normal") -> BaseLanguageModel:
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
            max_tokens=1024,
        )

    @staticmethod
    def _create_anthropic() -> BaseLanguageModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model="claude-3-5-sonnet-20241022",
            temperature=0.5,
            max_tokens=1024,
        )

    @staticmethod
    def _create_google() -> BaseLanguageModel:
        """
        SDK nuevo de Google (google-genai).
        Compatible con keys AQ... y modelos Gemini 2.x / 3.x.
        """
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.callbacks import CallbackManagerForLLMRun
        from pydantic import Field

        class GeminiChat(BaseChatModel):
            model_name: str = Field(default="gemini-2.0-flash")
            api_key: str = Field(default="")
            temperature: float = Field(default=0.5)

            @property
            def _llm_type(self) -> str:
                return "gemini-google-genai"

            def _generate(
                self,
                messages: List[BaseMessage],
                stop: Optional[List[str]] = None,
                run_manager: Optional[CallbackManagerForLLMRun] = None,
                **kwargs: Any,
            ) -> ChatResult:
                from google import genai

                client = genai.Client(api_key=self.api_key)

                parts = []
                for m in messages:
                    if isinstance(m, SystemMessage):
                        role = "system"
                    elif isinstance(m, AIMessage):
                        role = "model"
                    else:
                        role = "user"
                    content = m.content if isinstance(m.content, str) else str(m.content)
                    parts.append(f"{role}: {content}")

                prompt = "\n".join(parts)

                model_candidates = [
                    self.model_name,
                    "gemini-2.0-flash",
                    "gemini-2.0-flash-001",
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                ]

                last_err = None
                text = ""
                for model_id in model_candidates:
                    try:
                        response = client.models.generate_content(
                            model=model_id,
                            contents=prompt,
                        )
                        text = getattr(response, "text", None) or str(response)
                        if text:
                            break
                    except Exception as e:
                        last_err = e
                        logger.warning(f"Gemini modelo {model_id} falló: {e}")
                        continue

                if not text:
                    raise RuntimeError(f"Gemini no disponible: {last_err}")

                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=text))]
                )

            async def _agenerate(
                self,
                messages: List[BaseMessage],
                stop: Optional[List[str]] = None,
                run_manager: Optional[Any] = None,
                **kwargs: Any,
            ) -> ChatResult:
                import asyncio
                return await asyncio.to_thread(
                    self._generate, messages, stop, run_manager, **kwargs
                )

        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no configurada")

        return GeminiChat(
            api_key=api_key,
            model_name="gemini-2.0-flash",
            temperature=0.5,
        )

    @staticmethod
    def _create_groq() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            model=getattr(settings, "GROQ_MODEL", "openai/gpt-oss-20b"),
            base_url="https://api.groq.com/openai/v1",
            temperature=0.5,
            max_tokens=1024,
        )

    @staticmethod
    def _create_grok() -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.GROK_API_KEY,
            model="grok-3",
            base_url="https://api.x.ai/v1",
            temperature=0.5,
            max_tokens=1024,
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