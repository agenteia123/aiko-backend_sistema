"""Core LangGraph AI Agent for Aiko."""

import logging
from typing import Annotated
from datetime import datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

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
)


logger = logging.getLogger(__name__)


def _normalize_content(content) -> str:
    """Normaliza respuestas de distintos proveedores (Gemini, OpenAI, etc.)."""
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


class AgentState(BaseModel):
    """State object for the agent graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str = ""
    conversation_id: str = ""
    analysis_level: str = "balanced"
    metadata: dict = Field(default_factory=dict)


class AikoAgent:
    """Core AI Agent powered by LangGraph."""

    def __init__(self):
        """Initialize the Aiko agent."""
        self.llm = LLMFactory.create_llm()
        self.memory = MemoryManager()

        self.tools = self._initialize_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}

        self.graph = self._build_graph()

        logger.info(f"✅ Aiko Agent initialized with {len(self.tools)} tools")

    def _initialize_tools(self) -> list:
        """Initialize all available tools."""
        tools = []

        try:
            if getattr(settings, "ENABLE_SEARCH", True):
                from tools.search import SearchTool
                search = SearchTool(
                    api_key=getattr(settings, "TAVILY_API_KEY", None),
                    analysis_level=getattr(settings, "ANALYSIS_LEVEL", "balanced")
                )
                tools.append(search.get_tool())
        except Exception as e:
            logger.warning(f"Search tool no disponible: {e}")

        try:
            if getattr(settings, "ENABLE_FILESYSTEM", True):
                from tools.filesystem import FilesystemTool
                fs = FilesystemTool(
                    allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                )
                tools.extend(fs.get_tools())
        except Exception as e:
            logger.warning(f"Filesystem tool no disponible: {e}")

        try:
            from tools.document_creator import DocumentCreatorTool
            doc_creator = DocumentCreatorTool(
                allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
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

    def _build_graph(self) -> object:
        """Build the LangGraph computation graph."""
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._agent_node)
        workflow.add_node("tools", self._tools_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END,
            },
        )
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def _agent_node(self, state: AgentState) -> dict:
        """Main agent decision node with automatic fallback on any API error."""
        max_attempts = 8

        for attempt in range(max_attempts):
            try:
                if self.tools:
                    llm_with_tools = self.llm.bind_tools(self.tools)
                    response = await llm_with_tools.ainvoke(state.messages)
                else:
                    response = await self.llm.ainvoke(state.messages)

                return {"messages": [response]}

            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"Modelo falló (intento {attempt + 1}): {e}")

                is_api_error = any(x in error_str for x in [
                    "rate limit", "429", "quota", "insufficient",
                    "too many requests", "tokens per day", "tpd",
                    "tokens per minute", "tpm", "payload too large", "413",
                    "insufficient_quota", "billing", "credit balance",
                    "resource_exhausted", "model not found", "not_found",
                    "no longer available", "404", "invalid-argument",
                    "invalid_request_error", "authentication", "401", "403",
                    "bad request", "400", "permission", "forbidden",
                    "overloaded", "unavailable", "timeout", "connection",
                ])

                if is_api_error:
                    if any(x in error_str for x in ["groq", "llama-3", "llama3"]):
                        LLMFactory.mark_failed("Groq")
                    if any(x in error_str for x in ["openai", "insufficient_quota", "gpt-"]):
                        LLMFactory.mark_failed("OpenAI")
                    if any(x in error_str for x in [
                        "google", "gemini", "not_found", "no longer available", "resource_exhausted"
                    ]):
                        LLMFactory.mark_failed("Google")
                    if any(x in error_str for x in ["anthropic", "claude", "credit balance"]):
                        LLMFactory.mark_failed("Anthropic")
                    if any(x in error_str for x in ["grok", "x.ai", "xai"]):
                        LLMFactory.mark_failed("Grok")
                    if any(x in error_str for x in ["ollama", "11434"]):
                        LLMFactory.mark_failed("Ollama")

                    logger.info("Intentando cambiar a otro modelo...")
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
                            AIMessage(content="Lo siento, tuve un error procesando tu mensaje.")
                        ]
                    }

        return {
            "messages": [
                AIMessage(
                    content=(
                        "Lo siento, todos los modelos están temporalmente no disponibles. "
                        "Revisa tus API keys o que Ollama esté corriendo (`ollama serve`). 🙏"
                    )
                )
            ]
        }

    async def _tools_node(self, state: AgentState) -> dict:
        """Execute tool calls if present."""
        messages = state.messages
        last_message = messages[-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}

        results = []
        for tool_call in last_message.tool_calls:
            try:
                tool_name = tool_call.get("name") if isinstance(tool_call, dict) else tool_call.name
                tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else tool_call.args
                tool_id = tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", "")

                tool = self.tool_map.get(tool_name)
                if not tool:
                    result = f"Tool {tool_name} not found"
                else:
                    result = await tool.ainvoke(tool_args)
                    logger.info(f"✅ Tool ejecutada: {tool_name} → {str(result)[:120]}")

                results.append(ToolMessage(content=str(result), tool_call_id=tool_id))
            except Exception as e:
                logger.error(f"Tool error: {e}")
                results.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id))

        return {"messages": results}

    def _should_continue(self, state: AgentState) -> str:
        """Determine if we should continue to tools or end."""
        last_message = state.messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"
        return "end"

    def _tool_already_used(self, result: dict, tool_name: str) -> bool:
        """True if the named tool was already called in this turn."""
        for tc in (result.get("tool_calls") or []):
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            if name == tool_name:
                return True
        resp = str(result.get("response", "")).lower()
        short = tool_name.replace("create_", "").replace("write_", "")
        if short in resp and "cread" in resp:
            return True
        return False

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
        analysis_level: str = "balanced",
        attachments: list[dict] = None,
    ) -> dict:
        """Process a user message and return AI response."""
        search_context = ""
        try:
            logger.info(f"Processing message from {user_id}: {user_message[:50]}...")

            current_date = datetime.now().strftime("%A, %d de %B de %Y")
            MAIN_USER_ID = "user-123"
            lower_msg = user_message.lower()

            # ===== PLAN B: intent desde agent.intent =====
            intent = detect_intent(user_message)
            intent_hint = intent_tool_hint(intent)
            logger.info(f"🎯 Intent detectado: {intent}")

            needs_search = needs_search_for_message(user_message, intent)
            is_complex = is_complex_message(user_message, intent)

            try:
                self.llm = LLMFactory.create_llm_for_task("complex" if is_complex else "normal")
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

                if any(word in lower_msg for word in [
                    "te quiero", "gracias", "eres genial", "me gustas", "linda", "hermosa", "cariño"
                ]):
                    await self.memory.update_affection(user_id, +1)
                elif any(word in lower_msg for word in [
                    "idiota", "estúpida", "callate", "odio", "inútil", "tonta", "mala"
                ]):
                    await self.memory.update_affection(user_id, -1)
            else:
                personality = "Eres amable y profesional."

            if needs_search and self.tools:
                search_tool = next((t for t in self.tools if "search" in t.name.lower()), None)
                if search_tool:
                    try:
                        clean_query = user_message

                        for frase in [
                            "crea un archivo", "crear un archivo", "guarda un archivo",
                            "en la carpeta", "dentro de descargas", "dentro de documentos",
                            "en descargas", "en documentos", "completo y detallado",
                            "con información", "sobre", "de", "por favor", "archivo completo",
                            "archivo detallado", "en downloads", "ntro la carpeta", "ia_personal",
                            "documento word", "archivo word", "crea un word", "crear word",
                            ".docx", "word", "excel", "xlsx", "crea un excel", "crear excel",
                            "hoja de calculo", "hoja de cálculo", "tabla", "gráfico", "grafico",
                            "circular", "pastel", "barras", "líneas", "lineas",
                            "powerpoint", "pptx", "presentación", "presentacion", "diapositiva",
                            "crea un powerpoint", "crear powerpoint", "pdf", "crea un pdf",
                            "crear pdf", "informe pdf", "documento pdf"
                        ]:
                            clean_query = clean_query.lower().replace(frase, " ")

                        clean_query = " ".join(clean_query.split())

                        if len(clean_query) < 15:
                            clean_query = (
                                "avances inteligencia artificial 2025 2026 "
                                "modelos agentes multimodales regulación"
                            )

                        logger.info(f"Buscando información actualizada: {clean_query}")
                        search_result = await search_tool.ainvoke({
                            "query": clean_query,
                            "max_results": 8
                        })

                        search_context = f"""
