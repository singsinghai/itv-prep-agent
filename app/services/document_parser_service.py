from io import BytesIO
import asyncio

import fitz
from fastapi import UploadFile
import logging

from app.config import Settings
from app.utils.timing import timed


class DocumentParserService:
    def __init__(self, settings: Settings) -> None:
        _ = settings
        self._logger = logging.getLogger(__name__)

    # @timed("document_parser.extract_text")
    async def extract_text(self, input_file: UploadFile, file_label: str = "Document") -> str:
        filename = (input_file.filename or "").lower()
        data = await input_file.read()
        if not data:
            raise ValueError(f"Uploaded {file_label} file is empty")

        if filename.endswith(".md") or filename.endswith(".txt"):
            return data.decode("utf-8", errors="ignore")
        if filename.endswith(".pdf"):
            return await asyncio.to_thread(self._extract_pdf_text, data)
        if filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            raise ValueError(f"Image parsing is not supported in PyMuPDF mode yet. Please provide PDF/MD/TXT for {file_label}.")

        raise ValueError("Unsupported file type. Use .pdf, .md, .txt, .png, .jpg, .jpeg, or .webp")

    # @timed("document_parser.extract_pdf_text")
    def _extract_pdf_text(self, data: bytes) -> str:
        try:
            text_chunks: list[str] = []
            with fitz.open(stream=BytesIO(data), filetype="pdf") as doc:
                for page in doc:
                    text_chunks.append(page.get_text("text"))
            return "\n".join(text_chunks).strip()
        except Exception as exc:
            raise ValueError(f"Failed to parse PDF file with PyMuPDF: {exc}") from exc
