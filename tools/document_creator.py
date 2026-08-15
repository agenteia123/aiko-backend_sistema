"""Tools for creating Office documents (Word, Excel, PowerPoint, PDF)."""

import logging
import re
from datetime import datetime
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class CreateWordInput(BaseModel):
    path: str = Field(
        description=(
            "Ruta completa del archivo .docx. "
            "Ejemplo: C:/Users/User/Downloads/ia_personal/avances_ia.docx"
        )
    )
    title: str = Field(description="Título del documento")
    content: str = Field(
        description=(
            "Contenido completo del documento. Texto largo y bien estructurado. "
            "Usa saltos de línea para párrafos, líneas cortas como subtítulos y "
            "guiones (-) para viñetas. Mínimo recomendado: 200-300 palabras."
        )
    )


class CreateExcelInput(BaseModel):
    path: str = Field(
        description=(
            "Ruta completa del archivo .xlsx. "
            "Ejemplo: C:/Users/User/Downloads/ia_personal/reporte.xlsx"
        )
    )
    title: str = Field(description="Título del reporte o nombre de la hoja")
    headers: list[str] = Field(
        description="Lista de encabezados. Ejemplo: ['Nombre', 'Cantidad', 'Precio']"
    )
    rows: list[list[str]] = Field(
        description="Filas de datos. Cada fila es una lista en el mismo orden que headers."
    )
    chart_type: str = Field(
        default="bar",
        description=(
            "Tipo de gráfico: bar (barras), pie (circular/pastel), line (líneas), area (área). "
            "Si piden circular/pastel → pie. Si piden barras → bar. Si piden líneas → line."
        ),
    )


class CreatePowerPointInput(BaseModel):
    path: str = Field(
        description=(
            "Ruta completa del archivo .pptx. "
            "Ejemplo: C:/Users/User/Downloads/ia_personal/presentacion.pptx"
        )
    )
    title: str = Field(description="Título de la presentación")
    slides: list[dict] = Field(
        description=(
            "Lista de diapositivas. Cada una es un dict con: "
            "title (str) y content (str o lista de viñetas)."
        )
    )
    theme: str = Field(
        default="auto",
        description=(
            "Tema visual: auto, tech, business, education, health, creative, nature, minimal. "
            "Usa auto si no estás seguro."
        ),
    )


class CreatePDFInput(BaseModel):
    path: str = Field(
        description=(
            "Ruta completa del archivo .pdf. "
            "Ejemplo: C:/Users/User/Downloads/ia_personal/informe.pdf"
        )
    )
    title: str = Field(description="Título del documento PDF")
    content: str = Field(
        description=(
            "Contenido completo del PDF. Texto largo y estructurado. "
            "Usa saltos de línea para párrafos, líneas cortas como subtítulos y "
            "guiones (-) para viñetas. Mínimo recomendado: 200-300 palabras."
        )
    )


