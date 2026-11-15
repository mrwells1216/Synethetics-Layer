import io
import zipfile

import pytest

from synesthetic.annotate import load_lens
from synesthetic.cli import main
from synesthetic.overlay import OverlayError, overlay


@pytest.fixture(scope="module")
def lens():
    return load_lens()


def test_pdf_gets_highlights_and_keeps_its_text(fixtures, lens):
    import pymupdf

    src = (fixtures / "sample.pdf").read_bytes()
    ov = overlay("sample.pdf", src, lens)
    assert ov.name == "sample (colored).pdf" and ov.mime == "application/pdf"
    assert ov.counts["date"] == 2 and ov.counts["number"] == 2 and ov.counts["link"] == 2
    out = pymupdf.open(stream=ov.data, filetype="pdf")
    before = pymupdf.open(stream=src, filetype="pdf")
    assert [p.get_text() for p in out] == [p.get_text() for p in before]
    annots = [(a.type[1], a.info["content"]) for a in out[0].annots()]
    assert ("Highlight", lens.get("date").label) in annots
    # underline-only style uses underline marks instead
    ov_d = overlay("sample.pdf", src, lens, style={"mode": "d"})
    kinds = {a.type[1] for a in pymupdf.open(stream=ov_d.data, filetype="pdf")[0].annots()}
    assert kinds == {"Underline"}


def test_custom_light_color_is_used(fixtures, lens):
    import pymupdf

    ov = overlay("sample.pdf", (fixtures / "sample.pdf").read_bytes(), lens,
                 style={"colors": {"date": {"light": "#ff0000"}}})
    page = pymupdf.open(stream=ov.data, filetype="pdf")[0]
    date = next(a for a in page.annots() if a.info["content"] == lens.get("date").label)
    assert tuple(round(x, 2) for x in date.colors["stroke"]) == (1.0, 0.0, 0.0)


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
