from synesthetic.annotate import load_lens
from synesthetic.colorcheck import SURFACES, check, contrast

LENS = load_lens()
CONTENT = [c for c in LENS.categories if c.layer == "content"]


def test_every_text_color_meets_wcag_aa_on_its_surface():
    fails, _ = check(LENS)
    assert fails == [], fails


def test_known_contrast_values():
    assert round(contrast("#000000", "#ffffff"), 1) == 21.0
    assert contrast("#777777", "#ffffff") < 4.6  # classic borderline grey


def _cue(c):
    return (c.font, c.weight >= 600, c.underline)


def test_every_category_has_a_unique_non_color_cue():
    """Color is never the only signal (WCAG 1.4.1): no two categories share font, weight and underline."""
    cues = [_cue(c) for c in CONTENT]
    assert len(set(cues)) == len(cues), [c.name for c in CONTENT if cues.count(_cue(c)) > 1]


def test_color_blind_confusable_pairs_are_separated_by_a_cue():
    _, pairs = check(LENS)
    by_name = {c.name: c for c in CONTENT}
    for a, b, theme, pal, vision, d in pairs:
        assert _cue(by_name[a]) != _cue(by_name[b]), (a, b, theme, pal, vision, d)


def test_chip_text_is_readable_on_every_fill():
    from synesthetic.render import _on

    for c in CONTENT:
        for key in ("dark", "light", "cb_dark", "cb_light"):
            fill = c.colors[key]
            assert contrast(_on(fill), fill) >= 4.5, (c.name, key)
