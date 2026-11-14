import re

from synesthetic.annotate import load_lens
from synesthetic.cli import main
from synesthetic.extract import UnsupportedFile, extract
from synesthetic.render import render_document

import pytest

LENS = load_lens()


def kinds(doc):
    return [b.kind for b in doc.blocks]


def test_md_structure(fixtures):
    doc = extract(fixtures / "sample.md")
    assert doc.title == "Project Plan"
    ks = kinds(doc)
    assert ks.count("heading") == 2
    assert "table" in ks and "code" in ks and "quote" in ks
    items = [b for b in doc.blocks if b.kind == "item"]
    assert [i.marker for i in items][:2] == ["•", "•"]
    assert items[2].marker == "1."
    tbl = next(b for b in doc.blocks if b.kind == "table")
    assert tbl.header_rows == 1 and tbl.rows[1][1].text == "$4.50"
    strong = [b for b in doc.blocks if b.kind == "para" and b.emph]
    assert strong and strong[0].emph[0][2] == "b"


def test_txt_structure(fixtures):
    doc = extract(fixtures / "sample.txt")
    assert doc.blocks[0].kind == "heading" and doc.blocks[0].level == 1
    assert sum(1 for b in doc.blocks if b.kind == "item") == 2
    # the hard-wrapped paragraph is rejoined
    para = next(b for b in doc.blocks if b.kind == "para" and "Meeting held" in b.text)
    assert "\n" not in para.text and "$1,250.50 and the review" in para.text


def test_docx_structure(fixtures):
    doc = extract(fixtures / "sample.docx")
    ks = kinds(doc)
    assert ks[0] == "heading" and doc.blocks[0].level == 1
    assert "item" in ks and "table" in ks
    tbl = next(b for b in doc.blocks if b.kind == "table")
    assert tbl.rows[0][0].text == "Region" and tbl.rows[1][1].text == "$1,200"


def test_docx_hand_formatted_headings(fixtures):
    doc = extract(fixtures / "sample.docx")
    heads = {b.text: b.level for b in doc.blocks if b.kind == "heading"}
    assert heads["HAND FORMATTED TITLE"] == 1  # 18 pt bold
    assert heads["Bold Section Line"] == 3  # whole paragraph bold, Normal style
    assert not any("Only part" in t for t in heads)  # partly bold stays a paragraph
    assert any("Only part" in b.text for b in doc.blocks if b.kind == "para")


def test_xlsx_typed_cells(fixtures):
    doc = extract(fixtures / "sample.xlsx")
    tbl = next(b for b in doc.blocks if b.kind == "table")
    assert tbl.rows[0][0].text == "Item"
    assert tbl.rows[1][1].ctype == "number" and tbl.rows[1][2].ctype == "date"
    assert tbl.rows[2][1].text == "-3.5"


def test_pdf_headings_and_text(fixtures):
    doc = extract(fixtures / "sample.pdf")
    heads = [(b.text, b.level) for b in doc.blocks if b.kind == "heading"]
    assert ("Annual Overview", 1) in heads
    assert any(t == "Section One" and lvl == 2 for t, lvl in heads)
    assert any("Aug 14, 2026" in b.text for b in doc.blocks if b.kind == "para")
    assert sum(1 for b in doc.blocks if b.kind == "rule") == 2


def test_render_has_categories_and_modes(fixtures):
    html = render_document(extract(fixtures / "sample.md"), LENS)
    for cat in ("number", "date", "id", "link", "reference", "warning", "quote"):
        assert f'data-cat="{cat}"' in html, cat
    assert 'data-v="a"' in html and 'data-v="b"' in html and 'data-v="c"' in html
    assert ".m-b .c{" in html and ".m-c .c{" in html
    assert "<script>" in html


def test_copy_text_preserved(fixtures):
    """Stripping tags from the rendered body must give back the source text."""
    doc = extract(fixtures / "sample.md")
    html = render_document(doc, LENS)
    body = html.split("<main>", 1)[1].split("</main>", 1)[0]
    plain = re.sub(r"<[^>]+>", "", body)
    import html as h

    plain = h.unescape(plain)
    for b in doc.blocks:
        if b.kind in ("para", "item", "quote", "heading"):
            assert b.text in plain, b.text


