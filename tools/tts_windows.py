"""Windows TTS using Microsoft Sabina voice."""

import pyttsx3
import tempfile
import os


def generate_speech(text: str, output_path: str = None) -> str:
    """Generate speech using Microsoft Sabina voice."""
    engine = pyttsx3.init()
    
    # Seleccionar voz Sabina
    voices = engine.getProperty('voices')
    for v in voices:
        if 'Sabina' in v.name:
            engine.setProperty('voice', v.id)
            break
    
    # Ajustes de voz
    engine.setProperty('rate', 165)      # Velocidad (más bajo = más lento)
    engine.setProperty('volume', 1.0)
    
    if output_path:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        return output_path
    else:
        engine.say(text)
        engine.runAndWait()
        return "spoken"