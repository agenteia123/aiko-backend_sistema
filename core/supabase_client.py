"""Cliente Supabase para Aiko (DB + Storage)."""

import logging
from typing import Optional
from datetime import datetime

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None


def get_supabase():
    """Singleton del cliente Supabase (service role)."""
    global _client
    if _client is not None:
        return _client

    url = getattr(settings, "SUPABASE_URL", "") or ""
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "") or ""

    if not url or not key:
        logger.warning("Supabase no configurado (falta SUPABASE_URL o SERVICE_ROLE_KEY)")
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        logger.info("✅ Supabase client inicializado")
        return _client
    except Exception as e:
        logger.error(f"Error creando cliente Supabase: {e}")
        return None


def is_supabase_ready() -> bool:
    return get_supabase() is not None


# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------

def ensure_user(external_id: str, display_name: str = None) -> Optional[str]:
    """Crea o recupera app_users por external_id. Devuelve uuid o None."""
    sb = get_supabase()
    if not sb or not external_id:
        return None
    try:
        res = (
            sb.table("app_users")
            .select("id")
            .eq("external_id", external_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]

        payload = {"external_id": external_id}
        if display_name:
            payload["display_name"] = display_name
        ins = sb.table("app_users").insert(payload).execute()
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"ensure_user error: {e}")
    return None


# ------------------------------------------------------------------
# Conversaciones + mensajes
# ------------------------------------------------------------------

def ensure_conversation(
    conversation_id: str,
    external_user_id: str,
    title: str = "Chat Aiko",
) -> Optional[str]:
    """
    Usa conversation_id del front como referencia.
    Guarda external_user_id. Devuelve uuid de conversations si se pudo.
    """
    sb = get_supabase()
    if not sb:
        return None
    try:
        # Buscar por metadata en title o crear siempre una fila ligera
        # Aquí usamos el conversation_id del front guardado en title si es corto,
        # o creamos una nueva. Mejor: buscar por external + title exacto.
        user_uuid = ensure_user(external_user_id)

        res = (
            sb.table("conversations")
            .select("id")
            .eq("external_user_id", external_user_id)
            .eq("title", conversation_id[:120])
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]

        payload = {
            "external_user_id": external_user_id,
            "title": (conversation_id or title)[:120],
        }
        if user_uuid:
            payload["user_id"] = user_uuid
        ins = sb.table("conversations").insert(payload).execute()
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"ensure_conversation error: {e}")
    return None


def save_message(
    conversation_id: str,
    external_user_id: str,
    role: str,
    content: str,
    metadata: dict = None,
) -> bool:
    """Guarda un mensaje user/assistant en Supabase."""
    sb = get_supabase()
    if not sb or not content:
        return False
    try:
        conv_uuid = ensure_conversation(conversation_id, external_user_id)
        if not conv_uuid:
            return False
        payload = {
            "conversation_id": conv_uuid,
            "role": role if role in ("user", "assistant", "system") else "user",
            "content": content,
            "metadata": metadata or {},
        }
        sb.table("messages").insert(payload).execute()
        return True
    except Exception as e:
        logger.warning(f"save_message error: {e}")
        return False


# ------------------------------------------------------------------
# Hechos (memoria)
# ------------------------------------------------------------------

def save_user_fact(
    external_user_id: str,
    fact: str,
    category: str = "general",
    confidence: float = 0.8,
) -> bool:
    sb = get_supabase()
    if not sb or not fact:
        return False
    try:
        user_uuid = ensure_user(external_user_id)
        payload = {
            "external_user_id": external_user_id,
            "fact": fact,
            "category": category,
            "confidence": confidence,
        }
        if user_uuid:
            payload["user_id"] = user_uuid
        sb.table("user_facts").insert(payload).execute()
        return True
    except Exception as e:
        logger.warning(f"save_user_fact error: {e}")
        return False


def get_user_facts(external_user_id: str, limit: int = 20) -> list:
    sb = get_supabase()
    if not sb:
        return []
    try:
        res = (
            sb.table("user_facts")
            .select("fact, category, confidence, created_at")
            .eq("external_user_id", external_user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning(f"get_user_facts error: {e}")
        return []


# ------------------------------------------------------------------
# Afecto
# ------------------------------------------------------------------

def get_affection(external_user_id: str) -> int:
    sb = get_supabase()
    if not sb:
        return 3
    try:
        res = (
            sb.table("user_affection")
            .select("level")
            .eq("external_user_id", external_user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return int(res.data[0]["level"])
        # crear default
        sb.table("user_affection").insert(
            {"external_user_id": external_user_id, "level": 3}
        ).execute()
        return 3
    except Exception as e:
        logger.warning(f"get_affection error: {e}")
        return 3


def update_affection(external_user_id: str, delta: int) -> int:
    sb = get_supabase()
    if not sb:
        return 3
    try:
        current = get_affection(external_user_id)
        new_level = max(0, min(5, current + delta))
        res = (
            sb.table("user_affection")
            .select("id")
            .eq("external_user_id", external_user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            sb.table("user_affection").update(
                {"level": new_level, "updated_at": datetime.utcnow().isoformat()}
            ).eq("external_user_id", external_user_id).execute()
        else:
            sb.table("user_affection").insert(
                {"external_user_id": external_user_id, "level": new_level}
            ).execute()
        return new_level
    except Exception as e:
        logger.warning(f"update_affection error: {e}")
        return 3


# ------------------------------------------------------------------
# Storage: subir PDF/documento y registrar
# ------------------------------------------------------------------

def upload_document(
    local_path: str,
    filename: str,
    file_type: str,
    external_user_id: str,
    conversation_id: str = None,
    title: str = None,
) -> Optional[dict]:
    """
    Sube un archivo local a Supabase Storage y registra en tabla documents.
    Devuelve { public_url, storage_path, id } o None.
    """
    sb = get_supabase()
    if not sb:
        return None

    bucket = getattr(settings, "SUPABASE_STORAGE_BUCKET", "documents") or "documents"
    try:
        from pathlib import Path

        path_obj = Path(local_path)
        if not path_obj.exists():
            logger.error(f"Archivo no existe: {local_path}")
            return None

        # path en storage: user/fecha_filename
        safe_name = filename.replace(" ", "_")
        storage_path = f"{external_user_id}/{safe_name}"

        data = path_obj.read_bytes()
        content_type = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
        }.get(file_type, "application/octet-stream")

        # upload (upsert)
        sb.storage.from_(bucket).upload(
            path=storage_path,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )

        public_url = sb.storage.from_(bucket).get_public_url(storage_path)

        user_uuid = ensure_user(external_user_id)
        conv_uuid = None
        if conversation_id:
            conv_uuid = ensure_conversation(conversation_id, external_user_id)

        row = {
            "external_user_id": external_user_id,
            "filename": filename,
            "file_type": file_type,
            "storage_path": storage_path,
            "public_url": public_url,
            "title": title or filename,
            "size_bytes": len(data),
        }
        if user_uuid:
            row["user_id"] = user_uuid
        if conv_uuid:
            row["conversation_id"] = conv_uuid

        ins = sb.table("documents").insert(row).execute()
        doc_id = ins.data[0]["id"] if ins.data else None

        logger.info(f"✅ Documento subido a Supabase: {public_url}")
        return {
            "id": doc_id,
            "public_url": public_url,
            "storage_path": storage_path,
            "filename": filename,
        }
    except Exception as e:
        logger.error(f"upload_document error: {e}", exc_info=True)
        return None