"""Build the sample files offered under "Try a sample file" in Synesthesize.

The weekly market wrap (synesthetic/examples/market-wrap.md) becomes a multi-page PDF and a Word file in
synesthetic/static/samples/, so the colors can be tried on a real-looking document with its own layout.
`.venv\\Scripts\\python.exe tools\\build_samples.py`
"""
import html
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synesthetic.extract import extract  # noqa: E402

SRC = ROOT / "synesthetic" / "examples" / "market-wrap.md"
OUT = ROOT / "synesthetic" / "static" / "samples"

CSS = """
body{font-family:sans-serif;font-size:10.5pt;color:#1d2026;line-height:1.45}
h1{font-family:serif;font-size:22pt;color:#0d2a4a;margin:0 0 6pt}
h2{font-family:serif;font-size:14pt;color:#0d2a4a;margin:16pt 0 5pt;border-bottom:0.75pt solid #9fb3c8;padding-bottom:2pt}
p{margin:0 0 7pt}
li{margin:0 0 4pt}
table{border-collapse:collapse;width:100%;margin:4pt 0 10pt}
th{color:#0d2a4a;text-align:left;font-weight:bold;padding:3pt 5pt;border:0.5pt solid #b7c4d3;border-bottom:1.5pt solid #0d2a4a}
td{padding:3pt 5pt;border:0.5pt solid #c9d3de}
.meta{color:#4b5565;font-size:9.5pt}
.note{color:#6b4d00;font-style:italic;font-size:9.5pt}
"""


def blocks_html(doc) -> str:
    out, open_list = [], None
    for i, b in enumerate(doc.blocks):
        if b.kind == "item":
            tag = "ol" if (b.marker or "").rstrip(".").isdigit() else "ul"
            if open_list != tag:
                if open_list:
                    out.append(f"</{open_list}>")
                out.append(f"<{tag}>")
                open_list = tag
            out.append(f"<li>{html.escape(b.text)}</li>")
            continue
        if open_list:
            out.append(f"</{open_list}>")
            open_list = None
        if b.kind == "heading":
            lvl = min(max(b.level or 2, 1), 3)
            out.append(f"<h{lvl}>{html.escape(b.text)}</h{lvl}>")
        elif b.kind == "table":
            rows = []
            for ri, row in enumerate(b.rows or []):
                tag = "th" if ri < b.header_rows else "td"
                rows.append("<tr>" + "".join(f"<{tag}>{html.escape(c.text)}</{tag}>" for c in row) + "</tr>")
            out.append("<table>" + "".join(rows) + "</table>")
        else:
            cls = ' class="meta"' if i == 1 else ' class="note"' if b.text.startswith("Sample document") else ""
            out.append(f"<p{cls}>{html.escape(b.text)}</p>")
    if open_list:
        out.append(f"</{open_list}>")
    return "".join(out)


def build_pdf(doc) -> bytes:
    import pymupdf

    story = pymupdf.Story(html=blocks_html(doc), user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    page_rect = pymupdf.paper_rect("letter")
    where = page_rect + (60, 64, -60, -64)
    more = True
    while more:
        dev = writer.begin_page(page_rect)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    pdf = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
    for n, page in enumerate(pdf, 1):  # a footer with the page number
        page.insert_text((60, page.rect.height - 34), f"Harbor Point Advisors · Weekly Market Wrap · Sample · Page {n} of {len(pdf)}",
                         fontsize=8, fontname="helv", color=(0.42, 0.46, 0.52))
    pdf.set_metadata({"title": "Weekly Market Wrap: S&P 500 (sample)", "author": "Synesthetic Layer sample"})
    return pdf.tobytes(garbage=3, deflate=True)


def build_docx(doc) -> bytes:
    import docx
    from docx.shared import Pt, RGBColor

    d = docx.Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(11)
    for i, b in enumerate(doc.blocks):
        if b.kind == "heading":
            d.add_heading(b.text, level=min(max(b.level or 2, 1), 3) - (0 if (b.level or 2) == 1 else 0))
        elif b.kind == "item":
            numbered = (b.marker or "").rstrip(".").isdigit()
            d.add_paragraph(b.text, style="List Number" if numbered else "List Bullet")
        elif b.kind == "table":
            rows = b.rows or []
            t = d.add_table(rows=len(rows), cols=max(len(r) for r in rows))
            t.style = "Light Grid Accent 1"
            for ri, row in enumerate(rows):
                for ci, c in enumerate(row):
                    t.cell(ri, ci).text = c.text
        else:
            p = d.add_paragraph()
            r = p.add_run(b.text)
            if i == 1 or b.text.startswith("Sample document"):
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(0x4B, 0x55, 0x65)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    doc = extract(SRC)
    (OUT / "market-wrap.pdf").write_bytes(build_pdf(doc))
    (OUT / "market-wrap.docx").write_bytes(build_docx(doc))
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
