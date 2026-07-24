"""Document reader tool for various file formats."""

import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


class DocumentReaderTool:
    """Tool for reading documents."""
    
    def get_tools(self) -> list[Tool]:
        """Get document reading tools."""
        return [
            Tool(
                name="read_pdf",
                description="Extract text from a PDF file",
                func=self.read_pdf,
            ),
            Tool(
                name="read_docx",
                description="Extract text from a Word document",
                func=self.read_docx,
            ),
            Tool(
                name="read_txt",
                description="Read a text file",
                func=self.read_txt,
            ),
        ]
    
    def read_pdf(self, path: str) -> str:
        """Read PDF file."""
        try:
            from pypdf import PdfReader
            
            pdf = PdfReader(path)
            text = ""
            
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            
            return text[:5000] + "..." if len(text) > 5000 else text
        except Exception as e:
            logger.error(f"Error reading PDF: {e}")
            return f"Error reading PDF: {str(e)}"
    
    def read_docx(self, path: str) -> str:
        """Read Word document."""
        try:
            from docx import Document
            
            doc = Document(path)
            text = ""
            
            for para in doc.paragraphs:
                text += para.text + "\n"
            
            return text[:5000] + "..." if len(text) > 5000 else text
        except Exception as e:
            logger.error(f"Error reading DOCX: {e}")
            return f"Error reading DOCX: {str(e)}"
    
    def read_txt(self, path: str) -> str:
        """Read text file."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            
            return text[:5000] + "..." if len(text) > 5000 else text
        except Exception as e:
            logger.error(f"Error reading TXT: {e}")
            return f"Error reading TXT: {str(e)}"
