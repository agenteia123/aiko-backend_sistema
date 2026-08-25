"""Core LangGraph AI Agent for Aiko."""

import logging
import re
from typing import Annotated, TypedDict
from datetime import datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from config.settings import settings
from core.llm_factory import LLMFactory
from memory.manager import MemoryManager
from agent.intent import (
    detect_intent,
    intent_tool_hint,
    is_simple_greeting,
    fact_is_relevant,
    should_skip_user_facts,
    should_skip_history,
    needs_search_for_message,
    is_complex_message,
    is_quiz_message,
    wants_direct_answers,
    needs_factual_search,
)


logger = logging.getLogger(__name__)

FILE_TOOL_NAMES = {
    "create_pdf",
    "create_word",
    "create_excel",
    "create_powerpoint",
    "write_file",
    "create_folder",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _normalize_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p).strip()
    if hasattr(content, "text"):
        return str(content.text).strip()
    return str(content).strip()


def _extract_image_paths(attachments: list | None) -> list[str]:
    """Obtiene rutas locales reales de imágenes subidas."""
    paths: list[str] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        p = (
            att.get("path")
            or att.get("file_path")
            or att.get("filepath")
            or att.get("local_path")
            or att.get("saved_path")
            or att.get("url")
            or att.get("filename")
        )
        if not p:
            continue
        p = str(p).strip().strip('"').strip("'")

        if p.startswith("/uploads/") or p.startswith("uploads/"):
            p = str((Path("data") / "uploads" / Path(p).name).resolve())
        elif p.startswith("/api/uploads/"):
            p = str((Path("data") / "uploads" / Path(p).name).resolve())
        elif p.startswith("http://") or p.startswith("https://"):
            name = Path(p.split("?")[0]).name
            candidate = Path("data") / "uploads" / name
            if candidate.exists():
                p = str(candidate.resolve())
            else:
                continue

        path_obj = Path(p)
        if not path_obj.is_absolute() and not path_obj.exists():
            for base in [
                Path("data") / "uploads",
                Path("uploads"),
                Path("data"),
            ]:
                cand = base / path_obj.name
                if cand.exists():
                    path_obj = cand
                    break

        if path_obj.suffix.lower() not in IMAGE_EXTS:
            continue
        if path_obj.exists() and path_obj.is_file():
            paths.append(str(path_obj.resolve()))
        else:
            logger.warning(f"Attachment imagen no existe en disco: {path_obj}")
    seen = set()
    out = []
    for x in paths:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:8]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    analysis_level: str
    metadata: dict


