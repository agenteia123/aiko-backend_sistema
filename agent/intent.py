"""Detección de intención y reglas de privacidad para Aiko."""

from __future__ import annotations


def is_simple_greeting(message: str) -> bool:
    """True si el mensaje es solo un saludo corto."""
    msg = (message or "").lower().strip().rstrip("!?.")
    greetings = {
        "hola", "hola aiko", "buenas", "buenos días", "buenas tardes",
        "buenas noches", "hey", "qué tal", "que tal", "hi", "hello",
        "hola cómo estás", "hola como estas", "cómo estás", "como estas",
        "hola, cómo estás", "hola, como estas",
    }
    if msg in greetings:
        return True
    if len(msg.split()) <= 3 and any(g in msg for g in ["hola", "buenas", "hey", "hi"]):
        return True
    return False


def detect_intent(message: str) -> str:
    """
    Clasifica la intención del usuario.

    Returns:
        chat | search | file_txt | file_word | file_excel | file_pptx | file_pdf | folder
    """
    msg = (message or "").lower().strip()

    if msg.rstrip("!?.") in {
        "hola", "hola aiko", "buenas", "buenos días", "buenas tardes",
        "buenas noches", "hey", "qué tal", "que tal", "hi", "hello",
    } or is_simple_greeting(message):
        return "chat"

    wants_file = any(
        w in msg
        for w in [
            "crea", "crear", "genera", "generar", "guarda", "guardar",
            "escribe", "escribir", "haz un", "hazme", "armame", "arma un",
        ]
    ) or any(ext in msg for ext in [".txt", ".docx", ".xlsx", ".pptx", ".pdf"])

    if wants_file or any(
        w in msg
        for w in [
            "archivo", "documento", "informe", "reporte",
            "presentación", "presentacion",
        ]
    ):
        if any(w in msg for w in ["pdf", ".pdf"]):
            return "file_pdf"
        if any(
            w in msg
            for w in [
                "powerpoint", "pptx", ".pptx",
                "presentación", "presentacion", "diapositiva",
            ]
        ):
            return "file_pptx"
        if any(
            w in msg
            for w in [
                "excel", "xlsx", ".xlsx",
                "hoja de calculo", "hoja de cálculo", "tabla",
            ]
        ):
            return "file_excel"
        if any(w in msg for w in ["word", "docx", ".docx", "documento word"]):
            return "file_word"
        if any(w in msg for w in [".txt", "archivo de texto", "bloc de notas"]):
            return "file_txt"
        if any(w in msg for w in ["carpeta", "folder", "directorio"]):
            return "folder"
        if "documento" in msg or "informe" in msg:
            return "file_word"
        if "archivo" in msg:
            return "file_txt"

    if any(
        w in msg
        for w in [
            "busca", "buscar", "quién es", "quien es", "qué es", "que es",
            "noticias", "últimas", "ultimas", "actualidad",
            "información sobre", "info sobre",
            "cómo funciona", "como funciona",
        ]
    ):
        return "search"

    return "chat"


