"""Upload de archivos/imágenes para adjuntos del chat."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".pdf",
    ".txt",
    ".doc",
    ".docx",
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key),
):
    """Guarda el archivo en data/uploads y devuelve la ruta real en disco."""
    original = file.filename or "file.bin"
    ext = Path(original).suffix.lower() or ".bin"

    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {ext}",
        )

    name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / name

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Archivo vacío")
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Archivo demasiado grande (máx 20MB)",
            )
        dest.write_bytes(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    resolved = str(dest.resolve())
    kind = "image" if ext in IMAGE_EXT else "file"
    logger.info(f"✅ Upload guardado: {resolved} (original={original})")

    return {
        "success": True,
        "filename": name,
        "original_name": original,
        "path": resolved,
        "kind": kind,
        "url": f"/api/uploads/{name}",
        "size": len(content),
    }


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Sirve un archivo previamente subido."""
    safe = Path(filename).name
    path = UPLOAD_DIR / safe
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path)