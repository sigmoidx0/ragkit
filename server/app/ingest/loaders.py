"""Format-specific document loaders.

Returns a list of `langchain_core.documents.Document` objects, so the
downstream splitter can treat all formats uniformly.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

_PDF_EXT = {".pdf"}
_OFFICE_EXT = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}
_TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".log"}


def _load_pdf(path: Path) -> list[Document]:
    from langchain_community.document_loaders import PyMuPDFLoader

    return PyMuPDFLoader(str(path)).load()


def _load_office(path: Path) -> list[Document]:
    from langchain_community.document_loaders import UnstructuredFileLoader

    return UnstructuredFileLoader(str(path), mode="elements").load()


def _load_text(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": str(path)})]


def load_file(path: Path) -> list[Document]:
    ext = path.suffix.lower()
    if ext in _PDF_EXT:
        return _load_pdf(path)
    if ext in _OFFICE_EXT:
        return _load_office(path)
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
