"""Draw the app icons into synesthetic/static/ (run again after changing the colors below).

The icon is the upload card: a page whose lines are partly lettered in the category colors.
`.venv\\Scripts\\python.exe tools\\make_icons.py`
"""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent.parent / "synesthetic" / "static"
BG, CARD, EDGE, INK, GRAY = "#0e1014", "#1b1f27", "#2b303b", "#eceef2", "#3b414d"
NUMBER, DATE, WARNING, REFERENCE, LINK = "#6cb4ff", "#f2c14e", "#ff6b6b", "#b394ff", "#5fd38d"

# rows of (width, color) inside a 256-wide line, 12 apart
ROWS = [
    (160, 34, [(150, INK)]),
    (226, 26, [(48, GRAY), (60, NUMBER), (44, GRAY), (68, DATE)]),
    (274, 26, [(80, GRAY), (72, WARNING), (80, GRAY)]),
    (322, 26, [(92, REFERENCE), (64, GRAY), (76, LINK)]),
]


def sheet() -> str:
    parts = [f'<rect x="96" y="122" width="320" height="268" rx="36" fill="{CARD}" stroke="{EDGE}" stroke-width="4"/>']
    for y, h, bars in ROWS:
        x = 128
        for w, c in bars:
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{c}"/>')
            x += w + 12
    return "".join(parts)


def icon(maskable=False) -> str:
    # maskable: full-bleed background; the card's corners stay inside the safe circle (radius 204.8)
    bg = f'<rect width="512" height="512" fill="{BG}"/>' if maskable else f'<rect width="512" height="512" rx="112" fill="{BG}"/>'
    body = f'<g transform="translate(15.36 15.36) scale(.94)">{sheet()}</g>' if maskable else sheet()
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{bg}{body}</svg>'


def small() -> str:
    """Favicon: the same idea with three thick lines, readable at 16-32 px."""
    bars = [(14, [(30, INK)]), (28, [(16, NUMBER), (20, DATE)]), (42, [(22, REFERENCE), (14, WARNING)])]
    parts = [f'<rect width="64" height="64" rx="14" fill="{BG}"/>']
    for y, row in bars:
        x = 12
        for w, c in row:
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="9" rx="4.5" fill="{c}"/>')
            x += w + 4
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">{"".join(parts)}</svg>'


def png(svg: str, size: int, path: Path, alpha=True):
    doc = pymupdf.open(stream=svg.encode(), filetype="svg")
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(size / page.rect.width, size / page.rect.height), alpha=alpha)
    pix.save(path)


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "icon.svg").write_text(icon(), encoding="utf-8")
    (OUT / "favicon.svg").write_text(small(), encoding="utf-8")
    png(icon(), 192, OUT / "icon-192.png")
    png(icon(), 512, OUT / "icon-512.png")
    png(icon(maskable=True), 512, OUT / "icon-maskable-512.png", alpha=False)
    png(icon(maskable=True), 180, OUT / "apple-touch-icon.png", alpha=False)  # iOS rounds the corners itself
    png(small(), 32, OUT / "favicon-32.png")
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size)


if __name__ == "__main__":
    main()
