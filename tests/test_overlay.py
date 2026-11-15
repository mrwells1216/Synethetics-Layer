import io
import zipfile
from pathlib import Path

import pytest

from synesthetic.annotate import load_lens
from synesthetic.cli import main
from synesthetic.overlay import OverlayError, overlay


@pytest.fixture(scope="module")
def lens():
    return load_lens()


def test_pdf_notes_keep_the_text_exactly(fixtures, lens):
    import pymupdf

    src = (fixtures / "sample.pdf").read_bytes()
    ov = overlay("sample.pdf", src, lens, style={"pdf": "notes"})
    assert ov.name == "sample (colored).pdf" and ov.mime == "application/pdf"
    assert ov.counts["date"] == 2 and ov.counts["number"] == 2 and ov.counts["link"] == 2
    out = pymupdf.open(stream=ov.data, filetype="pdf")
    before = pymupdf.open(stream=src, filetype="pdf")
    assert [p.get_text() for p in out] == [p.get_text() for p in before]
    annots = [(a.type[1], a.info["content"]) for a in out[0].annots()]
    assert ("Highlight", lens.get("date").label) in annots
    # underline-only style uses underline marks instead
    ov_d = overlay("sample.pdf", src, lens, style={"mode": "d", "pdf": "notes"})
    kinds = {a.type[1] for a in pymupdf.open(stream=ov_d.data, filetype="pdf")[0].annots()}
    assert kinds == {"Underline"}


def test_custom_light_color_is_used(fixtures, lens):
    import pymupdf

    ov = overlay("sample.pdf", (fixtures / "sample.pdf").read_bytes(), lens,
                 style={"colors": {"date": {"light": "#ff0000"}}, "pdf": "notes"})
    page = pymupdf.open(stream=ov.data, filetype="pdf")[0]
    date = next(a for a in page.annots() if a.info["content"] == lens.get("date").label)
    assert tuple(round(x, 2) for x in date.colors["stroke"]) == (1.0, 0.0, 0.0)


def _pdf_with(lines):
    import pymupdf

    d = pymupdf.open()
    page = d.new_page()
    for i, t in enumerate(lines):
        page.insert_text((72, 100 + 30 * i), t, fontsize=12, fontname="tiro")
    return d.tobytes()


def test_pdf_words_are_redrawn_in_their_new_look(lens):
    import pymupdf

    src = _pdf_with(["Pay $1,450 by Sep 1, 2026. Do not be late.", "Please yell about it."])
    style = {"mode": "a", "wordbank": {"on": True, "words": [{"word": "yell", "caps": True, "color": "#c00000",
                                                             "bg": "#ffe14d", "font": "arial", "size": 1.3, "bold": True}]}}
    ov = overlay("x.pdf", src, lens, style=style)
    assert ov.counts["number"] == 1 and ov.counts["date"] == 1 and ov.counts["warning"] == 1 and ov.counts["Word Bank"] == 1
    page = pymupdf.open(stream=ov.data, filetype="pdf")[0]
    assert not list(page.annots())        # drawn into the page, not notes on top
    new = {}
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for sp in line["spans"]:
                if sp["color"] != 0:          # the redrawn words are the colored ones
                    new[sp["text"].strip()] = sp
    warn = new["DO NOT"]                                   # ALL CAPS, bold, in the warning color
    assert "Bold" in warn["font"] and warn["color"] == int(lens.get("warning").colors["light"][1:], 16)
    def tall(sp):   # drawn height (narrowed letters report a smaller "size", but keep their height)
        return sp["bbox"][3] - sp["bbox"][1]
    plain = 12 * 1.333   # the height of the 12 pt text around them, roughly
    assert tall(new["$1,450"]) > plain - 0.5             # numbers a little larger
    yell = new["YELL"]
    assert yell["font"] == "Helvetica-Bold" and yell["color"] == 0xC00000 and tall(yell) > plain - 0.5
    # everything else stays exactly where it was
    before = {w[4]: w[:2] for w in pymupdf.open(stream=src, filetype="pdf")[0].get_text("words")}
    after = {w[4]: w[:2] for w in page.get_text("words")}
    for word in ("Pay", "by", "be", "late.", "Please", "about", "it."):
        assert after[word] == before[word]


def test_pdf_restyle_does_not_cover_neighbors_or_miss_ligatures(lens):
    import pymupdf

    src = (Path(__file__).resolve().parent.parent / "synesthetic" / "static" / "samples" / "market-wrap.pdf").read_bytes()
    style = {"wordbank": {"on": True, "words": [{"word": "inflation", "bg": "#ffe14d"}]}}
    ov = overlay("market-wrap.pdf", src, lens, style=style)
    assert ov.counts["Word Bank"] >= 3            # "inflation" is set with an fl ligature in this file
    assert ov.counts["number"] > 50 and ov.counts["date"] > 20
    assert len(pymupdf.open(stream=ov.data, filetype="pdf")) == 3


def test_scanned_pdf_is_refused(lens):
    import pymupdf

    blank = pymupdf.open()
    blank.new_page()
    with pytest.raises(OverlayError):
        overlay("scan.pdf", blank.tobytes(), lens)


def test_word_text_is_unchanged_and_colored_in_place(fixtures, lens):
    import docx

    src = (fixtures / "sample.docx").read_bytes()
    for mode in ("a", "b", "c", "d"):
        ov = overlay("sample.docx", src, lens, style={"mode": mode})
        before, after = docx.Document(io.BytesIO(src)), docx.Document(io.BytesIO(ov.data))
        assert [p.text for p in after.paragraphs] == [p.text for p in before.paragraphs]
        assert after.tables[0].cell(1, 1).text == "$1,200"
        xml = zipfile.ZipFile(io.BytesIO(ov.data)).read("word/document.xml").decode()
        assert {"a": "<w:color", "b": "<w:shd", "c": "<w:shd", "d": "<w:u "}[mode] in xml
    assert ov.counts["number"] >= 3


