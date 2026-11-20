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
from .render import FONT_CHOICES, bank_spans, clean_style, default_look, with_bank

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
            grammar: bool = False, only: dict | None = None, log=print) -> Overlay:
    """`only`: the roller's choice, {unit number: [(start, end), ...]} as numbered by layout_units();
    when given, only matches that touch those ranges are colored."""
    ext = Path(name).suffix.lower()
    if ext not in OVERLAY_TYPES:
        raise OverlayError(f"Keeping the original look works for {', '.join(sorted(OVERLAY_TYPES))} files. "
                           "Other types get the styled page.")
    st = clean_style(style, lens)
    ctx = _Ctx(lens, _palette(lens, style, palette), st.get("mode", "c"), grammar, log,
               bank=st.get("wordbank", []), look=st.get("look", {}), only=only, off=st.get("off", []))
    ctx.pdf = st.get("pdf", "restyle")
    fn = {".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx, ".xlsm": _xlsx}[ext]
    out = fn(data, ctx, ext)
    if not ctx.counts:
        ctx.notes.append("Nothing in this file matched a category, so it has no colors.")
    return Overlay(out, out_name(name), OVERLAY_TYPES[ext], ctx.counts, ctx.notes)


class _Ctx:
    def __init__(self, lens, colors, mode, grammar, log, bank=(), look=None, only=None, off=()):
        self.lens, self.colors, self.mode, self.grammar, self.log = lens, colors, mode, grammar, log
        self.bank, self.only = list(bank), only
        self.off = set(off)   # categories the reader switched off in the Editor
        self.pdf = "restyle"   # PDF words: "restyle" (new letters in place) or "notes" (highlight notes on top)
        self.counts: Counter = Counter()
        self.notes: list[str] = []
        self.ann = None
        # ALL CAPS, size, bold, italic and underline per category: the lens defaults, then the reader's own
        self.look = {c.name: default_look(c) for c in lens.categories if c.layer in ("content", "grammar")}
        for name, v in (look or {}).items():
            self.look.setdefault(name, {}).update(v)

    def prepare(self, texts):
        self.ann = make_annotator(texts, self.lens, grammar=self.grammar, log=self.log)

    def allowed(self, unit) -> bool:
        return self.only is None or bool(self.only.get(unit))

    def spans(self, text, unit=None):
        out = [s for s in self.ann(text) if s.layer != "meaning"]
        if self.bank:
            out = with_bank(out, bank_spans(text, self.bank, self.lens))
        out = [s for s in out if s.layer == "bank" or not (self.lens.get(s.cat) and self.lens.get(s.cat).default_off)]
        if self.off:
            out = [s for s in out if s.cat not in self.off]
        if self.only is not None:
            rs = self.only.get(unit, [])
            out = [s for s in out if any(s.start < b and s.end > a for a, b in rs)]
        for s in out:
            self.counts["Word Bank" if s.layer == "bank" else s.cat] += 1
        return out

    def entry(self, cat):
        return self.bank[int(cat[3:])] if cat.startswith("wb-") else None

    def color(self, cat) -> str:
        e = self.entry(cat)
        if e:
            return e.get("bg") or e.get("color") or "#ffd400"
        return self.colors[cat]

    def label(self, cat) -> str:
        e = self.entry(cat)
        return f"Word Bank: {e['word']}" if e else self.lens.get(cat).label


# ---------------------------------------------------------------- PDF

def _open_pdf(data: bytes):
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise OverlayError(f"Could not open this PDF ({e}).") from None
    if doc.needs_pass:
        raise OverlayError("This PDF is password-protected.")
    return doc


def _pdf_units(doc) -> list:
    """Text units of a PDF, one per text block: (page number, text, [rect or None per char],
    [line id per char], [glyph info or None per char]). Lines are joined with one space.
    Glyph info: (font name, size, flags, color, baseline origin, horizontal?)."""
    import pymupdf

    # ligatures split into their letters, so "ﬂ" in "inﬂation" still reads as "fl"
    flags = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES & ~pymupdf.TEXT_PRESERVE_LIGATURES
    units = []
    for pno, page in enumerate(doc):
        for bi, block in enumerate(page.get_text("rawdict", flags=flags)["blocks"]):
            if block.get("type") != 0:
                continue
            chars, rects, lines, info = [], [], [], []
            for li, line in enumerate(block["lines"]):
                if chars:
                    chars.append(" "); rects.append(None); lines.append(None); info.append(None)
                flat = abs(line.get("dir", (1, 0))[1]) < 1e-3 and line.get("dir", (1, 0))[0] > 0
                for span in line["spans"]:
                    for ch in span["chars"]:
                        chars.append(ch["c"]); rects.append(pymupdf.Rect(ch["bbox"])); lines.append((bi, li))
                        info.append((span["font"], span["size"], span["flags"], span["color"], tuple(ch["origin"]), flat))
            text = "".join(chars)
            if text.strip():
                units.append((pno, text, rects, lines, info))
    if not units:
        raise OverlayError("This PDF has no text layer (it's probably a scan), so there is nothing to color.")
    return units


# base-14 fonts by family, bold, italic: what restyled PDF words are set in
_BASE14 = {("sans", 0, 0): "helv", ("sans", 1, 0): "hebo", ("sans", 0, 1): "heit", ("sans", 1, 1): "hebi",
           ("serif", 0, 0): "tiro", ("serif", 1, 0): "tibo", ("serif", 0, 1): "tiit", ("serif", 1, 1): "tibi",
           ("mono", 0, 0): "cour", ("mono", 1, 0): "cobo", ("mono", 0, 1): "coit", ("mono", 1, 1): "cobi"}
_SERIF_CHOICES = {"fraunces", "young", "literata", "source-serif", "georgia", "times"}
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                        "\u2026": "...", "\u00a0": " ", "\u2212": "-"})


