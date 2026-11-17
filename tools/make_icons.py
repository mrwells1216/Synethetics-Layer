"""Draw the app icons into synesthetic/static/ (run again after changing the colors below).

The icon is the Bookshelf: seven book spines in the seven category colors standing on a shelf,
the last one leaning. The page header draws the same shape next to the name.
`.venv\\Scripts\\python.exe tools\\make_icons.py`
"""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent.parent / "synesthetic" / "static"
BG = "#0e1014"
SHELF = "#eceef2"

# The books inside a 200 x 200 box, all standing on y = 168: (x, top, width, color).
# The leaning one is drawn first so its neighbor covers the corner it tips into.
LEANING = (170, 56, 20, "#b394ff")   # turned 12 degrees about its bottom right corner
BOOKS = [
    (22, 50, 20, "#ff6b6b"),
    (44, 72, 18, "#ff9f5a"),
    (64, 40, 24, "#f2c14e"),
    (90, 64, 18, "#5fd38d"),
    (110, 48, 22, "#3dd6d0"),
    (134, 78, 18, "#6cb4ff"),
]
CENTER = (102, 108.5)  # the middle of the drawing in that box (it spans x 10-194, y 40-177)


def book(x, top, w, color, extra="") -> str:
    return f'<rect x="{x}" y="{top}" width="{w}" height="{168 - top}" rx="5" fill="{color}"{extra}/>'


def shelf(size: float, scale: float) -> str:
    """The bookshelf centered in a size x size square, drawn at `scale` times its 200-box size."""
    dx, dy = size / 2 - CENTER[0] * scale, size / 2 - CENTER[1] * scale
    x, top, w, color = LEANING
    parts = [book(x, top, w, color, f' transform="rotate(-12 {x + w} 168)"')]
    parts += [book(*b) for b in BOOKS]
    parts.append(f'<rect x="10" y="166" width="184" height="11" rx="5.5" fill="{SHELF}"/>')
    return f'<g transform="translate({dx:.2f} {dy:.2f}) scale({scale})">' + "".join(parts) + "</g>"


def icon(maskable=False) -> str:
    # maskable: full-bleed background; the shelf stays inside the safe circle (radius 204.8)
    bg = f'<rect width="512" height="512" fill="{BG}"/>' if maskable else f'<rect width="512" height="512" rx="112" fill="{BG}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{bg}'
            f'{shelf(512, 1.6 if maskable else 2.1)}</svg>')


def small() -> str:
    """Favicon: the same shelf, filling more of the square so it reads at 16-32 px."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{BG}"/>{shelf(64, 0.3)}</svg>')


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
