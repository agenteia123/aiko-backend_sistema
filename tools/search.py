"""Internet search tool using Tavily and DuckDuckGo."""

import logging
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from config.settings import settings


logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=5, description="Maximum number of results")


class SearchTool:
    """Tool for searching the internet."""
    
    def __init__(self, api_key: Optional[str] = None, analysis_level: str = "balanced"):
        """Initialize search tool."""
        self.api_key = api_key or getattr(settings, "TAVILY_API_KEY", None)
        self.analysis_level = analysis_level
        self.tavily_available = False
        self.tavily = None
        self.ddgs = None
        
        # Tavily (prioridad)
        if self.api_key:
            try:
                from tavily import TavilyClient
                self.tavily = TavilyClient(api_key=self.api_key)
                self.tavily_available = True
                logger.info("✅ Tavily API configured")
            except Exception as e:
                logger.warning(f"Tavily not available: {e}")
        
        # DuckDuckGo (solo si se puede inicializar, no rompe el tool)
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
            logger.info("✅ DuckDuckGo available as fallback")
        except Exception as e:
            logger.warning(f"DuckDuckGo no disponible: {e}")
            self.ddgs = None
    
    def get_tool(self):
        """Get the search tool as a LangChain StructuredTool."""
        return StructuredTool.from_function(
            func=self._search_sync,
            name="search",
            description="Search the internet for current information, facts, news and details. ALWAYS use this before writing important informational files.",
            args_schema=SearchInput,
            coroutine=self._search_async,
        )
    
    async def _search_async(self, query: str, max_results: int = 5) -> str:
        try:
            if self.tavily_available:
                return await self._tavily_search(query, max_results)
            return self._ddgs_search_sync(query, max_results)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Error during search: {str(e)}"
    
    def _search_sync(self, query: str, max_results: int = 5) -> str:
        try:
            if self.tavily_available:
                return self._tavily_search_sync(query, max_results)
            return self._ddgs_search_sync(query, max_results)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Error during search: {str(e)}"
    
    async def _tavily_search(self, query: str, max_results: int = 5) -> str:
        try:
            response = self.tavily.search(
                query=query,
                max_results=max_results,
                include_answer=True,
            )
            
            parts = []
            if response.get("answer"):
                parts.append(f"Resumen: {response['answer']}")
            
            results = response.get("results", [])
            if results:
                parts.append("\nFuentes:")
                for r in results[:max_results]:
                    parts.append(f"- {r.get('title', '')}: {r.get('content', '')[:300]}")
            
            return "\n".join(parts) if parts else "No se encontraron resultados."
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return self._ddgs_search_sync(query, max_results)
    
    def _tavily_search_sync(self, query: str, max_results: int = 5) -> str:
        try:
            response = self.tavily.search(
                query=query,
                max_results=max_results,
                include_answer=True,
            )
            
            parts = []
            if response.get("answer"):
                parts.append(f"Resumen: {response['answer']}")
            
            results = response.get("results", [])
            if results:
                parts.append("\nFuentes:")
                for r in results[:max_results]:
                    parts.append(f"- {r.get('title', '')}: {r.get('content', '')[:300]}")
            
            return "\n".join(parts) if parts else "No se encontraron resultados."
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return self._ddgs_search_sync(query, max_results)
    
    def _ddgs_search_sync(self, query: str, max_results: int = 5) -> str:
        if not self.ddgs:
            return "No hay motor de búsqueda disponible."
        
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            
            if not results:
                return f"No results found for: {query}"
            
            formatted = "Search results:\n"
            for i, result in enumerate(results, 1):
                formatted += f"\n{i}. {result.get('title', 'No title')}\n"
                formatted += f"   {result.get('body', 'No description')[:250]}\n"
                formatted += f"   Link: {result.get('href', '')}\n"
            
            return formatted
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return f"Error searching: {str(e)}"