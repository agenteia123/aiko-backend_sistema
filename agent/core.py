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

BAD_PDF_MARKERS = [
    "no dispongo",
    "no puedo crear",
    "herramienta para crear",
    "no tengo una herramienta",
    "no puedo generar un pdf",
    "no puedo generar archivos",
    "candidates=",
    "finishreason",
    "malformed",
]


def _safe_delete(*paths: str) -> None:
    for p in paths:
        if not p:
            continue
        try:
            path = Path(p)
            if path.exists() and path.is_file():
                path.unlink()
                logger.info(f"🗑️ Temporal borrado: {path}")
        except Exception as e:
            logger.warning(f"No se pudo borrar temporal {p}: {e}")


def _is_bad_content(text: str) -> bool:
    if not text or len(text.strip()) < 40:
        return True
    low = text.lower()
    return any(m in low for m in BAD_PDF_MARKERS)


def _default_diet_guide() -> str:
    return """Guía de dieta saludable

1. Introducción
Una dieta saludable se basa en equilibrio, variedad y constancia. No se trata de eliminar grupos de alimentos, sino de elegir mejores opciones la mayor parte del tiempo y mantener hábitos sostenibles.

2. Principios básicos
- Come verduras y frutas todos los días
- Prioriza proteínas magras: pollo, pescado, huevos, legumbres, tofu
- Usa carbohidratos complejos: avena, arroz integral, quinoa, papa, pan integral
- Incluye grasas saludables: aguacate, nueces, semillas, aceite de oliva
- Bebe suficiente agua a lo largo del día
- Reduce ultraprocesados, bebidas azucaradas y azúcares añadidos

3. Cómo armar un plato equilibrado
- 1/2 del plato: vegetales
- 1/4 del plato: proteína
- 1/4 del plato: carbohidratos complejos
- Una porción pequeña de grasa saludable

4. Ejemplo de menú de un día
Desayuno: avena con fruta fresca y yogur natural
Media mañana: un puñado de frutos secos o una fruta
Almuerzo: pollo a la plancha, ensalada variada y arroz integral
Merienda: yogur natural o una fruta
Cena: pescado al horno con vegetales al vapor

5. Hidratación y hábitos
- Toma agua de forma regular
- Duerme entre 7 y 9 horas
- Camina al menos 30 minutos al día
- Evita comer muy tarde en la noche

6. Errores comunes
- Saltarse comidas
- Hacer dietas extremas de muy pocas calorías
- Eliminar por completo un grupo de alimentos sin supervisión
- No planificar comidas simples
- Confundir “comer sano” con “comer perfecto”

7. Consejos prácticos para empezar
- Prepara comidas 1 o 2 veces por semana
- Lleva snacks saludables cuando salgas
- Lee etiquetas de productos
- Cocina de forma simple: plancha, horno, vapor
- Mide el progreso por energía, digestión y constancia, no solo por la báscula

8. Conclusión
Una buena dieta es sostenible. Empieza con cambios pequeños, realistas y mantenibles. La constancia importa más que la perfección."""


def _default_generic_guide() -> str:
    return """Documento generado por Aiko

1. Introducción
Este documento resume el tema solicitado de forma clara y práctica.

2. Puntos clave
- Define el objetivo
- Organiza la información en secciones
- Aplica recomendaciones accionables

3. Desarrollo
Revisa el contexto, identifica lo esencial y prioriza pasos concretos que se puedan aplicar de inmediato.

4. Recomendaciones prácticas
- Empieza por lo más simple
- Mide resultados
- Ajusta según necesidad

5. Conclusión
Con estructura y constancia se obtienen mejores resultados a largo plazo."""


