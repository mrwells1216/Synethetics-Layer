"""Word (.docx) extractor (python-docx)."""
from __future__ import annotations

from pathlib import Path

from ..model import Block, Cell, Document


def _emph(par) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    pos = 0
    full = par.text
    runs = par.runs
    if "".join(r.text for r in runs) != full:
        return out  # hyperlinks etc. shift offsets; skip emphasis rather than misplace it
    for r in runs:
        end = pos + len(r.text)
        if r.text.strip():
            if r.bold:
                out.append((pos, end, "b"))
            if r.italic:
                out.append((pos, end, "i"))
            fname = (r.font.name or "") if r.font else ""
            if "mono" in fname.lower() or fname in ("Consolas", "Courier New"):
                out.append((pos, end, "code"))
        pos = end
    return out


def _visual_heading_level(par, text: str) -> int:
    """Headings that were formatted by hand (Normal style, whole paragraph bold) instead of by style.

    Returns 0 when the paragraph does not look like a heading. Mirrors the PDF reader's rule: short,
    entirely bold, no sentence ending.
    """
    runs = [r for r in par.runs if r.text.strip()]
    if not runs or not all(r.bold for r in runs) or len(text) > 90 or text.rstrip().endswith((",", ";", ":")):
        return 0
    size = max((r.font.size.pt for r in runs if r.font.size), default=0)
    if size >= 16:
        return 1
    if text.endswith(".") and len(text.split()) > 4:
        return 0  # a bold sentence, not a title
    if text.isupper() and len(text) >= 3:
        return 2
    return 3


def extract(path) -> Document:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    path = Path(path)
    d = docx.Document(str(path))
    doc = Document(source=str(path), title=path.stem)
    core_title = (d.core_properties.title or "").strip()
    if core_title:
        doc.title = core_title

    counters: dict[int, int] = {}
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            par = Paragraph(child, d)
            text = par.text
            if not text.strip():
                continue
            style = (par.style.name if par.style is not None else "").lower()
            ppr = par._p.pPr
            numpr = ppr.numPr if ppr is not None else None
            if style == "title":
                doc.blocks.append(Block("heading", text, level=1, emph=_emph(par)))
            elif style == "subtitle":
                doc.blocks.append(Block("heading", text, level=2, emph=_emph(par)))
            elif style.startswith("heading"):
                digits = "".join(c for c in style if c.isdigit())
                lvl = min(int(digits) + (0 if digits == "1" else 0), 6) if digits else 2
                doc.blocks.append(Block("heading", text, level=lvl, emph=_emph(par)))
            elif "quote" in style:
                doc.blocks.append(Block("quote", text, emph=_emph(par)))
            elif numpr is not None or style.startswith("list"):
                lvl = 0
                try:
                    if numpr is not None and numpr.ilvl is not None:
                        lvl = int(numpr.ilvl.val)
                except Exception:
                    pass
                ordered = "number" in style
                if ordered:
                    counters[lvl] = counters.get(lvl, 0) + 1
                    marker = f"{counters[lvl]}."
                else:
                    marker = "•"
                doc.blocks.append(Block("item", text, level=lvl, marker=marker, emph=_emph(par)))
            else:
                counters.clear()
                lvl = _visual_heading_level(par, text.strip())
                if lvl:
                    doc.blocks.append(Block("heading", text.strip(), level=lvl))
                else:
                    doc.blocks.append(Block("para", text, emph=_emph(par)))
        elif tag == "tbl":
            tbl = Table(child, d)
            rows = []
            for r in tbl.rows:
                seen = set()
                cells = []
                for c in r.cells:
                    if id(c._tc) in seen:
                        continue
                    seen.add(id(c._tc))
                    cells.append(Cell(c.text.replace("\n", " ").strip()))
                rows.append(cells)
            if rows:
                doc.blocks.append(Block("table", rows=rows, header_rows=1))

    if not doc.blocks:
        doc.notes.append("The file has no text.")
    return doc
