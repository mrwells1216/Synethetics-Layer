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
    "font-weight:inherit;font-style:inherit;font-family:inherit;font-size:inherit"
)


def _cat_css(lens: Lens) -> str:
    out = [
        # grammar: muted text tint only, in every mode; meaning: marker highlight, in every mode
        "body .c.l-grammar{background:none;box-shadow:none;padding:0;text-decoration:none;color:var(--c)}",
        "body .c.l-meaning{background:color-mix(in srgb,var(--c) 42%,transparent);color:inherit;"
        "padding:.04em .28em;font-weight:600;box-shadow:none;text-decoration:none}",
        # underline-only mode keeps glyphs neutral: grammar goes plain, meaning becomes a heavy underline
        ".m-d .c.l-grammar{color:inherit}",
        ".m-d .c.l-meaning{background:none;padding:0;text-decoration-line:underline;"
        "text-decoration-color:var(--c);text-decoration-thickness:4px;text-underline-offset:.2em}",
    ]
    for c in lens.categories:
        decl = [f"--c:var(--c-{c.name})", f"--on:var(--on-{c.name})"]
        if c.font in FONTS:
            decl.append(FONTS[c.font])
        if c.weight:
            decl.append(f"font-weight:{c.weight}")
        out.append(f".c-{c.name}{{{';'.join(decl)}}}")
        if c.underline and c.underline != "none":
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
    label = _esc(cat.label if cat else sp.cat)
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
                    grammar=False, ai=None, log=print) -> str:
    counts: Counter = Counter()
    ann = make_annotator(_doc_texts(doc), lens, grammar=grammar, ai=ai, log=log)
    body = "\n".join(_block(b, lens, counts, ann) for b in doc.blocks)
    legend = _legend(lens, counts)
    notes = "".join(f'<div class="note">{_esc(n)}</div>' for n in doc.notes)
    title = doc.title or Path(doc.source).stem
    fills = {
        "TITLE": _esc(title),
        "CSS_VARS": _css_vars(lens),
        "CAT_CSS": _cat_css(lens),
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
                "off": [c.name for c in lens.categories if c.default_off],
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
