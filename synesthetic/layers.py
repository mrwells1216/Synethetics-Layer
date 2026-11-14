"""Combine the layers into one annotator function."""
from __future__ import annotations

from typing import Callable

from .annotate import Lens, Span, annotate


def _subtract(spans: list[Span], blockers: list[Span]) -> list[Span]:
    """Cut grammar spans so they never sit under a content span."""
    if not blockers:
        return spans
    out: list[Span] = []
    for sp in spans:
        parts = [(sp.start, sp.end)]
        for b in blockers:
            nxt = []
            for s, e in parts:
                if b.end <= s or b.start >= e:
                    nxt.append((s, e))
                    continue
                if s < b.start:
                    nxt.append((s, b.start))
                if b.end < e:
                    nxt.append((b.end, e))
            parts = nxt
            if not parts:
                break
        out.extend(Span(s, e, sp.cat, sp.layer) for s, e in parts if e > s)
    return out


def make_annotator(texts: list[str], lens: Lens, *, grammar: bool = False, ai: dict | None = None,
                   log=print) -> Callable[[str], list[Span]]:
    uniq = list(dict.fromkeys(t for t in texts if t and t.strip()))
    gram: dict[str, list[Span]] = {}
    mean: dict[str, list[Span]] = {}
    if grammar:
        from . import grammar as g

        gram = g.tag_texts(uniq, lens)
    if ai is not None:
        from . import meaning as m

        try:
            mean = m.tag_texts(uniq, lens, log=log, **ai)
        except m.AIUnavailable as e:  # keep the document: render without the meaning layer
            log(f"AI layer skipped: {e}")

    def ann(text: str) -> list[Span]:
        content = annotate(text, lens)
        spans = content + _subtract(gram.get(text, []), content) + mean.get(text, [])
        spans.sort(key=lambda s: (s.start, s.layer != "meaning"))
        return spans

    return ann
