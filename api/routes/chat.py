"""Chat API routes for message handling."""

import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from agent.core import get_agent
from memory.manager import MemoryManager
from api.auth import verify_api_key


logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model matching frontend."""

    id: str
    role: str  # "user" | "aiko"
    text: str
    at: int
    attachments: Optional[list[dict]] = None
    tool: Optional[dict] = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    conversation_id: str
    user_id: str
    analysis_level: str = "balanced"
    attachments: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    success: bool
    message_id: str
    response: str
    conversation_id: str
    timestamp: int
    tool_calls: Optional[list] = None
    error: Optional[str] = None


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key),
):
    """Send a message and get AI response."""
    try:
        agent = await get_agent()

        result = await agent.process_message(
            user_message=request.message,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            analysis_level=request.analysis_level,
            attachments=request.attachments,
        )

        if not result.get("success"):
            # Devolvemos 200 con success=false para que el front muestre el error
            return ChatResponse(
                success=False,
                message_id=str(uuid.uuid4()),
                response=result.get("response") or "",
                conversation_id=request.conversation_id,
                timestamp=int(time.time() * 1000),
                error=result.get("error", "Unknown error"),
            )

        return ChatResponse(
            success=True,
            message_id=str(uuid.uuid4()),
            response=result.get("response") or "",
            conversation_id=request.conversation_id,
            timestamp=int(time.time() * 1000),
            tool_calls=result.get("tool_calls"),
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            message_id=str(uuid.uuid4()),
            response="",
            conversation_id=request.conversation_id,
            timestamp=int(time.time() * 1000),
            error=str(e),
        )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Get conversation history."""
    try:
        memory = await MemoryManager.get_instance()
        messages = await memory.get_conversation_history(conversation_id)
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str,
    api_key: str = Depends(verify_api_key),
):
    """Clear conversation history."""
    try:
        memory = await MemoryManager.get_instance()
        await memory.clear_conversation(conversation_id)
        return {
            "success": True,
            "conversation_id": conversation_id,
        }
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{user_id}/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    conversation_id: str,
):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()

    try:
        agent = await get_agent()

        while True:
            data = await websocket.receive_json()

            result = await agent.process_message(
                user_message=data.get("message"),
                user_id=user_id,
                conversation_id=conversation_id,
                analysis_level=data.get("analysis_level", "balanced"),
                attachments=data.get("attachments"),
            )

            await websocket.send_json(
                {
                    "success": result.get("success"),
                    "response": result.get("response"),
                    "error": result.get("error"),
                }
            )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"success": False, "error": str(e)})
        except Exception:
            pass


@router.post("/message/with-file", response_model=ChatResponse)
async def send_message_with_file(
    conversation_id: str,
    user_id: str,
    message: str,
    file: UploadFile = File(None),
    analysis_level: str = "balanced",
    api_key: str = Depends(verify_api_key),
):
    """Send message with optional file attachment (legacy helper)."""
    try:
        attachment = None
        if file and file.filename:
            upload_dir = Path("data/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)

            ext = Path(file.filename).suffix.lower() or ".bin"
            name = f"{uuid.uuid4().hex}{ext}"
            file_path = upload_dir / name
            content = await file.read()
            file_path.write_bytes(content)

            kind = (
                "image"
                if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
                else "file"
            )
            attachment = {
                "name": file.filename,
                "kind": kind,
                "path": str(file_path.resolve()),
            }

        agent = await get_agent()
        result = await agent.process_message(
            user_message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            analysis_level=analysis_level,
            attachments=[attachment] if attachment else None,
        )

        return ChatResponse(
            success=bool(result.get("success")),
            message_id=str(uuid.uuid4()),
            response=result.get("response") or "",
            conversation_id=conversation_id,
            timestamp=int(time.time() * 1000),
            tool_calls=result.get("tool_calls"),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))