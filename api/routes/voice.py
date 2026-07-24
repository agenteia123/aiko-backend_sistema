"""Voice API routes for speech-to-text and text-to-speech."""

import logging
import uuid
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from voice.manager import VoiceManager
from api.auth import verify_api_key


logger = logging.getLogger(__name__)
router = APIRouter()

voice_manager = VoiceManager()


class TTSRequest(BaseModel):
    """Text-to-speech request."""
    text: str
    voice: str = "default"
    language: str = "en"


class STTResponse(BaseModel):
    """Speech-to-text response."""
    success: bool
    text: str
    language: str
    confidence: float = 0.0


class TTSResponse(BaseModel):
    """Text-to-speech response."""
    success: bool
    audio_url: str
    duration: float = 0.0


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    request: TTSRequest,
    api_key: str = Depends(verify_api_key),
):
    """Convert text to speech."""
    try:
        # Generate speech
        audio_data = await voice_manager.synthesize(
            text=request.text,
            voice=request.voice,
            language=request.language,
        )
        
        if not audio_data:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        return TTSResponse(
            success=True,
            audio_url=f"data:audio/wav;base64,{audio_data}",
        )
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts/stream")
async def text_to_speech_stream(
    request: TTSRequest,
    api_key: str = Depends(verify_api_key),
):
    """Stream text-to-speech audio."""
    try:
        audio_path = await voice_manager.synthesize_to_file(
            text=request.text,
            voice=request.voice,
            language=request.language,
        )
        
        return StreamingResponse(
            open(audio_path, "rb"),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
    except Exception as e:
        logger.error(f"TTS stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = "en",
    api_key: str = Depends(verify_api_key),
):
    """Convert speech to text."""
    try:
        # Read audio file
        audio_data = await file.read()
        
        # Transcribe
        result = await voice_manager.transcribe(
            audio_data=audio_data,
            language=language,
        )
        
        return STTResponse(
            success=result["success"],
            text=result.get("text", ""),
            language=language,
            confidence=result.get("confidence", 0.0),
        )
    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def get_available_voices(
    api_key: str = Depends(verify_api_key),
):
    """Get available TTS voices."""
    return {
        "success": True,
        "voices": await voice_manager.get_available_voices(),
    }


@router.get("/languages")
async def get_supported_languages(
    api_key: str = Depends(verify_api_key),
):
    """Get supported languages."""
    return {
        "success": True,
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "zh", "name": "Chinese"},
        ]
    }