def intent_tool_hint(intent: str) -> str:
    """Reglas extra inyectadas al prompt según intención."""
    hints = {
        "file_pdf": (
            "INTENCIÓN DETECTADA: crear PDF.\n"
            "Debes usar SOLO la tool create_pdf.\n"
            "NO uses create_word, write_file, create_excel ni create_powerpoint.\n"
            "content debe ser completo y detallado.\n"
            "Al final confirma solo la ruta del archivo, sin pegar todo el texto."
        ),
        "file_word": (
            "INTENCIÓN DETECTADA: crear Word.\n"
            "Debes usar SOLO la tool create_word.\n"
            "NO uses create_pdf ni write_file.\n"
            "content completo. Confirma solo la ruta."
        ),
        "file_excel": (
            "INTENCIÓN DETECTADA: crear Excel.\n"
            "Debes usar SOLO create_excel.\n"
            "Incluye headers, rows y chart_type (bar/pie/line/area).\n"
            "Confirma solo la ruta."
        ),
        "file_pptx": (
            "INTENCIÓN DETECTADA: crear PowerPoint.\n"
            "Debes usar SOLO create_powerpoint.\n"
            "Envía title, slides (mínimo 3) y theme si aplica "
            "(auto/tech/business/...).\n"
            "Confirma solo la ruta."
        ),
        "file_txt": (
            "INTENCIÓN DETECTADA: crear archivo de texto.\n"
            "Debes usar SOLO write_file.\n"
            "content largo (mínimo ~400 palabras si es informativo).\n"
            "Confirma solo la ruta."
        ),
        "folder": (
            "INTENCIÓN DETECTADA: crear carpeta.\n"
            "Usa create_folder. Si también piden archivo, "
            "primero carpeta y luego el archivo."
        ),
        "search": (
            "INTENCIÓN DETECTADA: búsqueda / información.\n"
            "Usa search si necesitas datos actualizados.\n"
            "Responde con claridad; no crees archivos salvo que lo pidan "
            "explícitamente.\n"
            "NO saques temas personales de conversaciones pasadas si no "
            "están en este mensaje."
        ),
        "chat": (
            "INTENCIÓN DETECTADA: conversación / saludo.\n"
            "Responde de forma natural y BREVE.\n"
            "Si el usuario solo saluda, responde solo el saludo (1-2 frases).\n"
            "NO ofrezcas ejercicios, dietas, planes ni temas no pedidos.\n"
            "NO uses datos de conversaciones anteriores salvo que el usuario "
            "los mencione ahora.\n"
            "No crees archivos ni busques si no hace falta."
        ),
    }
    return hints.get(intent, hints["chat"])


def fact_is_relevant(fact: str, user_message: str) -> bool:
    """Solo usa un hecho si el mensaje actual parece tocarlo."""
    fact_l = (fact or "").lower()
    msg_l = (user_message or "").lower()

    sensitive_keywords = [
        "ejercicio", "calor", "calorías", "calorias", "peso", "dieta", "gym",
        "entren", "salud", "enfermedad", "médic", "medic", "dinero", "sueldo",
        "salario", "deuda", "novia", "novio", "pareja", "familia", "dirección",
        "direccion", "teléfono", "telefono", "dni", "password", "contraseña",
        "cuerpo", "bajar de peso", "adelgazar",
    ]

    if any(k in fact_l for k in sensitive_keywords):
        return any(k in msg_l for k in sensitive_keywords)

    stop = {
        "de", "la", "el", "en", "y", "a", "que", "un", "una", "mi", "me",
        "por", "con", "para", "los", "las", "es", "del", "al", "se", "lo",
    }
    fact_words = {
        w for w in fact_l.replace(",", " ").split()
        if len(w) > 3 and w not in stop
    }
    msg_words = {
        w for w in msg_l.replace(",", " ").split()
        if len(w) > 3 and w not in stop
    }
    if not fact_words:
        return False
    return len(fact_words & msg_words) >= 1


def should_skip_user_facts(user_message: str, intent: str) -> bool:
    """True si no debemos inyectar hechos del usuario (privacidad)."""
    lower = (user_message or "").lower()
    if is_simple_greeting(user_message):
        return True
    if intent == "chat" and len(lower.split()) <= 5:
        return True
    return False


def should_skip_history(user_message: str) -> bool:
    """True si no debemos inyectar historial de la conversación."""
    return is_simple_greeting(user_message)


def needs_search_for_message(user_message: str, intent: str) -> bool:
    """Decide si conviene buscar información externa."""
    if is_simple_greeting(user_message) or intent == "chat":
        return False

    lower = (user_message or "").lower()
    if intent in (
        "search", "file_txt", "file_word", "file_excel", "file_pptx", "file_pdf"
    ):
        return True

    return any(
        word in lower
        for word in [
            "quién", "quien", "busca", "noticias", "último", "ultimo",
            "actual", "ia", "inteligencia artificial", "avances", "tendencias",
        ]
    )


def is_complex_message(user_message: str, intent: str) -> bool:
    """True si conviene un modelo más capaz."""
    if intent.startswith("file_") or intent in ("search", "folder"):
        return True

    lower = (user_message or "").lower()
    return any(
        word in lower
        for word in [
            "explica", "analiza", "compara", "razona", "por qué", "porque",
            "crea", "crear", "guarda", "archivo", "documento", "word", "excel",
            "powerpoint", "pdf", "pptx", "xlsx",
        ]
    )