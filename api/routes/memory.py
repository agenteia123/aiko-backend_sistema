"""Memory API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from memory.manager import MemoryManager
from api.auth import verify_api_key


logger = logging.getLogger(__name__)
router = APIRouter()


class SaveFactRequest(BaseModel):
    """Save user fact request."""
    user_id: Optional[str] = None  # ignored; identity comes from the access token
    fact: str
    category: str = "general"
    confidence: float = 0.8


class SearchMemoryRequest(BaseModel):
    """Search memory request."""
    user_id: Optional[str] = None  # ignored; identity comes from the access token
    query: str
    limit: int = 5


@router.get("/facts/{user_id}")
async def get_user_facts(
    user_id: str,
    authenticated_user_id: str = Depends(verify_api_key),
):
    """Get all user facts."""
    try:
        memory = await MemoryManager.get_instance()
        if user_id != authenticated_user_id:
            raise HTTPException(status_code=403, detail="No puedes consultar la memoria de otro usuario.")
        facts = await memory.get_user_facts(authenticated_user_id)
        
        return {
            "success": True,
            "user_id": authenticated_user_id,
            "facts": facts,
        }
    except Exception as e:
        logger.error(f"Error getting user facts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/facts")
async def save_user_fact(
    request: SaveFactRequest,
    authenticated_user_id: str = Depends(verify_api_key),
):
    """Save a user fact."""
    try:
        memory = await MemoryManager.get_instance()
        fact_id = await memory.save_user_fact(
            user_id=authenticated_user_id,
            fact=request.fact,
            category=request.category,
            confidence=request.confidence,
        )
        
        return {
            "success": True,
            "fact_id": fact_id,
            "user_id": authenticated_user_id,
        }
    except Exception as e:
        logger.error(f"Error saving fact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memory(
    request: SearchMemoryRequest,
    authenticated_user_id: str = Depends(verify_api_key),
):
    """Search memory."""
    try:
        memory = await MemoryManager.get_instance()
        results = await memory.search_relevant(
            query=request.query,
            user_id=authenticated_user_id,
            limit=request.limit,
        )
        
        return {
            "success": True,
            "query": request.query,
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conversation_id}")
async def get_conversation_memory(
    conversation_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Get conversation memory."""
    try:
        memory = await MemoryManager.get_instance()
        messages = await memory.get_conversation_history(conversation_id)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Error getting conversation memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{conversation_id}")
async def delete_conversation_memory(
    conversation_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Delete conversation memory."""
    try:
        memory = await MemoryManager.get_instance()
        await memory.clear_conversation(conversation_id)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Conversation cleared",
        }
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