def _family(font: str, flags: int) -> str:
    n = font.lower()
    if flags & 8 or any(k in n for k in ("mono", "courier", "consol", "menlo")):
        return "mono"
    if "sans" not in n and (flags & 4 or any(k in n for k in ("times", "serif", "georgia", "roman", "garamond",
                                                                "cambria", "minion", "palatino", "book"))):
        return "serif"
    return "sans"


def _rgb_int(c: int) -> tuple:
    return ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255


def _restyle_look(sp, ctx: _Ctx, font: str, flags: int, color: int) -> dict:
    """How one matched PDF word is drawn: font, caps, size, text color, background and underline."""
    fam, bold, ital = _family(font, flags), bool(flags & 16) or "bold" in font.lower(), bool(flags & 2) or "italic" in font.lower()
    e = ctx.entry(sp.cat)
    if e:
        if "font" in e:
            fam = "mono" if e["font"] == "courier" else "serif" if e["font"] in _SERIF_CHOICES else "sans"
        return {"fam": fam, "bold": bold or e.get("bold", False), "ital": ital or e.get("italic", False),
                "caps": e.get("caps", False), "scale": e.get("size", 1),
                "ink": _rgb(e["color"]) if "color" in e else _rgb("#" + _on(e["bg"])) if "bg" in e else _rgb_int(color),
                "bg": _rgb(e["bg"]) if "bg" in e else None,
                "line": (_rgb(e.get("color", "#000000")) if e.get("underline") else None)}
    col = ctx.colors[sp.cat]
    look = ctx.look.get(sp.cat, {})
    if sp.layer == "grammar":   # a tint plus the word's own shape: bold, italic, a thin underline
        g = {"fam": fam, "bold": bold or look.get("bold", False), "ital": ital or look.get("italic", False),
             "caps": False, "scale": 1, "ink": _rgb(col), "bg": None, "line": None}
        if look.get("underline", "none") != "none":
            g.update(line=_rgb(col), lstyle=look["underline"])
        return g
    cat = ctx.lens.get(sp.cat)
    if cat.font in ("mono", "serif"):
        fam = cat.font
    out = {"fam": fam, "bold": bold or look.get("bold", False), "ital": ital or look.get("italic", False),
           "caps": look.get("case") == "upper", "scale": look.get("scale", 1), "bg": None, "line": None}
    ul, style = look.get("ul"), look.get("underline", "none")
    if ctx.mode == "b":
        out.update(ink=_rgb("#" + _on(col)), bg=_rgb(col))
    elif ctx.mode == "c":
        out.update(ink=_rgb(col), bg=_rgb(col), alpha=0.22)
    elif ctx.mode == "d":   # underline-only: always underlined, in its style (solid when it has none)
        out.update(ink=_rgb_int(color), line=_rgb(ul or col), lstyle=style if style != "none" else "solid")
    else:
        out.update(ink=_rgb(col))
    if ctx.mode != "d" and style != "none":   # its own underline, in the underline color or the text's
        out.update(line=_rgb(ul) if ul else out["ink"], lstyle=style)
    return out


