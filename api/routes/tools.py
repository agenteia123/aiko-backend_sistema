"""Tools API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from tools.search import SearchTool
from tools.filesystem import FilesystemTool
from tools.document_reader import DocumentReaderTool
from api.auth import verify_api_key
from config.settings import settings


logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    """Search request."""
    query: str
    max_results: int = 5


class SearchResponse(BaseModel):
    """Search response."""
    success: bool
    results: list[dict]
    query: str


class FileListRequest(BaseModel):
    """File list request."""
    path: str = "."


@router.post("/search", response_model=SearchResponse)
async def search_internet(
    request: SearchRequest,
    api_key: str = Depends(verify_api_key),
):
    """Search the internet."""
    try:
        if not settings.ENABLE_SEARCH:
            raise HTTPException(status_code=403, detail="Search tool is disabled")
        
        search = SearchTool(
            api_key=settings.TAVILY_API_KEY,
            analysis_level=settings.ANALYSIS_LEVEL
        )
        
        result = await search._search_async(request.query, request.max_results)
        
        # Parse results
        results = []
        if "Search results:" in result:
            for line in result.split("\n"):
                if line.strip():
                    results.append({"text": line.strip()})
        
        return SearchResponse(
            success=True,
            results=results,
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filesystem/list")
async def list_files(
    request: FileListRequest,
    api_key: str = Depends(verify_api_key),
):
    """List files in directory."""
    try:
        if not settings.ENABLE_FILESYSTEM:
            raise HTTPException(status_code=403, detail="Filesystem tool is disabled")
        
        fs = FilesystemTool(allowed_paths=settings.ALLOWED_PATHS)
        result = fs.list_files(request.path)
        
        return {
            "success": True,
            "path": request.path,
            "contents": result,
        }
    except Exception as e:
        logger.error(f"File listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filesystem/read")
async def read_file(
    path: str,
    api_key: str = Depends(verify_api_key),
):
    """Read file contents."""
    try:
        if not settings.ENABLE_FILESYSTEM:
            raise HTTPException(status_code=403, detail="Filesystem tool is disabled")
        
        fs = FilesystemTool(allowed_paths=settings.ALLOWED_PATHS)
        content = fs.read_file(path)
        
        return {
            "success": True,
            "path": path,
            "content": content,
        }
    except Exception as e:
        logger.error(f"File read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filesystem/write")
async def write_file(
    path: str,
    content: str,
    api_key: str = Depends(verify_api_key),
):
    """Write file contents."""
    try:
        if not settings.ENABLE_FILESYSTEM:
            raise HTTPException(status_code=403, detail="Filesystem tool is disabled")
        
        fs = FilesystemTool(allowed_paths=settings.ALLOWED_PATHS)
        result = fs.write_file(path, content)
        
        return {
            "success": True,
            "path": path,
            "message": result,
        }
    except Exception as e:
        logger.error(f"File write error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available")
async def get_available_tools(
    api_key: str = Depends(verify_api_key),
):
    """Get list of available tools."""
    return {
        "success": True,
        "tools": {
            "search": settings.ENABLE_SEARCH,
            "filesystem": settings.ENABLE_FILESYSTEM,
            "document_reader": settings.ENABLE_DOCUMENT_READER,
            "image_analysis": settings.ENABLE_IMAGE_ANALYSIS,
        }
    }
