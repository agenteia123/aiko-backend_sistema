"""Tools for creating Office documents (Word, Excel, PowerPoint, PDF)."""

import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class CreateWordInput(BaseModel):
    path: str = Field(
        description="Ruta completa del archivo .docx. Ejemplo: C:/Users/User/Downloads/ia_personal/avances_ia.docx"
    )
    title: str = Field(
        description="Título del documento"
    )
    content: str = Field(
        description="Contenido completo del documento. Debe ser texto largo y bien estructurado (mínimo 300 palabras). Usa saltos de línea para separar párrafos."
    )


class DocumentCreatorTool:
    """Tool for creating Word, Excel, PowerPoint and PDF files."""

    def __init__(self, allowed_paths: list[str] | None = None):
        self.allowed_paths = [Path(p).resolve() for p in (allowed_paths or ["./documents", "./uploads"])]
        # Rutas comunes del usuario
        self.extra_roots = [
            Path("C:/Users/User/Downloads").resolve(),
            Path("C:/Users/User/Documents").resolve(),
            Path("C:/Users/User/OneDrive/Documentos").resolve(),
        ]
        logger.info("✅ DocumentCreatorTool initialized")

    def _is_allowed(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            for allowed in self.allowed_paths + self.extra_roots:
                if str(resolved).lower().startswith(str(allowed).lower()):
                    return True
            return False
        except Exception:
            return False

    def create_word(self, path: str, title: str, content: str) -> str:
        """Create a nicely formatted Word (.docx) document."""
        try:
            if not content or len(content.strip()) < 50:
                return "❌ Error: el contenido es demasiado corto. Escribe un texto completo (mínimo 300 palabras)."

            file_path = Path(path)
            if file_path.suffix.lower() != ".docx":
                file_path = file_path.with_suffix(".docx")

            if not self._is_allowed(file_path):
                return f"❌ Ruta no permitida: {file_path}"

            from docx import Document
            from docx.shared import Pt, Inches, RGBColor, Cm
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
            from datetime import datetime

            doc = Document()

            # Márgenes más amplios
            for section in doc.sections:
                section.top_margin = Cm(2.5)
                section.bottom_margin = Cm(2.5)
                section.left_margin = Cm(2.5)
                section.right_margin = Cm(2.5)

            # ========== TÍTULO ==========
            heading = doc.add_heading(title, level=0)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in heading.runs:
                run.font.color.rgb = RGBColor(30, 64, 175)  # Azul elegante
                run.font.size = Pt(22)

            # ========== SUBTÍTULO / FECHA ==========
            subtitle = doc.add_paragraph()
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = subtitle.add_run(f"Documento generado por Aiko · {datetime.now().strftime('%d/%m/%Y')}")
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(100, 116, 139)
            run.italic = True

            # Línea separadora visual
            doc.add_paragraph("─" * 40).alignment = WD_ALIGN_PARAGRAPH.CENTER

            # ========== CONTENIDO ==========
            paragraphs = [p.strip() for p in content.replace("\r\n", "\n").split("\n") if p.strip()]

            for para_text in paragraphs:
                # Saltar si es el título repetido
                if para_text.lower() == title.lower():
                    continue

                # Detectar subtítulo (corto, sin punto final, no empieza con guión)
                is_subtitle = (
                    len(para_text) < 90
                    and not para_text.endswith(".")
                    and not para_text.startswith(("-", "•", "*", "–"))
                    and not para_text[0].isdigit()
                )

                # Detectar lista
                is_bullet = para_text.startswith(("-", "•", "*", "–")) or (
                    len(para_text) > 2 and para_text[0].isdigit() and para_text[1] in ".)"
                )

                if is_subtitle:
                    h = doc.add_heading(para_text, level=1)
                    for run in h.runs:
                        run.font.color.rgb = RGBColor(37, 99, 235)
                        run.font.size = Pt(14)

                elif is_bullet:
                    clean = para_text.lstrip("-•*– ").strip()
                    if clean and clean[0].isdigit() and len(clean) > 1 and clean[1] in ".)":
                        clean = clean[2:].strip()
                    p = doc.add_paragraph(clean, style="List Bullet")
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Calibri"

                else:
                    p = doc.add_paragraph(para_text)
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.space_after = Pt(10)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.line_spacing = 1.15
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Calibri"
                        run.font.color.rgb = RGBColor(30, 41, 59)

            # ========== PIE ==========
            doc.add_paragraph()
            footer = doc.add_paragraph()
            footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = footer.add_run("— Generado automáticamente por Aiko AI —")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(148, 163, 184)
            run.italic = True

            # Guardar
            file_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(file_path))

            logger.info(f"✅ Word creado (diseño mejorado): {file_path}")
            return f"✅ Documento Word creado: {file_path}"

        except Exception as e:
            logger.error(f"Error creating Word: {e}")
            return f"❌ Error al crear Word: {str(e)}"


    def get_tools(self) -> list:
        """Return available document creation tools."""
        return [
            StructuredTool.from_function(
                func=self.create_word,
                name="create_word",
                description=(
                    "Crea un documento de Word (.docx). "
                    "Usa esta herramienta cuando el usuario pida un archivo Word, documento .docx o un informe formal. "
                    "El parámetro content debe tener el texto completo y detallado."
                ),
                args_schema=CreateWordInput,
            ),
        ]