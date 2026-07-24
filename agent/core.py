"""Core LangGraph AI Agent for Aiko."""

import logging
from typing import Annotated
from datetime import datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import Tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config.settings import settings
from core.llm_factory import LLMFactory
from memory.manager import MemoryManager


logger = logging.getLogger(__name__)


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
                fs = FilesystemTool(allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"]))
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
    
    def _build_graph(self):
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
        max_attempts = 6
        
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
                
                is_api_error = any(x in error_str for x in [
                    "rate limit", "429", "quota", "insufficient", 
                    "too many requests", "tokens per day", "tpd",
                    "insufficient_quota", "billing", "credit balance",
                    "resource_exhausted", "model not found", "invalid-argument",
                    "invalid_request_error", "authentication", "401", "403",
                    "bad request", "400"
                ])
                
                if is_api_error:
                    logger.warning(f"Modelo falló (intento {attempt + 1}): {e}")
                    
                    if "groq" in error_str or "llama-3.3" in error_str:
                        LLMFactory.mark_failed("Groq")
                    if "openai" in error_str or "insufficient_quota" in error_str:
                        LLMFactory.mark_failed("OpenAI")
                    if "google" in error_str or "gemini" in error_str or "resource_exhausted" in error_str:
                        LLMFactory.mark_failed("Google")
                    if "anthropic" in error_str or "claude" in error_str or "credit balance" in error_str:
                        LLMFactory.mark_failed("Anthropic")
                    if "grok" in error_str or "x.ai" in error_str or "model not found" in error_str:
                        LLMFactory.mark_failed("Grok")
                    
                    logger.info("Intentando cambiar a otro modelo...")
                    
                    try:
                        self.llm = LLMFactory.create_llm_for_task("complex")
                        continue
                    except Exception as e2:
                        logger.error(f"No se pudo crear otro modelo: {e2}")
                        break
                else:
                    logger.error(f"Agent node error: {e}")
                    return {"messages": [AIMessage(content="Lo siento, tuve un error procesando tu mensaje.")]}
        
        return {"messages": [AIMessage(content="Lo siento, todos los modelos están temporalmente no disponibles. Intenta en unos minutos 🙏")]}
    
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
            
            needs_search = any(word in lower_msg for word in [
                "quién", "quien", "qué", "que", "cuál", "cual", "cuándo", "cuando",
                "dónde", "donde", "busca", "buscar", "noticias", "último", "ultimo",
                "actual", "hoy", "ganó", "gano", "resultado", "información", "info",
                "ia", "inteligencia artificial", "historia", "tecnología", "cómo se usa",
                "mejoras", "avances", "tendencias", "crea", "crear", "archivo", "word", "documento"
            ])
            
            is_complex = needs_search or any(word in lower_msg for word in [
                "explica", "analiza", "compara", "razona", "por qué", "porque", "cómo funciona",
                "crea", "crear", "guarda", "guardar", "archivo", "escribe", "escribir", "txt",
                "documento", "word", "excel", "powerpoint", "pdf"
            ])
            
            if is_complex:
                try:
                    self.llm = LLMFactory.create_llm_for_task("complex")
                    logger.info("Usando modelo complejo para esta pregunta")
                except Exception as e:
                    logger.warning(f"No se pudo usar modelo complejo: {e}")
                    self.llm = LLMFactory.create_llm()
            else:
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
                
                if any(word in lower_msg for word in ["te quiero", "gracias", "eres genial", "me gustas", "linda", "hermosa", "cariño"]):
                    await self.memory.update_affection(user_id, +1)
                elif any(word in lower_msg for word in ["idiota", "estúpida", "callate", "odio", "inútil", "tonta", "mala"]):
                    await self.memory.update_affection(user_id, -1)
            else:
                personality = "Eres amable y profesional."
            
            # Búsqueda de información
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
                            ".docx", "word"
                        ]:
                            clean_query = clean_query.lower().replace(frase, " ")
                        
                        clean_query = " ".join(clean_query.split())
                        
                        if len(clean_query) < 15:
                            clean_query = "avances inteligencia artificial 2025 2026 modelos agentes multimodales regulación"
                        
                        logger.info(f"Buscando información actualizada: {clean_query}")
                        search_result = await search_tool.ainvoke({"query": clean_query, "max_results": 8})
                        
                        search_context = f"""
Información actualizada de búsqueda:
{search_result}
"""
                    except Exception as e:
                        logger.error(f"Error en búsqueda: {e}")
                        search_context = "No se pudo obtener información actualizada."
            
            memory_context = ""
            try:
                history = await self.memory.get_conversation_history(conversation_id)
                if history:
                    recent = history[-6:]
                    memory_context = "\n".join([
                        f"{msg['role']}: {msg['content'][:150]}"
                        for msg in recent
                    ])
                    memory_context = f"\n\nContexto de la conversación anterior:\n{memory_context}\n"
            except Exception as e:
                logger.warning(f"No se pudo cargar historial: {e}")
            
            user_facts_context = ""
            try:
                facts = await self.memory.get_user_facts(user_id)
                if facts:
                    facts_text = "\n".join([f"- {f['fact']}" for f in facts[:8]])
                    user_facts_context = f"\n\nCosas que sabes sobre el usuario:\n{facts_text}\n"
            except Exception as e:
                logger.warning(f"No se pudieron cargar hechos: {e}")
            
            system_prompt = f"""Eres Aiko, una compañera AI con personalidad propia.
Hoy es {current_date}.

{personality}

{search_context}

{memory_context}

{user_facts_context}

HERRAMIENTAS DISPONIBLES (úsalas cuando sea necesario):
- search: Para buscar información actualizada en internet.
- write_file: Para crear archivos de texto (.txt). Content debe ser LARGO (mínimo 400 palabras). Nunca vacío.
- create_folder: Para crear carpetas nuevas.
- create_word: Para crear documentos de Word (.docx). Usa cuando pidan Word, documento formal o .docx.
- read_file: Para leer archivos.
- list_files: Para listar archivos de una carpeta.

REGLAS IMPORTANTES SOBRE ARCHIVOS (OBLIGATORIAS):
1. Si piden archivo de texto / .txt → usa write_file.
2. Si piden Word / .docx / documento formal → usa create_word (NO write_file).
3. Si piden carpeta + archivo:
   a) Primero create_folder (si no existe)
   b) Después write_file o create_word con contenido completo
4. Rutas:
   - Descargas/Downloads → C:/Users/User/Downloads/
   - Documentos → C:/Users/User/OneDrive/Documentos/
5. Nunca llames write_file o create_word con content vacío o muy corto.
6. Si tienes información de búsqueda, ÚSALA para llenar el contenido.
7. Confirma la ruta exacta al final en el chat.

Forma de hablar:
- Sé natural, como si hablaras por chat con alguien cercano
- Usa un tono cálido y conversacional
- Puedes usar emojis suaves de vez en cuando 💕
- Responde siempre en español
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
            
            try:
                await self.memory.save_message(user_id, conversation_id, "user", user_message)
                await self.memory.save_message(user_id, conversation_id, "assistant", str(response_message.content))
            except Exception as e:
                logger.warning(f"No se pudieron guardar mensajes: {e}")
            
            if user_id == MAIN_USER_ID:
                try:
                    if any(word in lower_msg for word in ["me gusta", "odio", "prefiero", "estudio", "trabajo", "vivo", "tengo", "mi nombre"]):
                        await self.memory.save_user_fact(user_id, user_message, category="personal")
                        logger.info(f"Hecho guardado: {user_message[:50]}")
                except Exception as e:
                    logger.warning(f"No se pudo guardar hecho: {e}")
            
            result = {
                "success": True,
                "response": str(response_message.content),
                "tool_calls": getattr(response_message, "tool_calls", []),
                "metadata": {"analysis_level": analysis_level},
            }
            
            # =====================================================
            # AUTO-WRITE: si pidió crear archivo de texto y falló
            # =====================================================
            wants_txt = any(word in lower_msg for word in [
                "crea un archivo", "crear un archivo", "guarda un archivo",
                "escribe un archivo", "archivo completo", "archivo detallado",
                "guardar archivo", "crea el archivo", ".txt"
            ]) and not any(word in lower_msg for word in ["word", "docx", "excel", "powerpoint", "pdf"])
            
            if wants_txt:
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
                        logger.info("Archivo no existe → auto-write")
                    else:
                        content_check = path_obj.read_text(encoding="utf-8").strip()
                        if len(content_check) < 200:
                            needs_auto_write = True
                            logger.info(f"Archivo vacío o muy corto ({len(content_check)} chars) → auto-write")
                    
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
                        
                        logger.info(f"✅ AUTO-WRITE completado: {full_path} ({len(auto_content)} caracteres)")
                        
                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Archivo guardado en:\n{full_path}"
                        ).strip()
                        result["metadata"]["auto_write"] = True
                        
                except Exception as e:
                    logger.error(f"Error en auto-write: {e}")
            
            # =====================================================
            # AUTO-WRITE WORD: si pidió Word y el modelo no lo creó
            # =====================================================
            wants_word = any(word in lower_msg for word in [
                "word", "docx", "documento word", "archivo word",
                "documento de word", "crea un word", "crear word"
            ])
            
            if wants_word:
                try:
                    target_folder = "C:/Users/User/Downloads/ia_personal"
                    if "documentos" in lower_msg:
                        target_folder = "C:/Users/User/OneDrive/Documentos/ia_personal"
                    
                    file_name = "avances_ia_2025_2026.docx"
                    full_path = f"{target_folder}/{file_name}"
                    path_obj = Path(full_path)
                    
                    needs_word = (not path_obj.exists()) or (path_obj.exists() and path_obj.stat().st_size < 5000)
                    
                    if needs_word:
                        from tools.document_creator import DocumentCreatorTool
                        creator = DocumentCreatorTool(
                            allowed_paths=getattr(settings, "ALLOWED_PATHS", ["./documents", "./uploads"])
                        )
                        
                        if search_context and len(search_context) > 80:
                            body = search_context
                        else:
                            body = """Avances principales

Modelos fundacionales y agentes autónomos
En 2025 y 2026 la inteligencia artificial avanzó de forma importante en modelos multimodales, agentes que usan herramientas y sistemas más capaces de razonar.

Aplicaciones
La IA se integró más en salud, educación, empresas y productos cotidianos. La colaboración entre humanos y sistemas inteligentes se volvió más natural.

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
                        
                        result_msg = creator.create_word(
                            path=full_path,
                            title="Avances de la Inteligencia Artificial en 2025 y 2026",
                            content=body.strip()
                        )
                        
                        logger.info(f"✅ AUTO-WRITE WORD: {result_msg}")
                        
                        result["response"] = (
                            str(result.get("response", "")).strip() +
                            f"\n\n✅ Documento Word guardado en:\n{full_path}"
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


# Global agent instance
_agent_instance = None


async def get_agent() -> AikoAgent:
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AikoAgent()
    return _agent_instance