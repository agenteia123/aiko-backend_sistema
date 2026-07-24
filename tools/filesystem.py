"""Filesystem tools for reading, writing and managing files."""

import logging
from pathlib import Path
from typing import List

from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class WriteFileInput(BaseModel):
    path: str = Field(description="Ruta completa del archivo a crear o sobrescribir. Ejemplo: C:/Users/User/Downloads/ia_personal/avances_ia.txt")
    content: str = Field(description="Contenido COMPLETO del archivo. Debe ser texto largo y detallado (mínimo 300-500 palabras). NUNCA vacío.")


class CreateFolderInput(BaseModel):
    path: str = Field(description="Ruta completa de la carpeta a crear. Ejemplo: C:/Users/User/Downloads/ia_personal")


class ReadFileInput(BaseModel):
    path: str = Field(description="Ruta del archivo a leer")


class ListFilesInput(BaseModel):
    path: str = Field(description="Ruta de la carpeta a listar")


class FilesystemTool:
    """Tool for safe filesystem operations."""

    def __init__(self, allowed_paths: List[str] | None = None):
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or ["./documents", "./uploads"])]
        logger.info(f"✅ Filesystem tool initialized with paths: {self.allowed_paths}")

    def _is_allowed(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            for allowed in self.allowed_paths:
                if resolved == allowed or allowed in resolved.parents or resolved in allowed.parents:
                    return True
                # Permitir subcarpetas de Downloads, Documents, etc.
                if str(resolved).lower().startswith(str(allowed).lower()):
                    return True
            # Permitir explícitamente Downloads y Documentos del usuario
            allowed_roots = [
                Path("C:/Users/User/Downloads").resolve(),
                Path("C:/Users/User/Documents").resolve(),
                Path("C:/Users/User/OneDrive/Documentos").resolve(),
            ]
            for root in allowed_roots:
                if str(resolved).lower().startswith(str(root).lower()):
                    return True
            return False
        except Exception:
            return False

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file. Content cannot be empty."""
        try:
            if not content or not str(content).strip():
                return "❌ Error: el contenido del archivo está vacío. Debes generar el texto completo (mínimo 300 palabras) antes de guardar."

            file_path = Path(path)
            
            # Crear carpeta padre si no existe
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if not self._is_allowed(file_path):
                return f"❌ Ruta no permitida: {path}"

            file_path.write_text(str(content), encoding="utf-8")
            logger.info(f"✅ File written: {file_path} ({len(content)} caracteres)")
            return f"✅ Archivo creado/actualizado: {file_path} ({len(content)} caracteres)"
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return f"❌ Error al escribir archivo: {str(e)}"

    def create_folder(self, path: str) -> str:
        """Create a folder."""
        try:
            folder_path = Path(path)
            if not self._is_allowed(folder_path):
                return f"❌ Ruta no permitida: {path}"

            folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Folder created: {folder_path}")
            return f"✅ Carpeta creada: {folder_path}"
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return f"❌ Error al crear carpeta: {str(e)}"

    def read_file(self, path: str) -> str:
        """Read a file."""
        try:
            file_path = Path(path)
            if not self._is_allowed(file_path):
                return f"❌ Ruta no permitida: {path}"
            if not file_path.exists():
                return f"❌ Archivo no encontrado: {path}"
            content = file_path.read_text(encoding="utf-8")
            return content
        except Exception as e:
            return f"❌ Error al leer archivo: {str(e)}"

    def list_files(self, path: str) -> str:
        """List files in a directory."""
        try:
            folder_path = Path(path)
            if not self._is_allowed(folder_path):
                return f"❌ Ruta no permitida: {path}"
            if not folder_path.exists():
                return f"❌ Carpeta no encontrada: {path}"
            
            files = list(folder_path.iterdir())
            if not files:
                return "La carpeta está vacía."
            
            lines = []
            for f in files:
                tipo = "📁" if f.is_dir() else "📄"
                lines.append(f"{tipo} {f.name}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error al listar: {str(e)}"

    def get_tools(self) -> list:
        """Return all filesystem tools."""
        return [
            StructuredTool.from_function(
                func=self.write_file,
                name="write_file",
                description=(
                    "Escribe un archivo de texto con contenido completo. "
                    "OBLIGATORIO: el parámetro 'content' debe tener el texto largo y detallado del archivo "
                    "(mínimo 300-500 palabras). NUNCA envíes content vacío o corto. "
                    "Usa esta herramienta cuando el usuario pida crear o guardar un archivo."
                ),
                args_schema=WriteFileInput,
            ),
            StructuredTool.from_function(
                func=self.create_folder,
                name="create_folder",
                description="Crea una carpeta nueva en la ruta indicada.",
                args_schema=CreateFolderInput,
            ),
            StructuredTool.from_function(
                func=self.read_file,
                name="read_file",
                description="Lee el contenido de un archivo de texto.",
                args_schema=ReadFileInput,
            ),
            StructuredTool.from_function(
                func=self.list_files,
                name="list_files",
                description="Lista los archivos y carpetas dentro de una ruta.",
                args_schema=ListFilesInput,
            ),
        ]