"""Chat API routes for message handling."""

import logging
import time
import uuid
import asyncio
import re
import webbrowser
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from agent.core import get_agent
from memory.manager import MemoryManager
from api.auth import verify_api_key
from api.auth import decode_access_token
from config.settings import settings
from voice.desktop import open_game_shortcut


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
    user_id: Optional[str] = None  # ignored; identity comes from the access token
    analysis_level: str = "balanced"
    attachments: Optional[list[dict]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    replace_message_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    success: bool
    message_id: str
    response: str
    conversation_id: str
    timestamp: int
    tool_calls: Optional[list] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None


def _response_metadata(result: dict, request: ChatRequest) -> dict:
    metadata = dict(result.get("metadata") or {})
    provider = (request.provider or settings.LLM_PROVIDER).lower()
    metadata["provider"] = provider
    if request.model:
        metadata["model"] = request.model
    elif provider == "ollama":
        metadata["model"] = settings.OLLAMA_MODEL
    elif provider == "groq":
        metadata["model"] = settings.GROQ_MODEL
    elif provider == "google":
        metadata["model"] = settings.GOOGLE_MODEL
    return metadata


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    http_request: Request,
    authenticated_user_id: str = Depends(verify_api_key),
):
    """Send a message and get AI response."""
    try:
        agent = await get_agent()

        result = await agent.process_message(
            user_message=request.message,
            user_id=authenticated_user_id,
            conversation_id=request.conversation_id,
            analysis_level=request.analysis_level,
            attachments=request.attachments,
            provider=request.provider,
            model=request.model,
        )

        if not result.get("success"):
            return ChatResponse(
                success=False,
                message_id=str(uuid.uuid4()),
                response=result.get("response") or "",
                conversation_id=request.conversation_id,
                timestamp=int(time.time() * 1000),
                error=result.get("error", "Unknown error"),
                metadata=_response_metadata(result, request),
            )

        metadata = _response_metadata(result, request)
        reply = result.get("response") or ""
        video_url = metadata.get("youtube_video_url", "")
        local_request = (
            http_request.client is not None
            and http_request.client.host in {"127.0.0.1", "::1"}
        )
        game = metadata.get("desktop_game")
        if game:
            if not local_request or not getattr(http_request.app.state, "allow_chat_games", False):
                reply = "La apertura de juegos por chat requiere el permiso de inicio del backend local en Windows."
            else:
                try:
                    await asyncio.to_thread(open_game_shortcut, game)
                except FileNotFoundError as exc:
                    reply = str(exc)
                except (OSError, ValueError):
                    reply = f"Windows no pudo iniciar {game}."
                else:
                    reply = f"Envié a Windows la orden de abrir {game}."

        if (
            local_request
            and getattr(http_request.app.state, "allow_chat_youtube", False)
            and re.fullmatch(r"https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}", video_url)
        ):
            try:
                opened = await asyncio.to_thread(webbrowser.open, video_url)
            except (OSError, webbrowser.Error):
                opened = False
            if opened:
                reply = "Envié el video a tu navegador. " + reply

        return ChatResponse(
            success=True,
            message_id=str(uuid.uuid4()),
            response=reply,
            conversation_id=request.conversation_id,
            timestamp=int(time.time() * 1000),
            tool_calls=result.get("tool_calls"),
            metadata=metadata,
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
            metadata=None,
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
    """WebSocket endpoint authenticated through the negotiated subprotocol."""
    protocols = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    bearer_protocol = next((p for p in protocols if p.startswith("bearer.")), None)
    if not bearer_protocol or "aiko-v1" not in protocols:
        await websocket.close(code=1008)
        return

    try:
        authenticated_user_id = decode_access_token(bearer_protocol.removeprefix("bearer."))
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept(subprotocol="aiko-v1")

    try:
        agent = await get_agent()

        while True:
            data = await websocket.receive_json()

            result = await agent.process_message(
                user_message=data.get("message"),
                user_id=authenticated_user_id,
                conversation_id=conversation_id,
                analysis_level=data.get("analysis_level", "balanced"),
                attachments=data.get("attachments"),
                provider=data.get("provider"),
                model=data.get("model"),
            )

            await websocket.send_json(
                {
                    "success": result.get("success"),
                    "response": result.get("response"),
                    "error": result.get("error"),
                    "metadata": result.get("metadata"),
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
    authenticated_user_id: str = Depends(verify_api_key),
):
    """Send message with optional file attachment (legacy helper)."""
    try:
        attachment = None
        if file and file.filename:
            upload_dir = Path(settings.UPLOAD_DIR)
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
            user_id=authenticated_user_id,
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
            metadata=result.get("metadata"),
        )
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
