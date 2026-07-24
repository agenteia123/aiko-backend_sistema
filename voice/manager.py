"""Voice management system with speech-to-text and text-to-speech."""

import logging
import io
import os
from pathlib import Path
from typing import Optional

from config.settings import settings


logger = logging.getLogger(__name__)


class VoiceManager:
    """Manage voice operations (STT and TTS)."""
    
    def __init__(self):
        """Initialize voice manager."""
        self.stt_provider = settings.STT_PROVIDER
        self.tts_provider = getattr(settings, "TTS_PROVIDER", "windows")
        self.piper_model = getattr(settings, "PIPER_MODEL", "es_MX-claude-high")
        self.cache_dir = Path("./cache/voice")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "es",
    ) -> dict:
        """Transcribe audio to text."""
        try:
            if self.stt_provider == "whisper":
                return await self._whisper_transcribe(audio_data, language)
            elif self.stt_provider == "google":
                return await self._google_transcribe(audio_data, language)
            else:
                return {
                    "success": False,
                    "text": "",
                    "error": f"Unknown STT provider: {self.stt_provider}",
                }
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return {
                "success": False,
                "text": "",
                "error": str(e),
            }
    
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        language: str = "es",
    ) -> Optional[str]:
        """Synthesize text to speech and return base64 audio."""
        try:
            if self.tts_provider == "piper":
                return await self._piper_synthesize(text, voice, language)
            elif self.tts_provider == "google":
                return await self._google_synthesize(text, voice, language)
            elif self.tts_provider == "windows":
                return await self._windows_synthesize(text, voice, language)
            else:
                # Fallback a Windows
                return await self._windows_synthesize(text, voice, language)
        except Exception as e:
            logger.error(f"Synthesis error: {e}", exc_info=True)
            return None
    
    async def synthesize_to_file(
        self,
        text: str,
        voice: str = "default",
        language: str = "es",
    ) -> str:
        """Synthesize text to speech and save to file."""
        import base64
        import tempfile
        
        audio_data = await self.synthesize(text, voice, language)
        
        if not audio_data:
            raise Exception("Failed to synthesize speech")
        
        # Decode base64 and save to file
        audio_bytes = base64.b64decode(audio_data.split(",")[1] if "," in audio_data else audio_data)
        
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)
        
        return temp_path
    
    async def _windows_synthesize(self, text: str, voice: str = "default", language: str = "es") -> Optional[str]:
        """Synthesize using Windows TTS (Microsoft Sabina)."""
        try:
            import pyttsx3
            import base64
            import tempfile
            
            engine = pyttsx3.init()
            
            # Seleccionar voz Sabina
            voices = engine.getProperty('voices')
            for v in voices:
                if 'Sabina' in v.name:
                    engine.setProperty('voice', v.id)
                    break
            
            engine.setProperty('rate', 165)
            engine.setProperty('volume', 1.0)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                output_path = tmp.name
            
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
            with open(output_path, "rb") as f:
                audio_bytes = f.read()
            
            os.unlink(output_path)
            
            return base64.b64encode(audio_bytes).decode()
        except Exception as e:
            logger.error(f"Windows TTS error: {e}")
            return None
    
    async def _whisper_transcribe(self, audio_data: bytes, language: str) -> dict:
        """Transcribe using OpenAI Whisper."""
        try:
            from openai import AsyncOpenAI
            
            if not settings.OPENAI_API_KEY:
                return {
                    "success": False,
                    "text": "",
                    "error": "OpenAI API key not configured",
                }
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            try:
                with open(temp_path, "rb") as f:
                    transcript = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language=language,
                    )
                
                return {
                    "success": True,
                    "text": transcript.text,
                    "language": language,
                    "confidence": 0.95,
                }
            finally:
                os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e),
            }
    
    async def _google_transcribe(self, audio_data: bytes, language: str) -> dict:
        """Transcribe using Google Speech-to-Text."""
        try:
            from google.cloud import speech
            
            client = speech.SpeechClient()
            
            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language,
            )
            
            response = client.recognize(config=config, audio=audio)
            
            text = ""
            confidence = 0.0
            
            for result in response.results:
                for alternative in result.alternatives:
                    text += alternative.transcript + " "
                    confidence = alternative.confidence
            
            return {
                "success": True,
                "text": text.strip(),
                "language": language,
                "confidence": confidence,
            }
        except Exception as e:
            logger.error(f"Google transcription error: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e),
            }
    
    async def _piper_synthesize(self, text: str, voice: str, language: str) -> Optional[str]:
        """Synthesize using Piper TTS."""
        try:
            import base64
            import subprocess
            import tempfile
            
            fd_in, temp_in = tempfile.mkstemp(suffix=".txt")
            fd_out, temp_out = tempfile.mkstemp(suffix=".wav")
            
            try:
                with os.fdopen(fd_in, "w") as f:
                    f.write(text)
                
                subprocess.run([
                    "python", "-m", "piper",
                    "--model", self.piper_model,
                    "--output_file", temp_out,
                ], input=text, text=True, check=True)
                
                with open(temp_out, "rb") as f:
                    audio_bytes = f.read()
                
                return base64.b64encode(audio_bytes).decode()
            finally:
                if os.path.exists(temp_in):
                    os.unlink(temp_in)
                if os.path.exists(temp_out):
                    os.unlink(temp_out)
        except Exception as e:
            logger.error(f"Piper synthesis error: {e}")
            return None
    
    async def _google_synthesize(self, text: str, voice: str, language: str) -> Optional[str]:
        """Synthesize using Google Text-to-Speech."""
        try:
            from google.cloud import texttospeech
            import base64
            
            client = texttospeech.TextToSpeechClient()
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language,
                name=voice if voice != "default" else None,
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            
            return base64.b64encode(response.audio_content).decode()
        except Exception as e:
            logger.error(f"Google synthesis error: {e}")
            return None
    
    async def get_available_voices(self) -> list[dict]:
        """Get available TTS voices."""
        return [
            {"id": "sabina", "name": "Microsoft Sabina (Español México)", "language": "es"},
            {"id": "helena", "name": "Microsoft Helena (Español España)", "language": "es"},
            {"id": "default", "name": "Default", "language": "es"},
        ]