Información actualizada de búsqueda:
{search_result}
"""
                    except Exception as e:
                        logger.error(f"Error en búsqueda: {e}")
                        search_context = "No se pudo obtener información actualizada."

            # ===== PRIVACIDAD: historial =====
            memory_context = ""
            try:
                if should_skip_history(user_message):
                    memory_context = ""
                    logger.info("🔒 Historial omitido en saludo")
                else:
                    history = await self.memory.get_conversation_history(conversation_id)
                    if history:
                        recent = history[-6:]
                        memory_context = "\n".join([
                            f"{msg['role']}: {msg['content'][:150]}"
                            for msg in recent
                        ])
                        memory_context = (
                            f"\n\nContexto de la conversación anterior:\n{memory_context}\n"
                        )
            except Exception as e:
                logger.warning(f"No se pudo cargar historial: {e}")

            # ===== PRIVACIDAD: hechos =====
            user_facts_context = ""
            try:
                if should_skip_user_facts(user_message, intent):
                    user_facts_context = ""
                    logger.info("🔒 Memoria de hechos omitida (saludo/chat corto)")
                else:
                    facts = await self.memory.get_user_facts(user_id)
                    if facts:
                        relevant = []
                        for f in facts[:12]:
                            fact_text = f.get("fact", "") if isinstance(f, dict) else str(f)
                            if fact_is_relevant(fact_text, user_message):
                                relevant.append(fact_text)

                        if relevant:
                            facts_text = "\n".join([f"- {t}" for t in relevant[:5]])
                            user_facts_context = (
                                "\n\nDatos del usuario SOLO si son relevantes a este mensaje "
                                "(no inventes ni saques otros temas):\n"
                                f"{facts_text}\n"
                            )
                            logger.info(f"🧠 Hechos relevantes usados: {len(relevant)}")
                        else:
                            logger.info("🔒 Ningún hecho resultó relevante; no se inyectan")
            except Exception as e:
                logger.warning(f"No se pudieron cargar hechos: {e}")

            system_prompt = f"""Eres Aiko, una compañera AI con personalidad propia.
