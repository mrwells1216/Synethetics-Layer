import json

import pytest

from synesthetic import meaning
from synesthetic.annotate import Span, load_lens
from synesthetic.layers import _subtract, make_annotator
from synesthetic.model import Block, Document
from synesthetic.render import render_document

LENS = load_lens()
TEXT = "To measure the rate, count the bubbles released per minute 12 times. Do not let the lamp overheat."


def test_subtract_cuts_grammar_around_content():
    out = _subtract([Span(0, 10, "noun", "grammar")], [Span(3, 5, "number")])
    assert [(s.start, s.end) for s in out] == [(0, 3), (5, 10)]


def test_grammar_spans_never_overlap_content():
    pytest.importorskip("spacy")
    from synesthetic import grammar

    if not grammar.available():
        pytest.skip("spaCy model not installed")
    ann = make_annotator([TEXT], LENS, grammar=True)
    spans = ann(TEXT)
    content = [s for s in spans if s.layer == "content"]
    gram = [s for s in spans if s.layer == "grammar"]
    assert gram and content
    for g in gram:
        assert not any(g.start < c.end and c.start < g.end for c in content)
    assert {"noun", "verb"} <= {g.cat for g in gram}


def test_meaning_layer_with_stand_in_model(monkeypatch, tmp_path):
    monkeypatch.setattr(meaning, "CACHE_PATH", tmp_path / "cache.json")
    calls = []

    def fake(prompt, model, cwd=None):
        calls.append(prompt)
        return json.dumps(
            [
                {"i": 0, "phrase": "count the bubbles released per minute", "cat": "action"},
                {"i": 0, "phrase": "Do not let the lamp overheat", "cat": "caution"},
                {"i": 0, "phrase": "text the model invented", "cat": "keyterm"},  # not in passage
                {"i": 0, "phrase": "the rate", "cat": "not_a_category"},  # unknown category
            ]
        )

    monkeypatch.setattr(meaning, "_run_claude", fake)
    spans = make_annotator([TEXT], LENS, ai={"model": "haiku", "max_calls": 5})(TEXT)
    mean = {(TEXT[s.start : s.end], s.cat) for s in spans if s.layer == "meaning"}
    assert mean == {
        ("count the bubbles released per minute", "action"),
        ("Do not let the lamp overheat", "caution"),
    }
    # second run is served from the cache: no new model call
    make_annotator([TEXT], LENS, ai={"model": "haiku", "max_calls": 5})(TEXT)
    assert len(calls) == 1


def test_ai_failure_keeps_document(monkeypatch, tmp_path):
    monkeypatch.setattr(meaning, "CACHE_PATH", tmp_path / "cache.json")

    def boom(prompt, model, cwd=None):
        raise meaning.AIUnavailable("Failed to authenticate")

    monkeypatch.setattr(meaning, "_run_claude", boom)
    messages = []
    doc = Document(source="x.txt", blocks=[Block("para", TEXT)])
    html = render_document(doc, LENS, ai={"model": "haiku", "max_calls": 5}, log=messages.append)
    assert any("AI layer skipped" in m for m in messages)
    assert "<p>" in html and "data-cat=\"number\"" in html


def test_claude_timeout_becomes_ai_unavailable(monkeypatch, tmp_path):
    import subprocess

    monkeypatch.setattr(meaning.shutil, "which", lambda name: "claude")

    def slow(*a, **k):
        raise subprocess.TimeoutExpired(a[0], 240)

    monkeypatch.setattr(meaning.subprocess, "run", slow)
    with pytest.raises(meaning.AIUnavailable, match="240"):
        meaning._run_claude("hi", "haiku", str(tmp_path))


def test_finished_batches_are_cached_when_another_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(meaning, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(meaning, "MAX_BATCH_ITEMS", 1)
    a = "First passage with enough characters to be eligible for the model call."
    b = "Second passage with enough characters to be eligible for the model call."

    def fake(prompt, model, cwd=None):
        if a in prompt:
            return json.dumps([{"i": 0, "phrase": "First passage", "cat": "keyterm"}])
        raise meaning.AIUnavailable("boom")

    monkeypatch.setattr(meaning, "_run_claude", fake)
    with pytest.raises(meaning.AIUnavailable):
        meaning.tag_texts([a, b], LENS, workers=1)
    out = meaning.tag_texts([a], LENS, workers=1)  # served from cache, no call for a
    assert [(a[s.start : s.end], s.cat) for s in out[a]] == [("First passage", "keyterm")]


def test_render_nests_content_inside_meaning(monkeypatch, tmp_path):
    monkeypatch.setattr(meaning, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(
        meaning,
        "_run_claude",
        lambda p, m, cwd=None: json.dumps([{"i": 0, "phrase": "released per minute 12 times", "cat": "example"}]),
    )
    doc = Document(source="x.txt", blocks=[Block("para", TEXT)])
    html = render_document(doc, LENS, ai={"model": "haiku", "max_calls": 5})
    assert 'class="c c-example l-meaning"' in html
    inner = html.split('c-example l-meaning"', 1)[1].split("</span></span>", 1)[0]
    assert 'data-cat="number"' in inner  # the number stays styled inside the marker
    assert "Meaning (AI)" in html


def test_grammar_words_differ_by_shape_not_only_color():
    from synesthetic.overlay import _Ctx
    from synesthetic.render import _cat_css

    lens = load_lens()
    css = _cat_css(lens)
    verb = css.split(".c-verb{", 1)[1].split("}", 1)[0]
    adjective = css.split(".c-adjective{", 1)[1].split("}", 1)[0]
    assert "font-weight:700" in verb and "font-style:italic" in adjective
    assert ".c.l-grammar.c-adverb{text-decoration:underline dotted" in css
    look = _Ctx(lens, {}, "a", True, print).look   # kept-layout files use the same shapes
    assert look["verb"]["bold"] and look["adjective"]["italic"] and look["adverb"]["underline"] == "dotted"
    assert not look["noun"]["bold"] and not look["noun"]["italic"]
