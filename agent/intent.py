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

    # Casos teóricos: hablan DE un agente/sistema, no piden crear archivo
    theoretical = msg.startswith(
        ("un agente", "si un", "si una", "un sistema", "el agente", "la ia ", "una ia ")
    ) or any(
        p in msg
        for p in [
            "en qué casos",
            "en que casos",
            "sería intelectualmente",
            "seria intelectualmente",
            "no debería inyectar",
            "no deberia inyectar",
            "por qué un asistente",
            "por que un asistente",
            "por qué un sistema",
            "por que un sistema",
        ]
    )

    is_question = "?" in msg or "¿" in (message or "") or theoretical

    # Pedido claro al asistente (tú / Aiko)
    user_asks_create = any(
        w in msg
        for w in [
            "me puedes hacer",
            "puedes hacer un",
            "me puedes crear",
            "puedes crear un",
            "quiero un pdf",
            "quiero un word",
            "quiero un excel",
            "quiero un powerpoint",
            "necesito un pdf",
            "necesito un word",
            "necesito un excel",
            "hazme un",
            "hazme una",
            "armame un",
            "guarda un archivo",
            "guardar un archivo",
            "escribe un archivo",
        ]
    )

    # Imperativo dirigido a crear
    imperative_create = any(
        w in msg
        for w in [
            "crea un pdf",
            "crear un pdf",
            "crea una pdf",
            "crea un word",
            "crear un word",
            "crea un excel",
            "crear un excel",
            "crea un powerpoint",
            "crear un powerpoint",
            "crea un archivo",
            "crear un archivo",
            "crea un documento",
            "crear un documento",
            "genera un pdf",
            "generar un pdf",
            "haz un pdf",
            "hacer un pdf",
        ]
    ) or msg.startswith(
        ("crea un", "crear un", "genera un", "generar un", "haz un", "hacer un")
    )

    wants_file = user_asks_create or imperative_create

    # Pregunta teórica sin pedido explícito → no crear archivo
    if is_question and theoretical and not user_asks_create:
        wants_file = False
    if is_question and not user_asks_create and not imperative_create:
        if not msg.startswith(("crea ", "crear ", "genera ", "haz ", "hacer ")):
            wants_file = False

    if wants_file:
        if any(w in msg for w in ["pdf", ".pdf"]):
            return "file_pdf"
        if any(
            w in msg
            for w in [
                "powerpoint",
                "pptx",
                ".pptx",
                "presentación",
                "presentacion",
                "diapositiva",
            ]
        ):
            return "file_pptx"
        if any(
            w in msg
            for w in [
                "excel",
                "xlsx",
                ".xlsx",
                "hoja de calculo",
                "hoja de cálculo",
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
            "busca",
            "buscar",
            "quién es",
            "quien es",
            "qué es",
            "que es",
            "noticias",
            "últimas",
            "ultimas",
            "actualidad",
            "información sobre",
            "info sobre",
            "cómo funciona",
            "como funciona",
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
            "title = frase completa en español (mínimo 5 palabras).\n"
            "content debe ser completo y detallado (varios párrafos).\n"
            "Al final confirma solo la ruta del archivo.\n"
            "NO respondas en formato de examen ni preguntas numeradas."
        ),
        "file_word": (
            "INTENCIÓN DETECTADA: crear Word.\n"
            "Debes usar SOLO la tool create_word.\n"
            "title = frase completa en español (mínimo 5 palabras).\n"
            "content completo y detallado.\n"
            "Confirma solo la ruta.\n"
            "NO respondas en formato de examen."
        ),
        "file_excel": (
            "INTENCIÓN DETECTADA: crear Excel.\n"
            "Debes usar SOLO create_excel.\n"
            "title = frase completa en español (mínimo 5 palabras).\n"
            "Incluye headers, rows útiles y chart_type (bar/pie/line/area).\n"
            "Confirma solo la ruta.\n"
            "NO respondas en formato de examen."
        ),
        "file_pptx": (
            "INTENCIÓN DETECTADA: crear PowerPoint.\n"
            "Debes usar SOLO create_powerpoint.\n"
            "title = frase completa en español (mínimo 5 palabras).\n"
            "Envía slides (mínimo 3).\n"
            "Confirma solo la ruta.\n"
            "NO respondas en formato de examen."
        ),
        "file_txt": (
            "INTENCIÓN DETECTADA: crear archivo de texto.\n"
            "Debes usar SOLO write_file.\n"
            "content largo si es informativo.\n"
            "Confirma solo la ruta.\n"
            "NO respondas en formato de examen."
        ),
        "folder": (
            "INTENCIÓN DETECTADA: crear carpeta.\n"
            "Usa create_folder."
        ),
        "search": (
            "INTENCIÓN DETECTADA: búsqueda / información.\n"
            "Responde con claridad; no crees archivos salvo pedido explícito.\n"
            "NO saques temas personales de conversaciones pasadas."
        ),
        "chat": (
            "INTENCIÓN DETECTADA: conversación / explicación.\n"
            "Responde de forma natural y clara.\n"
            "Si solo saluda, responde solo el saludo.\n"
            "NO crees PDF, Word ni Excel salvo pedido explícito "
            "(crea/genera/haz un archivo).\n"
            "NO uses datos viejos del usuario si no están en este mensaje."
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
    """True si no debemos inyectar hechos del usuario."""
    lower = (user_message or "").lower()
    if is_simple_greeting(user_message):
        return True
    if intent == "chat" and len(lower.split()) <= 5:
        return True
    if intent.startswith("file_") or intent == "folder":
        return True
    return False


def should_skip_history(user_message: str) -> bool:
    return is_simple_greeting(user_message)


def is_quiz_message(message: str) -> bool:
    msg = (message or "").lower()
    has_pregunta = "pregunta" in msg and any(
        f"pregunta {i}" in msg or f"pregunta{i}" in msg for i in range(1, 16)
    )
    has_opciones = msg.count("opción") >= 2 or msg.count("opcion") >= 2
    has_letters = sum(
        1 for x in ["opción a", "opcion a", "opción b", "opcion b"] if x in msg
    ) >= 1
    return bool(has_pregunta and (has_opciones or has_letters)) or (
        msg.count("pregunta") >= 2 and ("opción" in msg or "opcion" in msg)
    )


def wants_direct_answers(message: str) -> bool:
    msg = (message or "").lower()
    triggers = [
        "quiero tus respuestas",
        "dame tus respuestas",
        "tus respuestas por favor",
        "tus respuestas por favro",
        "responde tú",
        "responde tu",
        "dame las respuestas",
        "necesito las respuestas",
        "contesta todas",
        "responde todas",
    ]
    return any(t in msg for t in triggers)


def needs_factual_search(message: str, intent: str) -> bool:
    if is_simple_greeting(message):
        return False
    if intent == "chat" and len((message or "").split()) <= 4:
        return False
    msg = (message or "").lower()
    if any(k in msg for k in ["qué día es", "que dia es", "qué dia es", "que día es"]):
        if len(msg.split()) <= 10:
            return False

    keywords = [
        "senati", "quién fundó", "quien fundo", "quién impulsó", "quien impulso",
        "fundación", "fundacion", "ministerio", "sociedad nacional",
        "continente", "capital de", "quién pintó", "quien pinto",
        "número romano", "numero romano",
        "gdpr", "hadoop", "spark", "mapreduce", "docker",
        "evaluación", "evaluacion", "parcial", "examen",
        "ciiu", "formación profesional", "formacion profesional",
    ]
    return any(k in msg for k in keywords) or is_quiz_message(message)


def needs_search_for_message(user_message: str, intent: str) -> bool:
    if is_simple_greeting(user_message):
        return False

    if intent in ("file_pdf", "file_word", "file_excel", "file_pptx", "file_txt", "folder"):
        lower = (user_message or "").lower()
        if any(
            w in lower
            for w in [
                "información", "informacion", "sobre",
                "de cómo", "de como", "cómo hacer", "como hacer",
                "guía", "guia",
            ]
        ):
            return True
        return False

    if intent == "chat" and not needs_factual_search(user_message, intent):
        return False

    lower = (user_message or "").lower()
    if intent == "search":
        return True

    if needs_factual_search(user_message, intent) or is_quiz_message(user_message):
        return True

    return any(
        word in lower
        for word in [
            "quién", "quien", "busca", "noticias", "último", "ultimo",
            "actual", "ia", "inteligencia artificial", "avances", "tendencias",
        ]
    )


def is_complex_message(user_message: str, intent: str) -> bool:
    if intent.startswith("file_") or intent in ("search", "folder"):
        return True
    if is_quiz_message(user_message) or needs_factual_search(user_message, intent):
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