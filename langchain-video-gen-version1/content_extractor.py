"""
content_extractor.py — Extract text and images from uploaded files (PDF, PPTX, DOCX, images).
Provides structured content for script generation.
"""

import os
import base64
import tempfile
import mimetypes
from pathlib import Path

# Document loaders
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# Document loader mapping
LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc": Docx2txtLoader,
    ".pptx": UnstructuredPowerPointLoader,
    ".ppt": UnstructuredPowerPointLoader,
    ".txt": TextLoader,
    ".md": TextLoader,
}

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=200,
)


def extract_content(file_paths: list) -> dict:
    """
    Extract text and images from uploaded files.

    Returns:
        {
            "text_content": str,       # Combined text from all documents
            "image_data": list,        # List of (base64_str, mime_type, filename)
            "file_names": list,        # Names of processed files
            "summary": str,            # Brief processing summary
        }
    """
    text_content = []
    image_data = []
    file_names = []

    for file_path in file_paths:
        if file_path is None:
            continue

        path = Path(file_path)
        ext = path.suffix.lower()
        file_names.append(path.name)

        if ext in IMAGE_EXTENSIONS:
            # Process image
            b64, mime = _encode_image(file_path)
            if b64:
                image_data.append((b64, mime, path.name))
        elif ext in LOADER_MAP:
            # Process document
            text = _extract_text(file_path, ext)
            if text:
                text_content.append(f"--- Content from: {path.name} ---\n{text}")
        else:
            # Try as text
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if content.strip():
                    text_content.append(f"--- Content from: {path.name} ---\n{content}")
            except Exception:
                pass

    combined_text = "\n\n".join(text_content) if text_content else ""

    # Truncate if too long (keep first 15000 chars for script generation)
    if len(combined_text) > 15000:
        combined_text = combined_text[:15000] + "\n\n[...content truncated for processing...]"

    summary_parts = []
    if text_content:
        summary_parts.append(f"{len(text_content)} document(s) extracted")
    if image_data:
        summary_parts.append(f"{len(image_data)} image(s) loaded")

    return {
        "text_content": combined_text,
        "image_data": image_data,
        "file_names": file_names,
        "summary": ", ".join(summary_parts) if summary_parts else "No content extracted",
    }


def _extract_text(file_path: str, ext: str) -> str:
    """Extract text from a document file."""
    try:
        loader_cls = LOADER_MAP[ext]
        loader = loader_cls(file_path)
        docs = loader.load()
        chunks = text_splitter.split_documents(docs)
        return "\n\n".join(chunk.page_content for chunk in chunks)
    except Exception as e:
        return f"[Error extracting {file_path}: {e}]"


def _encode_image(file_path: str) -> tuple:
    """Encode image to base64 with mime type."""
    try:
        mime_type = mimetypes.guess_type(file_path)[0] or "image/png"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return b64, mime_type
    except Exception:
        return None, None