def test_word_run_properties_stay_in_schema_order(lens):
    import docx
    from docx.shared import Pt

    d = docx.Document()
    r = d.add_paragraph().add_run("Pay $40 now")
    r.bold = True
    r.font.size = Pt(14)
    buf = io.BytesIO()
    d.save(buf)
    ov = overlay("x.docx", buf.getvalue(), lens, style={"mode": "c"})
    xml = zipfile.ZipFile(io.BytesIO(ov.data)).read("word/document.xml").decode()
    import re

    rpr = re.search(r"<w:rPr>((?:(?!</w:rPr>).)*)</w:rPr><w:t[^>]*>\$40<", xml).group(1)
    assert rpr.index("<w:b/>") < rpr.index("<w:color") < rpr.index("<w:sz") < rpr.index("<w:shd")


def test_excel_cells_are_colored_and_formulas_kept(fixtures, lens):
    import openpyxl
    from openpyxl.cell.rich_text import CellRichText

    wb = openpyxl.load_workbook(fixtures / "sample.xlsx")
    wb.active["E2"] = "=B2*2"
    buf = io.BytesIO()
    wb.save(buf)
    ov = overlay("sample.xlsx", buf.getvalue(), lens)
    out = openpyxl.load_workbook(io.BytesIO(ov.data), rich_text=True).active
    assert out["E2"].value == "=B2*2"
    assert out["B2"].font.color.rgb.endswith(lens.get("number").colors["light"].lstrip("#").upper())
    assert isinstance(out["D2"].value, CellRichText) and str(out["D2"].value) == "see page 3"


def test_other_types_are_refused(lens):
    with pytest.raises(OverlayError):
        overlay("notes.md", b"# hi\n", lens)


def test_cli_keep_writes_a_colored_copy(fixtures, tmp_path):
    assert main([str(fixtures), "-o", str(tmp_path), "--keep"]) == 0
    names = {p.name for p in tmp_path.iterdir()}
    assert {"sample (colored).pdf", "sample (colored).docx", "sample (colored).xlsx", "sample.md.html"} <= names


def test_roller_units_match_what_gets_colored(fixtures, lens):
    from synesthetic.overlay import layout_units, parse_only

    for name in ("sample.pdf", "sample.docx", "sample.xlsx"):
        data = (fixtures / name).read_bytes()
        u = layout_units(name, data)
        assert u["texts"] and u["kind"] == name.split(".")[1]
        if name.endswith(".pdf"):
            page = u["pages"][0]
            assert page["img"].startswith("data:image/jpeg;base64,") and page["lines"]
            for line in page["lines"]:  # each line sits at its place in its unit's text
                assert u["texts"][line["u"]][line["s"]:line["s"] + len(line["t"])] == line["t"]
        full = overlay(name, data, lens)
        assert sum(overlay(name, data, lens, only={}).counts.values()) == 0
        everything = {i: [(0, 10 ** 9)] for i in range(len(u["texts"]))}
        assert overlay(name, data, lens, only=everything).counts == full.counts
    assert parse_only("3:0-5,9-12;7") == {3: [(0, 5), (9, 12)], 7: [(0, 10 ** 9)]}
    assert parse_only("") is None


def test_word_bank_and_caps_in_word(lens):
    import docx

    d = docx.Document()
    d.add_paragraph().add_run("Please yell, do not pay $40")
    buf = io.BytesIO()
    d.save(buf)
    style = {"wordbank": {"on": True, "words": [{"word": "yell", "caps": True, "bg": "#ffe600", "color": "#d00000",
                                                 "font": "arial", "size": 1.5, "bold": True}]}}
    ov = overlay("x.docx", buf.getvalue(), lens, style=style)
    xml = zipfile.ZipFile(io.BytesIO(ov.data)).read("word/document.xml").decode()
    import re

    def rpr(word):
        return re.search(r"<w:rPr>((?:(?!</w:rPr>).)*)</w:rPr><w:t[^>]*>" + re.escape(word) + "<", xml).group(1)
    yell = rpr("yell")
    assert 'w:ascii="Arial"' in yell and "<w:b/>" in yell and "<w:caps/>" in yell and 'w:val="33"' in yell
    assert 'w:fill="FFE600"' in yell and 'w:val="D00000"' in yell
    assert "<w:caps/>" in rpr("do not")           # warnings are ALL CAPS by default
    assert 'w:sz w:val="25"' in rpr("$40")         # numbers a little larger
    assert ov.counts["Word Bank"] == 1
    off = overlay("x.docx", buf.getvalue(), lens, style={"wordbank": {"on": False, "words": style["wordbank"]["words"]}})
    assert "Arial" not in zipfile.ZipFile(io.BytesIO(off.data)).read("word/document.xml").decode()


def test_word_bank_on_pages(lens):
    from synesthetic.model import Block, Document
    from synesthetic.render import render_document

    doc = Document(source="a.md", title="t", blocks=[Block(kind="para", text="Yell about $40 and yell again.")])
    style = {"wordbank": {"on": True, "words": [{"word": "yell", "caps": True, "color": "#d00000"}]},
             "look": {"number": {"case": "upper", "scale": 1.5}}}
    html = render_document(doc, lens, style=style, log=lambda *a, **k: None)
    assert html.count('class="c c-wb-0 l-bank"') == 2
    assert "body .c.c-wb-0{color:#d00000" in html and "text-transform:uppercase" in html
    assert ".c-number{text-transform:uppercase;font-size:1.5em}" in html