def _write_simple_pdf(path: str, title: str, content: str) -> None:
    """Genera un PDF básico con reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.colors import HexColor

    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path_obj),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleES",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        spaceAfter=8,
        fontSize=18,
        textColor=HexColor("#1a1a1a"),
    )
    heading_style = ParagraphStyle(
        "HeadingES",
        parent=styles["Heading2"],
        alignment=TA_LEFT,
        spaceBefore=14,
        spaceAfter=6,
        fontSize=13,
        textColor=HexColor("#222222"),
    )
    body_style = ParagraphStyle(
        "BodyES",
        parent=styles["Normal"],
        alignment=TA_JUSTIFY,
        fontSize=11,
        leading=15,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "BulletES",
        parent=styles["Normal"],
        leftIndent=12,
        fontSize=11,
        leading=15,
        spaceAfter=3,
    )

    story = []
    story.append(Paragraph(title.replace("\n", " "), title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#cccccc")))
    story.append(Spacer(1, 0.4 * cm))

    text = (content or "").strip()
    if _is_bad_content(text):
        text = _default_diet_guide() if "dieta" in title.lower() or "dieta" in text.lower() else _default_generic_guide()

    for block in text.split("\n"):
        line = block.strip()
        if not line:
            story.append(Spacer(1, 0.15 * cm))
            continue
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        # Títulos tipo "1. Introducción"
        if re.match(r"^\d+\.\s+\S+", line) and len(line) < 80:
            story.append(Paragraph(safe, heading_style))
        elif line.startswith("- "):
            story.append(Paragraph("• " + safe[2:], bullet_style))
        else:
            story.append(Paragraph(safe, body_style))

    doc.build(story)

    if not path_obj.exists() or path_obj.stat().st_size < 100:
        raise FileNotFoundError(f"PDF no escrito: {path_obj}")


def _normalize_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        text = content.strip()
        if "candidates=" in text or "FinishReason" in text:
            return "Listo. Si pediste un documento, revisa el enlace de descarga."
        return text
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
                llm_type = getattr(self.llm, "_llm_type", "")
                if active and llm_type != "gemini-google-genai":
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
                        "respuesta vacía",
                        "malformed",
                    ]
                )
                if is_api_error:
                    if any(x in error_str for x in ["groq", "llama-3", "llama3", "gpt-oss"]):
                        LLMFactory.mark_failed("Groq")
                    elif any(
                        x in error_str
                        for x in ["openai", "insufficient_quota", "gpt-4", "gpt-3"]
                    ) and "gpt-oss" not in error_str:
                        LLMFactory.mark_failed("OpenAI")
                    elif any(
                        x in error_str
                        for x in ["google", "gemini", "generativelanguage", "respuesta vacía"]
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
                        "Inténtalo de nuevo en un momento. 🙏"
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
                    results.append(
                        ToolMessage(
                            content="Error: tool no permitida en este turno.",
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
                    if self._turn_images:
                        tool_args["images"] = list(self._turn_images)
                    else:
                        tool_args["images"] = []

                tool = active_map.get(tool_name) or self.tool_map.get(tool_name)
                if not tool:
                    result = f"Tool {tool_name} not found"
                else:
                    result = await tool.ainvoke(tool_args)
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
        return str((Path("data") / "documents").resolve())

    def _clean_search_query(self, user_message: str, lower_msg: str) -> str:
        trash = [
            "crea un pdf",
            "crear un pdf",
            "hazme un pdf",
            "hacer un pdf",
            "por favor",
            "incluye la imagen",
            "incluye la foto",
        ]
        cq = user_message.lower()
        for frase in trash:
            cq = cq.replace(frase, " ")
        cq = re.sub(r"\s+", " ", cq).strip()
        if len(cq) < 12 and "dieta" in lower_msg:
            return "dieta saludable guía completa"
        return cq or user_message[:200]

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

            self._active_tools = self._tools_for_intent(intent)

            if is_simple_greeting(user_message) or len(user_message.strip()) < 40:
                self._active_tools = []
                logger.info("🔒 Tools desactivadas (saludo / mensaje corto)")

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

            needs_search = needs_search_for_message(user_message, intent)
            is_complex = is_complex_message(user_message, intent)
            use_complex = is_complex or intent.startswith("file_") or intent == "folder"

            try:
                self.llm = LLMFactory.create_llm_for_task(
                    "complex" if use_complex else "normal"
                )
                if use_complex:
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
                    for word in ["te quiero", "gracias", "eres genial", "me gustas", "linda", "hermosa", "cariño"]
                ):
                    await self.memory.update_affection(user_id, +1)
                elif any(
                    word in lower_msg
                    for word in ["idiota", "estúpida", "callate", "odio", "inútil", "tonta", "mala"]
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
                        clean_query = self._clean_search_query(user_message, lower_msg)
                        search_result = await search_tool.ainvoke(
                            {"query": clean_query, "max_results": 8}
                        )
                        search_context = f"Información actualizada de búsqueda:\n{search_result}"
                    except Exception as e:
                        logger.error(f"Error en búsqueda: {e}")

            memory_context = ""
            try:
                if not should_skip_history(user_message):
                    history = await self.memory.get_conversation_history(conversation_id)
                    if history:
                        recent = history[-6:]
                        memory_context = "\n".join(
                            [f"{msg['role']}: {msg['content'][:150]}" for msg in recent]
                        )
                        memory_context = f"\n\nContexto anterior:\n{memory_context}\n"
            except Exception as e:
                logger.warning(f"No se pudo cargar historial: {e}")

            user_facts_context = ""
            try:
                if not should_skip_user_facts(user_message, intent) and not intent.startswith("file_"):
                    facts = await self.memory.get_user_facts(user_id)
                    if facts:
                        relevant = []
                        for f in facts[:12]:
                            fact_text = f.get("fact", "") if isinstance(f, dict) else str(f)
                            if fact_is_relevant(fact_text, user_message):
                                relevant.append(fact_text)
                        if relevant:
                            facts_text = "\n".join([f"- {t}" for t in relevant[:5]])
                            user_facts_context = f"\n\nDatos del usuario relevantes:\n{facts_text}\n"
            except Exception as e:
                logger.warning(f"No se pudieron cargar hechos: {e}")

            search_block = search_context if search_context else "Usa conocimiento general fiable."

            file_pdf_rules = ""
            if intent == "file_pdf":
                file_pdf_rules = """