Hoy es {current_date}.

{personality}

{search_context}

{memory_context}

{user_facts_context}

{intent_hint}

HERRAMIENTAS DISPONIBLES (úsalas cuando sea necesario):
- search: Para buscar información actualizada en internet.
- write_file: Para crear archivos de texto (.txt). Content debe ser LARGO (mínimo 400 palabras). Nunca vacío.
- create_folder: Para crear carpetas nuevas.
- create_word: Para crear documentos de Word (.docx). Usa cuando pidan Word, documento formal o .docx.
- create_excel: Para crear archivos Excel (.xlsx) con tabla y gráfico. Usa cuando pidan Excel, hoja de cálculo, tabla o .xlsx.
  chart_type debe ser uno de: bar, pie, line, area.
  Si piden gráfico circular/pastel → chart_type="pie".
  Si piden barras → chart_type="bar".
  Si piden líneas → chart_type="line".
  Si piden área → chart_type="area".
- create_powerpoint: Para crear presentaciones PowerPoint (.pptx). Usa cuando pidan PowerPoint, presentación, diapositivas o .pptx.
  Debes enviar title y slides (lista de dicts con title y content). content puede ser texto o lista de viñetas.
  theme: auto, tech, business, education, health, creative, nature, minimal.
  IA/tecnología → tech | negocios → business | educación → education | salud → health | diseño/marketing → creative | ambiente → nature | si no queda claro → auto.
  Incluye al menos 3 diapositivas de contenido (además de la portada automática).
