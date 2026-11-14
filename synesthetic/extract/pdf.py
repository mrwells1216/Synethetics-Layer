"""PDF extractor (PyMuPDF): headings from font size/weight, lists, tables."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..model import Block, Cell, Document

BULLET = re.compile(r"^\s*([•●▪◦■·–\-]|\(?\d{1,3}[.)]|[a-z][.)])\s+(.*)$")


class _Line:
    __slots__ = ("text", "size", "bold")

    def __init__(self, text, size, bold):
        self.text, self.size, self.bold = text, size, bold


class _TBlock:
    __slots__ = ("lines", "bbox", "page")

    def __init__(self, lines, bbox, page):
        self.lines, self.bbox, self.page = lines, bbox, page

    @property
    def text(self):
        return " ".join(ln.text for ln in self.lines)

    @property
    def size(self):
        tot = sum(len(ln.text) for ln in self.lines) or 1
        return sum(ln.size * len(ln.text) for ln in self.lines) / tot

    @property
    def bold(self):
        return all(ln.bold for ln in self.lines)


def _join(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif out.endswith("-") and ln[:1].islower() and len(out) > 1 and out[-2].isalpha():
            out = out[:-1] + ln
        else:
            out += " " + ln
    return out


def _table_rows(page, table) -> list[list[str]]:
    """Cell text rebuilt from page words, so spacing survives (t.extract() can drop spaces)."""
    import pymupdf

    out = []
    for row in table.rows:
        cells = []
        for cb in row.cells:
            if cb is None:
                cells.append("")
                continue
            words = page.get_text("words", clip=pymupdf.Rect(cb))
            words.sort(key=lambda w: (w[5], w[6], w[7]))
            cells.append(" ".join(w[4] for w in words))
        out.append(cells)
    return out


def extract(path, *, find_tables: bool = True) -> Document:
    """find_tables: run PyMuPDF table detection (about 0.6 s per ruled page); off for folder runs."""
    import pymupdf

    path = Path(path)
    with pymupdf.open(path) as pdf:
        return _extract(pdf, path, find_tables)


def _extract(pdf, path: Path, find_tables: bool) -> Document:
    doc = Document(source=str(path), title=path.stem)
    meta_title = (pdf.metadata or {}).get("title", "").strip()
    if meta_title:
        doc.title = meta_title

    pages: list[dict] = []
    sizes: Counter = Counter()
    total_chars = 0
    for pno, page in enumerate(pdf, start=1):
        d = page.get_text("dict", sort=True)
        height = page.rect.height
        tblocks: list[_TBlock] = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            lines = []
            for ln in b.get("lines", []):
                spans = [s for s in ln.get("spans", []) if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in ln["spans"]).strip()
                chars = sum(len(s["text"]) for s in spans)
                size = sum(s["size"] * len(s["text"]) for s in spans) / max(chars, 1)
                bold = all((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
                lines.append(_Line(text, size, bold))
                sizes[round(size * 2) / 2] += chars
                total_chars += chars
            if lines:
                tblocks.append(_TBlock(lines, b["bbox"], pno))
        tables = []
        try:
            # find_tables is slow (~0.6s/page). Ruled tables need at least one drawing, so skip pages with none.
            if find_tables and page.get_drawings():
                for t in page.find_tables().tables:
                    rows = _table_rows(page, t)
                    if rows and len(rows) >= 2 and max(len(r) for r in rows) >= 2:
                        tables.append((t.bbox, rows))
        except Exception:
            pass
        pages.append({"no": pno, "height": height, "blocks": tblocks, "tables": tables})

    if total_chars < 20 * max(len(pages), 1) and total_chars < 200:
        doc.notes.append("This PDF has little or no extractable text. It may be a scan that needs OCR.")
    body = sizes.most_common(1)[0][0] if sizes else 11.0

    # repeated header/footer text
    drop: set[str] = set()
    if len(pages) >= 4:
        seen: Counter = Counter()
        for p in pages:
            keys = set()
            for tb in p["blocks"]:
                if tb.bbox[1] < p["height"] * 0.07 or tb.bbox[3] > p["height"] * 0.93:
                    keys.add(re.sub(r"\d+", "#", tb.text.strip()))
            seen.update(keys)
        drop = {k for k, c in seen.items() if c >= max(3, len(pages) * 0.5)}

    provisional: list[tuple[Block, float | None]] = []
    for p in pages:
        provisional.append((Block("rule", f"Page {p['no']}"), None))
        text_blocks = [
            tb
            for tb in p["blocks"]
            if not (
                (tb.bbox[1] < p["height"] * 0.07 or tb.bbox[3] > p["height"] * 0.93)
                and re.sub(r"\d+", "#", tb.text.strip()) in drop
            )
        ]

        def in_table(tb):
            cx, cy = (tb.bbox[0] + tb.bbox[2]) / 2, (tb.bbox[1] + tb.bbox[3]) / 2
            return any(t[0][0] <= cx <= t[0][2] and t[0][1] <= cy <= t[0][3] for t in p["tables"])

        text_blocks = [tb for tb in text_blocks if not in_table(tb)]
        pending_tables = sorted(p["tables"], key=lambda t: t[0][1])

        def flush_tables(before_y):
            while pending_tables and (before_y is None or pending_tables[0][0][1] <= before_y):
                _bbox, rows = pending_tables.pop(0)
                cells = [[Cell((c or "").replace("\n", " ").strip()) for c in r] for r in rows]
                provisional.append((Block("table", rows=cells, header_rows=1), None))

        for tb in text_blocks:
            flush_tables(tb.bbox[1])
            size = tb.size
            text = tb.text.strip()
            if not text:
                continue
            is_big = size >= body * 1.18 and len(text) <= 200
            is_boldshort = tb.bold and len(text) <= 90 and not text.endswith((".", ",", ";")) and size >= body * 0.97
            has_bullets = any(BULLET.match(ln.text) for ln in tb.lines)
            if (is_big or is_boldshort) and not has_bullets and len(tb.lines) <= 4:
                provisional.append((Block("heading", _join([ln.text for ln in tb.lines])), size if is_big else None))
            elif has_bullets:
                cur: Block | None = None
                lead: list[str] = []
                for ln in tb.lines:
                    m = BULLET.match(ln.text)
                    if m:
                        if lead:
                            provisional.append((Block("para", _join(lead)), None))
                            lead = []
                        marker = m.group(1)
                        marker = marker if marker[0].isalnum() or marker[0] == "(" else "•"
                        cur = Block("item", m.group(2).strip(), marker=marker)
                        provisional.append((cur, None))
                    elif cur is not None:
                        cur.text = _join([cur.text, ln.text])
                    else:
                        lead.append(ln.text)
                if lead:
                    provisional.append((Block("para", _join(lead)), None))
            else:
                provisional.append((Block("para", _join([ln.text for ln in tb.lines])), None))
        flush_tables(None)

    # assign heading levels from the distinct heading sizes (largest = h1)
    hsizes = sorted({round(s * 2) / 2 for b, s in provisional if b.kind == "heading" and s}, reverse=True)
    for b, s in provisional:
        if b.kind == "heading":
            if s:
                b.level = min(hsizes.index(round(s * 2) / 2) + 1, 4)
            else:
                b.level = min(len(hsizes) + 1, 5)
            doc.blocks.append(b)
        else:
            doc.blocks.append(b)

    if not doc.title or doc.title == path.stem:
        for b in doc.blocks:
            if b.kind == "heading" and b.level == 1 and b.text:
                doc.title = b.text
                break
    return doc
