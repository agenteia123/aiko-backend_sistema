"""Factory for creating LLM instances based on configuration."""

import logging
from typing import Any, List, Optional

from langchain_core.language_models import BaseLanguageModel

from config.settings import settings


logger = logging.getLogger(__name__)


class LLMFactory:
    """Create only the provider selected by the user or private backend config."""

    _failed_providers: set[str] = set()

    @staticmethod
    def _prefer_local() -> bool:
        env = str(getattr(settings, "ENVIRONMENT", "local") or "local").lower()
        prefer = getattr(settings, "PREFER_OLLAMA", None)
        if prefer is not None:
            return bool(prefer)
        return env not in ("production", "prod", "cloud", "render")

    @staticmethod
    def create_llm() -> BaseLanguageModel:
        return LLMFactory.create_llm_for_task("normal")

    @staticmethod
    def create_llm_for_task(
        task_type: str = "normal",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseLanguageModel:
        """Build the exact selected provider/model; never silently cascade."""
        selected = (provider or settings.LLM_PROVIDER).strip().lower()
        allowed = {item.strip().lower() for item in settings.ALLOWED_LLM_PROVIDERS}
        creators = {
            "ollama": ("Ollama", LLMFactory._create_ollama, True),
            "groq": ("Groq", LLMFactory._create_groq, bool(settings.GROQ_API_KEY)),
            "google": ("Google", LLMFactory._create_google, bool(settings.GOOGLE_API_KEY)),
            "openai": ("OpenAI", LLMFactory._create_openai, bool(settings.OPENAI_API_KEY)),
            "anthropic": ("Anthropic", LLMFactory._create_anthropic, bool(settings.ANTHROPIC_API_KEY)),
            "grok": ("Grok", LLMFactory._create_grok, bool(settings.GROK_API_KEY)),
        }
        if selected not in allowed or selected not in creators:
            raise ValueError(f"Proveedor no autorizado: {selected}")

        name, creator, configured = creators[selected]
        if not configured:
            raise ValueError(f"El proveedor {name} no tiene credenciales configuradas")

        logger.info("Usando proveedor seleccionado: %s", name)
        return creator(model)

    @staticmethod
    def mark_failed(provider_name: str):
        LLMFactory._failed_providers.add(provider_name)
        logger.warning(f"Proveedor marcado como fallido: {provider_name}")

    @staticmethod
    def reset_failed():
        LLMFactory._failed_providers.clear()
        logger.info("Lista de proveedores fallidos reiniciada")

    @staticmethod
    def _create_openai(model: Optional[str] = None) -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model or "gpt-4o-mini",
            temperature=0.5,
            max_tokens=2048,
        )

    @staticmethod
    def _create_anthropic(model: Optional[str] = None) -> BaseLanguageModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model=model or "claude-3-5-sonnet-20241022",
            temperature=0.5,
            max_tokens=2048,
        )

    @staticmethod
    def _create_google(model: Optional[str] = None) -> BaseLanguageModel:
        """Create the explicitly selected Google GenAI model; never cascade."""
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.callbacks import CallbackManagerForLLMRun
        from langchain_core.pydantic_v1 import Field

        class GeminiChat(BaseChatModel):
            model_name: str = Field(default=settings.GOOGLE_MODEL)
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

                model_id = self.model_name
                response = client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                )
                text = str(getattr(response, "text", None) or "").strip()
                if not text:
                    raise RuntimeError(f"Gemini devolvió respuesta vacía ({model_id})")

                logger.info("Gemini respondió con el modelo seleccionado: %s", model_id)
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
            model_name=model or settings.GOOGLE_MODEL,
            temperature=0.5,
        )

    @staticmethod
    def _create_groq(model: Optional[str] = None) -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            model=model or getattr(settings, "GROQ_MODEL", "openai/gpt-oss-20b"),
            base_url="https://api.groq.com/openai/v1",
            temperature=0.5,
            max_tokens=2048,
        )

    @staticmethod
    def _create_grok(model: Optional[str] = None) -> BaseLanguageModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.GROK_API_KEY,
            model=model or "grok-3",
            base_url="https://api.x.ai/v1",
            temperature=0.5,
            max_tokens=2048,
        )

    @staticmethod
    def _create_ollama(model: Optional[str] = None) -> BaseLanguageModel:
        model = model or getattr(settings, "OLLAMA_MODEL", "qwen2.5:7b")
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        timeout = getattr(settings, "OLLAMA_TIMEOUT", 120)
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "Falta langchain-ollama. Ejecuta: "
                "pymanager exec -3.11 -m pip install -r requirements.txt"
            ) from exc

        return ChatOllama(
            base_url=base_url,
            model=model,
            temperature=0.5,
            num_ctx=8192,
            keep_alive=getattr(settings, "OLLAMA_KEEP_ALIVE", "10m"),
            client_kwargs={"timeout": timeout},
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
                    "Inténtalo de nuevo en un momento."
                )

        return DummyLLM()