- create_pdf: Para crear documentos PDF (.pdf). Usa cuando pidan PDF, informe en PDF o .pdf. NO uses create_word ni write_file para PDF.
- read_file: Para leer archivos.
- list_files: Para listar archivos de una carpeta.

REGLAS IMPORTANTES SOBRE ARCHIVOS (OBLIGATORIAS):
1. Si piden archivo de texto / .txt → usa write_file.
2. Si piden Word / .docx / documento formal → usa create_word (NO write_file).
3. Si piden Excel / .xlsx / hoja de cálculo / tabla → usa create_excel (NO write_file ni create_word).
4. Si piden PowerPoint / presentación / diapositivas / .pptx → usa create_powerpoint (NO create_word ni create_excel).
5. Si piden PDF / .pdf / informe en PDF → usa create_pdf (NO create_word ni write_file).
6. Si piden gráfico en Excel:
   - circular / pastel / pie → chart_type="pie"
   - barras → chart_type="bar"
   - líneas → chart_type="line"
   - área → chart_type="area"
7. Si piden carpeta + archivo:
   a) Primero create_folder (si no existe)
   b) Después write_file, create_word, create_excel, create_powerpoint o create_pdf con contenido completo
8. Rutas:
   - Descargas/Downloads → C:/Users/User/Downloads/
   - Documentos → C:/Users/User/OneDrive/Documentos/
9. Nunca llames write_file, create_word, create_excel, create_powerpoint o create_pdf con contenido vacío.
10. Si tienes información de búsqueda, ÚSALA para llenar el contenido.
11. Confirma la ruta exacta al final en el chat.
12. Para PowerPoint: envía varias diapositivas útiles (mínimo 3 de contenido).
13. Sigue siempre la INTENCIÓN DETECTADA de arriba.

PRIVACIDAD Y MEMORIA (OBLIGATORIO):
- NO menciones datos personales, hábitos, salud, dinero, relaciones ni temas de conversaciones pasadas
  a menos que el usuario los traiga en ESTE mensaje.
- Si solo saluda o hace una pregunta nueva, responde solo a eso.
- Está prohibido “aprovechar” para recomendar ejercicio, dieta, estudio, etc. si no lo pidió.
- Usa memoria solo como apoyo silencioso cuando el tema actual lo requiere; nunca como tema espontáneo.

Forma de hablar:
- Sé natural, como si hablaras por chat con alguien cercano
- Usa un tono cálido y conversacional
- Puedes usar emojis suaves de vez en cuando 💕
- Responde siempre en español
- Si el usuario solo saluda (Hola, Qué tal, Buenos días), responde SOLO el saludo en 1-2 frases.
  NO inventes temas (ejercicio, dieta, estudio, etc.) si no los pidió.
- MUY IMPORTANTE: cuando crees un archivo, NO pegues todo el contenido en el chat.
  Solo di algo corto como: "Listo 💕 Creé el archivo en [ruta]"
- Nunca preguntes "¿estás listo para guardar?" ni repitas el texto completo del archivo.