def _underline(page, x: float, y: float, w: float, fs: float, color, style: str):
    """An underline under a redrawn PDF word: solid, dotted, dashed, double or wavy."""
    import math

    lw = max(0.8, fs * 0.075)
    y0 = y + fs * 0.17
    if style == "double":
        for dy in (-lw * 0.9, lw * 0.9):
            page.draw_line((x, y0 + dy), (x + w, y0 + dy), color=color, width=lw * 0.7)
    elif style == "wavy":
        step, amp = fs * 0.09, lw * 1.1
        n = max(4, int(w / step))
        pts = [(x + w * i / n, y0 + amp * math.sin(i * math.pi / 2)) for i in range(n + 1)]
        page.draw_polyline(pts, color=color, width=lw * 0.85)
    elif style == "dotted":
        page.draw_line((x, y0), (x + w, y0), color=color, width=lw, dashes=f"[0 {lw * 2.2:.2f}] 0", lineCap=1)
    elif style == "dashed":
        page.draw_line((x, y0), (x + w, y0), color=color, width=lw, dashes=f"[{lw * 4:.2f} {lw * 2.5:.2f}] 0")
    else:
        page.draw_line((x, y0), (x + w, y0), color=color, width=lw)


def _segments(text, rects, lines, info, a, b):
    """The parts of text[a:b] on each line: (first index, last index) of non-space characters."""
    out, cur = [], None
    for i in range(a, b):
        if rects[i] is None or info[i] is None:
            continue
        if cur and lines[cur[0]] == lines[i]:
            if text[i].strip():
                cur[1] = i
        elif text[i].strip():
            cur = [i, i]
            out.append(cur)
    return out


