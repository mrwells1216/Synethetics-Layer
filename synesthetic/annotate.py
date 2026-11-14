"""Lens loading and the content-type annotator."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LENS = Path(__file__).resolve().parent.parent / "lenses" / "default.toml"
_FLAGS = {"i": re.I, "m": re.M, "s": re.S}


@dataclass
class Category:
    name: str
    label: str
    priority: int
    patterns: list[re.Pattern]
    colors: dict[str, str]  # dark, light, cb_dark, cb_light
    font: str = "normal"  # normal | mono | serif | italic | tabular
    weight: int = 0  # 0 = inherit
    underline: str = "none"  # none | dotted | dashed | solid | double | wavy
    example: str = ""
    default_off: bool = False  # starts unchecked in the page legend
    layer: str = "content"  # content | grammar | meaning
    pos: tuple[str, ...] = ()  # grammar layer: spaCy coarse POS tags this category covers
    description: str = ""  # meaning layer: what the model should mark


@dataclass
class Span:
    start: int
    end: int
    cat: str
    layer: str = "content"


@dataclass
class Lens:
    categories: list[Category] = field(default_factory=list)

    def get(self, name: str) -> Category | None:
        for c in self.categories:
            if c.name == name:
                return c
        return None


def load_lens(path: str | Path | None = None) -> Lens:
    path = Path(path) if path else DEFAULT_LENS
    with open(path, "rb") as f:
        data = tomllib.load(f)
    cats = []
    for raw in data.get("category", []):
        flags = 0
        for ch in raw.get("flags", ""):
            flags |= _FLAGS[ch]
        pats = [re.compile(p, flags) for p in raw.get("patterns", [])]
        cats.append(
            Category(
                name=raw["name"],
                label=raw.get("label", raw["name"]),
                priority=int(raw.get("priority", 50)),
                patterns=pats,
                colors={
                    "dark": raw["dark"],
                    "light": raw["light"],
                    "cb_dark": raw.get("cb_dark", raw["dark"]),
                    "cb_light": raw.get("cb_light", raw["light"]),
                },
                font=raw.get("font", "normal"),
                weight=int(raw.get("weight", 0)),
                underline=raw.get("underline", "none"),
                example=raw.get("example", ""),
                default_off=bool(raw.get("default_off", False)),
                layer=raw.get("layer", "content"),
                pos=tuple(raw.get("pos", ())),
                description=raw.get("description", ""),
            )
        )
    return Lens(cats)


def annotate(text: str, lens: Lens) -> list[Span]:
    """Return non-overlapping spans. Lower priority number wins an overlap;
    ties go to the earlier, then longer, match."""
    if not text:
        return []
    cands = []
    for cat in lens.categories:
        if cat.layer != "content":
            continue
        for pat in cat.patterns:
            for m in pat.finditer(text):
                g = 1 if pat.groups and m.group(1) is not None else 0
                s, e = m.span(g)
                if e > s:
                    cands.append((cat.priority, s, -(e - s), cat.name, e))
    cands.sort()
    taken = bytearray(len(text))
    out: list[Span] = []
    for _prio, s, _neg, name, e in cands:
        if any(taken[s:e]):
            continue
        taken[s:e] = b"\x01" * (e - s)
        out.append(Span(s, e, name))
    out.sort(key=lambda sp: sp.start)
    return out
