from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.core.exceptions import IngestionError
from app.core.security import ALLOWED_UPLOAD_EXTENSIONS


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_text(path: Path, raw: bytes | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise IngestionError(f"Unsupported document type: {suffix}")

    if suffix in {".txt", ".md", ".markdown"}:
        payload = raw if raw is not None else path.read_bytes()
        return _decode_text(payload)

    if suffix == ".json":
        payload = raw if raw is not None else path.read_bytes()
        try:
            parsed = json.loads(_decode_text(payload))
        except json.JSONDecodeError as exc:
            raise IngestionError("JSON document is not valid JSON.") from exc
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    if suffix == ".pdf":
        return _extract_pdf(path if raw is None else None, raw)

    if suffix == ".docx":
        return _extract_docx(path, raw)

    raise IngestionError(f"No parser registered for {suffix}")


def normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _decode_text(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _extract_pdf(path: Path | None, raw: bytes | None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IngestionError("pypdf is required to parse PDF files.") from exc

    from io import BytesIO

    stream = BytesIO(raw) if raw is not None else open(path, "rb")  # type: ignore[arg-type]
    close = raw is None
    try:
        reader = PdfReader(stream)
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"[page {index}]\n{page_text}")
        text = "\n\n".join(pages)
        if not text.strip():
            raise IngestionError("PDF contained no extractable text.")
        return text
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Failed to parse PDF: {exc}") from exc
    finally:
        if close and hasattr(stream, "close"):
            stream.close()


def _extract_docx(path: Path, raw: bytes | None) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise IngestionError("python-docx is required to parse DOCX files.") from exc

    from io import BytesIO

    try:
        document = Document(BytesIO(raw) if raw is not None else str(path))
        paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
        text = "\n".join(paragraphs)
        if not text.strip():
            raise IngestionError("DOCX contained no extractable text.")
        return text
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(f"Failed to parse DOCX: {exc}") from exc
