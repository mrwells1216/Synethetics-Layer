"""Keep the original look: add the color layer on top of a PDF, Word or Excel file and give the same
kind of file back, instead of re-rendering the text as a new page.

- PDF: highlight annotations over the matched words (underlines in underline-only mode). The pages
  themselves are untouched, so layout, images and fonts stay; the colors can be hidden or deleted in
  any PDF viewer.
- Word: matched text is recolored in place (text color, a shaded background, or a colored underline,
  following the highlight style). Everything else in the file stays as it was.
- Excel: matched text in cells is recolored (cells can't hold per-word backgrounds); number and date
  cells take the number and date colors. Formulas are left alone.

Colors are the light-theme ones (documents are paper-white), with the reader's own light colors from
Customize when given.
"""
from __future__ import annotations

import copy
import datetime as dt
import io
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .annotate import Lens
from .colorcheck import contrast
from .layers import make_annotator
from .render import clean_style

OVERLAY_TYPES = {".pdf": "application/pdf",
                 ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12"}


class OverlayError(Exception):
    pass


@dataclass
class Overlay:
    data: bytes
    name: str
    mime: str
    counts: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)


def _hex(h: str) -> str:
    return h.lstrip("#").lower()


def _rgb(h: str) -> tuple[float, float, float]:
    h = _hex(h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _tint(h: str, keep: float = 0.2) -> str:
    """Mix a color with white, keeping `keep` of it: the soft fill behind colored text."""
    r, g, b = (round(255 - (255 - c * 255) * keep) for c in _rgb(h))
    return f"{r:02X}{g:02X}{b:02X}"


def _on(h: str) -> str:
    return "101216" if contrast("#" + _hex(h), "#101216") >= contrast("#" + _hex(h), "#ffffff") else "FFFFFF"


def _palette(lens: Lens, style, palette: str) -> dict[str, str]:
    key = "cb_light" if palette == "cb" else "light"
    cols = {c.name: c.colors[key] for c in lens.categories}
    if palette != "cb":  # custom colors apply to the standard palette, as on converted pages
        cols.update(clean_style(style, lens)["light"])
    return cols


def out_name(name: str) -> str:
    p = Path(name)
    return f"{p.stem} (colored){p.suffix}"


def overlay(name: str, data: bytes, lens: Lens, *, style=None, palette: str = "default",
            grammar: bool = False, log=print) -> Overlay:
    ext = Path(name).suffix.lower()
    if ext not in OVERLAY_TYPES:
        raise OverlayError(f"Keeping the original look works for {', '.join(sorted(OVERLAY_TYPES))} files. "
                           "Other types get the styled page.")
    mode = clean_style(style, lens).get("mode", "c")
    ctx = _Ctx(lens, _palette(lens, style, palette), mode, grammar, log)
    fn = {".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx, ".xlsm": _xlsx}[ext]
    out = fn(data, ctx, ext)
    if not ctx.counts:
        ctx.notes.append("Nothing in this file matched a category, so it has no colors.")
    return Overlay(out, out_name(name), OVERLAY_TYPES[ext], ctx.counts, ctx.notes)


class _Ctx:
    def __init__(self, lens, colors, mode, grammar, log):
        self.lens, self.colors, self.mode, self.grammar, self.log = lens, colors, mode, grammar, log
        self.counts: Counter = Counter()
        self.notes: list[str] = []
        self.ann = None

    def prepare(self, texts):
        self.ann = make_annotator(texts, self.lens, grammar=self.grammar, log=self.log)

    def spans(self, text):
        out = [s for s in self.ann(text) if s.layer != "meaning"]
        for s in out:
            self.counts[s.cat] += 1
        return out


# ---------------------------------------------------------------- PDF

def _pdf(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise OverlayError(f"Could not open this PDF ({e}).") from None
    if doc.needs_pass:
        raise OverlayError("This PDF is password-protected.")
    flags = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    units = []  # (page number, text, [rect or None per char], [line id per char])
    for pno, page in enumerate(doc):
        for bi, block in enumerate(page.get_text("rawdict", flags=flags)["blocks"]):
            if block.get("type") != 0:
                continue
            chars, rects, lines = [], [], []
            for li, line in enumerate(block["lines"]):
                if chars:
                    chars.append(" "); rects.append(None); lines.append(None)
                for span in line["spans"]:
                    for ch in span["chars"]:
                        chars.append(ch["c"]); rects.append(pymupdf.Rect(ch["bbox"])); lines.append((bi, li))
            text = "".join(chars)
            if text.strip():
                units.append((pno, text, rects, lines))
    if not units:
        raise OverlayError("This PDF has no text layer (it's probably a scan), so there is nothing to color.")
    ctx.prepare([u[1] for u in units])
    marks: dict[tuple[int, str, str], list] = {}
    for pno, text, rects, lines in units:
        for sp in ctx.spans(text):
            if sp.layer == "grammar" and ctx.mode == "d":
                continue  # underline-only mode keeps grammar plain, as on converted pages
            kind = "underline" if ctx.mode == "d" or sp.layer == "grammar" else "highlight"
            per_line: dict = {}
            for i in range(sp.start, sp.end):
                if rects[i] is None or not text[i].strip():
                    continue
                r = per_line.get(lines[i])
                per_line[lines[i]] = rects[i] if r is None else r | rects[i]
            marks.setdefault((pno, sp.cat, kind), []).extend(per_line.values())
    for (pno, cat, kind), rects in marks.items():
        if not rects:
            continue
        page = doc[pno]
        add = page.add_highlight_annot if kind == "highlight" else page.add_underline_annot
        a = add(quads=[r.quad for r in rects])
        a.set_colors(stroke=_rgb(ctx.colors[cat]))
        a.set_opacity(0.4 if kind == "highlight" else 0.9)
        a.set_info(title="Synesthetic Layer", content=ctx.lens.get(cat).label)
        a.update()
    return doc.tobytes(garbage=3, deflate=True)


# ---------------------------------------------------------------- Word

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
# schema order of run properties: Word rejects a file whose w:rPr children are out of order
_RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline",
              "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
              "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText",
              "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath"]
_U = {"dotted": "dotted", "dashed": "dash", "double": "double", "wavy": "wave"}


def _q(tag: str) -> str:
    return f"{{{_W}}}{tag}"


def _set_rpr(run, tag: str, attrs: dict):
    from lxml import etree

    rpr = run.find(_q("rPr"))
    if rpr is None:
        rpr = etree.Element(_q("rPr"))
        run.insert(0, rpr)
    for old in rpr.findall(_q(tag)):
        rpr.remove(old)
    el = etree.Element(_q(tag))
    for k, v in attrs.items():
        el.set(_q(k), v)
    rank = _RPR_ORDER.index(tag)
    for i, child in enumerate(rpr):
        name = etree.QName(child).localname
        if name in _RPR_ORDER and _RPR_ORDER.index(name) > rank:
            rpr.insert(i, el)
            return
    rpr.append(el)


def _paint_run(run, cat: str, layer: str, ctx: _Ctx):
    col = _hex(ctx.colors[cat]).upper()  # Word writes RGB in upper case
    if layer == "grammar":
        if ctx.mode != "d":
            _set_rpr(run, "color", {"val": col})
        return
    if ctx.mode == "d":
        _set_rpr(run, "u", {"val": _U.get(ctx.lens.get(cat).underline, "single"), "color": col})
    elif ctx.mode == "b":
        _set_rpr(run, "color", {"val": _on(col)})
        _set_rpr(run, "shd", {"val": "clear", "color": "auto", "fill": col})
    else:
        _set_rpr(run, "color", {"val": col})
        if ctx.mode == "c":
            _set_rpr(run, "shd", {"val": "clear", "color": "auto", "fill": _tint(col)})


def _runs(p):
    """The paragraph's own runs with their text; a run is splittable only if it holds plain text."""
    out = []
    for r in p.iter(_q("r")):
        if next(r.iterancestors(_q("p")), None) is not p:
            continue  # belongs to a nested paragraph (a text box)
        kids = [k for k in r if k.tag != _q("rPr")]
        if kids and all(k.tag == _q("t") for k in kids):
            out.append((r, "".join(k.text or "" for k in kids), True))
        else:
            text = "".join((k.text or "") if k.tag == _q("t") else "\t" if k.tag == _q("tab")
                           else "\n" if k.tag in (_q("br"), _q("cr")) else "" for k in kids)
            out.append((r, text, False))
    return out


def _split_run(run, text: str, segs, ctx: _Ctx):
    from lxml import etree

    parent = run.getparent()
    at = parent.index(run)
    parent.remove(run)
    for k, (a, b, sp) in enumerate(segs):
        nr = copy.deepcopy(run)
        for t in nr.findall(_q("t")):
            nr.remove(t)
        t = etree.SubElement(nr, _q("t"))
        t.text = text[a:b]
        t.set(_XML_SPACE, "preserve")
        if sp is not None:
            _paint_run(nr, sp.cat, sp.layer, ctx)
        parent.insert(at + k, nr)


def _docx(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    import docx

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise OverlayError(f"Could not open this Word file ({e}).") from None
    roots, seen = [d.element.body], set()
    for sec in d.sections:
        for part in (sec.header, sec.footer, sec.first_page_header, sec.first_page_footer,
                     sec.even_page_header, sec.even_page_footer):
            try:
                el = part._element if not part.is_linked_to_previous else None
            except Exception:
                el = None
            if el is not None and id(el) not in seen:
                seen.add(id(el)); roots.append(el)
    paras = []
    for root in roots:
        for p in root.iter(_q("p")):
            runs = _runs(p)
            text = "".join(t for _r, t, _ok in runs)
            if text.strip():
                paras.append((runs, text))
    ctx.prepare([t for _r, t in paras])
    for runs, text in paras:
        spans = ctx.spans(text)
        if not spans:
            continue
        pos = 0
        for run, rtext, ok in runs:
            a, b = pos, pos + len(rtext)
            pos = b
            if not ok or a == b:
                continue
            hits = [s for s in spans if s.start < b and s.end > a]
            if not hits:
                continue
            segs, cur = [], a
            for s in hits:
                s0, s1 = max(s.start, a), min(s.end, b)
                if s0 > cur:
                    segs.append((cur - a, s0 - a, None))
                if s1 > max(s0, cur):
                    segs.append((max(s0, cur) - a, s1 - a, s))
                cur = max(cur, s1)
            if cur < b:
                segs.append((cur - a, b - a, None))
            _split_run(run, rtext, segs, ctx)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- Excel

def _xlsx(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    import openpyxl
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.styles.colors import Color

    try:
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        wb = openpyxl.load_workbook(io.BytesIO(data), keep_vba=ext == ".xlsm", rich_text=True)
    except Exception as e:
        raise OverlayError(f"Could not open this Excel file ({e}).") from None
    if any(n.startswith(("xl/charts/", "xl/drawings/")) for n in names):
        ctx.notes.append("Charts, shapes and pictures in this workbook are not kept in the colored copy.")
    cells = [c for ws in wb.worksheets for row in ws.iter_rows() for c in row
             if c.value is not None and c.data_type != "f"]
    ctx.prepare([c.value for c in cells if isinstance(c.value, str)])

    def colored(cell, cat):
        f = copy.copy(cell.font)
        f.color = Color(rgb="FF" + _hex(ctx.colors[cat]).upper())
        cell.font = f

    for cell in cells:
        v = cell.value
        if isinstance(v, bool) or isinstance(v, CellRichText):
            continue
        if isinstance(v, (dt.datetime, dt.date, dt.time)):
            colored(cell, "date"); ctx.counts["date"] += 1
        elif isinstance(v, (int, float)):
            colored(cell, "number"); ctx.counts["number"] += 1
        elif isinstance(v, str):
            spans = [s for s in ctx.spans(v) if not (s.layer == "grammar" and ctx.mode == "d")]
            if not spans:
                continue
            base = cell.font
            def font(color):
                return InlineFont(rFont=base.name, sz=base.sz, b=base.b, i=base.i, u=base.u,
                                  strike=base.strike, vertAlign=base.vertAlign, color=color)
            plain = font(base.color)
            parts, cur = [], 0
            for s in spans:
                if s.start > cur:
                    parts.append(TextBlock(plain, v[cur:s.start]))
                parts.append(TextBlock(font(Color(rgb="FF" + _hex(ctx.colors[s.cat]).upper())), v[s.start:s.end]))
                cur = s.end
            if cur < len(v):
                parts.append(TextBlock(plain, v[cur:]))
            cell.value = CellRichText(parts)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
