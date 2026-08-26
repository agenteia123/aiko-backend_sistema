"""Cliente Supabase para Aiko (DB + Storage)."""

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None

MIME_BY_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


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


def _safe_filename(name: str, file_type: str = "pdf") -> str:
    """Nombre limpio para Storage y para Content-Disposition."""
    ext = f".{(file_type or 'pdf').lstrip('.').lower()}"
    base = (name or "documento").strip().replace("\\", "/").split("/")[-1]
    base = re.sub(r'[<>:"|?*]+', "", base)
    base = re.sub(r"\s+", "_", base).strip("._") or "documento"
    if not base.lower().endswith(ext):
        # quita extensión previa rara y pone la correcta
        if "." in base:
            base = base.rsplit(".", 1)[0]
        base = f"{base}{ext}"
    return base


def _clean_public_url(url: str) -> str:
    if not url:
        return url
    return str(url).rstrip("?& ")


def _with_download_param(url: str, filename: str) -> str:
    """
    ?download=archivo.pdf hace que el navegador baje el archivo
    CON ese nombre (no 'anonymous').
    """
    clean = _clean_public_url(url)
    if not clean:
        return clean
    sep = "&" if "?" in clean else "?"
    return f"{clean}{sep}download={quote(filename)}"


# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------

def ensure_user(external_id: str, display_name: str = None) -> Optional[str]:
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
    sb = get_supabase()
    if not sb:
        return None
    try:
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
    Devuelve { public_url, download_url, view_url, storage_path, filename, id }.

    public_url == download_url  → el chat usa esta para que al pulsar
    se descargue CON el nombre del archivo (no anonymous).
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

        file_type = (file_type or path_obj.suffix.lstrip(".") or "pdf").lower()
        safe_name = _safe_filename(filename or path_obj.name, file_type)
        storage_path = f"{external_user_id}/{safe_name}"
        content_type = MIME_BY_TYPE.get(file_type, "application/octet-stream")

        data = path_obj.read_bytes()

        sb.storage.from_(bucket).upload(
            path=storage_path,
            file=data,
            file_options={
                "content-type": content_type,
                "content-disposition": f'inline; filename="{safe_name}"',
                "upsert": "true",
            },
        )

        raw_url = sb.storage.from_(bucket).get_public_url(storage_path)
        view_url = _clean_public_url(raw_url)
        download_url = _with_download_param(view_url, safe_name)

        user_uuid = ensure_user(external_user_id)
        conv_uuid = None
        if conversation_id:
            conv_uuid = ensure_conversation(conversation_id, external_user_id)

        row = {
            "external_user_id": external_user_id,
            "filename": safe_name,
            "file_type": file_type,
            "storage_path": storage_path,
            "public_url": download_url,
            "title": title or safe_name,
            "size_bytes": len(data),
        }
        if user_uuid:
            row["user_id"] = user_uuid
        if conv_uuid:
            row["conversation_id"] = conv_uuid

        ins = sb.table("documents").insert(row).execute()
        doc_id = ins.data[0]["id"] if ins.data else None

        logger.info(f"✅ Documento subido a Supabase: {download_url}")
        return {
            "id": doc_id,
            "public_url": download_url,
            "download_url": download_url,
            "view_url": view_url,
            "storage_path": storage_path,
            "filename": safe_name,
        }
    except Exception as e:
        logger.error(f"upload_document error: {e}", exc_info=True)
        return None