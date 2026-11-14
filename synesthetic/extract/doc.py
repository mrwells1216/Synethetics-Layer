"""Legacy Word 97-2003 (.doc) text reader, no Office or LibreOffice needed.

Reads the main-document text through the Word piece table. Gives paragraphs and plain text only
(no heading or table structure); when LibreOffice is installed the dispatcher converts to .docx
instead and keeps the structure.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

from ..model import Document
from . import txt as txt_mod


class DocReadError(Exception):
    pass


def text_from_streams(word: bytes, table: bytes) -> str:
    """Pure function over the two streams, so it can be tested without an OLE file."""
    if len(word) < 0x1AA or struct.unpack_from("<H", word, 0)[0] != 0xA5EC:
        raise DocReadError("Not a Word 97-2003 document.")
    flags = struct.unpack_from("<H", word, 0x0A)[0]
    if flags & 0x0100:
        raise DocReadError("This .doc is encrypted.")
    ccp_text = struct.unpack_from("<i", word, 0x4C)[0]
    fc_clx, lcb_clx = struct.unpack_from("<II", word, 0x1A2)
    clx = table[fc_clx : fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:  # skip Prc entries
        pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if pos >= len(clx) or clx[pos] != 0x02:
        raise DocReadError("Could not find the text piece table.")
    lcb = struct.unpack_from("<I", clx, pos + 1)[0]
    plc = clx[pos + 5 : pos + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    out: list[str] = []
    total = 0
    for i in range(n):
        fc = struct.unpack_from("<I", plc, (n + 1) * 4 + i * 8 + 2)[0]
        count = cps[i + 1] - cps[i]
        if fc & 0x40000000:  # 8-bit text
            start = (fc & 0x3FFFFFFF) // 2
            out.append(word[start : start + count].decode("cp1252", errors="replace"))
        else:  # UTF-16
            out.append(word[fc : fc + count * 2].decode("utf-16-le", errors="replace"))
        total += count
        if total >= ccp_text:
            break
    return "".join(out)[:ccp_text]


def clean(text: str) -> str:
    text = re.sub(r"\x13[^\x14\x15]*\x14", "", text)  # field code, keep the result
    text = re.sub(r"\x13[^\x15]*\x15", "", text)  # field with no result
    text = text.replace("\x15", "")
    text = text.replace("\x07", " ").replace("\x0b", "\n").replace("\x0c", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract(path) -> Document:
    import olefile

    path = Path(path)
    try:
        ole = olefile.OleFileIO(str(path))
    except Exception as e:
        raise DocReadError(f"Not a readable .doc file: {e}") from e
    try:
        word = ole.openstream("WordDocument").read()
        flags = struct.unpack_from("<H", word, 0x0A)[0]
        table = ole.openstream("1Table" if flags & 0x0200 else "0Table").read()
    finally:
        ole.close()
    text = clean(text_from_streams(word, table))
    # reuse the plain-text heuristics: blank-line paragraphs, bullets, headings
    text = re.sub(r"\n(?!\n)", "\n\n", text)
    tmp = txt_mod.extract_text(text, path)
    tmp.notes.append("Legacy .doc read as plain text: headings and tables are not recovered. "
                     "Install LibreOffice or re-save as .docx for full structure.")
    return tmp