def _paper(pix, box, zoom) -> tuple:
    """The color around a word on the rendered page (its paper, table shading or box), so covering
    the old word leaves no mark."""
    from collections import Counter as _C

    x0, y0 = max(int(box.x0 * zoom) - 2, 0), max(int(box.y0 * zoom) - 2, 0)
    x1, y1 = min(int(box.x1 * zoom) + 2, pix.width - 1), min(int(box.y1 * zoom) + 2, pix.height - 1)
    seen, sums = _C(), {}
    pts = [(x, y) for x in range(x0, x1 + 1, 2) for y in (y0, y1)] + [(x, y) for y in range(y0, y1 + 1, 2) for x in (x0, x1)]
    for x, y in pts:
        c = pix.pixel(x, y)[:3]
        key = tuple(v // 12 for v in c)
        seen[key] += 1
        t = sums.setdefault(key, [0, 0, 0])
        for i in range(3):
            t[i] += c[i]
    if not seen:
        return (1, 1, 1)
    key, n = seen.most_common(1)[0]
    return tuple(v / n / 255 for v in sums[key])


def _restyle_page(page, jobs, ctx):
    """Draw each matched word again in its new look, right where it was: the old word is covered with
    the color of the paper around it, so nothing else on the page moves."""
    import pymupdf

    zoom = 2
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    for j in jobs:
        page.draw_rect(j["rect"] + (-0.2, 0, 0.2, 0), color=None, fill=_paper(pix, j["rect"], zoom))
    for j in jobs:   # backgrounds next, so every word sits on top of its own; never over a neighbor
        if j["look"]["bg"]:
            x, y, fs, w = j["x"], j["y"], j["fs"], j["w"]
            x0 = max(x - fs * 0.14, (j["lo"] + x) / 2)
            x1 = max(min(x + w + fs * 0.14, (x + w + j["hi"]) / 2), x + w)
            page.draw_rect(pymupdf.Rect(x0, y - fs * 0.84, x1, y + fs * 0.24), color=None, fill=j["look"]["bg"],
                           fill_opacity=j["look"].get("alpha", 1), radius=0.18)
    for j in jobs:
        x, y, fs, w, k = j["x"], j["y"], j["fs"], j["w"], j["k"]
        pt = pymupdf.Point(x, y)
        page.insert_text(pt, j["text"], fontsize=fs, fontname=j["font"], color=j["look"]["ink"],
                         morph=(pt, pymupdf.Matrix(k, 1)) if k < 0.999 else None)
        if j["look"]["line"]:
            _underline(page, x, y, w, fs, j["look"]["line"], j["look"].get("lstyle", "solid"))


def _pdf(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    import pymupdf

    doc = _open_pdf(data)
    units = _pdf_units(doc)
    ctx.prepare([u[1] for u in units])
    marks: dict[tuple[int, str, str], list] = {}
    jobs: dict[int, list] = {}
    for ui, (pno, text, rects, lines, info) in enumerate(units):
        page = doc[pno]
        for sp in ctx.spans(text, ui):
            if sp.layer == "grammar" and ctx.mode == "d":
                continue  # underline-only mode keeps grammar plain, as on converted pages
            if ctx.pdf == "restyle" and page.rotation == 0:
                made = []
                for i0, i1 in _segments(text, rects, lines, info, sp.start, sp.end):
                    font, size, flags, color, origin, flat = info[i0]
                    word = text[i0:i1 + 1].translate(_PLAIN)
                    look = _restyle_look(sp, ctx, font, flags, color)
                    if look["caps"]:
                        word = word.upper()
                    try:
                        word.encode("latin-1")
                    except UnicodeEncodeError:
                        made = None
                        break
                    if not flat or size <= 0:
                        made = None
                        break
                    box = pymupdf.Rect(rects[i0])
                    for i in range(i0, i1 + 1):
                        if rects[i] is not None and not rects[i].is_empty:
                            box |= rects[i]
                    # room to grow: up to the next word on the same line, or the page margin
                    nxt = next((rects[j].x0 for j in range(i1 + 1, len(text))
                                if lines[j] == lines[i0] and rects[j] is not None and text[j].strip()), None)
                    prv = next((rects[j].x1 for j in range(i0 - 1, -1, -1)
                                if lines[j] == lines[i0] and rects[j] is not None and text[j].strip()), None)
                    # a bigger word may use a third of the space after it, so words stay apart; when it
                    # doesn't fit, its letters get narrower, then it may use more of the space, then it
                    # shrinks, but never below the size of the text around it
                    own = box.x1 - origin[0]
                    gap = max(nxt - box.x1, 0) if nxt is not None else min(page.rect.x1 - 24 - box.x1, own)
                    room, wide_room = own + gap * 0.35, own + gap * 0.85
                    fname = _BASE14[(look["fam"], int(look["bold"]), int(look["ital"]))]
                    fs = size * look["scale"]
                    w = pymupdf.get_text_length(word, fontname=fname, fontsize=fs)
                    k = 1.0
                    if w > room:
                        k = room / w
                        if k < 0.62:
                            fs = max(size, fs * room / (w * 0.62))
                            w = pymupdf.get_text_length(word, fontname=fname, fontsize=fs)
                            k = min(1.0, max(room / w, min(0.62, wide_room / w)))
                            k = max(k, 0.45)
                    made.append({"rect": box, "x": origin[0], "y": origin[1], "fs": fs, "w": w * k, "k": k,
                                 "text": word, "font": fname, "look": look,
                                 "lo": prv if prv is not None else origin[0] - fs * 0.3,
                                 "hi": nxt if nxt is not None else origin[0] + w * k + fs * 0.3})
                if made:
                    jobs.setdefault(pno, []).extend(made)
                    continue
                if made == []:
                    continue
            e = ctx.entry(sp.cat)
            if e:  # highlight notes: a Word Bank word gets its highlight or underline
                kind = "highlight" if "bg" in e or "underline" not in e else "underline"
            else:
                kind = "underline" if ctx.mode == "d" or sp.layer == "grammar" else "highlight"
            per_line: dict = {}
            for i in range(sp.start, sp.end):
                if rects[i] is None or not text[i].strip():
                    continue
                r = per_line.get(lines[i])
                per_line[lines[i]] = rects[i] if r is None else r | rects[i]
            marks.setdefault((pno, sp.cat, kind), []).extend(per_line.values())
    for pno, page_jobs in jobs.items():
        _restyle_page(doc[pno], page_jobs, ctx)
    for (pno, cat, kind), rects in marks.items():
        if not rects:
            continue
        page = doc[pno]
        add = page.add_highlight_annot if kind == "highlight" else page.add_underline_annot
        a = add(quads=[r.quad for r in rects])
        a.set_colors(stroke=_rgb(ctx.color(cat)))
        a.set_opacity(0.4 if kind == "highlight" else 0.9)
        a.set_info(title="Synesthetic Layer", content=ctx.label(cat))
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
_WORD_FONTS = {"mono": "Consolas", "serif": "Georgia"}


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


def _size(run) -> int:
    """The run's own size in half-points (Word's default 11 pt when it has none)."""
    rpr = run.find(_q("rPr"))
    sz = rpr.find(_q("sz")) if rpr is not None else None
    try:
        return int(sz.get(_q("val"))) if sz is not None else 22
    except (TypeError, ValueError):
        return 22


def _paint_bank(run, e: dict):
    if "font" in e:
        name = FONT_CHOICES[e["font"]][0]
        _set_rpr(run, "rFonts", {"ascii": name, "hAnsi": name, "cs": name})
    if e.get("bold"):
        _set_rpr(run, "b", {})
    if e.get("italic"):
        _set_rpr(run, "i", {})
    if e.get("caps"):
        _set_rpr(run, "caps", {})
    col = _hex(e["color"]).upper() if "color" in e else (_on(e["bg"]) if "bg" in e else None)
    if col:
        _set_rpr(run, "color", {"val": col})
    if "size" in e:
        _set_rpr(run, "sz", {"val": str(round(_size(run) * e["size"]))})
    if e.get("underline"):
        _set_rpr(run, "u", {"val": "single", **({"color": _hex(e["color"]).upper()} if "color" in e else {})})
    if "bg" in e:
        _set_rpr(run, "shd", {"val": "clear", "color": "auto", "fill": _hex(e["bg"]).upper()})


def _paint_run(run, cat: str, layer: str, ctx: _Ctx):
    e = ctx.entry(cat)
    if e:
        return _paint_bank(run, e)
    col = _hex(ctx.colors[cat]).upper()  # Word writes RGB in upper case
    look = ctx.look.get(cat, {})
    c = ctx.lens.get(cat)
    if layer == "content" and c is not None:   # the category's own font cues, as on colored pages
        if c.font in _WORD_FONTS:
            f = _WORD_FONTS[c.font]
            _set_rpr(run, "rFonts", {"ascii": f, "hAnsi": f, "cs": f})
        if look.get("bold"):
            _set_rpr(run, "b", {})
        if look.get("italic"):
            _set_rpr(run, "i", {})
    if layer == "content" and look.get("case") == "upper":
        _set_rpr(run, "caps", {})
    if layer == "content" and look.get("scale", 1) != 1:
        _set_rpr(run, "sz", {"val": str(round(_size(run) * look["scale"]))})
    if layer == "grammar":   # a tint plus the word's own shape; underline-only mode leaves grammar plain
        if ctx.mode != "d":
            _set_rpr(run, "color", {"val": col})
            if look.get("bold"):
                _set_rpr(run, "b", {})
            if look.get("italic"):
                _set_rpr(run, "i", {})
            if look.get("underline", "none") != "none":
                _set_rpr(run, "u", {"val": _U.get(look["underline"], "single"), "color": col})
        return
    style, ul = look.get("underline", "none"), (_hex(look["ul"]).upper() if look.get("ul") else None)
    if ctx.mode == "d":
        _set_rpr(run, "u", {"val": _U.get(style, "single"), "color": ul or col})
    elif ctx.mode == "b":
        _set_rpr(run, "color", {"val": _on(col)})
        _set_rpr(run, "shd", {"val": "clear", "color": "auto", "fill": col})
    else:
        _set_rpr(run, "color", {"val": col})
        if ctx.mode == "c":
            _set_rpr(run, "shd", {"val": "clear", "color": "auto", "fill": _tint(col)})
    if ctx.mode != "d" and style != "none":   # its own underline, in the underline color or the text's
        _set_rpr(run, "u", {"val": _U.get(style, "single"), "color": ul or (_on(col) if ctx.mode == "b" else col)})


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


def _open_docx(data: bytes):
    import docx

    try:
        return docx.Document(io.BytesIO(data))
    except Exception as e:
        raise OverlayError(f"Could not open this Word file ({e}).") from None


def _docx_paras(d) -> list:
    """Text units of a Word file: (runs, text) per paragraph with text, body first, then headers
    and footers."""
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
    return paras


def _docx(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    d = _open_docx(data)
    paras = _docx_paras(d)
    ctx.prepare([t for _r, t in paras])
    for ui, (runs, text) in enumerate(paras):
        spans = ctx.spans(text, ui)
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

def _open_xlsx(data: bytes, ext: str):
    import openpyxl

    try:
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        wb = openpyxl.load_workbook(io.BytesIO(data), keep_vba=ext == ".xlsm", rich_text=True)
    except Exception as e:
        raise OverlayError(f"Could not open this Excel file ({e}).") from None
    return wb, names


def _xlsx_cells(wb) -> list:
    """Text units of a workbook: every cell with a value that is not a formula, sheet by sheet."""
    return [c for ws in wb.worksheets for row in ws.iter_rows() for c in row
            if c.value is not None and c.data_type != "f"]


def _xlsx(data: bytes, ctx: _Ctx, ext: str) -> bytes:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.styles.colors import Color

    wb, names = _open_xlsx(data, ext)
    if any(n.startswith(("xl/charts/", "xl/drawings/")) for n in names):
        ctx.notes.append("Charts, shapes and pictures in this workbook are not kept in the colored copy.")
    cells = _xlsx_cells(wb)
    ctx.prepare([c.value for c in cells if isinstance(c.value, str)])

    def xl_under(style):   # Excel underlines are single or double, in the text's own color
        return None if style in (None, "none") else "double" if style == "double" else "single"

    def colored(cell, cat):
        f = copy.copy(cell.font)
        f.color = Color(rgb="FF" + _hex(ctx.colors[cat]).upper())
        lk = ctx.look.get(cat, {})
        scale = lk.get("scale", 1)
        if scale != 1:
            f.sz = round((f.sz or 11) * scale, 1)
        if lk.get("bold"):
            f.b = True
        if lk.get("italic"):
            f.i = True
        if xl_under(lk.get("underline")):
            f.u = xl_under(lk.get("underline"))
        cell.font = f

    for ui, cell in enumerate(cells):
        v = cell.value
        if isinstance(v, bool) or isinstance(v, CellRichText):
            continue
        if isinstance(v, (dt.datetime, dt.date, dt.time)):
            if ctx.allowed(ui):
                colored(cell, "date"); ctx.counts["date"] += 1
        elif isinstance(v, (int, float)):
            if ctx.allowed(ui):
                colored(cell, "number"); ctx.counts["number"] += 1
        elif isinstance(v, str):
            spans = [s for s in ctx.spans(v, ui) if not (s.layer == "grammar" and ctx.mode == "d")]
            if not spans:
                continue
            base = cell.font

            def font(color, e=None, scale=1):
                e = e or {}
                return InlineFont(rFont=FONT_CHOICES[e["font"]][0] if "font" in e else base.name,
                                  sz=round((base.sz or 11) * e.get("size", scale), 1) if ("size" in e or scale != 1) else base.sz,
                                  b=True if e.get("bold") else base.b, i=True if e.get("italic") else base.i,
                                  u=(e["underline"] if isinstance(e.get("underline"), str) else "single")
                                  if e.get("underline") else base.u,
                                  strike=base.strike, vertAlign=base.vertAlign, color=color)
            plain = font(base.color)
            parts, cur = [], 0
            for s in spans:
                if s.start > cur:
                    parts.append(TextBlock(plain, v[cur:s.start]))
                e = ctx.entry(s.cat)
                hexcol = (e.get("color") or e.get("bg") or "#000000") if e else ctx.colors[s.cat]
                scale = ctx.look.get(s.cat, {}).get("scale", 1) if s.layer == "content" else 1
                if not e and s.layer in ("content", "grammar"):
                    c, lk = ctx.lens.get(s.cat), ctx.look.get(s.cat, {})
                    e = {k: v for k, v in (("bold", lk.get("bold")), ("italic", lk.get("italic")),
                                           ("underline", xl_under(lk.get("underline")))) if v}
                    if c.font == "mono":
                        e["font"] = "courier"
                    elif c.font == "serif":
                        e["font"] = "georgia"
                parts.append(TextBlock(font(Color(rgb="FF" + _hex(hexcol).upper()), e, scale), v[s.start:s.end]))
                cur = s.end
            if cur < len(v):
                parts.append(TextBlock(plain, v[cur:]))
            cell.value = CellRichText(parts)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- the roller's view of a file

MAX_PAGES = 20
MAX_CELLS = 3000


def layout_units(name: str, data: bytes, *, width: int = 760) -> dict:
    """What the roller shows: the file's text units, numbered as overlay() numbers them.
    PDF: page pictures with each line's place on the page. Word: paragraphs. Excel: cells."""
    import base64

    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        import pymupdf

        doc = _open_pdf(data)
        units = _pdf_units(doc)
        pages = []
        for pno in range(min(len(doc), MAX_PAGES)):
            page = doc[pno]
            w, h = page.rect.width, page.rect.height
            pix = page.get_pixmap(matrix=pymupdf.Matrix(width / w, width / w))
            lines = []
            for ui, (upno, text, rects, lids, _info) in enumerate(units):
                if upno != pno:
                    continue
                i = 0
                while i < len(text):
                    if lids[i] is None:
                        i += 1
                        continue
                    j, box = i, None
                    while j < len(text) and lids[j] == lids[i]:
                        if rects[j] is not None and not rects[j].is_empty:
                            box = rects[j] if box is None else box | rects[j]
                        j += 1
                    if box is not None:
                        lines.append({"u": ui, "s": i, "t": text[i:j],
                                      "b": [round(box.x0 / w, 5), round(box.y0 / h, 5), round(box.x1 / w, 5), round(box.y1 / h, 5)]})
                    i = j
            pages.append({"w": w, "h": h, "lines": lines,
                          "img": "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpg", jpg_quality=62)).decode()})
        return {"kind": "pdf", "texts": [u[1] for u in units], "pages": pages, "total": len(doc)}
    if ext == ".docx":
        return {"kind": "docx", "texts": [t for _r, t in _docx_paras(_open_docx(data))]}
    if ext in (".xlsx", ".xlsm"):
        wb, _names = _open_xlsx(data, ext)
        cells = _xlsx_cells(wb)[:MAX_CELLS]
        texts, where = [], []
        for c in cells:
            v = c.value
            texts.append(v.isoformat() if isinstance(v, (dt.datetime, dt.date, dt.time)) else str(v))
            where.append([c.parent.title, c.row, c.column])
        return {"kind": "xlsx", "texts": texts, "where": where}
    raise OverlayError("The roller works on PDF, Word and Excel files.")


def parse_only(raw: str) -> dict | None:
    """The roller's choice from the page: "unit:start-end,start-end;unit;..." (a bare unit means all of it)."""
    if not raw:
        return None
    out: dict[int, list[tuple[int, int]]] = {}
    for part in raw.split(";"):
        if not part.strip():
            continue
        u, _, rs = part.partition(":")
        try:
            ui = int(u)
            if not rs:
                out.setdefault(ui, []).append((0, 10 ** 9))
                continue
            for r in rs.split(","):
                a, _, b = r.partition("-")
                out.setdefault(ui, []).append((int(a), int(b)))
        except ValueError:
            continue
    return out
