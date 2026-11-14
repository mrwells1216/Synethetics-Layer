"""Excel (.xlsx/.xlsm) extractor (openpyxl): each sheet becomes a typed table."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ..model import Block, Cell, Document

MAX_ROWS = 5000
MAX_COLS = 60


def _cell(v) -> Cell:
    if v is None:
        return Cell("")
    if isinstance(v, bool):
        return Cell("TRUE" if v else "FALSE")
    if isinstance(v, (dt.datetime, dt.date)):
        if isinstance(v, dt.datetime) and (v.hour or v.minute or v.second):
            return Cell(v.strftime("%Y-%m-%d %H:%M"), "date")
        return Cell(v.strftime("%Y-%m-%d"), "date")
    if isinstance(v, dt.time):
        return Cell(v.strftime("%H:%M"), "date")
    if isinstance(v, int):
        return Cell(str(v), "number")
    if isinstance(v, float):
        return Cell(f"{v:.10g}", "number")
    return Cell(str(v).replace("\n", " ").strip())


def extract(path) -> Document:
    import openpyxl

    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    doc = Document(source=str(path), title=path.stem)
    for ws in wb.worksheets:
        doc.blocks.append(Block("heading", ws.title, level=2))
        rows: list[list[Cell]] = []
        truncated = False
        for ri, row in enumerate(ws.iter_rows(values_only=True)):
            if ri >= MAX_ROWS:
                truncated = True
                break
            cells = [_cell(v) for v in row[:MAX_COLS]]
            while cells and not cells[-1].text:
                cells.pop()
            rows.append(cells)
        while rows and not rows[-1]:
            rows.pop()
        if not rows or all(not any(c.text for c in r) for r in rows):
            doc.blocks.append(Block("para", "(empty sheet)"))
            continue
        width = max(len(r) for r in rows)
        for r in rows:
            r.extend(Cell("") for _ in range(width - len(r)))
        doc.blocks.append(Block("table", rows=rows, header_rows=1))
        if truncated:
            doc.notes.append(f"Sheet '{ws.title}' was cut at {MAX_ROWS} rows.")
    wb.close()
    return doc
