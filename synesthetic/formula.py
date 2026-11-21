"""A formula on a line of its own: told apart from prose so it can sit in its own box.

A line counts when it states a relation (=, ≈, ≤, →, ...) between things that look like math
(variables, numbers, operators, superscripts, Greek letters) and carries little prose around it.
"Revenue = Price × Quantity" and "E = mc²" are formulas; "Set the margin = 2 inches and keep
going" is a sentence. A short label before a colon stays with it ("Osmotic pressure: Π = iMRT").
"""
from __future__ import annotations

import re

MAX_CHARS = 120
MAX_TOKENS = 14
MAX_PROSE = 3  # whole words a formula may carry ("Revenue = Price × Quantity")

RELATION = re.compile(r"[=≈≠≤≥≡∝→←↔]|(?<=\s)[<>](?=\s)")
OPERATOR = re.compile(r"[+−×÷±·√∑∏∫∂∞^/]|\\[a-z]+|[²³⁴⁰¹⁵⁶⁷⁸⁹₀-₉]|[α-ωΑ-Ω]|\d")
UNITS = {"per", "for", "where", "with", "and", "the", "of", "in", "at", "to", "mol", "kg", "cm", "mm", "km", "sec",
         "min", "hr", "day", "year", "if", "then"}
SENTENCE = re.compile(r"[.!?]\s+[A-Za-z]")


def _is_math_token(tok: str) -> bool:
    if OPERATOR.search(tok):
        return True
    letters = re.sub(r"[^A-Za-z]", "", tok)
    if not letters:
        return True  # punctuation alone (=, ±, parentheses)
    if len(letters) == 1:
        return True  # a variable: x, F, r
    # a short symbol like PV, nRT, ATP: all caps or mixed case, three letters or fewer
    return len(letters) <= 3 and (letters.isupper() or not (letters.islower() or letters.istitle()))


def _is_formula(core: str) -> bool:
    if not core or len(core) > MAX_CHARS or not RELATION.search(core) or SENTENCE.search(core):
        return False
    tokens = core.split()
    if len(tokens) > MAX_TOKENS:
        return False
    prose = [w for w in re.findall(r"[A-Za-z]{3,}", core) if w.lower() not in UNITS]
    if len(prose) > MAX_PROSE:
        return False
    # a sentence runs in lowercase words; a formula names its parts in capitals or short symbols
    if sum(1 for w in prose if w.islower() and len(w) >= 4) > 1:
        return False
    if not any(_is_math_token(t) for t in tokens if not RELATION.fullmatch(t)):
        return False
    return len(prose) < len(tokens)


def parse_formula(text: str) -> tuple[str, str] | None:
    """(label, formula) when the line is a formula, else None. Markdown's $$...$$ and $...$ always count."""
    t = (text or "").strip()
    if not t:
        return None
    m = re.fullmatch(r"\$\$(.+?)\$\$|\$(.+?)\$", t, re.S)
    if m:
        inner = (m.group(1) or m.group(2) or "").strip()
        return ("", inner) if inner else None
    label, core = "", t
    if ": " in t:
        head, rest = t.split(": ", 1)
        if 0 < len(head.split()) <= 4 and not RELATION.search(head) and rest.strip():
            label, core = head.strip(), rest.strip()
    if _is_formula(core):
        return label, core
    return None