def test_escape_html(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("<script>alert(1)</script> & done", encoding="utf-8")
    html = render_document(extract(f), LENS)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(" in html and "&lt;/script&gt;" in html


def test_cli_folder(fixtures, tmp_path):
    out = tmp_path / "out"
    rc = main([str(fixtures), "-o", str(out)])
    assert rc == 0
    assert (out / "index.html").exists()
    for name in ("sample.md", "sample.txt", "sample.pdf", "sample.docx", "sample.xlsx"):
        assert (out / f"{name}.html").exists(), name


def test_cp1252_text_is_not_read_as_utf16(tmp_path):
    f = tmp_path / "legacy.txt"
    f.write_bytes("It’s done — café “ok”".encode("cp1252"))  # even length, no BOM
    doc = extract(f)
    assert doc.blocks[0].text == "It’s done — café “ok”"
    g = tmp_path / "wide.txt"
    g.write_bytes("Title\n\nBody here".encode("utf-16"))  # with BOM
    assert [b.text for b in extract(g).blocks] == ["Title", "Body here"]


def test_txt_lead_in_line_is_not_glued_to_previous_bullet(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("- a\n\nNote here\n- b\n  more b\n", encoding="utf-8")
    blocks = [(b.kind, b.text) for b in extract(f).blocks]
    assert blocks == [("item", "a"), ("para", "Note here"), ("item", "b more b")]


def test_template_placeholder_in_document_text_survives(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("Jinja uses {{BODY}} and {{DEFAULTS}} markers.\n", encoding="utf-8")
    html = render_document(extract(f), LENS)
    assert "{{BODY}}" in html and "{{DEFAULTS}}" in html
    assert html.count('"palette":') == 1  # the options JSON appears once, in the script


def test_user_style_reaches_the_page(tmp_path):
    f = tmp_path / "s.md"
    f.write_text("Pay $5 today.\n", encoding="utf-8")
    style = {"colors": {"number": {"dark": "#ABCDEF", "light": "#123456"}}, "body": "lexend",
             "heading": "georgia", "size": 120, "mode": "b", "theme": "light"}
    html = render_document(extract(f), LENS, style=style)
    assert ':root:not([data-theme="light"]):not([data-pal="cb"]){--c-number:#abcdef' in html
    assert ':root[data-theme="light"]:not([data-pal="cb"]){--c-number:#123456' in html
    assert "family=Lexend" in html and "body{font-family:Lexend" in html
    assert "font-size:20.4px" in html and '"mode": "b"' in html and '"theme": "light"' in html


def test_bad_style_values_are_dropped(tmp_path):
    f = tmp_path / "s.md"
    f.write_text("Pay $5 today.\n", encoding="utf-8")
    plain = render_document(extract(f), LENS)
    evil = {"colors": {"number": {"dark": "red;}</style><script>x()</script>"}, "nope": {"dark": "#ffffff"}},
            "body": "x;}body{display:none", "size": 9999, "mode": "z", "theme": 3}
    assert render_document(extract(f), LENS, style=evil) == plain
    assert render_document(extract(f), LENS, style="not a dict") == plain


def test_cli_style_file(tmp_path):
    import json

    src = tmp_path / "n.md"
    src.write_text("Pay $5.\n", encoding="utf-8")
    style = tmp_path / "synesthetic-style.json"
    style.write_text(json.dumps({"version": 1, "colors": {"number": {"dark": "#00ff00"}}}), encoding="utf-8")
    assert main([str(src), "-o", str(tmp_path / "out"), "--style", str(style)]) == 0
    assert "--c-number:#00ff00" in (tmp_path / "out" / "n.md.html").read_text(encoding="utf-8")


def test_unsupported(tmp_path):
    f = tmp_path / "a.xyz"
    f.write_text("x")
    with pytest.raises(UnsupportedFile):
        extract(f)
