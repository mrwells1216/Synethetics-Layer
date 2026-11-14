"""Vercel entry point: the same upload page and converter as `synesthetic serve`.

vercel.json rewrites every path here. Uploads are capped just under Vercel's 4.5 MB request limit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synesthetic.annotate import load_lens  # noqa: E402
from synesthetic.serve import make_handler  # noqa: E402

MAX_BYTES = 4_400_000


class handler(make_handler(load_lens(), max_bytes=MAX_BYTES, hosted=True)):
    pass
