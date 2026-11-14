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
    subprocess.run(
        [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out), str(path)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    produced = out / (path.stem + ".docx")
    if not produced.exists():
        raise UnsupportedFile("LibreOffice could not convert this .doc file.")
    return produced


def extract(path) -> Document:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".txt":
        from . import txt as mod
    elif ext in (".md", ".markdown"):
        from . import md as mod
    elif ext == ".pdf":
        from . import pdf as mod
    elif ext == ".docx":
        from . import docx as mod
    elif ext in (".xlsx", ".xlsm"):
        from . import xlsx as mod
    elif ext == ".doc":
        # LibreOffice keeps headings and tables; without it, fall back to a built-in text reader
        if _find_soffice():
            from . import docx as mod

            doc = mod.extract(_convert_doc(path))
            doc.source = str(path)
            return doc
        from . import doc as mod
    else:
        raise UnsupportedFile(f"Unsupported file type: {ext or '(none)'}")
    return mod.extract(path)
