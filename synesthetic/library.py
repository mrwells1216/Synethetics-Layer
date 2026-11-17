"""Our own word library: the grammar layer without a language model.

lenses/library.toml lists small words, verbs, adjectives, adverbs and the owner's own pins.
`tag` reads a text with it and says which words are nouns, verbs, adjectives and adverbs.
The chat add-on carries a line-for-line port (chat-mod/synesthetic-chat/hooks/library.ts);
tools/parity.py checks the two agree, so change them together.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .annotate import Lens, Span

DEFAULT_LIBRARY = Path(__file__).resolve().parent.parent / "lenses" / "library.toml"

KINDS = ("noun", "verb", "adjective", "adverb")
KIND_POS = {"noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADV"}
_PIN_CLASS = {"noun": "N", "verb": "V", "adjective": "J", "adverb": "R", "skip": "X"}

# Word classes. Small words: D the/your, E some/each, A these/both, P of/in, T to, S I/you, G me/them, H he/she/it,
# W that/which, L let's/you'll, K please, O not, X other. Helping verbs: M can/does, B is/has.
# Open words: V Vs Vd Vg verb forms, VN NV noun-or-verb (first letter = the usual side) and their
# -s forms VNs NVs, JV adjective-or-verb, J adjective, R adverb, Q adverb a verb follows, N noun,
# U not in the library.
_FUNCTION = {"determiners": "D", "quantifiers": "E", "plural": "A", "prepositions": "P", "to": "T", "subjects": "S",
             "objects": "G", "third": "H", "pointers": "W", "preverb": "L", "softeners": "K",
             "negation": "O", "skip": "X"}
_CLOSED = frozenset("DEAPTSGHWLKOXMB")
_THROUGH = frozenset("ROQK")            # looked past when asking what came before
_NOUN_BEFORE = frozenset("DPJEA")
_VERB_BEFORE = frozenset("TMLS")
_LEX_VERB = frozenset(("V", "Vs", "Vd", "Vg"))
_OBJECT = frozenset("DEAHG")
_PARTICLES = frozenset(("for", "at", "on", "up", "out", "off", "by", "into", "through", "down", "over", "in"))
_ADJ_ENDS = ("ous", "ful", "less", "able", "ible", "ive", "ic", "al", "ary")
_NOUN_ENDS = ("tion", "sion", "ness", "ity", "ism", "ship", "ence", "ance")
_MID = frozenset(",>)]/&-–—%+=|~#@*_")
_OPENERS = frozenset(" \t\n\"'“”‘’([")

TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
_VOWELS = "aeiou"


@dataclass
class Library:
    words: dict[str, str] = field(default_factory=dict)      # word -> class
    pins: dict[str, str] = field(default_factory=dict)       # the owner's single words -> kind or "skip"
    phrases: list[tuple[str, str]] = field(default_factory=list)  # the owner's phrases, longest first


def _doubles(w: str, double: set[str]) -> bool:
    if len(w) < 3 or w[-1] in _VOWELS + "wxy" or w[-2] not in _VOWELS:
        return False
    if w[-3] in _VOWELS and w[-4:-2] != "qu":
        return False
    return w in double or len(re.findall(r"[aeiouy]+", w.replace("qu", "q"))) == 1


def _s_form(w: str) -> str:
    if w.endswith(("s", "x", "z", "ch", "sh", "o")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
        return w[:-1] + "ies"
    return w + "s"


def _ed_form(w: str, double: set[str]) -> str:
    if w.endswith("e"):
        return w + "d"
    if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
        return w[:-1] + "ied"
    return w + (w[-1] if _doubles(w, double) else "") + "ed"


def _ing_form(w: str, double: set[str]) -> str:
    if w.endswith("ie"):
        return w[:-2] + "ying"
    if w.endswith("e") and not w.endswith(("ee", "ye", "oe")):
        return w[:-1] + "ing"
    return w + (w[-1] if _doubles(w, double) else "") + "ing"


def load_library(path: str | Path | None = None) -> Library:
    with open(Path(path) if path else DEFAULT_LIBRARY, "rb") as f:
        data = tomllib.load(f)
    words: dict[str, str] = {}

    def put(text: str, cls: str) -> None:
        for w in text.split():
            words.setdefault(w.lower(), cls)

    for key, cls in _FUNCTION.items():
        put(data.get("function", {}).get(key, ""), cls)
    put(data.get("aux", {}).get("modal", ""), "M")
    put(data.get("aux", {}).get("be", ""), "B")
    put(data.get("adjective", {}).get("words", ""), "J")
    put(data.get("adverb", {}).get("preverb", ""), "Q")
    put(data.get("adverb", {}).get("words", ""), "R")
    put(data.get("noun", {}).get("words", ""), "N")
    both, verb = data.get("both", {}), data.get("verb", {})
    put(both.get("verb_first", ""), "VN")
    put(both.get("noun_first", ""), "NV")
    put(both.get("adjective_first", ""), "JV")
    irregular: dict[str, tuple[str, str]] = {}
    for line in verb.get("irregular", "").splitlines():
        parts = line.split()
        if len(parts) == 3:
            irregular[parts[0]] = (parts[1], parts[2])
    put(verb.get("words", ""), "V")
    put(" ".join(irregular), "V")

    double = set(verb.get("double", "").split())
    for base, cls in list(words.items()):
        if cls not in ("V", "VN", "NV", "JV"):
            continue
        words.setdefault(_s_form(base), {"VN": "VNs", "NV": "NVs"}.get(cls, "Vs"))
        for form in irregular.get(base) or (_ed_form(base, double),):
            words.setdefault(form, "Vd")
        words.setdefault(_ing_form(base, double), "Vg")

    lib = Library(words=words)
    for raw, kind in data.get("own", {}).items():
        key = " ".join(_lower(raw).split())
        if kind not in _PIN_CLASS or not key:
            raise ValueError(f"library.toml [own]: {raw!r} must be noun, verb, adjective, adverb or skip")
        if TOKEN.fullmatch(key):
            lib.pins[key] = kind
        else:
            lib.phrases.append((key, kind))
    lib.phrases.sort(key=lambda p: (-len(p[0]), p[0]))
    return lib


_LIB: Library | None = None


def default_library() -> Library:
    global _LIB
    if _LIB is None:
        _LIB = load_library()
    return _LIB


def _lower(s: str) -> str:
    """ASCII-only lowercase with straight apostrophes: the same length in every language."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else ("'" if c == "’" else c) for c in s)