IMPORTANTE (creación de PDF):
- El sistema generará el PDF automáticamente.
- NO digas que no puedes crear PDF ni que no tienes herramientas.
- Escribe el CONTENIDO COMPLETO de la guía en español.
- Usa secciones numeradas, consejos prácticos y texto útil.
- No pidas al usuario que copie el texto a otro programa.
"""

            file_ban = ""
            if not (intent.startswith("file_") or intent == "folder"):
                file_ban = "\nPROHIBIDO crear archivos en este turno. Responde solo en texto.\n"

            if is_simple_greeting(user_message) or len(user_message.strip()) < 40:
                system_prompt = f"""Eres Aiko, una compañera AI amable y cercana.
Hoy es {current_date}.
Responde en español, breve y natural. No uses herramientas.

Usuario: {user_message}"""
            else:
                system_prompt = f"""Eres Aiko, una compañera AI con personalidad propia.
Hoy es {current_date}.

{personality}

{search_block}

{memory_context}

{user_facts_context}

{intent_hint}
{file_pdf_rules}
{file_ban}

Responde en español, claro y útil.
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
                await self.memory.save_message(user_id, conversation_id, "user", user_message)
                await self.memory.save_message(user_id, conversation_id, "assistant", clean_response)
            except Exception as e:
                logger.warning(f"No se pudieron guardar mensajes locales: {e}")

            try:
                from core.supabase_client import save_message as sb_save_message

                sb_save_message(conversation_id, user_id, "user", user_message)
                sb_save_message(conversation_id, user_id, "assistant", clean_response)
            except Exception as e:
                logger.warning(f"Supabase save_message: {e}")

            if user_id == MAIN_USER_ID:
                try:
                    if (
                        not is_quiz_message(user_message)
                        and not is_simple_greeting(user_message)
                        and not intent.startswith("file_")
                        and any(
                            word in lower_msg
                            for word in [
                                "me gusta", "odio", "prefiero", "estudio", "trabajo",
                                "vivo", "tengo", "mi nombre", "soy ", "recuerda",
                            ]
                        )
                    ):
                        await self.memory.save_user_fact(user_id, user_message, category="personal")
                        try:
                            from core.supabase_client import save_user_fact as sb_fact
                            sb_fact(user_id, user_message, category="personal")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"No se pudo guardar hecho: {e}")

            # Si el modelo dijo que no puede crear PDF, limpiar respuesta al usuario
            chat_response = clean_response
            if intent == "file_pdf" and _is_bad_content(clean_response):
                chat_response = (
                    "¡Listo! Estoy generando tu PDF con la guía completa. "
                    "En un momento tendrás el enlace de descarga. 📄"
                )

            result = {
                "success": True,
                "response": chat_response,
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
                    "word", "docx", "excel", "xlsx", "powerpoint", "pptx",
                    "presentación", "presentacion",
                ]
            )

            if (
                intent == "file_pdf"
                and wants_pdf
                and not self._tool_already_used(result, "create_pdf")
            ):
                try:
                    target_dir = Path(target_folder)
                    target_dir.mkdir(parents=True, exist_ok=True)

                    filename = "informe_aiko.pdf"
                    title = "Documento generado por Aiko"
                    if "dieta" in lower_msg:
                        filename = "dieta_saludable.pdf"
                        title = "Guía de dieta saludable"

                    path_obj = (target_dir / filename).resolve()
                    full_path = str(path_obj)

                    # Elegir contenido útil
                    body = ""
                    if not _is_bad_content(clean_response) and len(clean_response.strip()) > 120:
                        body = clean_response.strip()
                    elif search_context and len(search_context) > 80:
                        body = search_context.strip()
                    elif "dieta" in lower_msg:
                        body = _default_diet_guide()
                    else:
                        body = _default_generic_guide()

                    _write_simple_pdf(path=full_path, title=title, content=body)

                    logger.info(
                        f"✅ AUTO-WRITE PDF: {full_path} ({path_obj.stat().st_size} bytes)"
                    )

                    download_note = "\n\n✅ PDF creado."
                    try:
                        from core.supabase_client import upload_document

                        up = upload_document(
                            local_path=full_path,
                            filename=path_obj.name,
                            file_type="pdf",
                            external_user_id=user_id,
                            conversation_id=conversation_id,
                            title=title,
                        )
                        if up and up.get("public_url"):
                            url = up["public_url"].rstrip("?")
                            download_note = f"\n\n✅ PDF listo. Descárgalo aquí:\n{url}"
                            result["metadata"]["document_url"] = url
                            _safe_delete(full_path, *list(self._turn_images))
                        else:
                            download_note = (
                                f"\n\n⚠️ PDF creado pero no se pudo subir a Supabase:\n{full_path}"
                            )
                    except Exception as e:
                        logger.error(f"Error subiendo PDF a Supabase: {e}")
                        download_note = f"\n\n⚠️ Error al subir a Supabase: {e}"

                    result["response"] = (
                        str(result.get("response", "")).strip() + download_note
                    ).strip()
                    result["metadata"]["auto_write_pdf"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write PDF: {e}", exc_info=True)
                    result["response"] = (
                        str(result.get("response", "")).strip()
                        + f"\n\n⚠️ No se pudo generar el PDF: {e}"
                    ).strip()

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