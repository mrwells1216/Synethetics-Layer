"""The Roller's looks (Core Pool, preset rollers) as the server reads and draws them."""
from synesthetic.annotate import load_lens
from synesthetic.render import _custom_css, bank_css, clean_bank, clean_rich, clean_style, look_rules, rich_css


def test_clean_rich_keeps_good_values_and_drops_the_rest():
    got = clean_rich({
        "weight": 900, "italic": True, "caps": "yes", "font": "fraunces", "color": "#5FD38D", "size": 22,
        "underline": {"w": 3, "color": "#ff6b6b"}, "overline": {"w": 9, "color": "red"},
        "hl": {"color": "#f2c14e", "h": 80, "w": 0.2}, "ls": 0.05, "ws": 5, "lh": 2.4,
        "evil": "url(javascript:alert(1))",
    })
    assert got == {"weight": 900, "italic": True, "font": "fraunces", "color": "#5fd38d", "size": 22,
                   "underline": {"w": 3, "color": "#ff6b6b"}, "overline": {},
                   "hl": {"color": "#f2c14e", "h": 80, "w": 0.2}, "ls": 0.05, "lh": 2.4}
    assert clean_rich("nope") == {} and clean_rich({"font": "comic-sans", "size": 200}) == {}


def test_rich_css_draws_every_enhancer():
    css = rich_css({"weight": 700, "italic": True, "font": "courier", "size": 20, "caps": True, "ls": 0.1, "ws": 0.3, "lh": 2,
                    "underline": {"w": 3, "color": "#ff6b6b"}, "overline": {"w": 2, "color": "#3dd6d0"},
                    "hl": {"color": "#f2c14e", "h": 60, "w": 0.2}})
    for part in ("font-weight:700", "font-style:italic", "Courier New", "font-size:20px", "text-transform:uppercase",
                 "letter-spacing:0.1em", "word-spacing:0.3em", "line-height:2", "text-decoration-thickness:3px",
                 "text-decoration-color:#ff6b6b", "linear-gradient(#3dd6d0,#3dd6d0) left top/100% 2px",
                 "linear-gradient(#f2c14e,#f2c14e) center/100% 60%", "padding:0 0.2em", "color:#101216"):
        assert part in css, part


def test_core_pool_looks_reach_colored_pages():
    lens = load_lens()
    st = clean_style({
        "look": {"number": {"bold": True, "rich": {"overline": {"w": 3, "color": "#ff6b6b"}, "font": "young", "bad": 1}}},
        "wordbank": {"on": True, "words": [{"word": "tree", "color": "#5fd38d", "rich": {"caps": True, "hl": {"color": "#ffffff", "h": 40}}}]},
    }, lens)
    assert st["look"]["number"]["rich"] == {"overline": {"w": 3, "color": "#ff6b6b"}, "font": "young"}
    assert st["wordbank"][0]["rich"] == {"caps": True, "hl": {"color": "#ffffff", "h": 40}}
    rules = "".join(look_rules("number", {**st["look"]["number"], "underline": "none"}))
    # an overline alone keeps the category's tint: it adds a background image, not a new background
    assert "body .c-number" in rules and "background-size:100% 3px" in rules and "background:" not in rules.split("body .c-number")[1]
    assert "center/100% 40%" in bank_css(st["wordbank"])
    css, links = _custom_css(st, lens)
    assert "Young+Serif" in links   # a font set in the Core Pool is loaded on the page


def test_word_bank_without_rich_is_unchanged():
    bank = clean_bank({"on": True, "words": [{"word": "yell", "bold": True}]})
    assert bank == [{"word": "yell", "bold": True}]
