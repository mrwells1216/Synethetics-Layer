import tomllib
from collections import Counter

import pytest

from synesthetic import library
from synesthetic.annotate import Span, load_lens
from synesthetic.layers import make_annotator

LENS = load_lens()
LIB = library.load_library()


def looks(text, lib=None):
    return [(text[s:e], k) for s, e, k in library.tag(text, lib or LIB)]


def look_of(text, word, lib=None):
    hits = [k for w, k in looks(text, lib) if word in w.split()]
    assert hits, f"{word!r} got no look in {text!r}"
    return hits[0]


def test_every_word_is_listed_once():
    with open(library.DEFAULT_LIBRARY, "rb") as f:
        data = tomllib.load(f)
    lists = [v for sec in ("function", "aux", "adjective", "adverb", "noun", "both") for v in data[sec].values()]
    lists.append(data["verb"]["words"])
    seen = Counter(w for text in lists for w in text.split())
    assert [w for w, n in seen.items() if n > 1] == []


def test_verb_forms_are_worked_out():
    w = LIB.words
    assert w["adds"] == "Vs" and w["added"] == "Vd" and w["adding"] == "Vg"
    assert w["committed"] == "Vd" and w["referring"] == "Vg" and w["stopped"] == "Vd"
    assert w["tries"] == "Vs" and w["tried"] == "Vd" and w["tying"] == "Vg"
    assert w["quitting"] == "Vg" and w["hidden"] == "Vd" and w["wrote"] == "Vd"
    assert w["opened"] == "Vd" and "openned" not in w and w["visited"] == "Vd"
    assert w["lists"] == "NVs" and w["shows"] == "VNs"


def test_the_screenshot_sentences():
    a = "Your screenshot 4 is the wait-list entry, not the appointment."
    assert looks(a) == [("screenshot", "noun"), ("is", "verb"), ("wait-list entry", "noun"), ("appointment", "noun")]

    b = "Filters can still hide it. Rules can hide by department or visit type."
    assert looks(b) == [("Filters", "noun"), ("can", "verb"), ("still", "adverb"), ("hide", "verb"),
                        ("Rules", "noun"), ("can hide", "verb"), ("department", "noun"), ("visit type", "noun")]

    c = "Next step: find the scheduled appointment contact and read its value."
    assert looks(c) == [("Next", "adjective"), ("step", "noun"), ("find", "verb"), ("scheduled", "adjective"),
                        ("appointment contact", "noun"), ("read", "verb"), ("value", "noun")]

    d = "Then check closed or open encounters and the filters."
    assert look_of(d, "Then") == "adverb" and look_of(d, "check") == "verb"
    assert look_of(d, "open") == "adjective" and look_of(d, "filters") == "noun"


@pytest.mark.parametrize("text, word, kind", [
    ("Add it to the list.", "list", "noun"),
    ("You can list every file.", "list", "verb"),
    ("Search for the patient by name.", "Search", "verb"),
    ("The search is slow.", "search", "noun"),
    ("The table shows it.", "shows", "verb"),
    ("Both rows show the value.", "show", "verb"),
    ("Open Settings and click Save.", "Open", "verb"),
    ("Leave the file open.", "open", "adjective"),
    ("It runs quickly.", "quickly", "adverb"),
    ("A famous painting.", "famous", "adjective"),
    ("Press the Hide button.", "Hide", "noun"),
    ("the EPT record", "EPT", "noun"),
    ("They should restart the app.", "restart", "verb"),
    ("You must reticulate the splines.", "reticulate", "verb"),
    ("It doesn't matter.", "doesn't", "verb"),
    ("The patient's chart loads.", "patient's", "noun"),
    ("Use the following steps.", "following", "adjective"),
    ("Thanks for the meeting.", "meeting", "noun"),
])
def test_words_in_context(text, word, kind):
    assert look_of(text, word) == kind


def test_small_words_get_no_look():
    styled = {w.lower() for w, _k in looks("If you want it, the answer is in there for us and them.")}
    assert not styled & {"if", "you", "it", "the", "in", "for", "us", "and", "them"}


def test_own_words_win(tmp_path):
    src = library.DEFAULT_LIBRARY.read_text(encoding="utf-8")
    src = src.replace("[own]\n", '[own]\n"check in" = "noun"\n"quickly" = "skip"\n"run" = "noun"\n', 1)
    p = tmp_path / "library.toml"
    p.write_text(src, encoding="utf-8")
    lib = library.load_library(p)
    text = "Please run the Check In step quickly."
    got = looks(text, lib)
    assert ("Check In step", "noun") in got and ("run", "noun") in got
    assert "quickly" not in {w for w, _k in got}
    # the same pins lie over spans from any other tagger
    spans = library.apply_pins(text, [Span(7, 10, "verb", "grammar"), Span(29, 36, "adverb", "grammar")], LENS, lib)
    assert [(text[s.start:s.end], s.cat) for s in spans] == [("run", "noun"), ("Check In", "noun")]


def test_library_stands_in_when_the_model_is_missing(monkeypatch):
    from synesthetic import grammar

    def gone(texts, lens):
        raise ImportError("no spaCy here")

    monkeypatch.setattr(grammar, "tag_texts", gone)
    text = "Warning: pay $1,250.50 by Aug 14, 2026, then quickly check the new list."
    spans = make_annotator([text], LENS, grammar=True)(text)
    content = [s for s in spans if s.layer == "content"]
    gram = [s for s in spans if s.layer == "grammar"]
    assert {"noun", "verb", "adjective", "adverb"} <= {g.cat for g in gram}
    for g in gram:
        assert not any(g.start < c.end and c.start < g.end for c in content)
