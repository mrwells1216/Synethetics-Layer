"""Measure the word library against the language model (spaCy) on the repo's own texts.

    python tools/library_check.py [top]

For every word, compares the look the library gives (noun, verb, adjective, adverb or none) with
the model's. Prints the agreement and the most common disagreements, which is the list of words
worth adding to lenses/library.toml. Only reads README.md and synesthetic/examples: never the
owner's own documents.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synesthetic import library  # noqa: E402
from synesthetic.extract import extract  # noqa: E402

POS_KIND = {"NOUN": "noun", "PROPN": "noun", "VERB": "verb", "AUX": "verb", "ADJ": "adjective", "ADV": "adverb"}


def texts() -> list[str]:
    out: list[str] = []
    for p in [ROOT / "README.md", *sorted((ROOT / "synesthetic" / "examples").glob("*.md"))]:
        out += [b.text for b in extract(p).blocks if b.kind in ("para", "item", "quote") and b.text]
    return out


def main(top: int) -> int:
    import spacy

    nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "parser"])
    same = total = 0
    miss: Counter = Counter()
    corpus = texts()
    for text, doc in zip(corpus, nlp.pipe(corpus, batch_size=64)):
        ours = {}
        for s, e, kind in library.tag(text):
            for i in range(s, e):
                ours[i] = kind
        for tok in doc:
            if not tok.text[:1].isalpha() or not tok.text.isascii():
                continue
            want = POS_KIND.get(tok.pos_)
            got = ours.get(tok.idx)
            total += 1
            if want == got:
                same += 1
            else:
                miss[(tok.text.lower(), got or "-", want or "-")] += 1
    print(f"{len(corpus)} texts, {total} words, {same / max(total, 1):.1%} agree with the model")
    for (word, got, want), n in miss.most_common(top):
        print(f"{n:4d}  {word:<18} library {got:<10} model {want}")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 60))