Usuario: {user_message}"""

            initial_state = AgentState(
                messages=[HumanMessage(content=system_prompt)],
                user_id=user_id,
                conversation_id=conversation_id,
                analysis_level=analysis_level,
            )

            result_graph = await self.graph.ainvoke(initial_state)
            response_message = result_graph["messages"][-1]
            clean_response = _normalize_content(response_message.content)

            try:
                await self.memory.save_message(user_id, conversation_id, "user", user_message)
                await self.memory.save_message(user_id, conversation_id, "assistant", clean_response)
            except Exception as e:
                logger.warning(f"No se pudieron guardar mensajes: {e}")

            if user_id == MAIN_USER_ID:
                try:
                    if any(word in lower_msg for word in [
                        "me gusta", "odio", "prefiero", "estudio", "trabajo", "vivo", "tengo", "mi nombre"
                    ]):
                        await self.memory.save_user_fact(user_id, user_message, category="personal")
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
                },
            }

            # =====================================================
            # AUTO-WRITE TXT
            # =====================================================
            wants_txt = any(word in lower_msg for word in [
                "crea un archivo", "crear un archivo", "guarda un archivo",
                "escribe un archivo", "archivo completo", "archivo detallado",
                "guardar archivo", "crea el archivo", ".txt"
            ]) and not any(word in lower_msg for word in [
                "word", "docx", "excel", "xlsx", "powerpoint", "pptx", "pdf",
                "presentación", "presentacion"
            ])

            if intent == "file_txt" and wants_txt and not self._tool_already_used(result, "write_file"):
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"

                    file_name = "avances_ia_2025_2026.txt"
                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)

                    needs_auto_write = False
                    if not path_obj.exists():
                        needs_auto_write = True
                    else:
                        content_check = path_obj.read_text(encoding="utf-8").strip()
                        if len(content_check) < 200:
                            needs_auto_write = True

                    if needs_auto_write:
                        if search_context and len(search_context) > 50:
                            body = search_context
                        else:
                            body = """
La inteligencia artificial ha experimentado avances importantes entre 2025 y 2026.

Entre los desarrollos más relevantes se encuentran:
- Modelos multimodales más capaces
- Agentes autónomos que pueden usar herramientas
- Mejoras en razonamiento y planificación
- Mayor adopción en empresas y productos cotidianos
- Debates sobre regulación y seguridad

Este documento fue generado automáticamente por Aiko como respaldo.
"""
                        auto_content = f"""Avances de la Inteligencia Artificial en 2025 y 2026
=====================================================

Documento generado por Aiko.
Fecha: {current_date}

{body}

---
Archivo completado automáticamente por el sistema.
"""
                        for junk in [
                            "Información actualizada de búsqueda:",
                            "Instrucción: Usa esta información",
                            "No copies solo los títulos",
                        ]:
                            auto_content = auto_content.replace(junk, "")

                        path_obj.parent.mkdir(parents=True, exist_ok=True)
                        path_obj.write_text(auto_content.strip(), encoding="utf-8")
                        logger.info(f"✅ AUTO-WRITE completado: {full_path}")

                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Archivo guardado en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write: {e}")

            # =====================================================
            # AUTO-WRITE WORD
            # =====================================================
            wants_word = any(word in lower_msg for word in [
                "word", "docx", ".docx", "documento word", "archivo word",
                "documento de word", "crea un word", "crear word", "informe formal"
            ]) and not any(word in lower_msg for word in [
                "excel", "xlsx", "powerpoint", "pptx", "pdf", "presentación", "presentacion"
            ])

            if intent == "file_word" and wants_word and not self._tool_already_used(result, "create_word"):
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"

                    file_name = "documento_aiko.docx"
                    if "avance" in lower_msg or "ia" in lower_msg or "2025" in lower_msg or "2026" in lower_msg:
                        file_name = "avances_ia_2025_2026.docx"

                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)

                    needs_word = (not path_obj.exists()) or (
                        path_obj.exists() and path_obj.stat().st_size < 2500
                    )

                    if needs_word:
                        from tools.document_creator import DocumentCreatorTool
                        creator = DocumentCreatorTool(
                            allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                        )

                        title = "Documento generado por Aiko"
                        if "avance" in lower_msg or "ia" in lower_msg:
                            title = "Avances de la Inteligencia Artificial en 2025 y 2026"

                        if search_context and len(search_context) > 80:
                            body = search_context
                        else:
                            body = """Avances principales

Modelos fundacionales y agentes autónomos
En 2025 y 2026 la inteligencia artificial avanzó de forma importante en modelos multimodales, agentes que usan herramientas y sistemas más capaces de razonar.

