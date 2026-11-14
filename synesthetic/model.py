"""Common document model produced by every extractor."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cell:
    text: str
    ctype: str | None = None  # "number" | "date" | None (let the annotator decide)


@dataclass
class Block:
    kind: str  # heading | para | item | quote | code | table | rule
    text: str = ""
    level: int = 0  # heading level (1-6) or list depth (0-based)
    marker: str = ""  # list marker, e.g. "•" or "3."
    # inline emphasis: (start, end, style) with style in {"b", "i", "code"}
    emph: list[tuple[int, int, str]] = field(default_factory=list)
    rows: list[list[Cell]] | None = None
    header_rows: int = 0


@dataclass
class Document:
    source: str
    title: str = ""
    blocks: list[Block] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def read_text(path) -> str:
    """Read a text file, tolerating common encodings."""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")
