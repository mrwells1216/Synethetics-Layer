"""Extractor dispatch by file extension."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..model import Document

SUPPORTED = {".txt", ".md", ".markdown", ".pdf", ".docx", ".doc", ".xlsx", ".xlsm"}


class UnsupportedFile(Exception):
    pass


def _find_soffice() -> str | None:
    exe = shutil.which("soffice")
    if exe:
        return exe
    for base in (r"C:\Program Files\LibreOffice\program", r"C:\Program Files (x86)\LibreOffice\program"):
        cand = Path(base) / "soffice.exe"
        if cand.exists():
            return str(cand)
    return None


def _convert_doc(path: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise UnsupportedFile(
            "Legacy .doc needs LibreOffice to convert. Install it (winget install TheDocumentFoundation.LibreOffice) "
            "or re-save the file as .docx."
        )
    out = Path(tempfile.mkdtemp(prefix="synesthetic_doc_"))
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out), str(path)],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise UnsupportedFile("LibreOffice took too long converting this .doc file.") from None
    except (subprocess.CalledProcessError, OSError) as e:
        raise UnsupportedFile(f"LibreOffice could not convert this .doc file ({e}).") from None
    produced = out / (path.stem + ".docx")
    if not produced.exists():
        raise UnsupportedFile("LibreOffice could not convert this .doc file.")
    return produced


def extract(path, *, find_tables: bool = True) -> Document:
    """Read a file into the common Document model. find_tables: run PDF table detection (slow)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".txt":
        from . import txt as mod
    elif ext in (".md", ".markdown"):
        from . import md as mod
    elif ext == ".pdf":
        from . import pdf

        return pdf.extract(path, find_tables=find_tables)
    elif ext == ".docx":
        from . import docx as mod
    elif ext in (".xlsx", ".xlsm"):
        from . import xlsx as mod
    elif ext == ".doc":
        # LibreOffice keeps headings and tables; without it, fall back to a built-in text reader
        if _find_soffice():
            from . import docx as mod

            produced = _convert_doc(path)
            try:
                doc = mod.extract(produced)
            finally:
                shutil.rmtree(produced.parent, ignore_errors=True)
            doc.source = str(path)
            return doc
        from . import doc as mod
    else:
        raise UnsupportedFile(f"Unsupported file type: {ext or '(none)'}")
    return mod.extract(path)