class DocumentCreatorTool:
    """Tool for creating Word, Excel, PowerPoint and PDF files."""

    def __init__(self, allowed_paths: list[str] | None = None):
        self.allowed_paths = [
            Path(p).resolve() for p in (allowed_paths or ["./documents", "./uploads"])
        ]
        self.extra_roots = [
            Path("C:/Users/User/Downloads").resolve(),
            Path("C:/Users/User/Documents").resolve(),
            Path("C:/Users/User/OneDrive/Documentos").resolve(),
            Path("C:/Users/aleja/Downloads").resolve(),
            Path("C:/Users/aleja/Documents").resolve(),
            Path("C:/Users/aleja/OneDrive/Documentos").resolve(),
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

    @staticmethod
    def _clean_bullet(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^[-•*–—]\s*", "", text)
        text = re.sub(r"^\d+[.)]\s*", "", text)
        return text.strip()

    @staticmethod
    def _is_markdown_heading(text: str) -> tuple[bool, int, str]:
        m = re.match(r"^(#{1,3})\s+(.+)$", text.strip())
        if m:
            return True, len(m.group(1)), m.group(2).strip()
        return False, 0, text

    @staticmethod
    def _is_subtitle(text: str, title: str) -> bool:
        t = text.strip()
        if not t or t.lower() == title.lower():
            return False
        if t.startswith(("#", "-", "•", "*", "–", "—")):
            return False
        if re.match(r"^\d+[.)]\s+", t):
            return False
        if len(t) > 100:
            return False
        if t.endswith(".") and len(t) > 60:
            return False
        if t.count(" ") > 12:
            return False
        return True

    @staticmethod
    def _is_bullet(text: str) -> bool:
        t = text.strip()
        if t.startswith(("-", "•", "*", "–", "—")):
            return True
        if re.match(r"^\d+[.)]\s+\S", t):
            return True
        return False

    @staticmethod
    def _escape_pdf(text: str) -> str:
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def create_word(self, path: str, title: str, content: str) -> str:
        """Create a nicely formatted Word (.docx) document."""
        try:
            if not content or len(content.strip()) < 40:
                return (
                    "❌ Error: el contenido es demasiado corto. "
                    "Escribe un texto completo (recomendado mínimo 200-300 palabras)."
                )

            file_path = Path(path)
            if file_path.suffix.lower() != ".docx":
                file_path = file_path.with_suffix(".docx")

            if not self._is_allowed(file_path):
                return (
                    f"❌ Ruta no permitida: {file_path}\n"
                    "Usa Descargas, Documentos o una carpeta permitida."
                )

            from docx import Document
            from docx.shared import Pt, Cm, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            doc = Document()

            for section in doc.sections:
                section.top_margin = Cm(2.2)
                section.bottom_margin = Cm(2.2)
                section.left_margin = Cm(2.5)
                section.right_margin = Cm(2.5)

            try:
                core = doc.core_properties
                core.author = "Aiko AI"
                core.title = title
                core.comments = "Generado por Aiko AI Assistant"
            except Exception:
                pass

            heading = doc.add_heading(title.strip(), level=0)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in heading.runs:
                run.font.color.rgb = RGBColor(30, 64, 175)
                run.font.size = Pt(22)
                run.font.name = "Calibri"

            subtitle = doc.add_paragraph()
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = subtitle.add_run(
                f"Documento generado por Aiko · {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(100, 116, 139)
            run.italic = True
            run.font.name = "Calibri"

            sep = doc.add_paragraph("─" * 42)
            sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in sep.runs:
                run.font.color.rgb = RGBColor(203, 213, 225)
                run.font.size = Pt(10)

            raw = content.replace("\r\n", "\n").replace("\r", "\n")
            paragraphs = [p.strip() for p in raw.split("\n") if p.strip()]

            for para_text in paragraphs:
                if para_text.lower() == title.strip().lower():
                    continue

                is_md, level, md_text = self._is_markdown_heading(para_text)
                if is_md:
                    h = doc.add_heading(md_text, level=min(level, 3))
                    for run in h.runs:
                        run.font.color.rgb = RGBColor(37, 99, 235)
                        run.font.name = "Calibri"
                    continue

                if self._is_bullet(para_text):
                    clean = self._clean_bullet(para_text)
                    if not clean:
                        continue
                    if re.match(r"^\d+[.)]\s+", para_text.strip()):
                        p = doc.add_paragraph(clean, style="List Number")
                    else:
                        p = doc.add_paragraph(clean, style="List Bullet")
                    for run in p.runs:
                        run.font.size = Pt(11)
                        run.font.name = "Calibri"
                        run.font.color.rgb = RGBColor(30, 41, 59)
                    continue

                if self._is_subtitle(para_text, title):
                    h = doc.add_heading(para_text, level=1)
                    for run in h.runs:
                        run.font.color.rgb = RGBColor(37, 99, 235)
                        run.font.size = Pt(14)
                        run.font.name = "Calibri"
                    continue

                p = doc.add_paragraph(para_text)
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.space_after = Pt(10)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.line_spacing = 1.15
                for run in p.runs:
                    run.font.size = Pt(11)
                    run.font.name = "Calibri"
                    run.font.color.rgb = RGBColor(30, 41, 59)

            doc.add_paragraph()
            footer = doc.add_paragraph()
            footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = footer.add_run("— Generado automáticamente por Aiko AI —")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(148, 163, 184)
            run.italic = True
            run.font.name = "Calibri"

            file_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(file_path))

            size_kb = file_path.stat().st_size / 1024
            logger.info(f"✅ Word creado: {file_path} ({size_kb:.1f} KB)")
            return (
                f"✅ Documento Word creado correctamente\n"
                f"📄 Archivo: {file_path}\n"
                f"📝 Título: {title}\n"
                f"📦 Tamaño: {size_kb:.1f} KB"
            )

        except Exception as e:
            logger.error(f"Error creating Word: {e}", exc_info=True)
            return f"❌ Error al crear Word: {str(e)}"

    def create_excel(
        self,
        path: str,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        chart_type: str = "bar",
    ) -> str:
        """Create a formatted Excel (.xlsx) with table + chart (bar/pie/line/area)."""
        try:
            if not headers or not isinstance(headers, list) or len(headers) == 0:
                return "❌ Error: debes indicar al menos un encabezado de columna."

            if rows is None:
                rows = []

            file_path = Path(path)
            if file_path.suffix.lower() != ".xlsx":
                file_path = file_path.with_suffix(".xlsx")

            if not self._is_allowed(file_path):
                return (
                    f"❌ Ruta no permitida: {file_path}\n"
                    "Usa Descargas, Documentos o una carpeta permitida."
                )

            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from openpyxl.chart import BarChart, PieChart, LineChart, AreaChart, Reference
            from openpyxl.chart.label import DataLabelList
            from openpyxl.chart.axis import ChartLines
            from openpyxl.chart.shapes import GraphicalProperties
            from openpyxl.drawing.line import LineProperties
            from openpyxl.worksheet.table import Table, TableStyleInfo

            wb = Workbook()
            ws = wb.active

            sheet_name = (title or "Hoja1").strip()[:31] or "Hoja1"
            ws.title = sheet_name

            title_font = Font(name="Calibri", size=16, bold=True, color="1E40AF")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            header_fill = PatternFill("solid", fgColor="2563EB")
            cell_font = Font(name="Calibri", size=11, color="1E293B")
            thin = Border(
                left=Side(style="thin", color="E2E8F0"),
                right=Side(style="thin", color="E2E8F0"),
                top=Side(style="thin", color="E2E8F0"),
                bottom=Side(style="thin", color="E2E8F0"),
            )
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            left = Alignment(horizontal="left", vertical="center", wrap_text=True)
            right = Alignment(horizontal="right", vertical="center")

            col_count = max(len(headers), 1)

            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
            title_cell = ws.cell(row=1, column=1, value=title)
            title_cell.font = title_font
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 28

            ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=col_count)
            date_cell = ws.cell(
                row=2,
                column=1,
                value=f"Generado por Aiko · {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            )
            date_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")
            date_cell.alignment = Alignment(horizontal="center")

            header_row = 4
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=header_row, column=col_idx, value=str(header))
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center
                cell.border = thin
            ws.row_dimensions[header_row].height = 22

            def to_number(value):
                if isinstance(value, (int, float)):
                    return value
                if value is None:
                    return ""
                s = str(value).replace("S/", "").replace("s/", "").replace(",", "").strip()
                try:
                    if s == "":
                        return ""
                    if "." in s:
                        return float(s)
                    return int(s)
                except Exception:
                    return value

            for row_idx, row in enumerate(rows, start=header_row + 1):
                if not isinstance(row, (list, tuple)):
                    row = [row]
                for col_idx in range(1, len(headers) + 1):
                    raw_val = row[col_idx - 1] if col_idx - 1 < len(row) else ""
                    header_lower = str(headers[col_idx - 1]).lower()
                    numeric_keys = ["precio", "igv", "total", "monto", "venta", "cantidad", "cant", "stock"]
                    if any(k in header_lower for k in numeric_keys):
                        cell_value = to_number(raw_val)
                    else:
                        cell_value = raw_val

                    cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
                    cell.font = cell_font
                    cell.border = thin

                    if any(k in header_lower for k in ["precio", "igv", "total", "monto", "venta"]):
                        cell.alignment = right
                        if isinstance(cell_value, (int, float)):
                            cell.number_format = "#,##0.00"
                    elif any(k in header_lower for k in ["cantidad", "cant", "stock"]):
                        cell.alignment = center
                    else:
                        cell.alignment = left

                    if (row_idx - header_row) % 2 == 0:
                        cell.fill = PatternFill("solid", fgColor="F8FAFC")

            last_data_row = header_row + max(len(rows), 1)

            for col_idx, header in enumerate(headers, start=1):
                max_len = len(str(header))
                for row in rows:
                    if isinstance(row, (list, tuple)) and col_idx - 1 < len(row):
                        max_len = max(max_len, len(str(row[col_idx - 1])))
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 4, 12), 40)

            if len(rows) > 0:
                table_ref = f"A{header_row}:{get_column_letter(len(headers))}{last_data_row}"
                table = Table(displayName="TablaAiko", ref=table_ref)
                table.tableStyleInfo = TableStyleInfo(
                    name="TableStyleMedium2",
                    showFirstColumn=False,
                    showLastColumn=False,
                    showRowStripes=True,
                    showColumnStripes=False,
                )
                ws.add_table(table)

            ct = (chart_type or "bar").strip().lower()
            if ct in ["circular", "pastel", "pie", "dona", "donut"]:
                ct = "pie"
            elif ct in ["barra", "barras", "column", "col", "bar"]:
                ct = "bar"
            elif ct in ["linea", "línea", "lineas", "líneas", "line"]:
                ct = "line"
            elif ct in ["area", "área"]:
                ct = "area"
            else:
                ct = "bar"

            if len(rows) > 0 and len(headers) >= 2:
                cat_col = 1
                for i, h in enumerate(headers):
                    hl = str(h).lower()
                    if any(x in hl for x in ["nombre", "producto", "item", "descripcion", "descripción"]):
                        cat_col = i + 1
                        break

                value_col = len(headers)
                for key in ["total", "precio de venta", "precio", "venta", "cantidad"]:
                    found = False
                    for i, h in enumerate(headers):
                        if key in str(h).lower():
                            value_col = i + 1
                            found = True
                            break
                    if found:
                        break

                data = Reference(
                    ws,
                    min_col=value_col,
                    min_row=header_row,
                    max_row=last_data_row,
                )
                cats = Reference(
                    ws,
                    min_col=cat_col,
                    min_row=header_row + 1,
                    max_row=last_data_row,
                )

                if ct == "pie":
                    chart = PieChart()
                    chart.title = title[:50] if title else "Resumen"
                    chart.add_data(data, titles_from_data=True)
                    chart.set_categories(cats)
                    chart.dataLabels = DataLabelList()
                    chart.dataLabels.showPercent = True
                    chart.dataLabels.showCatName = True
                    chart.dataLabels.showVal = False
                    chart.dataLabels.showSerName = False
                    chart.legend.position = "r"
                    chart.legend.overlay = False

                elif ct == "line":
                    chart = LineChart()
                    chart.style = 10
                    chart.title = title[:50] if title else "Resumen"
                    chart.y_axis.title = str(headers[value_col - 1])
                    chart.x_axis.title = None
                    chart.add_data(data, titles_from_data=True)
                    chart.set_categories(cats)
                    chart.legend.position = "b"
                    chart.legend.overlay = False
                    chart.dataLabels = DataLabelList()
                    chart.dataLabels.showVal = True
                    soft_line = GraphicalProperties(ln=LineProperties(w=4000, solidFill="E5E7EB"))
                    grid = ChartLines()
                    grid.spPr = soft_line
                    chart.y_axis.majorGridlines = grid
                    chart.x_axis.majorGridlines = None

                elif ct == "area":
                    chart = AreaChart()
                    chart.style = 10
                    chart.title = title[:50] if title else "Resumen"
                    chart.y_axis.title = str(headers[value_col - 1])
                    chart.add_data(data, titles_from_data=True)
                    chart.set_categories(cats)
                    chart.legend.position = "b"
                    chart.legend.overlay = False
                    soft_line = GraphicalProperties(ln=LineProperties(w=4000, solidFill="E5E7EB"))
                    grid = ChartLines()
                    grid.spPr = soft_line
                    chart.y_axis.majorGridlines = grid

                else:
                    chart = BarChart()
                    chart.type = "col"
                    chart.grouping = "clustered"
                    chart.style = 10
                    chart.title = title[:50] if title else "Resumen"
                    chart.y_axis.title = str(headers[value_col - 1])
                    chart.x_axis.title = None
                    chart.add_data(data, titles_from_data=True)
                    chart.set_categories(cats)
                    chart.legend.position = "b"
                    chart.legend.overlay = False
                    chart.varyColors = True
                    chart.dataLabels = DataLabelList()
                    chart.dataLabels.showVal = True
                    soft_line = GraphicalProperties(ln=LineProperties(w=4000, solidFill="E5E7EB"))
                    grid = ChartLines()
                    grid.spPr = soft_line
                    chart.y_axis.majorGridlines = grid
                    chart.x_axis.majorGridlines = None

                chart.width = 16
                chart.height = 10
                anchor_col = len(headers) + 2
                ws.add_chart(chart, f"{get_column_letter(anchor_col)}4")

            file_path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(str(file_path))

            chart_label = {
                "pie": "circular/pastel",
                "line": "líneas",
                "area": "área",
                "bar": "barras",
            }.get(ct, "barras")

            size_kb = file_path.stat().st_size / 1024
            logger.info(f"✅ Excel creado ({chart_label}): {file_path} ({size_kb:.1f} KB)")
            return (
                f"✅ Archivo Excel creado correctamente\n"
                f"📊 Archivo: {file_path}\n"
                f"📝 Título: {title}\n"
                f"📋 Columnas: {len(headers)} | Filas: {len(rows)}\n"
                f"📈 Gráfico: {chart_label}\n"
                f"📦 Tamaño: {size_kb:.1f} KB"
            )

        except Exception as e:
            logger.error(f"Error creating Excel: {e}", exc_info=True)
            return f"❌ Error al crear Excel: {str(e)}"

    def create_powerpoint(
        self,
        path: str,
        title: str,
        slides: list[dict],
        theme: str = "auto",
    ) -> str:
        """Create a modern PowerPoint with theme-aware design."""
        try:
            if not slides or not isinstance(slides, list) or len(slides) == 0:
                return "❌ Error: debes indicar al menos una diapositiva en slides."

            file_path = Path(path)
            if file_path.suffix.lower() != ".pptx":
                file_path = file_path.with_suffix(".pptx")

            if not self._is_allowed(file_path):
                return (
                    f"❌ Ruta no permitida: {file_path}\n"
                    "Usa Descargas, Documentos o una carpeta permitida."
                )

            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
            from pptx.enum.shapes import MSO_SHAPE

            def detect_theme(title_text: str, slides_data: list, forced: str) -> str:
                forced = (forced or "auto").strip().lower()
                valid = {"tech", "business", "education", "health", "creative", "nature", "minimal"}
                if forced in valid:
                    return forced

                blob = (title_text or "").lower()
                for s in slides_data:
                    if isinstance(s, dict):
                        blob += " " + str(s.get("title", "")).lower()
                        c = s.get("content", "")
                        if isinstance(c, list):
                            blob += " " + " ".join(str(x).lower() for x in c)
                        else:
                            blob += " " + str(c).lower()

                rules = [
                    ("tech", [
                        "ia", "inteligencia artificial", "tecnolog", "software", "datos",
                        "digital", "robot", "algoritmo", "cloud", "program", "app",
                        "modelo", "machine learning", "ai", "startup tech"
                    ]),
                    ("business", [
                        "negocio", "empresa", "venta", "finanza", "inversión", "inversion",
                        "marketing comercial", "estrategia", "roi", "cliente", "mercado",
                        "presupuesto", "startup", "emprend"
                    ]),
                    ("education", [
                        "educaci", "escuela", "universidad", "curso", "aprendizaje",
                        "estudiante", "clase", "enseñ", "ensen", "académ", "academ"
                    ]),
                    ("health", [
                        "salud", "médic", "medic", "hospital", "clínica", "clinica",
                        "bienestar", "nutrición", "nutricion", "paciente", "terapia"
                    ]),
                    ("creative", [
                        "diseño", "diseno", "creativ", "marca", "branding", "arte",
                        "publicidad", "campaña", "campana", "contenido", "visual"
                    ]),
                    ("nature", [
                        "medio ambiente", "sostenib", "ecológ", "ecolog", "clima",
                        "verde", "naturaleza", "energía renovable", "energia renovable",
                        "recicl"
                    ]),
                ]

                scores = {k: 0 for k, _ in rules}
                for key, words in rules:
                    for w in words:
                        if w in blob:
                            scores[key] += 1

                best = max(scores, key=scores.get)
                if scores[best] == 0:
                    return "minimal"
                return best

            chosen = detect_theme(title, slides, theme)

            THEMES = {
                "tech": {
                    "name": "Tech",
                    "cover_bg": RGBColor(15, 23, 42),
                    "primary": RGBColor(37, 99, 235),
                    "accent": RGBColor(34, 211, 238),
                    "text": RGBColor(30, 41, 59),
                    "muted": RGBColor(100, 116, 139),
                    "card": RGBColor(241, 245, 249),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(15, 23, 42),
                    "style": "cards",
                },
                "business": {
                    "name": "Business",
                    "cover_bg": RGBColor(17, 24, 39),
                    "primary": RGBColor(5, 150, 105),
                    "accent": RGBColor(251, 191, 36),
                    "text": RGBColor(31, 41, 55),
                    "muted": RGBColor(107, 114, 128),
                    "card": RGBColor(243, 244, 246),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(17, 24, 39),
                    "style": "left_panel",
                },
                "education": {
                    "name": "Education",
                    "cover_bg": RGBColor(30, 58, 138),
                    "primary": RGBColor(59, 130, 246),
                    "accent": RGBColor(251, 146, 60),
                    "text": RGBColor(30, 41, 59),
                    "muted": RGBColor(100, 116, 139),
                    "card": RGBColor(239, 246, 255),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(30, 58, 138),
                    "style": "cards",
                },
                "health": {
                    "name": "Health",
                    "cover_bg": RGBColor(6, 78, 59),
                    "primary": RGBColor(16, 185, 129),
                    "accent": RGBColor(45, 212, 191),
                    "text": RGBColor(6, 78, 59),
                    "muted": RGBColor(100, 116, 139),
                    "card": RGBColor(236, 253, 245),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(6, 78, 59),
                    "style": "soft",
                },
                "creative": {
                    "name": "Creative",
                    "cover_bg": RGBColor(76, 29, 149),
                    "primary": RGBColor(168, 85, 247),
                    "accent": RGBColor(244, 114, 182),
                    "text": RGBColor(49, 46, 129),
                    "muted": RGBColor(107, 114, 128),
                    "card": RGBColor(245, 243, 255),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(76, 29, 149),
                    "style": "cards",
                },
                "nature": {
                    "name": "Nature",
                    "cover_bg": RGBColor(20, 83, 45),
                    "primary": RGBColor(34, 197, 94),
                    "accent": RGBColor(132, 204, 22),
                    "text": RGBColor(20, 83, 45),
                    "muted": RGBColor(100, 116, 139),
                    "card": RGBColor(240, 253, 244),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(20, 83, 45),
                    "style": "soft",
                },
                "minimal": {
                    "name": "Minimal",
                    "cover_bg": RGBColor(24, 24, 27),
                    "primary": RGBColor(63, 63, 70),
                    "accent": RGBColor(161, 161, 170),
                    "text": RGBColor(39, 39, 42),
                    "muted": RGBColor(113, 113, 122),
                    "card": RGBColor(250, 250, 250),
                    "white": RGBColor(255, 255, 255),
                    "dark": RGBColor(24, 24, 27),
                    "style": "minimal",
                },
            }

            T = THEMES.get(chosen, THEMES["minimal"])

            prs = Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)
            blank = prs.slide_layouts[6]

            def add_rect(slide, left, top, width, height, color):
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, left, top, width, height
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = color
                shape.line.fill.background()
                return shape

            def add_round(slide, left, top, width, height, color):
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = color
                shape.line.fill.background()
                try:
                    shape.adjustments[0] = 0.1
                except Exception:
                    pass
                return shape

            def normalize_bullets(content):
                if isinstance(content, list):
                    return [str(x).strip() for x in content if str(x).strip()][:6]
                raw = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
                out = []
                for line in raw.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    line = re.sub(r"^[-•*–—]\s*", "", line)
                    line = re.sub(r"^\d+[.)]\s*", "", line)
                    if line:
                        out.append(line)
                return out[:6] or ["(Sin contenido)"]

            # Portada
            cover = prs.slides.add_slide(blank)
            add_rect(cover, Inches(0), Inches(0), prs.slide_width, prs.slide_height, T["cover_bg"])

            if T["style"] == "left_panel":
                add_rect(cover, Inches(0), Inches(0), Inches(4.2), prs.slide_height, T["primary"])
                add_rect(cover, Inches(4.2), Inches(0), Inches(0.12), prs.slide_height, T["accent"])
                title_left = Inches(4.8)
            elif T["style"] == "soft":
                add_rect(cover, Inches(0), Inches(0), prs.slide_width, Inches(0.25), T["primary"])
                add_rect(cover, Inches(0), Inches(7.25), prs.slide_width, Inches(0.25), T["accent"])
                title_left = Inches(0.9)
            elif T["style"] == "minimal":
                add_rect(cover, Inches(0.9), Inches(3.9), Inches(1.6), Inches(0.06), T["accent"])
                title_left = Inches(0.9)
            else:
                add_rect(cover, Inches(0), Inches(0), Inches(0.28), prs.slide_height, T["primary"])
                add_rect(cover, Inches(10.9), Inches(0), Inches(2.5), Inches(1.0), T["primary"])
                add_rect(cover, Inches(11.5), Inches(1.0), Inches(1.9), Inches(0.15), T["accent"])
                title_left = Inches(0.9)

            btxt = cover.shapes.add_textbox(title_left, Inches(1.72), Inches(2.0), Inches(0.32))
            tf = btxt.text_frame
            p = tf.paragraphs[0]
            p.text = T["name"].upper()
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = T["white"]
            p.font.name = "Calibri"
            p.alignment = PP_ALIGN.CENTER

            tbox = cover.shapes.add_textbox(title_left, Inches(2.3), Inches(10.5), Inches(2.0))
            tf = tbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = (title or "Presentación").strip()
            p.font.size = Pt(40)
            p.font.bold = True
            p.font.color.rgb = T["white"]
            p.font.name = "Calibri"

            add_rect(cover, title_left, Inches(4.5), Inches(2.0), Inches(0.08), T["accent"])

            sbox = cover.shapes.add_textbox(title_left, Inches(4.75), Inches(9.5), Inches(0.5))
            tf = sbox.text_frame
            p = tf.paragraphs[0]
            p.text = f"Generado por Aiko  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            p.font.size = Pt(13)
            p.font.color.rgb = T["muted"]
            p.font.italic = True
            p.font.name = "Calibri"

            total = len(slides)
            for idx, item in enumerate(slides):
                if not isinstance(item, dict):
                    continue

                slide_title = str(item.get("title") or f"Diapositiva {idx + 1}").strip()
                bullets = normalize_bullets(item.get("content", ""))
                slide = prs.slides.add_slide(blank)

                add_rect(slide, Inches(0), Inches(0), prs.slide_width, prs.slide_height, T["white"])

                if T["style"] == "left_panel":
                    add_rect(slide, Inches(0), Inches(0), Inches(0.22), prs.slide_height, T["primary"])
                    add_rect(slide, Inches(0), Inches(0), prs.slide_width, Inches(0.1), T["primary"])
                    add_rect(slide, Inches(0.22), Inches(0.1), Inches(13.1), Inches(1.2), T["card"])

                    nbox = slide.shapes.add_textbox(Inches(0.55), Inches(0.25), Inches(1.2), Inches(0.3))
                    tf = nbox.text_frame
                    p = tf.paragraphs[0]
                    p.text = f"0{idx + 1}" if idx < 9 else str(idx + 1)
                    p.font.size = Pt(12)
                    p.font.bold = True
                    p.font.color.rgb = T["primary"]
                    p.font.name = "Calibri"

                    tbox = slide.shapes.add_textbox(Inches(0.55), Inches(0.55), Inches(12), Inches(0.55))
                    tf = tbox.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_title
                    p.font.size = Pt(24)
                    p.font.bold = True
                    p.font.color.rgb = T["dark"]
                    p.font.name = "Calibri"

                    for i, bullet in enumerate(bullets):
                        top = 1.55 + i * 0.85
                        add_round(slide, Inches(0.55), Inches(top), Inches(0.55), Inches(0.55), T["primary"])
                        num = slide.shapes.add_textbox(Inches(0.55), Inches(top + 0.08), Inches(0.55), Inches(0.4))
                        tf = num.text_frame
                        p = tf.paragraphs[0]
                        p.text = str(i + 1)
                        p.font.size = Pt(14)
                        p.font.bold = True
                        p.font.color.rgb = T["white"]
                        p.font.name = "Calibri"
                        p.alignment = PP_ALIGN.CENTER

                        cbox = slide.shapes.add_textbox(Inches(1.3), Inches(top + 0.08), Inches(11.2), Inches(0.5))
                        tf = cbox.text_frame
                        tf.word_wrap = True
                        p = tf.paragraphs[0]
                        p.text = bullet
                        p.font.size = Pt(16)
                        p.font.color.rgb = T["text"]
                        p.font.name = "Calibri"

                elif T["style"] == "soft":
                    add_rect(slide, Inches(0), Inches(0), prs.slide_width, Inches(0.18), T["primary"])
                    add_rect(slide, Inches(0), Inches(7.32), prs.slide_width, Inches(0.18), T["accent"])

                    tbox = slide.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(11.8), Inches(0.7))
                    tf = tbox.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_title
                    p.font.size = Pt(26)
                    p.font.bold = True
                    p.font.color.rgb = T["dark"]
                    p.font.name = "Calibri"

                    add_rect(slide, Inches(0.7), Inches(1.2), Inches(1.8), Inches(0.07), T["accent"])

                    for i, bullet in enumerate(bullets):
                        top = 1.55 + i * 0.8
                        add_round(slide, Inches(0.7), Inches(top), Inches(11.9), Inches(0.7), T["card"])
                        cbox = slide.shapes.add_textbox(Inches(1.05), Inches(top + 0.18), Inches(11.2), Inches(0.45))
                        tf = cbox.text_frame
                        tf.word_wrap = True
                        p = tf.paragraphs[0]
                        p.text = f"•  {bullet}"
                        p.font.size = Pt(16)
                        p.font.color.rgb = T["text"]
                        p.font.name = "Calibri"

                elif T["style"] == "minimal":
                    add_rect(slide, Inches(0.7), Inches(0.9), Inches(0.9), Inches(0.06), T["primary"])

                    tbox = slide.shapes.add_textbox(Inches(0.7), Inches(1.15), Inches(11.8), Inches(0.7))
                    tf = tbox.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_title
                    p.font.size = Pt(28)
                    p.font.bold = True
                    p.font.color.rgb = T["dark"]
                    p.font.name = "Calibri"

                    cbox = slide.shapes.add_textbox(Inches(0.7), Inches(2.2), Inches(11.8), Inches(4.5))
                    tf = cbox.text_frame
                    tf.word_wrap = True
                    for i, bullet in enumerate(bullets):
                        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                        p.text = bullet
                        p.font.size = Pt(18)
                        p.font.color.rgb = T["text"]
                        p.font.name = "Calibri"
                        p.space_after = Pt(14)

                else:
                    add_rect(slide, Inches(0), Inches(0), Inches(0.18), prs.slide_height, T["primary"])
                    add_rect(slide, Inches(0), Inches(0), prs.slide_width, Inches(0.1), T["primary"])
                    add_rect(slide, Inches(0.18), Inches(0.1), Inches(13.15), Inches(1.15), T["card"])

                    nbox = slide.shapes.add_textbox(Inches(0.55), Inches(0.25), Inches(1.0), Inches(0.3))
                    tf = nbox.text_frame
                    p = tf.paragraphs[0]
                    p.text = f"{idx + 1:02d}"
                    p.font.size = Pt(12)
                    p.font.bold = True
                    p.font.color.rgb = T["accent"]
                    p.font.name = "Calibri"

                    tbox = slide.shapes.add_textbox(Inches(0.55), Inches(0.55), Inches(12), Inches(0.55))
                    tf = tbox.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = slide_title
                    p.font.size = Pt(24)
                    p.font.bold = True
                    p.font.color.rgb = T["dark"]
                    p.font.name = "Calibri"

                    for i, bullet in enumerate(bullets):
                        top = 1.55 + i * 0.85
                        add_round(slide, Inches(0.55), Inches(top), Inches(12.2), Inches(0.72), T["card"])
                        add_rect(
                            slide,
                            Inches(0.55),
                            Inches(top),
                            Inches(0.12),
                            Inches(0.72),
                            T["primary"] if i % 2 == 0 else T["accent"],
                        )
                        cbox = slide.shapes.add_textbox(
                            Inches(0.9), Inches(top + 0.18), Inches(11.5), Inches(0.45)
                        )
                        tf = cbox.text_frame
                        tf.word_wrap = True
                        p = tf.paragraphs[0]
                        p.text = bullet
                        p.font.size = Pt(16)
                        p.font.color.rgb = T["text"]
                        p.font.name = "Calibri"

                foot_l = slide.shapes.add_textbox(Inches(0.55), Inches(7.05), Inches(6), Inches(0.3))
                tf = foot_l.text_frame
                p = tf.paragraphs[0]
                p.text = f"Aiko AI  ·  {T['name']}"
                p.font.size = Pt(10)
                p.font.color.rgb = T["muted"]
                p.font.name = "Calibri"

                foot_r = slide.shapes.add_textbox(Inches(9.5), Inches(7.05), Inches(3.2), Inches(0.3))
                tf = foot_r.text_frame
                p = tf.paragraphs[0]
                p.text = f"{idx + 1} / {total}"
                p.font.size = Pt(10)
                p.font.color.rgb = T["muted"]
                p.font.name = "Calibri"
                p.alignment = PP_ALIGN.RIGHT

            file_path.parent.mkdir(parents=True, exist_ok=True)
            prs.save(str(file_path))

            size_kb = file_path.stat().st_size / 1024
            logger.info(f"✅ PowerPoint ({chosen}) creado: {file_path} ({size_kb:.1f} KB)")
            return (
                f"✅ Presentación PowerPoint creada correctamente\n"
                f"📊 Archivo: {file_path}\n"
                f"📝 Título: {title}\n"
                f"🎨 Tema visual: {T['name']} ({chosen})\n"
                f"📑 Diapositivas: {len(slides) + 1} (incluye portada)\n"
                f"📦 Tamaño: {size_kb:.1f} KB"
            )

        except Exception as e:
            logger.error(f"Error creating PowerPoint: {e}", exc_info=True)
            return f"❌ Error al crear PowerPoint: {str(e)}"

    def create_pdf(self, path: str, title: str, content: str) -> str:
        """Create a clean, professional PDF document."""
        try:
            if not content or len(content.strip()) < 40:
                return (
                    "❌ Error: el contenido es demasiado corto. "
                    "Escribe un texto completo (recomendado mínimo 200-300 palabras)."
                )

            file_path = Path(path)
            if file_path.suffix.lower() != ".pdf":
                file_path = file_path.with_suffix(".pdf")

            if not self._is_allowed(file_path):
                return (
                    f"❌ Ruta no permitida: {file_path}\n"
                    "Usa Descargas, Documentos o una carpeta permitida."
                )

            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, HRFlowable
            )
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

            PRIMARY = HexColor("#2563EB")
            TEXT = HexColor("#1E293B")
            MUTED = HexColor("#64748B")
            LINE = HexColor("#E2E8F0")

            file_path.parent.mkdir(parents=True, exist_ok=True)

            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                rightMargin=2.2 * cm,
                leftMargin=2.2 * cm,
                topMargin=2.0 * cm,
                bottomMargin=2.0 * cm,
                title=title,
                author="Aiko AI",
            )

            styles = getSampleStyleSheet()

            style_title = ParagraphStyle(
                "AikoTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=22,
                textColor=PRIMARY,
                alignment=TA_CENTER,
                spaceAfter=6,
                leading=26,
            )
            style_meta = ParagraphStyle(
                "AikoMeta",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=9,
                textColor=MUTED,
                alignment=TA_CENTER,
                spaceAfter=14,
            )
            style_h1 = ParagraphStyle(
                "AikoH1",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=14,
                textColor=PRIMARY,
                spaceBefore=14,
                spaceAfter=6,
                leading=18,
            )
            style_body = ParagraphStyle(
                "AikoBody",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=11,
                textColor=TEXT,
                alignment=TA_JUSTIFY,
                spaceAfter=8,
                leading=15,
            )
            style_bullet = ParagraphStyle(
                "AikoBullet",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=11,
                textColor=TEXT,
                leftIndent=14,
                spaceAfter=4,
                leading=15,
            )
            style_footer = ParagraphStyle(
                "AikoFooter",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=8,
                textColor=MUTED,
                alignment=TA_CENTER,
                spaceBefore=20,
            )

            story = []
            story.append(Spacer(1, 1.2 * cm))
            story.append(Paragraph(self._escape_pdf(title.strip()), style_title))
            story.append(
                Paragraph(
                    f"Documento generado por Aiko · {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    style_meta,
                )
            )
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=1.5,
                    color=PRIMARY,
                    spaceBefore=4,
                    spaceAfter=16,
                )
            )

            raw = content.replace("\r\n", "\n").replace("\r", "\n")
            paragraphs = [p.strip() for p in raw.split("\n") if p.strip()]

            for para_text in paragraphs:
                if para_text.lower() == title.strip().lower():
                    continue

                is_md, level, md_text = self._is_markdown_heading(para_text)
                if is_md:
                    story.append(Paragraph(self._escape_pdf(md_text), style_h1))
                    continue

                if self._is_bullet(para_text):
                    clean = self._clean_bullet(para_text)
                    if clean:
                        story.append(
                            Paragraph(f"•  {self._escape_pdf(clean)}", style_bullet)
                        )
                    continue

                if self._is_subtitle(para_text, title):
                    story.append(Paragraph(self._escape_pdf(para_text), style_h1))
                    continue

                story.append(Paragraph(self._escape_pdf(para_text), style_body))

            story.append(Spacer(1, 0.6 * cm))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.8,
                    color=LINE,
                    spaceBefore=8,
                    spaceAfter=8,
                )
            )
            story.append(
                Paragraph("— Generado automáticamente por Aiko AI —", style_footer)
            )

            def _header_footer(canvas, doc_):
                canvas.saveState()
                canvas.setFillColor(PRIMARY)
                canvas.rect(0, A4[1] - 8, A4[0], 8, fill=1, stroke=0)
                canvas.setFillColor(MUTED)
                canvas.setFont("Helvetica", 8)
                canvas.drawString(2.2 * cm, 1.2 * cm, "Aiko AI Assistant")
                canvas.drawRightString(A4[0] - 2.2 * cm, 1.2 * cm, f"Pág. {doc_.page}")
                canvas.restoreState()

            doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

            size_kb = file_path.stat().st_size / 1024
            logger.info(f"✅ PDF creado: {file_path} ({size_kb:.1f} KB)")
            return (
                f"✅ Documento PDF creado correctamente\n"
                f"📄 Archivo: {file_path}\n"
                f"📝 Título: {title}\n"
                f"📦 Tamaño: {size_kb:.1f} KB"
            )

        except Exception as e:
            logger.error(f"Error creating PDF: {e}", exc_info=True)
            return f"❌ Error al crear PDF: {str(e)}"

    def get_tools(self) -> list:
        """Return available document creation tools."""
        return [
            StructuredTool.from_function(
                func=self.create_word,
                name="create_word",
                description=(
                    "Crea un documento de Word (.docx) con buen formato. "
                    "Úsala cuando el usuario pida Word, .docx, informe formal o documento. "
                    "IMPORTANTE: el parámetro content debe ser el texto COMPLETO y detallado."
                ),
                args_schema=CreateWordInput,
            ),
            StructuredTool.from_function(
                func=self.create_excel,
                name="create_excel",
                description=(
                    "Crea un archivo Excel (.xlsx) con tabla y gráfico. "
                    "Úsala cuando pidan Excel, hoja de cálculo, tabla o .xlsx. "
                    "chart_type: bar, pie, line o area."
                ),
                args_schema=CreateExcelInput,
            ),
            StructuredTool.from_function(
                func=self.create_powerpoint,
                name="create_powerpoint",
                description=(
                    "Crea una presentación PowerPoint (.pptx) con diseño según el tema. "
                    "Úsala para PowerPoint, presentación, diapositivas o .pptx. "
                    "theme: auto, tech, business, education, health, creative, nature, minimal."
                ),
                args_schema=CreatePowerPointInput,
            ),
            StructuredTool.from_function(
                func=self.create_pdf,
                name="create_pdf",
                description=(
                    "Crea un documento PDF profesional (.pdf). "
                    "Úsala cuando pidan PDF, informe en PDF o archivo .pdf. "
                    "NO uses create_word ni write_file para PDF. "
                    "El parámetro content debe ser texto COMPLETO y detallado."
                ),
                args_schema=CreatePDFInput,
            ),
        ]