def _wordish(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9")


def _phrase_hits(low: str, lib: Library) -> list[tuple[int, int, str]]:
    hits: list[tuple[int, int, str]] = []
    for phrase, kind in lib.phrases:
        at = low.find(phrase)
        while at != -1:
            end = at + len(phrase)
            if not (at > 0 and _wordish(low[at - 1])) and not (end < len(low) and _wordish(low[end])) \
                    and all(end <= s or at >= e for s, e, _k in hits):
                hits.append((at, end, kind))
            at = low.find(phrase, at + 1)
    hits.sort()
    return hits


def _guess(w: str) -> str:
    n = len(w)
    if n > 4 and w.endswith("ly"):
        return "R"
    if n > 5 and w.endswith(("ize", "ify")):
        return "V"
    if n > 6 and w.endswith(("izes", "ifies")):
        return "Vs"
    if n > 5 and w.endswith("ing"):
        return "Vg"
    if n > 4 and w.endswith("ed") and not w.endswith("eed"):
        return "Vd"
    for end in _ADJ_ENDS:
        if n > len(end) + (2 if len(end) == 2 else 1) and w.endswith(end):
            return "J"
    for end in _NOUN_ENDS:
        if n > len(end) + 2 and w.endswith(end):
            return "N"
    return "U"


def _mid_sentence(text: str, at: int) -> bool:
    j = at - 1
    while j >= 0 and text[j] in _OPENERS:
        j -= 1
    return j >= 0 and (_wordish(text[j]) or text[j] in _MID)


def _blank(text: str, a: int, b: int) -> bool:
    return all(c in " \t\n" for c in text[a:b])


def tag(text: str, lib: Library | None = None) -> list[tuple[int, int, str]]:
    """(start, end, kind) for each noun, verb, adjective and adverb; neighbours of one kind are joined."""
    lib = lib or default_library()
    low_text = _lower(text)
    hits = _phrase_hits(low_text, lib) if lib.phrases else []
    toks: list[dict] = []
    hi = 0
    for m in TOKEN.finditer(text):
        s, e = m.span()
        low = low_text[s:e]
        stem, poss = low, False
        cls = lib.words.get(low)
        if cls is None and "'" in low:
            if low.endswith("'s"):
                stem, poss = low[:-2], True
                cls = lib.words.get(stem)
            else:
                cls = "M" if low.endswith("n't") else "X"
        while hi < len(hits) and hits[hi][1] <= s:
            hi += 1
        hit = hi if hi < len(hits) and hits[hi][0] <= s and e <= hits[hi][1] else -1
        pin = hits[hit][2] if hit >= 0 else lib.pins.get(stem)
        first = text[s]
        if pin is not None:
            cls = _PIN_CLASS[pin]
        else:
            if cls is None:
                cls = _guess(stem)
            if cls not in _CLOSED:
                letters = text[s:s + len(stem)]
                if (len(letters) >= 2 and letters == letters.upper()) or ("A" <= first <= "Z" and _mid_sentence(text, s)):
                    cls = "N"
        toks.append({"s": s, "e": e, "cls": cls, "low": stem, "poss": poss, "pin": pin, "hit": hit,
                     "lower": "a" <= first <= "z", "start": not _mid_sentence(text, s)})

    def before(i: int) -> tuple[str, bool]:
        crossed = False
        while i > 0 and _blank(text, toks[i - 1]["e"], toks[i]["s"]):
            i -= 1
            t = toks[i]
            if t["poss"]:
                return "D", crossed
            if t["cls"] in _THROUGH:
                crossed = crossed or t["cls"] in "QK"
                continue
            return t["cls"], crossed
        return "", crossed

    def after(i: int) -> dict | None:
        if i + 1 < len(toks) and _blank(text, toks[i]["e"], toks[i + 1]["s"]):
            return toks[i + 1]
        return None

    def kind_of(i: int) -> str | None:
        t = toks[i]
        c = t["cls"]
        if t["pin"] is not None:
            return None if t["pin"] == "skip" else t["pin"]
        if c in _CLOSED:
            return "verb" if c in "MB" else None
        if c in ("R", "Q"):
            return "adverb"
        if c == "J":
            return "adjective"
        if c == "N":
            return "noun"
        p, crossed = before(i)
        nxt = after(i)
        n = nxt["cls"] if nxt else ""
        n_open = bool(nxt) and n not in _CLOSED and n not in ("R", "Q")
        if c == "U":
            if t["lower"] and (p in ("M", "L", "S") or (p in ("H", "W") and len(t["low"]) > 3 and t["low"].endswith("s"))):
                return "verb"
            return "noun"
        if c == "V":
            return "noun" if p == "D" else "verb"
        if c == "Vs":
            return "verb"
        if c == "Vd":
            if p in ("D", "P", "E", "A") and n_open:
                return "adjective"
            return "noun" if p == "D" else "verb"
        if c == "Vg":
            if p == "D":
                return "adjective" if n_open else "noun"
            return "verb"
        verb_lead = p in _VERB_BEFORE or (crossed and p not in _NOUN_BEFORE)
        if c == "JV":
            if verb_lead or n in _OBJECT or n == "W":
                return "verb"
            # "open Settings": an instruction when a capitalized name follows
            return "verb" if n == "N" and nxt and not nxt["lower"] else "adjective"
        if c in ("NV", "VN"):
            if verb_lead or (c == "VN" and p == "A"):
                return "verb"
            if p in _NOUN_BEFORE or (c == "NV" and p in _LEX_VERB):
                return "noun"
            if n in _OBJECT or n == "W":
                return "verb"
            if n in ("M", "B"):
                return "noun"
            if t["start"] and nxt and nxt["low"] in _PARTICLES:
                return "verb"
            return "verb" if c == "VN" else "noun"
        # NVs / VNs: "lists", "shows"
        if p in _NOUN_BEFORE or p in _LEX_VERB:
            return "noun"
        if p in ("H", "W") or n in _OBJECT:
            return "verb"
        if n in ("M", "B"):
            return "noun"
        return "verb" if c == "VNs" else "noun"

    out: list[tuple[int, int, str]] = []
    last_hit = -1
    for i, t in enumerate(toks):
        kind = kind_of(i)
        if kind is None:
            continue
        joined = t["hit"] >= 0 and t["hit"] == last_hit   # one pinned phrase, even across a hyphen
        last_hit = t["hit"]
        if out and out[-1][2] == kind and (joined or _blank(text, out[-1][1], t["s"])):
            out[-1] = (out[-1][0], t["e"], kind)
        else:
            out.append((t["s"], t["e"], kind))
    return out


def _categories(lens: Lens) -> dict[str, str]:
    """kind -> the lens grammar category that covers it."""
    names: dict[str, str] = {}
    for c in lens.categories:
        if c.layer == "grammar":
            for kind, pos in KIND_POS.items():
                if pos in c.pos:
                    names.setdefault(kind, c.name)
    return names


def tag_texts(texts: list[str], lens: Lens, lib: Library | None = None) -> dict[str, list[Span]]:
    """The grammar layer from the library alone: each text mapped to its grammar spans."""
    names = _categories(lens)
    if not names:
        return {}
    return {t: [Span(s, e, names[k], "grammar") for s, e, k in tag(t, lib) if k in names] for t in texts}


def pinned(text: str, lib: Library | None = None) -> list[tuple[int, int, str]]:
    """Where the owner's own words sit in a text: (start, end, kind or "skip")."""
    lib = lib or default_library()
    if not lib.pins and not lib.phrases:
        return []
    low_text = _lower(text)
    out = _phrase_hits(low_text, lib)
    for m in TOKEN.finditer(text):
        s, e = m.span()
        low = low_text[s:e]
        kind = lib.pins.get(low[:-2] if low.endswith("'s") else low)
        if kind and all(e <= a or s >= b for a, b, _k in out):
            out.append((s, e, kind))
    out.sort()
    return out


def apply_pins(text: str, spans: list[Span], lens: Lens, lib: Library | None = None) -> list[Span]:
    """Lay the owner's own words over grammar spans from any tagger."""
    pins = pinned(text, lib)
    if not pins:
        return spans
    from .layers import _subtract

    names = _categories(lens)
    kept = _subtract(spans, [Span(s, e, "", "grammar") for s, e, _k in pins])
    kept += [Span(s, e, names[k], "grammar") for s, e, k in pins if k in names]
    kept.sort(key=lambda sp: sp.start)
    return kept
