"""Small pictures of a colored file for the Recent and Saved lists in the web app.

PDF: the first page of the colored copy, highlights included. Word and Excel have no renderer here,
so their picture is the start of the text, laid out by MuPDF with the same colors the copy got.
"""
from __future__ import annotations

import html
import io
import tempfile
from pathlib import Path

from .annotate import Lens
from .extract import extract
from .layers import make_annotator
from .overlay import OverlayError, _on, _palette, _tint
from .render import clean_style

MAX_BLOCKS = 45


def thumbnail(name: str, data: bytes, lens: Lens, *, style=None, palette: str = "default",
              width: int = 900) -> bytes:
    """JPEG of the file's first page, `width` pixels wide."""
    import pymupdf

    ext = Path(name).suffix.lower()
    if ext in (".docx", ".xlsx", ".xlsm"):
        data = _text_page(name, data, lens, style, palette)
    elif ext != ".pdf":
        raise OverlayError("Pictures are made for PDF, Word and Excel files.")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise OverlayError(f"Could not open this PDF ({e}).") from None
    if doc.needs_pass or not len(doc):
        raise OverlayError("This PDF has no page to show.")
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(width / page.rect.width, width / page.rect.width))
    return pix.tobytes("jpg", jpg_quality=78)


def _text_page(name, data, lens, style, palette) -> bytes:
    """A one-page PDF of the start of the text, colored like the copy."""
    import pymupdf

    with tempfile.TemporaryDirectory(prefix="synesthetic_th_") as d:
        src = Path(d) / Path(name).name
        src.write_bytes(data)
        doc = extract(src, find_tables=False)
    blocks = doc.blocks[:MAX_BLOCKS]
    texts = [b.text for b in blocks if b.kind in ("para", "item", "quote")]
    for b in blocks:
        if b.kind == "table":
            texts.extend(c.text for row in (b.rows or [])[:14] for c in row)
    ann = make_annotator(texts, lens, log=lambda *a, **k: None)
    colors = _palette(lens, style, palette)
    mode = clean_style(style, lens).get("mode", "c")

    def paint(text: str) -> str:
        out, pos = [], 0
        for s in sorted((s for s in ann(text) if s.layer == "content"), key=lambda s: s.start):
            if s.start < pos:
                continue
            c = colors.get(s.cat, "#000000").lstrip("#")
            if mode == "b":
                css = f"background-color:#{c};color:#{_on(c)}"
            elif mode == "c":
                css = f"color:#{c};background-color:#{_tint(c, 0.22)}"
            elif mode == "d":
                css = f"text-decoration:underline;color:#{c}"
            else:
                css = f"color:#{c}"
            out += [html.escape(text[pos:s.start]), f'<span style="{css}">{html.escape(text[s.start:s.end])}</span>']
            pos = s.end
        out.append(html.escape(text[pos:]))
        return "".join(out)

    parts = []
    for b in blocks:
        if b.kind == "heading":
            lvl = min(max(b.level or 2, 1), 4)
            parts.append(f"<h{lvl}>{html.escape(b.text)}</h{lvl}>")
        elif b.kind == "table":
            rows = "".join("<tr>" + "".join(f"<td>{paint(c.text)}</td>" for c in row) + "</tr>"
                           for row in (b.rows or [])[:14])
            parts.append(f"<table>{rows}</table>")
        elif b.kind == "item":
            parts.append(f"<p>{html.escape(b.marker or '•')} {paint(b.text)}</p>")
        elif b.kind in ("para", "quote"):
            parts.append(f"<p>{paint(b.text)}</p>")
    css = ("body{font-family:sans-serif;font-size:11pt;color:#1d2026}h1,h2,h3,h4{font-family:serif;margin:10pt 0 4pt}"
           "p{margin:0 0 6pt}table{border-collapse:collapse;margin:4pt 0 8pt}td{border:0.5pt solid #c8ccd4;padding:2pt 4pt;font-size:9pt}")
    story = pymupdf.Story(html="".join(parts) or "<p>(empty)</p>", user_css=css)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    rect = pymupdf.paper_rect("letter")
    dev = writer.begin_page(rect)
    story.place(rect + (54, 54, -54, -54))
    story.draw(dev)
    writer.end_page()
    writer.close()
    return buf.getvalue()
