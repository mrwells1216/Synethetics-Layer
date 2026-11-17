"""Draw the app icons into synesthetic/static/ (run again after changing the colors below).

The icon is the Ribbon S: an S drawn as one thick ribbon in seven color segments, the same
shape the page header draws next to the name.
`.venv\\Scripts\\python.exe tools\\make_icons.py`
"""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent.parent / "synesthetic" / "static"
BG = "#0e1014"

# The S inside a 200 x 200 box: two arcs of radius 38 cut into seven equal pieces, top to bottom.
# (path, color, round ends). The two end pieces come first so the middle ones cover their inner caps.
RIBBON = [
    ("M132.91 47 A38 38 0 0 0 94.34 28.43", "#ff6b6b", True),
    ("M105.66 179.57 A38 38 0 0 1 67.09 161", "#b394ff", True),
    ("M94.34 28.43 A38 38 0 0 0 62.95 57.54", "#ff9f5a", False),
    ("M62.95 57.54 A38 38 0 0 0 78.59 97.4", "#f2c14e", False),
    ("M78.59 97.4 A38 38 0 0 0 100 104 A38 38 0 0 1 121.41 110.6", "#5fd38d", False),
    ("M121.41 110.6 A38 38 0 0 1 137.05 150.46", "#3dd6d0", False),
    ("M137.05 150.46 A38 38 0 0 1 105.66 179.57", "#6cb4ff", False),
]
CENTER = (100, 104)  # the middle of the S in that box


def ribbon(size: float, scale: float) -> str:
    """The S centered in a size x size square, drawn at `scale` times its 200-box size."""
    dx, dy = size / 2 - CENTER[0] * scale, size / 2 - CENTER[1] * scale
    parts = [
        f'<path d="{d}" stroke="{c}"' + (' stroke-linecap="round"' if cap else "") + "/>"
        for d, c, cap in RIBBON
    ]
    return (f'<g transform="translate({dx:.2f} {dy:.2f}) scale({scale})" fill="none" stroke-width="26">'
            + "".join(parts) + "</g>")


def icon(maskable=False) -> str:
    # maskable: full-bleed background; the S stays inside the safe circle (radius 204.8)
    bg = f'<rect width="512" height="512" fill="{BG}"/>' if maskable else f'<rect width="512" height="512" rx="112" fill="{BG}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{bg}'
            f'{ribbon(512, 1.7 if maskable else 2.0)}</svg>')


def small() -> str:
    """Favicon: the same S, filling more of the square so it reads at 16-32 px."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{BG}"/>{ribbon(64, 0.3)}</svg>')


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
