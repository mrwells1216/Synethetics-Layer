import pytest

from synesthetic.annotate import annotate, load_lens

LENS = load_lens()


def spans(text):
    return {(text[s.start : s.end], s.cat) for s in annotate(text, LENS)}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Pay $1,250.50 now", ("$1,250.50", "number")),
        ("Up 12% overall", ("12%", "number")),
        ("Temp is -5 today", ("-5", "number")),
        ("Due Aug 14, 2026.", ("Aug 14, 2026", "date")),
        ("Due 2026-08-14", ("2026-08-14", "date")),
        ("At 3:45 PM.", ("3:45 PM", "date")),
        ("Ref INV-20481 here", ("INV-20481", "id")),
        ("Ticket #4521 open", ("#4521", "id")),
        ("See page 5 for more", ("See page 5", "reference")),
        ("Visit https://x.com/a, then", ("https://x.com/a", "link")),
        ("Mail jane@example.com now", ("jane@example.com", "link")),
        ("Call 608.271.9000 today", ("608.271.9000", "link")),
        ("Call (608) 271-9000 today", ("(608) 271-9000", "link")),
        ("Open C:\\Users\\me\\file.txt please", ("C:\\Users\\me\\file.txt", "link")),
        ("Warning: this is bad", ("Warning", "warning")),
        ("Do not skip it", ("Do not", "warning")),
        ('He said "quality first" twice', ('"quality first"', "quote")),
        ("Status: all good", ("Status", "term")),
        ("Alpha means the first thing", ("Alpha", "term")),
        ("We met Jane Smith there", ("Jane Smith", "name")),
    ],
)
def test_detects(text, expected):
    assert expected in spans(text)


@pytest.mark.parametrize(
    "text",
    [
        "Option 1 or 2 applies",  # lone digits are not numbers
        "Create/Edit/View access",  # slash lists are not paths
        "Sex/GI/SAAB options",
        'values like ", " and ": " appear',  # stray quote fragments
    ],
)
def test_known_noise_not_flagged(text):
    cats = {c for _, c in spans(text)}
    assert not cats & {"number", "link", "quote"}, spans(text)


def test_real_paths_and_numbers_still_found():
    assert ("/epic/pki/certs/a.crt", "link") in spans("see /epic/pki/certs/a.crt now")
    assert ("src/app/main.py", "link") in spans("edit src/app/main.py today")
    assert ("42", "number") in spans("there are 42 items")
    assert ("3.5", "number") in spans("rate of 3.5 per day")
    assert ('"XHC"', "quote") in spans('the code "XHC" is used')


def test_name_category_starts_off():
    assert LENS.get("name").default_off is True
    assert LENS.get("number").default_off is False


def test_slash_date_is_date_not_path():
    s = spans("Filed 10/12/2026 ok")
    assert ("10/12/2026", "date") in s
    assert not any(c == "link" for _, c in s)


def test_no_false_positives_in_plain_prose():
    assert spans("the quick brown fox jumps over the lazy dog") == set()


def test_spans_do_not_overlap():
    t = 'Warning: "do not pay $5 on Aug 14, 2026 to INV-1234" see page 5 at https://a.com/b'
    sp = annotate(t, LENS)
    for a, b in zip(sp, sp[1:]):
        assert a.end <= b.start


def test_priority_quote_beats_inner_number():
    t = 'He said "pay 5 now" ok'
    assert spans(t) == {('"pay 5 now"', "quote")}
