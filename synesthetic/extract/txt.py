"""Plain-text extractor with light structure heuristics."""
from __future__ import annotations

import re
from pathlib import Path

from ..model import Block, Document, read_text

BULLET = re.compile(r"^\s*([-*•●▪◦·]|\d{1,3}[.)]|[A-Za-z][.)])\s+(.*)$")
NUMBERED_HEAD = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?|[IVXL]+\.|[A-Z]\.)\s+\S")
UNDERLINE = re.compile(r"^\s*([=\-~#*_])\1{2,}\s*$")


def _is_heading_line(line: str, prev_blank: bool, next_blank: bool) -> bool:
    s = line.strip()
    if not s or len(s) > 90 or not (prev_blank and next_blank):
        return False
    if s.endswith((".", ",", ";")):
        return False
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    if s.isupper() and len(letters) >= 3:
        return True
    if NUMBERED_HEAD.match(s) and len(s.split()) <= 12 and not BULLET.match(line):
        return True
    words = s.split()
    return len(words) <= 8 and all(w[0].isupper() or not w[0].isalpha() or len(w) <= 3 for w in words)


def _looks_aligned(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    hits = sum(1 for ln in lines if re.search(r"\S {2,}\S", ln) or "\t" in ln)
    return hits >= max(2, int(len(lines) * 0.6))


def extract(path) -> Document:
    return extract_text(read_text(Path(path)), path)


def extract_text(text: str, path) -> Document:
    path = Path(path)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    doc = Document(source=str(path), title=path.stem)
    lines = text.split("\n")

    # group into paragraphs separated by blank lines
    groups: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                groups.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        groups.append(cur)

    first_heading_seen = False
    for gi, g in enumerate(groups):
        # setext / banner underline: "Title\n=====" or lines of ==== around a title
        g = [ln for ln in g if not UNDERLINE.match(ln)] if any(UNDERLINE.match(ln) for ln in g) else g
        if not g:
            continue
        if len(g) == 1 and _is_heading_line(g[0], True, True):
            level = 1 if not first_heading_seen else 2
            first_heading_seen = True
            doc.blocks.append(Block("heading", g[0].strip(), level=level))
            continue
        if _looks_aligned(g):
            doc.blocks.append(Block("code", "\n".join(g)))
            continue
        if any(BULLET.match(ln) for ln in g):
            para: list[str] = []
            for ln in g:
                m = BULLET.match(ln)
                if m:
                    indent = len(ln) - len(ln.lstrip())
                    marker = m.group(1)
                    marker = marker if marker[0].isdigit() or marker[0].isalpha() else "•"
                    doc.blocks.append(Block("item", m.group(2).strip(), level=min(indent // 2, 4), marker=marker))
                    para = []
                elif doc.blocks and doc.blocks[-1].kind == "item":
                    doc.blocks[-1].text += " " + ln.strip()
                else:
                    para.append(ln.strip())
                    if len(para) == 1:
                        doc.blocks.append(Block("para", ""))
                    doc.blocks[-1].text = " ".join(para)
            continue
        joined = " ".join(ln.strip() for ln in g)
        # Hyphen-wrapped words
        joined = re.sub(r"(\w)- (?=[a-z])", r"\1", joined)
        doc.blocks.append(Block("para", joined))

    if not doc.blocks:
        doc.notes.append("The file has no text.")
    return doc
