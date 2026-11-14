import struct

import pytest

from synesthetic.extract.doc import DocReadError, clean, text_from_streams


def build_streams(pieces):
    """Build minimal WordDocument/table streams holding the given (text, compressed) pieces."""
    word = bytearray(0x400)
    struct.pack_into("<H", word, 0, 0xA5EC)
    chunks = []
    cps = [0]
    pcds = b""
    offset = 0x200
    for text, compressed in pieces:
        raw = text.encode("cp1252") if compressed else text.encode("utf-16-le")
        word[offset : offset + len(raw)] = raw
        fc = (offset * 2) | 0x40000000 if compressed else offset
        pcds += struct.pack("<HIH", 0, fc, 0)
        cps.append(cps[-1] + len(text))
        offset += len(raw)
        chunks.append(raw)
    struct.pack_into("<i", word, 0x4C, cps[-1])
    plc = struct.pack(f"<{len(cps)}I", *cps) + pcds
    clx = b"\x02" + struct.pack("<I", len(plc)) + plc
    struct.pack_into("<II", word, 0x1A2, 0, len(clx))
    return bytes(word), clx


def test_pieces_8bit_and_utf16():
    word, table = build_streams([("Hello, world.\r", True), ("Café – ok\r", False)])
    assert text_from_streams(word, table) == "Hello, world.\rCafé – ok\r"


def test_clean_fields_and_cells():
    raw = "Total\x07 \x13 HYPERLINK \"x\" \x14click here\x15 now\rNext\x0bline\r"
    assert clean(raw) == "Total click here now\nNext\nline"


def test_rejects_non_word():
    with pytest.raises(DocReadError):
        text_from_streams(b"\x00" * 0x400, b"")
