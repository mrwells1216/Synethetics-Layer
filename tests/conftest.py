import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLE_MD = """# Project Plan

Status: **on track**. Contact jane@example.com or see https://example.com/docs.

## Costs

- Budget is $12,500 (up 8%)
- Invoice INV-20481 due Aug 14, 2026
1. First step, see page 5
2. Do not skip the review

> "Quality over speed" said Maria Lopez.

| Item | Cost |
|------|------|
| Lamp | $4.50 |
| Desk | $120 |

```
raw code 123
```
"""

SAMPLE_TXT = """PROJECT NOTES

Meeting held on 2026-08-14 at 3:45 PM with the team. Total cost was $1,250.50
and the review is required before launch.

- first bullet with 42 items
- second bullet

Term: a definition goes here
"""


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory):
    d = tmp_path_factory.mktemp("fx")
    (d / "sample.md").write_text(SAMPLE_MD, encoding="utf-8")
    (d / "sample.txt").write_text(SAMPLE_TXT, encoding="utf-8")

    import docx

    dd = docx.Document()
    dd.add_heading("Quarterly Report", 1)
    dd.add_paragraph("Revenue grew 12% to $4.2M by Sep 30, 2026. Warning: figures are unaudited.")
    dd.add_heading("Details", 2)
    big = dd.add_paragraph().add_run("HAND FORMATTED TITLE")
    big.bold = True
    big.font.size = docx.shared.Pt(18)
    dd.add_paragraph().add_run("Bold Section Line").bold = True
    mixed = dd.add_paragraph()
    mixed.add_run("Only part ").bold = True
    mixed.add_run("is bold here, so this stays a paragraph.")
    dd.add_paragraph("First point", style="List Bullet")
    dd.add_paragraph("Second point", style="List Number")
    t = dd.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Region"
    t.cell(0, 1).text = "Sales"
    t.cell(1, 0).text = "North"
    t.cell(1, 1).text = "$1,200"
    dd.save(d / "sample.docx")

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Item", "Qty", "Date", "Note"])
    ws.append(["Lamp", 12, dt.date(2026, 8, 14), "see page 3"])
    ws.append(["Desk", -3.5, dt.date(2026, 9, 1), "Do not reorder"])
    wb.save(d / "sample.xlsx")

    import pymupdf

    pdf = pymupdf.open()
    for n in (1, 2):
        pg = pdf.new_page()
        pg.insert_text((72, 90), "Annual Overview", fontsize=24, fontname="hebo")
        pg.insert_text((72, 130), "Section One", fontsize=16, fontname="hebo")
        pg.insert_text(
            (72, 160),
            "The meeting is on Aug 14, 2026 and the budget is $9,000.",
            fontsize=11,
        )
        pg.insert_text((72, 180), "Contact: ops@example.com for help.", fontsize=11)
    pdf.save(d / "sample.pdf")
    return d
