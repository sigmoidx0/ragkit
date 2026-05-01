"""Format-specific document loaders.

Returns a list of `langchain_core.documents.Document` objects, so the
downstream splitter can treat all formats uniformly.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

_PDF_EXT = {".pdf"}
_OFFICE_EXT = {".docx", ".pptx", ".xlsx", ".xls"}
_LEGACY_OFFICE_EXT = {".doc", ".ppt"}  # old binary formats not supported by MarkItDown
_TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".log"}


def _load_pdf(path: Path) -> list[Document]:
    import pymupdf4llm

    md = pymupdf4llm.to_markdown(str(path))
    return [Document(page_content=md, metadata={"source": str(path)})]


def _load_office(path: Path) -> list[Document]:
    from markitdown import MarkItDown

    md = MarkItDown().convert(str(path)).text_content
    return [Document(page_content=md, metadata={"source": str(path)})]


def _load_text(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": str(path)})]


def convert_to_documents(path: Path) -> list[Document]:
    ext = path.suffix.lower()
    if ext in _PDF_EXT:
        return _load_pdf(path)
    if ext in _OFFICE_EXT:
        return _load_office(path)
    if ext in _LEGACY_OFFICE_EXT:
        raise ValueError(f"{ext} (old binary format) is not supported; please convert to {ext}x first")
    if ext in _TEXT_EXT:
        return _load_text(path)
    # Fallback: treat unknown formats as plain text.
    try:
        return _load_text(path)
    except Exception as e:
        raise ValueError(f"unsupported file type: {ext}") from e


def guess_mime_type(filename: str) -> str:
    import mimetypes

    mt, _ = mimetypes.guess_type(filename)
    return mt or "application/octet-stream"
