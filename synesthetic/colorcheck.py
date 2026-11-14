"""Contrast (WCAG 2.2) and color-vision-deficiency checks for a lens.

The research report asked for these as code, not by eye: every category color must meet 4.5:1
against its surface, and the colors must stay distinguishable under simulated red-green and
blue-yellow color blindness (Machado et al. 2009 matrices, severity 1.0).
"""
from __future__ import annotations

import itertools
import math

from .annotate import Lens

SURFACES = {"dark": "#14161b", "light": "#fbfbf8"}

# Machado, Oliveira and Fernandes 2009, severity 1.0, applied to linear RGB
_MACHADO = {
    "protan": [(0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)],
    "deutan": [(0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)],
    "tritan": [(1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)],
}


def _rgb(hexcolor: str) -> tuple[float, float, float]:
    h = hexcolor.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _unlin(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def luminance(hexcolor: str) -> float:
    r, g, b = (_lin(c) for c in _rgb(hexcolor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def simulate(hexcolor: str, kind: str) -> tuple[float, float, float]:
    lin = [_lin(c) for c in _rgb(hexcolor)]
    m = _MACHADO[kind]
    return tuple(_unlin(sum(m[i][j] * lin[j] for j in range(3))) for i in range(3))  # type: ignore[return-value]


def _lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(_lab(a), _lab(b))


def check(lens: Lens, *, min_text=4.5, min_delta=12.0):
    """Return (contrast_failures, confusable_pairs).

    contrast_failures: (category, theme, palette, ratio) below `min_text` against the surface.
    confusable_pairs: (cat1, cat2, theme, palette, vision, deltaE) closer than `min_delta`
    once simulated, *counting only pairs whose normal-vision difference is clear* (a pair that is
    already close for everyone is a different problem).
    """
    cats = [c for c in lens.categories if c.layer == "content"]
    fails, pairs = [], []
    for theme in ("dark", "light"):
        for pal, key in (("default", theme), ("cb", f"cb_{theme}")):
            for c in cats:
                ratio = contrast(c.colors[key], SURFACES[theme])
                if ratio < min_text:
                    fails.append((c.name, theme, pal, round(ratio, 2)))
            for a, b in itertools.combinations(cats, 2):
                ca, cb = a.colors[key], b.colors[key]
                normal = delta_e(_rgb(ca), _rgb(cb))
                if normal < min_delta:
                    pairs.append((a.name, b.name, theme, pal, "normal", round(normal, 1)))
                    continue
                for vision in ("protan", "deutan", "tritan"):
                    d = delta_e(simulate(ca, vision), simulate(cb, vision))
                    if d < min_delta:
                        pairs.append((a.name, b.name, theme, pal, vision, round(d, 1)))
    return fails, pairs
