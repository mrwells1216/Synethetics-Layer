from synesthetic.annotate import load_lens
from synesthetic.extract import extract
from synesthetic.formula import parse_formula
from synesthetic.render import render_document

import pytest

LENS = load_lens()


@pytest.mark.parametrize(
    "text, label, core",
    [
        ("E = mc²", "", "E = mc²"),
        ("a² + b² = c²", "", "a² + b² = c²"),
        ("Revenue = Price × Quantity", "", "Revenue = Price × Quantity"),
        ("F = ma", "", "F = ma"),
        ("PV = nRT", "", "PV = nRT"),
        ("Total = 1,250", "", "Total = 1,250"),
        ("x ≈ 3.14", "", "x ≈ 3.14"),
        ("Osmotic pressure: Π = iMRT", "Osmotic pressure", "Π = iMRT"),
        ("Surface area to volume: SA/V = 3/r for a sphere", "Surface area to volume", "SA/V = 3/r for a sphere"),
        ("$$ΔG = ΔH − TΔS$$", "", "ΔG = ΔH − TΔS"),
        ("$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$", "", "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"),
    ],
)
def test_formulas_found(text, label, core):
    assert parse_formula(text) == (label, core)


@pytest.mark.parametrize(
    "text",
    [
        "Set the margin = 2 inches and keep going",
        "x = 5 means the answer is five",
        "Name = John Smith",
        "Mitochondria: the organelles that turn glucose into usable energy (ATP).",
        "The exam is on Oct 14 at 9:00 AM in Room B-204.",
        "Do not confuse diffusion with active transport: only active transport requires energy.",
        "a = b. Then we move on to the next step of the proof here",
        "",
    ],
)
def test_prose_left_alone(text):
    assert parse_formula(text) is None


def test_formula_block_through_extract_and_render(tmp_path):
    src = tmp_path / "notes.md"
    src.write_text("# Notes\n\nSome prose here with 42 items.\n\nOsmotic pressure: Π = iMRT\n\n$$E = mc^2$$\n", encoding="utf-8")
    doc = extract(src)
    kinds = [b.kind for b in doc.blocks]
    assert kinds == ["heading", "para", "formula", "formula"]
    assert doc.blocks[2].marker == "Osmotic pressure" and doc.blocks[2].text == "Π = iMRT"
    assert doc.blocks[3].marker == "" and doc.blocks[3].text == "E = mc^2"
    html = render_document(doc, LENS)
    assert '<div class="fx"><span class="fxl">Osmotic pressure</span><span class="fxm">' in html
    assert html.count('class="fx"') == 2
    assert ".fx{" in html  # the box's style ships with the page
