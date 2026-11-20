"""Render a Document to a self-contained HTML page."""
from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path

from .annotate import Lens, Span
from .colorcheck import contrast
from .layers import make_annotator
from .model import Block, Cell, Document

LAYER_LABELS = {"content": "Content types", "grammar": "Grammar", "meaning": "Meaning (AI)"}

TEMPLATE = Path(__file__).resolve().parent / "templates" / "page.html"
EMPH_TAG = {"b": "strong", "i": "em", "code": "code"}
FONTS = {
    "mono": "font-family:ui-monospace,Consolas,'Cascadia Mono',monospace;font-size:.93em",
    "serif": "font-family:Georgia,'Times New Roman',serif",
    "italic": "font-style:italic",
    "tabular": "font-variant-numeric:tabular-nums",
}


# Fonts a user may pick for body text and headings: key -> (label, CSS stack, Google Fonts family or None).
# Only these keys are accepted from a style, so no CSS from outside ever reaches the page.
FONT_CHOICES = {
    "atkinson": ("Atkinson Hyperlegible", "'Atkinson Hyperlegible Next','Atkinson Hyperlegible',system-ui,sans-serif",
                 "Atkinson+Hyperlegible+Next:ital,wght@0,300;0,400;0,700;1,300;1,400;1,700"),
    "lexend": ("Lexend", "Lexend,system-ui,sans-serif", "Lexend:wght@300..700"),
    "plex": ("IBM Plex Sans", "'IBM Plex Sans',system-ui,sans-serif", "IBM+Plex+Sans:ital,wght@0,300;0,400;0,600;0,700;1,300;1,400"),
    "space": ("Space Grotesk", "'Space Grotesk',system-ui,sans-serif", "Space+Grotesk:wght@300..700"),
    "system": ("System sans", "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif", None),
    "verdana": ("Verdana", "Verdana,Tahoma,sans-serif", None),
    "fraunces": ("Fraunces", "Fraunces,Georgia,serif", "Fraunces:opsz,wght@9..144,300..700"),
    "young": ("Young Serif", "'Young Serif',Georgia,serif", "Young+Serif"),
    "literata": ("Literata", "Literata,Georgia,serif", "Literata:ital,wght@0,300;0,400;0,700;1,300;1,400"),
    "source-serif": ("Source Serif", "'Source Serif 4',Georgia,serif", "Source+Serif+4:ital,wght@0,300;0,400;0,700;1,300;1,400"),
    "georgia": ("Georgia", "Georgia,'Iowan Old Style','Times New Roman',serif", None),
    "arial": ("Arial", "Arial,Helvetica,sans-serif", None),
    "times": ("Times New Roman", "'Times New Roman',Times,serif", None),
    "courier": ("Courier New", "'Courier New',Courier,monospace", None),
}
STYLE_DEFAULTS = {"body": "atkinson", "heading": "fraunces", "size": 100, "mode": "c", "theme": "dark"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def clean_style(style, lens: Lens) -> dict:
    """Keep only well-formed values from a user style (colors per category and theme, fonts from
    FONT_CHOICES, size 80-150 %, mode, theme). Anything else is dropped."""
    out: dict = {"dark": {}, "light": {}}
    if not isinstance(style, dict):
        return out
    colors = style.get("colors")
    if isinstance(colors, dict):
        for name, pair in colors.items():
            if lens.get(name) and isinstance(pair, dict):
                for t in ("dark", "light"):
                    c = pair.get(t)
                    if isinstance(c, str) and _HEX.match(c):
                        out[t][name] = c.lower()
    for k in ("body", "heading"):
        if style.get(k) in FONT_CHOICES:
            out[k] = style[k]
    size = style.get("size")
    if isinstance(size, (int, float)) and not isinstance(size, bool) and 80 <= size <= 150:
        out["size"] = round(size)
    if style.get("mode") in ("a", "b", "c", "d"):
        out["mode"] = style["mode"]
    if style.get("theme") in ("auto", "dark", "light"):
        out["theme"] = style["theme"]
    if style.get("palette") in ("default", "cb"):
        out["palette"] = style["palette"]
    if style.get("hl") in HL_SIZES:
        out["hl"] = style["hl"]
    if style.get("pdf") in ("restyle", "notes"):
        out["pdf"] = style["pdf"]
    look = style.get("look")
    if isinstance(look, dict):  # per category: ALL CAPS, size, bold or thin, italic, underline and its color
        clean = {}
        for name, v in look.items():
            c = lens.get(name)
            if not c or c.layer not in ("content", "grammar") or not isinstance(v, dict):
                continue
            item = {}
            if v.get("case") in ("upper", "normal"):
                item["case"] = v["case"]
            if _num(v.get("scale"), 0.8, 2.0):
                item["scale"] = round(float(v["scale"]), 2)
            for k in ("bold", "thin", "italic"):
                if isinstance(v.get(k), bool):
                    item[k] = v[k]
            if item.get("bold") and item.get("thin"):
                del item["thin"]
            if v.get("underline") in UNDERLINES:
                item["underline"] = v["underline"]
            if isinstance(v.get("ul"), str) and _HEX.match(v["ul"]):
                item["ul"] = v["ul"].lower()
            if item:
                clean[name] = item
        if clean:
            out["look"] = clean
    off = style.get("off")
    if isinstance(off, dict):   # categories the reader switched off everywhere
        names = [n for n, v in off.items() if v is True and lens.get(n) and lens.get(n).layer in ("content", "grammar")]
        if names:
            out["off"] = sorted(names)
    bank = clean_bank(style.get("wordbank"), lens)
    if bank:
        out["wordbank"] = bank
    return out


UNDERLINES = ("none", "solid", "dotted", "dashed", "double", "wavy")


def chat_style(style, lens: Lens) -> dict:
    """The Editor's looks as the chat add-on reads them: colors per category and theme, the highlight
    style, theme and palette, each category's look, the categories switched off and the Word Bank."""
    from datetime import datetime, timezone

    st = clean_style(style, lens)
    colors: dict = {}
    for theme in ("dark", "light"):
        for name, c in st[theme].items():
            colors.setdefault(name, {})[theme] = c
    return {"colors": colors, "mode": st.get("mode", "c"), "theme": st.get("theme", "dark"),
            "palette": st.get("palette", "default"), "look": st.get("look", {}), "off": st.get("off", []),
            "words": st.get("wordbank", []), "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def default_look(c) -> dict:
    """A content or grammar category's look from the lens: ALL CAPS, size, bold, italic and underline style.
    The underline color is the text's own color unless a look sets "ul"."""
    return {"case": c.case, "scale": c.scale, "bold": c.weight >= 600, "thin": 0 < c.weight <= 300,
            "italic": c.font == "italic", "underline": c.underline if c.underline in UNDERLINES else "none"}


def look_for(c, user: dict | None) -> dict:
    return {**default_look(c), **(user or {})}


def underline_rules(sel: str, style: str) -> list[str]:
    """Underline for one category in each highlight style. Its color is --ul when the reader picked one,
    else the category color (on a filled chip, the chip's text color)."""
    if style == "none":
        return [f".m-a {sel},.m-b {sel},.m-c {sel}{{text-decoration:none}}",
                f".m-d {sel}{{text-decoration-style:solid}}"]
    line = (f"text-decoration-line:underline;text-decoration-style:{style};text-decoration-thickness:2px;"
            "text-underline-offset:.22em")
    return [f".m-a {sel},.m-c {sel}{{{line};text-decoration-color:var(--ul,var(--c))}}",
            f".m-b {sel}{{{line};text-decoration-color:var(--ul,var(--on))}}",
            f".m-d {sel}{{text-decoration-style:{style}}}"]


def look_rules(name: str, lk: dict, layer: str = "content") -> list[str]:
    """The whole look of a content or grammar category as CSS (the app's lookCss writes the same rules).
    A grammar rule names the layer too, so it outranks the page's own grammar rules; none of them
    applies while the category is switched off (body.off-NAME)."""
    sel = (f".c.l-grammar.c-{name}" if layer == "grammar" else f".c-{name}") + f":not(.off-{name} *)"
    d = ["text-transform:" + ("uppercase" if lk.get("case") == "upper" else "none"),
         f"font-size:{float(lk.get('scale', 1)):g}em",
         "font-weight:" + ("700" if lk.get("bold") else "300" if lk.get("thin") else "inherit"),
         "font-style:" + ("italic" if lk.get("italic") else "inherit")]
    if lk.get("ul"):
        d.append(f"--ul:{lk['ul']}")
    return [f"{sel}{{{';'.join(d)}}}", *underline_rules(sel, lk.get("underline", "none"))]


def _num(v, lo, hi) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def clean_bank(bank, lens: Lens | None = None) -> list[dict]:
    """The Word Bank: your own words, each with its own look, used in every document while it is on.
    An entry with "cat" takes that category's look instead ("treat encounter as a noun").
    Returns the usable entries (an empty list when the bank is off)."""
    if not isinstance(bank, dict) or not bank.get("on") or not isinstance(bank.get("words"), list):
        return []
    out = []
    for w in bank["words"][:200]:
        if not isinstance(w, dict) or w.get("off"):
            continue
        word = w.get("word")
        if not isinstance(word, str) or not word.strip() or len(word) > 80:
            continue
        e = {"word": word.strip()}
        for k in ("color", "bg"):
            if isinstance(w.get(k), str) and _HEX.match(w[k]):
                e[k] = w[k].lower()
        if w.get("font") in FONT_CHOICES:
            e["font"] = w["font"]
        if _num(w.get("size"), 0.8, 2.5):
            e["size"] = round(float(w["size"]), 2)
        for k in ("caps", "bold", "italic", "underline"):
            if w.get(k) is True:
                e[k] = True
        cat = w.get("cat")
        if lens is not None and isinstance(cat, str) and lens.get(cat) and lens.get(cat).layer in ("content", "grammar"):
            e = {"word": e["word"], "cat": cat}
        out.append(e)
    return out


def bank_spans(text: str, bank: list[dict], lens: Lens | None = None) -> list[Span]:
    """Whole-word, case-insensitive matches of the Word Bank. Earlier words win an overlap.
    A "treat as" entry becomes a span of that category."""
    taken = bytearray(len(text))
    out = []
    for i, e in enumerate(bank):
        for m in re.finditer(r"(?<!\w)" + re.escape(e["word"]) + r"(?!\w)", text, re.I):
            a, b = m.span()
            if b > a and not any(taken[a:b]):
                taken[a:b] = b"\x01" * (b - a)
                if e.get("cat"):
                    c = lens.get(e["cat"]) if lens else None
                    out.append(Span(a, b, e["cat"], c.layer if c else "content"))
                else:
                    out.append(Span(a, b, f"wb-{i}", "bank"))
    return sorted(out, key=lambda sp: sp.start)


def with_bank(spans: list[Span], bank_hits: list[Span]) -> list[Span]:
    """Word Bank spans replace any other span that touches them (meaning spans still wrap them)."""
    if not bank_hits:
        return spans
    keep = [s for s in spans if s.layer == "meaning"
            or not any(s.start < b.end and b.start < s.end for b in bank_hits)]
    return sorted(keep + bank_hits, key=lambda sp: sp.start)


def bank_css(bank: list[dict]) -> str:
    rules = []
    for i, e in enumerate(bank):
        if "cat" in e:
            continue   # drawn as its category
        d = []
        if "color" in e:
            d.append(f"color:{e['color']}")
        if "bg" in e:
            d.append(f"background:{e['bg']};padding:.04em .3em;box-shadow:none")
            if "color" not in e:
                d.append(f"color:{_on(e['bg'])}")
        else:
            d.append("background:none;box-shadow:none;padding:0")
        if e.get("caps"):
            d.append("text-transform:uppercase")
        if "font" in e:
            d.append(f"font-family:{FONT_CHOICES[e['font']][1]}")
        if "size" in e:
            d.append(f"font-size:{e['size']}em")
        if e.get("bold"):
            d.append("font-weight:700")
        if e.get("italic"):
            d.append("font-style:italic")
        d.append("text-decoration:" + (f"underline 2px {e.get('color', 'currentColor')}" if e.get("underline") else "none"))
        rules.append(f"body .c.c-wb-{i}{{{';'.join(d)}}}")
    return "".join(rules)


# highlight size: how much room a highlight takes (chip padding, underline thickness)
HL_SIZES = {
    "sm": ".m-b .c{padding:0 .2em}.m-c .c{padding:0 .16em;box-shadow:inset 0 -1px 0 color-mix(in srgb,var(--c) 70%,transparent)}"
          ".m-d .c{text-decoration-thickness:2px}",
    "md": "",
    "lg": ".m-b .c{padding:.12em .5em}.m-c .c{padding:.1em .42em;box-shadow:inset 0 -3px 0 color-mix(in srgb,var(--c) 75%,transparent)}"
          ".m-d .c{text-decoration-thickness:4px;text-underline-offset:.26em}",
}


def _custom_css(st: dict, lens: Lens | None = None) -> tuple[str, str]:
    """CSS and <head> font links for a cleaned style. Custom colors apply to the standard palette;
    the color-blind palette stays as designed."""
    css = []
    for theme, sel in (("dark", ':root:not([data-theme="light"]):not([data-pal="cb"])'),
                       ("light", ':root[data-theme="light"]:not([data-pal="cb"])')):
        if st[theme]:
            decl = ";".join(f"--c-{n}:{c};--on-{n}:{_on(c)}" for n, c in sorted(st[theme].items()))
            css.append(f"{sel}{{{decl}}}")
    if "body" in st:
        css.append(f"body{{font-family:{FONT_CHOICES[st['body']][1]}}}")
    if "heading" in st:
        css.append(f"h1,h2,h3,h4,h5,h6{{font-family:{FONT_CHOICES[st['heading']][1]}}}")
    if "size" in st:
        k = st["size"] / 100
        css.append(f"body{{font-size:{17 * k:.1f}px}}@media (max-width:560px){{body{{font-size:{16 * k:.1f}px}}}}")
    if st.get("hl"):
        css.append(HL_SIZES[st["hl"]])
    for name, v in st.get("look", {}).items():
        c = lens.get(name) if lens else None
        if c:
            css.extend(look_rules(name, look_for(c, v), c.layer))
    bank_fonts = set()
    if st.get("wordbank"):
        css.append(bank_css(st["wordbank"]))
        bank_fonts = {FONT_CHOICES[e["font"]][2] for e in st["wordbank"] if "font" in e}
    families = sorted(({FONT_CHOICES[st[k]][2] for k in ("body", "heading") if k in st} | bank_fonts) - {None})
    links = ""
    if families:
        q = "&".join(f"family={f}" for f in families)
        links = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
                 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                 f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{q}&display=swap">')
    return "\n".join(css), links


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _on(hexcolor: str) -> str:
    """Readable text color for a chip filled with hexcolor (same contrast math as colorcheck)."""
    return "#101216" if contrast(hexcolor, "#101216") >= contrast(hexcolor, "#ffffff") else "#ffffff"


def _css_vars(lens: Lens) -> str:
    def block(sel: str, key: str) -> str:
        parts = []
        for c in lens.categories:
            col = c.colors[key]
            parts.append(f"--c-{c.name}:{col};--on-{c.name}:{_on(col)}")
        return f"{sel}{{{';'.join(parts)}}}"

    return "\n".join(
        [
            block(":root", "dark"),
            block(':root[data-theme="light"]', "light"),
            block(':root[data-pal="cb"]', "cb_dark"),
            block(':root[data-theme="light"][data-pal="cb"]', "cb_light"),
        ]
    )


_RESET = (
    "color:inherit;background:none;box-shadow:none;padding:0;text-decoration:none;"
    "font-weight:inherit;font-style:inherit;font-family:inherit;font-size:inherit;text-transform:none"
)


def _cat_css(lens: Lens) -> str:
    out = [
        # grammar: muted text tint only, in every mode; meaning: marker highlight, in every mode
        "body .c.l-grammar{background:none;box-shadow:none;padding:0;text-decoration:none;color:var(--c)}",
        "body .c.l-meaning{background:color-mix(in srgb,var(--c) 42%,transparent);color:inherit;"
        "padding:.04em .28em;font-weight:600;box-shadow:none;text-decoration:none}",
        # underline-only mode keeps glyphs neutral: grammar goes plain, meaning becomes a heavy underline
        ".m-d .c.l-grammar{color:inherit;font-weight:inherit;font-style:inherit}",
        ".m-d .c.l-meaning{background:none;padding:0;text-decoration-line:underline;"
        "text-decoration-color:var(--c);text-decoration-thickness:4px;text-underline-offset:.2em}",
    ]
    for c in lens.categories:
        decl = [f"--c:var(--c-{c.name})", f"--on:var(--on-{c.name})"]
        if c.font in FONTS:
            decl.append(FONTS[c.font])
        if c.weight:
            decl.append(f"font-weight:{c.weight}")
        if c.case == "upper":
            decl.append("text-transform:uppercase")
        if c.scale != 1:
            decl.append(f"font-size:{c.scale:g}em")
        out.append(f".c-{c.name}{{{';'.join(decl)}}}")
        if c.layer == "content":   # underline in every highlight style, in its own color when one is set
            out.extend(underline_rules(f".c-{c.name}", default_look(c)["underline"]))
        elif c.layer == "grammar":   # a grammar word's own underline, thin, in every style but underline-only
            if c.underline in UNDERLINES and c.underline != "none":
                out.append(f":is(.m-a,.m-b,.m-c) .c.l-grammar.c-{c.name}{{text-decoration:underline {c.underline} "
                           "var(--c);text-decoration-thickness:1px;text-underline-offset:.2em}")
        elif c.underline and c.underline != "none":
            out.append(
                f".m-a .c-{c.name},.m-c .c-{c.name}{{text-decoration:underline {c.underline} var(--c);"
                f"text-decoration-thickness:1px;text-underline-offset:.22em}}"
            )
            out.append(f".m-d .c-{c.name}{{text-decoration-style:{c.underline}}}")
        else:
            out.append(f".m-d .c-{c.name}{{text-decoration-style:solid}}")
        out.append(f"body.off-{c.name} .c-{c.name}{{{_RESET}}}")
    for layer in ("content", "grammar", "meaning"):
        out.append(f"body.off-layer-{layer} .c.l-{layer}{{{_RESET}}}")
    return "\n".join(out)


def _region(text: str, a: int, b: int, emph) -> str:
    if a >= b:
        return ""
    cuts = {a, b}
    for s, e, _ in emph:
        if a < s < b:
            cuts.add(s)
        if a < e < b:
            cuts.add(e)
    pts = sorted(cuts)
    out = []
    for x, y in zip(pts, pts[1:]):
        frag = _esc(text[x:y])
        for s, e, st in emph:
            if s <= x and e >= y:
                tag = EMPH_TAG[st]
                frag = f"<{tag}>{frag}</{tag}>"
        out.append(frag)
    return "".join(out)


def _open(sp, lens: Lens) -> str:
    cat = lens.get(sp.cat)
    label = _esc(cat.label if cat else "Word Bank" if sp.layer == "bank" else sp.cat)
    return f'<span class="c c-{sp.cat} l-{sp.layer}" data-cat="{sp.cat}" title="{label}">'


def _flat(text: str, a: int, b: int, spans, emph, lens: Lens) -> str:
    """Render text[a:b] with non-nested spans, clipping any that cross the edges."""
    out = []
    pos = a
    for sp in spans:
        s, e = max(sp.start, pos), min(sp.end, b)
        if e <= s:
            continue
        out.append(_region(text, pos, s, emph))
        out.append(_open(sp, lens) + _region(text, s, e, emph) + "</span>")
        pos = e
    out.append(_region(text, pos, b, emph))
    return "".join(out)


def _inline(text: str, spans, emph, lens: Lens, counts: Counter) -> str:
    """Meaning-layer spans wrap the content/grammar spans that fall inside them."""
    for sp in spans:
        counts[sp.cat] += 1
    meaning = [s for s in spans if s.layer == "meaning"]
    flat = sorted((s for s in spans if s.layer != "meaning"), key=lambda s: s.start)
    if not meaning:
        return _flat(text, 0, len(text), flat, emph, lens)
    out = []
    pos = 0
    for m in meaning:
        if m.start < pos:
            continue
        out.append(_flat(text, pos, m.start, flat, emph, lens))
        out.append(_open(m, lens) + _flat(text, m.start, m.end, flat, emph, lens) + "</span>")
        pos = m.end
    out.append(_flat(text, pos, len(text), flat, emph, lens))
    return "".join(out)


def _cell_html(cell: Cell, lens: Lens, counts: Counter, ann) -> tuple[str, str]:
    text = cell.text
    if cell.ctype in ("number", "date") and text:
        spans = [Span(0, len(text), cell.ctype)]
        cls = " num" if cell.ctype == "number" else ""
    else:
        spans = ann(text)
        cls = ""
    return _inline(text, spans, [], lens, counts), cls


def _block(b: Block, lens: Lens, counts: Counter, ann) -> str:
    k = b.kind
    if k == "heading":
        lvl = min(max(b.level or 2, 1), 6)
        return f"<h{lvl}>{_esc(b.text)}</h{lvl}>"
    if k == "rule":
        return f'<div class="pg">{_esc(b.text)}</div>' if b.text else "<hr>"
    if k == "code":
        return f"<pre><code>{_esc(b.text)}</code></pre>"
    if k == "table":
        rows = b.rows or []
        out = ['<div class="tw"><table>']
        for ri, row in enumerate(rows):
            is_head = ri < b.header_rows
            out.append("<tr>")
            for cell in row:
                if is_head:
                    out.append(f"<th>{_esc(cell.text)}</th>")
                else:
                    inner, cls = _cell_html(cell, lens, counts, ann)
                    out.append(f'<td class="{cls.strip()}">{inner}</td>' if cls else f"<td>{inner}</td>")
            out.append("</tr>")
        out.append("</table></div>")
        return "".join(out)
    spans = ann(b.text)
    inner = _inline(b.text, spans, b.emph, lens, counts)
    if k == "para":
        style = f' style="margin-left:{b.level * 1.4}em"' if b.level else ""
        return f"<p{style}>{inner}</p>"
    if k == "item":
        return (
            f'<div class="li" style="--lvl:{b.level}"><span class="mk">{_esc(b.marker or "•")}</span>'
            f'<span class="tx">{inner}</span></div>'
        )
    if k == "quote":
        return f"<blockquote>{inner}</blockquote>"
    return f"<p>{inner}</p>"


def _doc_texts(doc: Document) -> list[str]:
    texts = []
    for b in doc.blocks:
        if b.kind in ("para", "item", "quote"):
            texts.append(b.text)
        elif b.kind == "table":
            for ri, row in enumerate(b.rows or []):
                if ri >= b.header_rows:
                    texts.extend(c.text for c in row if not c.ctype)
    return texts


def _legend(lens: Lens, counts: Counter) -> str:
    groups = []
    for layer in ("content", "grammar", "meaning"):
        cats = [c for c in lens.categories if c.layer == layer and counts[c.name]]
        if not cats:
            continue
        items = "".join(
            f'<label><input type="checkbox" data-c="{c.name}" checked>'
            f'<span class="c c-{c.name} l-{layer}" title="{_esc(c.example)}">{_esc(c.label)}</span>'
            f'<span class="n">{counts[c.name]}</span></label>'
            for c in cats
        )
        head = (
            f'<label class="lh"><input type="checkbox" data-c="layer-{layer}" checked>'
            f"{LAYER_LABELS[layer]}</label>"
        )
        groups.append(f'<div class="lg">{head}{items}</div>')
    return "".join(groups)


def render_document(doc: Document, lens: Lens, *, mode="c", theme="auto", palette="default",
                    grammar=False, ai=None, log=print, style=None) -> str:
    st = clean_style(style, lens)
    mode, theme, palette = st.get("mode", mode), st.get("theme", theme), st.get("palette", palette)
    custom_css, font_links = _custom_css(st, lens)
    counts: Counter = Counter()
    ann = make_annotator(_doc_texts(doc), lens, grammar=grammar, ai=ai, log=log)
    if st.get("wordbank"):
        base, bank = ann, st["wordbank"]
        ann = lambda text: with_bank(base(text), bank_spans(text, bank, lens))  # noqa: E731
    body = "\n".join(_block(b, lens, counts, ann) for b in doc.blocks)
    legend = _legend(lens, counts)
    notes = "".join(f'<div class="note">{_esc(n)}</div>' for n in doc.notes)
    title = doc.title or Path(doc.source).stem
    fills = {
        "TITLE": _esc(title),
        "CSS_VARS": _css_vars(lens),
        "CAT_CSS": _cat_css(lens),
        "CUSTOM_CSS": custom_css,
        "FONT_LINKS": font_links,
        "LEGEND": legend or '<span class="n">Nothing detected.</span>',
        "NOTES": notes,
        "SOURCE": _esc(Path(doc.source).name),
        "MODE": mode,
        "BODY": body,
        "DEFAULTS": json.dumps(
            {
                "mode": mode,
                "theme": theme,
                "palette": palette,
                "off": sorted({c.name for c in lens.categories if c.default_off} | set(st.get("off", []))),
            }
        ),
    }
    # one pass, so a literal "{{BODY}}" inside the document text is never filled in
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fills[m.group(1)], TEMPLATE.read_text(encoding="utf-8"))


def render_index(entries: list[dict], root_name: str) -> str:
    """entries: {href, name, kind, status} dicts."""
    rows = []
    for e in entries:
        if e.get("href"):
            link = f'<a href="{_esc(e["href"])}">{_esc(e["name"])}</a>'
        else:
            link = f'{_esc(e["name"])}'
        rows.append(f"<tr><td>{link}</td><td>{_esc(e['kind'])}</td><td>{_esc(e['status'])}</td></tr>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Synesthetic index</title>
<style>
:root{{color-scheme:dark light}}
body{{margin:0;font:16px/1.6 system-ui,sans-serif;background:#14161b;color:#e6e8ec}}
@media (prefers-color-scheme:light){{body{{background:#fbfbf8;color:#1d2026}}}}
main{{max-width:900px;margin:0 auto;padding:24px 16px}}
h1{{font-family:Georgia,serif}}a{{color:#6cb4ff}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 10px;border-bottom:1px solid #8884;text-align:left}}
</style></head><body><main><h1>{_esc(root_name)}</h1>
<p>{len(entries)} files.</p>
<table><tr><th>File</th><th>Type</th><th>Status</th></tr>{''.join(rows)}</table></main></body></html>"""