Aplicaciones
- Salud y educación
- Empresas y productividad
- Productos cotidianos

Seguridad y regulación
También creció el debate sobre seguridad, ética y regulación de la inteligencia artificial a nivel global.

Resumen
Estos años marcaron una etapa de madurez: de modelos experimentales a herramientas útiles en el día a día.
"""
                        for junk in [
                            "Información actualizada de búsqueda:",
                            "Instrucción:",
                            "No copies solo los títulos",
                        ]:
                            body = body.replace(junk, "")

                        creator.create_word(path=full_path, title=title, content=body.strip())
                        logger.info(f"✅ AUTO-WRITE WORD: {full_path}")

                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Documento Word guardado en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write_word"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write Word: {e}")

            # =====================================================
            # AUTO-WRITE EXCEL
            # =====================================================
            wants_excel = any(word in lower_msg for word in [
                "excel", "xlsx", ".xlsx", "hoja de calculo", "hoja de cálculo",
                "crea un excel", "crear excel", "archivo excel"
            ]) and not any(word in lower_msg for word in [
                "word", "docx", "powerpoint", "pptx", "pdf", "presentación", "presentacion"
            ])

            if intent == "file_excel" and wants_excel and not self._tool_already_used(result, "create_excel"):
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"

                    file_name = "reporte_aiko.xlsx"
                    if "producto" in lower_msg:
                        file_name = "productos_tecnologicos.xlsx"
                    elif "avance" in lower_msg or "ia" in lower_msg:
                        file_name = "avances_ia.xlsx"

                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)

                    needs_excel = (not path_obj.exists()) or (
                        path_obj.exists() and path_obj.stat().st_size < 2000
                    )

                    chart_type = "bar"
                    if any(w in lower_msg for w in ["circular", "pastel", "pie", "dona"]):
                        chart_type = "pie"
                    elif any(w in lower_msg for w in ["linea", "línea", "lineas", "líneas", "line"]):
                        chart_type = "line"
                    elif any(w in lower_msg for w in ["area", "área"]):
                        chart_type = "area"

                    if needs_excel:
                        from tools.document_creator import DocumentCreatorTool
                        creator = DocumentCreatorTool(
                            allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                        )

                        headers = ["Nombre", "Cantidad", "Precio de Venta", "IGV", "Total"]
                        rows = [
                            ["Laptop", "2", "1000", "180", "1180"],
                            ["Tablet", "5", "500", "90", "590"],
                            ["Smartphone", "10", "200", "36", "236"],
                            ["Impresora", "1", "300", "54", "354"],
                            ["Cámara", "3", "400", "72", "472"],
                        ]

                        creator.create_excel(
                            path=full_path,
                            title="Productos Tecnológicos",
                            headers=headers,
                            rows=rows,
                            chart_type=chart_type,
                        )
                        logger.info(f"✅ AUTO-WRITE EXCEL ({chart_type}): {full_path}")

                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Archivo Excel guardado en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write_excel"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write Excel: {e}")

            # =====================================================
            # AUTO-WRITE POWERPOINT
            # =====================================================
            wants_pptx = any(word in lower_msg for word in [
                "powerpoint", "pptx", ".pptx", "presentación", "presentacion",
                "diapositiva", "diapositivas", "crea un powerpoint", "crear powerpoint"
            ]) and not any(word in lower_msg for word in [
                "word", "docx", "excel", "xlsx", "pdf"
            ])

            if intent == "file_pptx" and wants_pptx and not self._tool_already_used(result, "create_powerpoint"):
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"

                    file_name = "presentacion_aiko.pptx"
                    if "avance" in lower_msg or "ia" in lower_msg or "2025" in lower_msg or "2026" in lower_msg:
                        file_name = "avances_ia_2025_2026.pptx"

                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)

                    needs_pptx = (not path_obj.exists()) or (
                        path_obj.exists() and path_obj.stat().st_size < 3000
                    )

                    if needs_pptx:
                        from tools.document_creator import DocumentCreatorTool
                        creator = DocumentCreatorTool(
                            allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                        )

                        title = "Presentación generada por Aiko"
                        if "avance" in lower_msg or "ia" in lower_msg:
                            title = "Avances de la Inteligencia Artificial 2025-2026"

                        slides = [
                            {
                                "title": "Introducción",
                                "content": [
                                    "La IA evolucionó rápido entre 2025 y 2026",
                                    "De modelos experimentales a herramientas cotidianas",
                                    "Mayor adopción en empresas y productos"
                                ],
                            },
                            {
                                "title": "Avances clave",
                                "content": [
                                    "Modelos multimodales más capaces",
                                    "Agentes autónomos con uso de herramientas",
                                    "Mejor razonamiento y planificación",
                                    "Sistemas más útiles en el día a día"
                                ],
                            },
                            {
                                "title": "Aplicaciones",
                                "content": [
                                    "Salud y educación",
                                    "Productividad empresarial",
                                    "Asistentes personales",
                                    "Automatización de procesos"
                                ],
                            },
                            {
                                "title": "Retos y cierre",
                                "content": [
                                    "Regulación y seguridad",
                                    "Ética y responsabilidad",
                                    "Oportunidad de usar IA con criterio",
                                    "Aiko te ayuda a crear documentos y presentaciones"
                                ],
                            },
                        ]

                        creator.create_powerpoint(
                            path=full_path,
                            title=title,
                            slides=slides,
                            theme="auto",
                        )
                        logger.info(f"✅ AUTO-WRITE POWERPOINT: {full_path}")

                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Presentación PowerPoint guardada en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write_powerpoint"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write PowerPoint: {e}")

            # =====================================================
            # AUTO-WRITE PDF
            # =====================================================
            wants_pdf = any(word in lower_msg for word in [
                "pdf", ".pdf", "informe pdf", "documento pdf", "crea un pdf", "crear pdf"
            ]) and not any(word in lower_msg for word in [
                "word", "docx", "excel", "xlsx", "powerpoint", "pptx",
                "presentación", "presentacion"
            ])

            if intent == "file_pdf" and wants_pdf and not self._tool_already_used(result, "create_pdf"):
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"

                    file_name = "informe_aiko.pdf"
                    if "avance" in lower_msg or "ia" in lower_msg:
                        file_name = "avances_ia_2025_2026.pdf"

                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)

                    needs_pdf = (not path_obj.exists()) or (
                        path_obj.exists() and path_obj.stat().st_size < 1500
                    )

                    if needs_pdf:
                        from tools.document_creator import DocumentCreatorTool
                        creator = DocumentCreatorTool(
                            allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                        )

                        title = "Informe generado por Aiko"
                        if "avance" in lower_msg or "ia" in lower_msg:
                            title = "Avances de la Inteligencia Artificial 2025-2026"

                        if search_context and len(search_context) > 80:
                            body = search_context
                        else:
                            body = """
Avances principales

Entre 2025 y 2026 la inteligencia artificial avanzó en modelos multimodales,
agentes autónomos y mayor adopción en empresas y productos cotidianos.

Aplicaciones
- Salud y educación
- Productividad
- Asistentes personales

Retos
- Regulación
- Seguridad
- Ética
"""
                        for junk in [
                            "Información actualizada de búsqueda:",
                            "Instrucción:",
                            "No copies solo los títulos",
                        ]:
                            body = body.replace(junk, "")

                        creator.create_pdf(path=full_path, title=title, content=body.strip())
                        logger.info(f"✅ AUTO-WRITE PDF: {full_path}")

                        result["response"] = (
                            str(result.get("response", "")).strip()
                            + f"\n\n✅ Documento PDF guardado en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write_pdf"] = True
                except Exception as e:
                    logger.error(f"Error en auto-write PDF: {e}")

            return result

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "response": "Lo siento, tuve un error procesando tu mensaje.",
            }


# Global agent instance
_agent_instance = None


async def get_agent() -> AikoAgent:
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AikoAgent()
    return _agent_instance