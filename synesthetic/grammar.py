"""Grammar layer: color words by part of speech (spaCy, offline, optional)."""
from __future__ import annotations

from .annotate import Lens, Span

_NLP = None


def available() -> bool:
    try:
        import spacy  # noqa: F401

        spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "parser"])
        return True
    except Exception:
        return False


def _nlp():
    global _NLP
    if _NLP is None:
        import spacy

        _NLP = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "parser"])
    return _NLP


def tag_texts(texts: list[str], lens: Lens) -> dict[str, list[Span]]:
    """Map each text to its grammar spans. Runs of the same category separated only by
    whitespace are merged ("quick brown" is one adjective span)."""
    posmap: dict[str, str] = {}
    for c in lens.categories:
        if c.layer == "grammar":
            for p in c.pos:
                posmap[p] = c.name
    if not posmap:
        return {}
    nlp = _nlp()
    out: dict[str, list[Span]] = {}
    for text, doc in zip(texts, nlp.pipe(texts, batch_size=64)):
        spans: list[Span] = []
        for tok in doc:
            cat = posmap.get(tok.pos_)
            if not cat:
                continue
            s, e = tok.idx, tok.idx + len(tok.text)
            if spans and spans[-1].cat == cat and text[spans[-1].end : s].strip() == "":
                spans[-1].end = e
            else:
                spans.append(Span(s, e, cat, "grammar"))
        out[text] = spans
    return out