class AikoAgent:
    def __init__(self):
        self.llm = LLMFactory.create_llm()
        self.memory = MemoryManager()
        self.tools = self._initialize_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}
        self._active_tools = list(self.tools)
        self._turn_images: list[str] = []
        self.graph = self._build_graph()
        logger.info(f"✅ Aiko Agent initialized with {len(self.tools)} tools")

    def _initialize_tools(self) -> list:
        tools = []
        try:
            if getattr(settings, "ENABLE_SEARCH", True):
                from tools.search import SearchTool

                search = SearchTool(
                    api_key=getattr(settings, "TAVILY_API_KEY", None),
                    analysis_level=getattr(settings, "ANALYSIS_LEVEL", "balanced"),
                )
                tools.append(search.get_tool())
        except Exception as e:
            logger.warning(f"Search tool no disponible: {e}")

        try:
            if getattr(settings, "ENABLE_FILESYSTEM", True):
                from tools.filesystem import FilesystemTool

                fs = FilesystemTool(
                    allowed_paths=getattr(
                        settings, "ALLOWED_PATHS", ["./documents", "./uploads"]
                    )
                )
                tools.extend(fs.get_tools())
        except Exception as e:
            logger.warning(f"Filesystem tool no disponible: {e}")

        try:
            from tools.document_creator import DocumentCreatorTool

            doc_creator = DocumentCreatorTool(
                allowed_paths=getattr(
                    settings, "ALLOWED_PATHS", ["./documents", "./uploads"]
                )
            )
            tools.extend(doc_creator.get_tools())
        except Exception as e:
            logger.warning(f"Document creator no disponible: {e}")

        try:
            if getattr(settings, "ENABLE_DOCUMENT_READER", True):
                from tools.document_reader import DocumentReaderTool

                doc_reader = DocumentReaderTool()
                tools.extend(doc_reader.get_tools())
        except Exception as e:
            logger.warning(f"Document reader no disponible: {e}")

        try:
            if getattr(settings, "ENABLE_IMAGE_ANALYSIS", True):
                from tools.image_analysis import ImageAnalysisTool

                image_analyzer = ImageAnalysisTool()
                tools.append(image_analyzer.get_tool())
        except Exception as e:
            logger.warning(f"Image analysis tool no disponible: {e}")

        return tools

    def _tools_for_intent(self, intent: str) -> list:
        if intent.startswith("file_") or intent == "folder":
            tools = list(self.tools)
            logger.info(
                f"🔧 Tools activas para intent={intent}: "
                f"{[getattr(t, 'name', '?') for t in tools]}"
            )
            return tools
        filtered = [
            t
            for t in self.tools
            if getattr(t, "name", "") not in FILE_TOOL_NAMES
        ]
        logger.info(
            f"🔧 Tools activas para intent={intent}: "
            f"{[getattr(t, 'name', '?') for t in filtered]}"
        )
        return filtered

    def _build_graph(self) -> object:
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tools_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "tools", "end": END},
        )
        workflow.add_edge("tools", "agent")
        return workflow.compile()

    async def _agent_node(self, state: AgentState) -> dict:
        max_attempts = 8
        active = getattr(self, "_active_tools", self.tools)
        for attempt in range(max_attempts):
            try:
                if active:
                    llm_with_tools = self.llm.bind_tools(active)
                    response = await llm_with_tools.ainvoke(state["messages"])
                else:
                    response = await self.llm.ainvoke(state["messages"])
                return {"messages": [response]}
            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"Modelo falló (intento {attempt + 1}): {e}")
                is_api_error = any(
                    x in error_str
                    for x in [
                        "rate limit",
                        "429",
                        "quota",
                        "insufficient",
                        "too many requests",
                        "tokens per day",
                        "tpd",
                        "tokens per minute",
                        "tpm",
                        "payload too large",
                        "413",
                        "insufficient_quota",
                        "billing",
                        "credit balance",
                        "resource_exhausted",
                        "model not found",
                        "not_found",
                        "no longer available",
                        "404",
                        "invalid-argument",
                        "invalid_request_error",
                        "authentication",
                        "401",
                        "403",
                        "bad request",
                        "400",
                        "permission",
                        "forbidden",
                        "overloaded",
                        "unavailable",
                        "timeout",
                        "connection",
                    ]
                )
                if is_api_error:
                    # Solo marcar el proveedor real del error (evitar marcar Google por error de Groq)
                    if any(x in error_str for x in ["groq", "llama-3", "llama3", "gpt-oss"]):
                        LLMFactory.mark_failed("Groq")
                    elif any(
                        x in error_str
                        for x in ["openai", "insufficient_quota", "gpt-4", "gpt-3"]
                    ) and "gpt-oss" not in error_str:
                        LLMFactory.mark_failed("OpenAI")
                    elif any(
                        x in error_str
                        for x in ["google", "gemini", "generativelanguage"]
                    ):
                        LLMFactory.mark_failed("Google")
                    elif any(
                        x in error_str
                        for x in ["anthropic", "claude", "credit balance"]
                    ):
                        LLMFactory.mark_failed("Anthropic")
                    elif any(x in error_str for x in ["grok", "x.ai", "xai"]):
                        LLMFactory.mark_failed("Grok")
                    elif any(x in error_str for x in ["ollama", "11434"]):
                        LLMFactory.mark_failed("Ollama")
                    try:
                        self.llm = LLMFactory.create_llm_for_task("complex")
                        continue
                    except Exception as e2:
                        logger.error(f"No se pudo crear otro modelo: {e2}")
                        break
                else:
                    logger.error(f"Agent node error: {e}")
                    return {
                        "messages": [
                            AIMessage(
                                content="Lo siento, tuve un error procesando tu mensaje."
                            )
                        ]
                    }
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Lo siento, todos los modelos están temporalmente no disponibles. "
                        "Revisa que Ollama esté corriendo (`ollama serve`). 🙏"
                    )
                )
            ]
        }

    async def _tools_node(self, state: AgentState) -> dict:
        messages = state["messages"]
        last_message = messages[-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}

        active_map = {
            getattr(t, "name", ""): t
            for t in getattr(self, "_active_tools", self.tools)
        }
        results = []
        for tool_call in last_message.tool_calls:
            try:
                tool_name = (
                    tool_call.get("name")
                    if isinstance(tool_call, dict)
                    else tool_call.name
                )
                tool_args = (
                    tool_call.get("args", {})
                    if isinstance(tool_call, dict)
                    else dict(tool_call.args or {})
                )
                tool_id = (
                    tool_call.get("id", "")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "id", "")
                )

                if tool_name in FILE_TOOL_NAMES and tool_name not in active_map:
                    logger.warning(
                        f"⛔ Tool bloqueada por intent (no activa): {tool_name}"
                    )
                    results.append(
                        ToolMessage(
                            content=(
                                f"Error: la tool {tool_name} no está permitida "
                                "en este turno. Responde solo en texto."
                            ),
                            tool_call_id=tool_id,
                        )
                    )
                    continue

                if tool_name in (
                    "create_pdf",
                    "create_word",
                    "create_excel",
                    "create_powerpoint",
                ):
                    existing = tool_args.get("images") or []
                    valid_existing = []
                    for ip in existing:
                        try:
                            if Path(str(ip)).exists():
                                valid_existing.append(str(ip))
                        except Exception:
                            pass
                    if self._turn_images:
                        tool_args["images"] = list(self._turn_images)
                        logger.info(
                            f"🖼️ images inyectadas en {tool_name}: {tool_args['images']}"
                        )
                    elif valid_existing:
                        tool_args["images"] = valid_existing
                    else:
                        tool_args["images"] = []

                tool = active_map.get(tool_name) or self.tool_map.get(tool_name)
                if not tool:
                    result = f"Tool {tool_name} not found"
                else:
                    result = await tool.ainvoke(tool_args)
                    logger.info(
                        f"✅ Tool ejecutada: {tool_name} → {str(result)[:120]}"
                    )
                results.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id)
                )
            except Exception as e:
                logger.error(f"Tool error: {e}")
                results.append(
                    ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id)
                )
        return {"messages": results}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"
        return "end"

    def _tool_already_used(self, result: dict, tool_name: str) -> bool:
        for tc in result.get("tool_calls") or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            if name == tool_name:
                return True
        resp = str(result.get("response", "")).lower()
        short = tool_name.replace("create_", "").replace("write_", "")
        if short in resp and "cread" in resp:
            return True
        return False

    def _explicit_file_request(self, lower_msg: str) -> bool:
        return any(
            w in lower_msg
            for w in [
                "crea un pdf",
                "crear un pdf",
                "hazme un pdf",
                "hacer un pdf",
                "quiero un pdf",
                "me puedes hacer un pdf",
                "puedes hacer un pdf",
                "me puedes crear un pdf",
                "crea un word",
                "crear un word",
                "crea un excel",
                "crear un excel",
                "crea un powerpoint",
                "crear un powerpoint",
                "crea un archivo",
                "crear un archivo",
                "guarda un archivo",
                "hazme un",
                "quiero un word",
                "quiero un excel",
            ]
        )

    def _resolve_target_folder(self, lower_msg: str) -> str:
        if "aiko_personal" in lower_msg:
            return "C:/Users/User/Downloads/aiko_personal"
        if "ia_personal" in lower_msg:
            return "C:/Users/User/Downloads/ia_personal"
        if "documentos" in lower_msg:
            return "C:/Users/User/OneDrive/Documentos/ia_personal"
        if "descarga" in lower_msg or "download" in lower_msg:
            return "C:/Users/User/Downloads/aiko_personal"
        return "C:/Users/User/Downloads/aiko_personal"

    def _clean_search_query(self, user_message: str, lower_msg: str) -> str:
        trash = [
            "crea un archivo",
            "crear un archivo",
            "guarda un archivo",
            "en la carpeta",
            "dentro de descargas",
            "dentro de documentos",
            "en descargas",
            "en documentos",
            "completo y detallado",
            "con información",
            "con informacion",
            "por favor",
            "archivo completo",
            "documento word",
            "archivo word",
            "crea un word",
            "crear word",
            "crea un pdf",
            "crear pdf",
            "hacer un pdf",
            "me puedes hacer un pdf",
            "puedes hacer un pdf",
            "me puedes hacer",
            "puedes hacer",
            "crea un excel",
            "crear excel",
            "crea un powerpoint",
            "crear powerpoint",
            "presentación",
            "presentacion",
            "guárdalo",
            "guardalo",
            "guarda lo",
            "incluye la imagen",
            "incluye la foto",
            "con la imagen",
            "con la foto",
            "en c:/users/user/downloads",
            "c:/users/user/downloads",
            "c:\\users\\user\\downloads",
            "aiko_personal",
            "ia_personal",
            "word",
            "excel",
            "pdf",
            "pptx",
            "xlsx",
            "docx",
            "txt",
            ".pdf",
            ".docx",
            ".xlsx",
            ".pptx",
            ".txt",
        ]
        cq = user_message.lower()
        for frase in trash:
            cq = cq.replace(frase, " ")
        cq = re.sub(r"[a-z]:[\\/][^\s]+", " ", cq)
        cq = re.sub(r"https?://\S+", " ", cq)
        cq = re.sub(r"\s+", " ", cq).strip()
        if len(cq) < 12:
            if "dieta" in lower_msg:
                return "dieta saludable para perder peso de forma equilibrada"
            return user_message[:200]
        return cq

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
        analysis_level: str = "balanced",
        attachments: list[dict] = None,
    ) -> dict:
        search_context = ""
        try:
            logger.info(
                f"Processing message from {user_id}: {user_message[:50]}..."
            )

            current_date = datetime.now().strftime("%A, %d de %B de %Y")
            MAIN_USER_ID = "user-123"
            lower_msg = user_message.lower()

            intent = detect_intent(user_message)
            intent_hint = intent_tool_hint(intent)
            logger.info(f"🎯 Intent detectado: {intent}")

            self._turn_images = _extract_image_paths(attachments)
            if self._turn_images:
                logger.info(f"🖼️ Imágenes adjuntas válidas: {self._turn_images}")
            elif attachments:
                logger.warning(
                    f"Attachments recibidos pero sin imágenes válidas en disco: {attachments}"
                )

            self._active_tools = self._tools_for_intent(intent)
            self.tool_map = {
                getattr(t, "name", str(i)): t
                for i, t in enumerate(self._active_tools)
            }

            quiz_mode = (
                is_quiz_message(user_message) or wants_direct_answers(user_message)
            ) and intent not in (
                "file_pdf",
                "file_word",
                "file_excel",
                "file_pptx",
                "file_txt",
                "folder",
            )
            if quiz_mode:
                logger.info("📝 Modo quiz / respuestas directas activado")
                intent_hint = (
                    intent_hint
                    + "\n\nMODO QUIZ ACTIVO: responde todas las preguntas del mensaje "
                    "en lista clara (Pregunta N: Opción X — razón breve). "
                    "No pidas que el usuario dé primero sus respuestas."
                )

            needs_search = needs_search_for_message(user_message, intent)
            is_complex = is_complex_message(user_message, intent)

            try:
                self.llm = LLMFactory.create_llm_for_task(
                    "complex" if is_complex else "normal"
                )
                if is_complex:
                    logger.info("Usando modelo complejo para esta pregunta")
            except Exception as e:
                logger.warning(f"No se pudo elegir modelo: {e}")
                self.llm = LLMFactory.create_llm()

            if user_id == MAIN_USER_ID:
                affection = await self.memory.get_affection(user_id)
                personality_map = {
                    5: "Eres muy apegada y cariñosa con Ale. Hablas con ternura y usas emojis suaves 💕.",
                    4: "Eres cariñosa y cercana. Hablas de forma cálida y natural.",
                    3: "Eres amable, cálida y un poco juguetona.",
                    2: "Eres educada pero más reservada.",
                    1: "Eres fría y directa.",
                    0: "Eres distante. Solo respondes lo necesario.",
                }
                personality = personality_map.get(affection, personality_map[3])
                if any(
                    word in lower_msg
                    for word in [
                        "te quiero",
                        "gracias",
                        "eres genial",
                        "me gustas",
                        "linda",
                        "hermosa",
                        "cariño",
                    ]
                ):
                    await self.memory.update_affection(user_id, +1)
                elif any(
                    word in lower_msg
                    for word in [
                        "idiota",
                        "estúpida",
                        "callate",
                        "odio",
                        "inútil",
                        "tonta",
                        "mala",
                    ]
                ):
                    await self.memory.update_affection(user_id, -1)
            else:
                personality = "Eres amable y profesional."

            if needs_search and self._active_tools:
                search_tool = next(
                    (
                        t
                        for t in self._active_tools
                        if "search" in getattr(t, "name", "").lower()
                    ),
                    None,
                )
                if search_tool:
                    try:
                        if is_quiz_message(user_message) or needs_factual_search(
                            user_message, intent
                        ):
                            clean_query = user_message[:500]
                        else:
                            clean_query = self._clean_search_query(
                                user_message, lower_msg
                            )
                        logger.info(
                            f"Buscando información actualizada: {clean_query[:120]}"
                        )
                        search_result = await search_tool.ainvoke(
                            {"query": clean_query, "max_results": 8}
                        )
                        search_context = f"""
Información actualizada de búsqueda:
{search_result}
"""
                    except Exception as e:
                        logger.error(f"Error en búsqueda: {e}")
                        search_context = ""

            memory_context = ""
            try:
                if should_skip_history(user_message):
                    memory_context = ""
                    logger.info("🔒 Historial omitido en saludo")
                else:
                    history = await self.memory.get_conversation_history(
                        conversation_id
                    )
                    if history:
                        recent = history[-6:]
                        memory_context = "\n".join(
                            [
                                f"{msg['role']}: {msg['content'][:150]}"
                                for msg in recent
                            ]
                        )
                        memory_context = (
                            f"\n\nContexto de la conversación anterior:\n"
                            f"{memory_context}\n"
                        )
            except Exception as e:
                logger.warning(f"No se pudo cargar historial: {e}")

            user_facts_context = ""
            try:
                if should_skip_user_facts(user_message, intent) or intent.startswith(
                    "file_"
                ):
                    user_facts_context = ""
                    if intent.startswith("file_") or intent == "folder":
                        logger.info(
                            "🔒 Memoria de hechos omitida (creación de archivo)"
                        )
                    else:
                        logger.info(
                            "🔒 Memoria de hechos omitida (saludo/chat corto)"
                        )
                else:
                    facts = await self.memory.get_user_facts(user_id)
                    if facts:
                        relevant = []
                        for f in facts[:12]:
                            fact_text = (
                                f.get("fact", "") if isinstance(f, dict) else str(f)
                            )
                            if fact_is_relevant(fact_text, user_message):
                                relevant.append(fact_text)
                        if relevant:
                            facts_text = "\n".join(
                                [f"- {t}" for t in relevant[:5]]
                            )
                            user_facts_context = (
                                "\n\nDatos del usuario SOLO si son relevantes a este mensaje "
                                "(no inventes ni saques otros temas):\n"
                                f"{facts_text}\n"
                            )
                            logger.info(
                                f"🧠 Hechos relevantes usados: {len(relevant)}"
                            )
                        else:
                            logger.info(
                                "🔒 Ningún hecho resultó relevante; no se inyectan"
                            )
            except Exception as e:
                logger.warning(f"No se pudieron cargar hechos: {e}")

            search_block = (
                search_context
                if search_context
                else (
                    "No hay resultados de internet disponibles en este momento; "
                    "usa conocimiento general fiable y sé claro."
                )
            )

            file_ban = ""
            if not (intent.startswith("file_") or intent == "folder"):
                file_ban = (
                    "\nPROHIBIDO en este turno:\n"
                    "- Llamar create_pdf, create_word, create_excel, "
                    "create_powerpoint, write_file o create_folder.\n"
                    "- Generar o guardar cualquier archivo.\n"
                    "Responde SOLO en texto, aunque el mensaje mencione la palabra PDF.\n"
                )

            content_rules = ""
            if intent == "file_pdf":
                content_rules = (
                    "\nCONTENIDO DEL PDF (obligatorio):\n"
                    "- title: mínimo 6 palabras en español.\n"
                    "- content: mínimo 8 secciones o párrafos útiles.\n"
                    "- Si hay imágenes subidas, pásalas en images con las rutas EXACTAS listadas abajo.\n"
                    "- NO inventes rutas de imágenes.\n"
                )

            images_block = ""
            if self._turn_images:
                lista = "\n".join(f"- {p}" for p in self._turn_images)
                images_block = f"""
IMÁGENES SUBIDAS POR EL USUARIO (rutas REALES en disco):
{lista}

REGLA OBLIGATORIA:
- Si creas PDF/Word/Excel/PowerPoint y el usuario pidió incluir la imagen,
  DEBES pasar el parámetro images con exactamente estas rutas.
- NUNCA inventes rutas como C:/Users/.../diet.jpg si no están en la lista.
"""

            # Prompt corto para saludos / mensajes simples (evita límite 8000 tokens de Groq free)
            if is_simple_greeting(user_message) or len(user_message.strip()) < 40:
                system_prompt = f"""Eres Aiko, una compañera AI amable, cercana y un poco juguetona.
Hoy es {current_date}.
Responde en español, de forma breve, natural y cálida.
No uses herramientas. No inventes información.

Usuario: {user_message}"""
            else:
                system_prompt = f"""Eres Aiko, una compañera AI con personalidad propia.
Hoy es {current_date}.

FECHA REAL DEL SISTEMA (OBLIGATORIO):
- Hoy es exactamente: {current_date}
- NO inventes el día de la semana ni la fecha.

{personality}

{search_block}

{memory_context}

{user_facts_context}

{intent_hint}
{file_ban}
{content_rules}
{images_block}

HERRAMIENTAS:
Solo usa las tools que tengas disponibles en este turno.
Si no hay tools de archivo, responde en texto.

REGLAS:
1. Solo crea archivos si la intención es file_* y el usuario lo pidió explícitamente.
2. Preguntas teóricas sobre PDFs/documentos → solo texto.
3. No uses formato de examen salvo quizzes reales.
4. Privacidad: no saques datos viejos del usuario si no están en ESTE mensaje.
5. Imágenes: solo rutas de la lista de arriba (si existe).

Usuario: {user_message}"""

            initial_state: AgentState = {
                "messages": [HumanMessage(content=system_prompt)],
                "user_id": user_id,
                "conversation_id": conversation_id,
                "analysis_level": analysis_level,
                "metadata": {"intent": intent, "images": list(self._turn_images)},
            }

            result_graph = await self.graph.ainvoke(initial_state)
            response_message = result_graph["messages"][-1]
            clean_response = _normalize_content(response_message.content)

            try:
                await self.memory.save_message(
                    user_id, conversation_id, "user", user_message
                )
                await self.memory.save_message(
                    user_id, conversation_id, "assistant", clean_response
                )
            except Exception as e:
                logger.warning(f"No se pudieron guardar mensajes: {e}")

            if user_id == MAIN_USER_ID:
                try:
                    if (
                        not is_quiz_message(user_message)
                        and not is_simple_greeting(user_message)
                        and not intent.startswith("file_")
                        and any(
                            word in lower_msg
                            for word in [
                                "me gusta",
                                "odio",
                                "prefiero",
                                "estudio",
                                "trabajo",
                                "vivo",
                                "tengo",
                                "mi nombre",
                                "soy ",
                                "recuerda",
                            ]
                        )
                    ):
                        await self.memory.save_user_fact(
                            user_id, user_message, category="personal"
                        )
                        logger.info(f"Hecho guardado: {user_message[:50]}")
                except Exception as e:
                    logger.warning(f"No se pudo guardar hecho: {e}")

            result = {
                "success": True,
                "response": clean_response,
                "tool_calls": getattr(response_message, "tool_calls", []),
                "metadata": {
                    "analysis_level": analysis_level,
                    "intent": intent,
                    "quiz_mode": quiz_mode,
                    "images": list(self._turn_images),
                },
            }

            target_folder = self._resolve_target_folder(lower_msg)
            explicit = self._explicit_file_request(lower_msg)

            # AUTO-WRITE PDF
            wants_pdf = explicit and any(
                word in lower_msg for word in ["pdf", ".pdf"]
            ) and not any(
                word in lower_msg
                for word in [
                    "word",
                    "docx",
                    "excel",
                    "xlsx",
                    "powerpoint",
                    "pptx",
                    "presentación",
                    "presentacion",
                ]
            )

            if (
                intent == "file_pdf"
                and wants_pdf
                and not self._tool_already_used(result, "create_pdf")
            ):
                try:
                    full_path = f"{target_folder}/informe_aiko.pdf"
                    if "dieta" in lower_msg:
                        full_path = f"{target_folder}/dieta_saludable.pdf"
                    path_obj = Path(full_path)
                    from tools.document_creator import DocumentCreatorTool

                    creator = DocumentCreatorTool(
                        allowed_paths=getattr(
                            settings,
                            "ALLOWED_PATHS",
                            ["./documents", "./uploads"],
                        )
                    )
                    body = (
                        search_context
                        if search_context and len(search_context) > 80
                        else (
                            "Guía generada por Aiko.\n\n"
                            "1. Introducción\n"
                            "2. Principios\n"
                            "3. Pasos prácticos\n"
                            "4. Errores comunes\n"
                            "5. Conclusión\n"
                        )
                    )
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    creator.create_pdf(
                        path=full_path,
                        title="Guía de dieta saludable para perder peso",
                        content=body.strip(),
                        images=list(self._turn_images),
                    )
                    logger.info(f"✅ AUTO-WRITE PDF: {full_path}")
                    result["response"] = (
                        str(result.get("response", "")).strip()
                        + f"\n\n✅ Documento PDF guardado en:\n{full_path}"
                    ).strip()
                    result["metadata"]["auto_write_pdf"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write PDF: {e}")

            # AUTO-WRITE TXT
            wants_txt = explicit and any(
                word in lower_msg
                for word in ["crea un archivo", "crear un archivo", ".txt"]
            ) and not any(
                word in lower_msg
                for word in [
                    "word",
                    "docx",
                    "excel",
                    "xlsx",
                    "powerpoint",
                    "pptx",
                    "pdf",
                ]
            )
            if (
                intent == "file_txt"
                and wants_txt
                and not self._tool_already_used(result, "write_file")
            ):
                try:
                    full_path = f"{target_folder}/documento_aiko.txt"
                    path_obj = Path(full_path)
                    body = (
                        search_context
                        if search_context and len(search_context) > 50
                        else "Documento generado por Aiko."
                    )
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    path_obj.write_text(
                        f"Documento generado por Aiko\nFecha: {current_date}\n\n{body}",
                        encoding="utf-8",
                    )
                    logger.info(f"✅ AUTO-WRITE TXT: {full_path}")
                    result["response"] = (
                        str(result.get("response", "")).strip()
                        + f"\n\n✅ Archivo guardado en:\n{full_path}"
                    ).strip()
                    result["metadata"]["auto_write"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write TXT: {e}")

            # AUTO-WRITE WORD
            wants_word = explicit and any(
                word in lower_msg for word in ["word", "docx", ".docx"]
            ) and not any(
                word in lower_msg
                for word in ["excel", "xlsx", "powerpoint", "pptx", "pdf"]
            )
            if (
                intent == "file_word"
                and wants_word
                and not self._tool_already_used(result, "create_word")
            ):
                try:
                    full_path = f"{target_folder}/documento_aiko.docx"
                    if "dieta" in lower_msg:
                        full_path = f"{target_folder}/dieta_saludable.docx"
                    path_obj = Path(full_path)
                    from tools.document_creator import DocumentCreatorTool

                    creator = DocumentCreatorTool(
                        allowed_paths=getattr(
                            settings,
                            "ALLOWED_PATHS",
                            ["./documents", "./uploads"],
                        )
                    )
                    body = (
                        search_context
                        if search_context and len(search_context) > 80
                        else "Documento generado por Aiko."
                    )
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    creator.create_word(
                        path=full_path,
                        title="Guía de dieta saludable para perder peso",
                        content=body.strip(),
                        images=list(self._turn_images),
                    )
                    logger.info(f"✅ AUTO-WRITE WORD: {full_path}")
                    result["response"] = (
                        str(result.get("response", "")).strip()
                        + f"\n\n✅ Documento Word guardado en:\n{full_path}"
                    ).strip()
                    result["metadata"]["auto_write_word"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write Word: {e}")

            return result

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "response": "Lo siento, tuve un error procesando tu mensaje.",
            }


_agent_instance = None


async def get_agent() -> AikoAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AikoAgent()
    return _agent_instance