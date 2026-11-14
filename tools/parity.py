"""Check that the chat mod's TypeScript annotator gives the same spans as synesthetic/annotate.py.

    python tools/parity.py [mod_folder]

Copies the mod's hooks to a temp folder with explicit .ts import paths (so plain Node can run
them), runs both annotators over a corpus, and reports any difference.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synesthetic.annotate import annotate, load_lens  # noqa: E402
from synesthetic.extract import extract  # noqa: E402

DEFAULT_MOD = Path(__file__).resolve().parent.parent / "chat-mod" / "synesthetic-chat"

BASE = [
    "Warning: do not pay $1,250.50 (12%) by Aug 14, 2026 to INV-20481. See page 5 at https://x.com/a, then email a@b.com.",
    "Call 608.271.9000 or (608) 271-9000 today.",
    'He said "quality first" twice and “smart quotes” once.',
    "Status: all good",
    "Alpha means the first thing",
    "We met Jane Smith there and John Brown too.",
    "Open C:\\Users\\me\\file.txt or /epic/pki/certs/a.crt or src/app/main.py please",
    "Filed 10/12/2026 at 3:45 PM and 14:30:05, ticket #4521, id 99486174-D1AD-43A5-A199-B4AE6E9761C6",
    "Option 1 or 2 applies; Create/Edit/View access; Sex/GI/SAAB options",
    "Temp is -5 today, rate of 3.5 per day, 42 items, 1,000,000 total, $4.5M",
    "Don't skip it. It's REQUIRED and you cannot fail; error 404.",
    "the quick brown fox jumps over the lazy dog",
    "Step 2: see Section 3.1, Figure 4 and pp. 12-14 (Table 5).",
]


def corpus() -> list[str]:
    texts = list(BASE)
    docs = ROOT / "tests"
    for p in (ROOT / "README.md",):
        d = extract(p)
        texts += [b.text for b in d.blocks if b.kind in ("para", "item", "quote") and b.text]
    return texts


def main(mod: Path) -> int:
    lens = load_lens()
    texts = corpus()
    py = [[(s.start, s.end, s.cat) for s in annotate(t, lens)] for t in texts]

    tmp = Path(tempfile.mkdtemp(prefix="synesthetic_parity_"))
    try:
        for name in ("annotate.ts", "lens.ts"):
            src = (mod / "hooks" / name).read_text(encoding="utf-8")
            src = re.sub(r"from '\./(\w+)'", r"from './\1.ts'", src)
            (tmp / name).write_text(src, encoding="utf-8")
        (tmp / "texts.json").write_text(json.dumps(texts), encoding="utf-8")
        (tmp / "run.mjs").write_text(
            "import { annotate } from './annotate.ts'\n"
            "import { readFileSync } from 'node:fs'\n"
            "const texts = JSON.parse(readFileSync(new URL('./texts.json', import.meta.url), 'utf8'))\n"
            "console.log(JSON.stringify(texts.map(t => annotate(t).map(s => [s.start, s.end, s.cat]))))\n",
            encoding="utf-8",
        )
        res = subprocess.run(["node", "run.mjs"], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            print(res.stderr[-1500:])
            return 2
        ts = [[tuple(x) for x in row] for row in json.loads(res.stdout)]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # JS strings index by UTF-16 units, Python by code points: convert Python spans for comparison
    def to_utf16(text: str, spans):
        out = []
        for s, e, c in spans:
            out.append((len(text[:s].encode("utf-16-le")) // 2, len(text[:e].encode("utf-16-le")) // 2, c))
        return out

    bad = 0
    for t, a, b in zip(texts, py, ts):
        a16 = to_utf16(t, a)
        if a16 != [tuple(x) for x in b]:
            bad += 1
            print("MISMATCH:", t[:90])
            print("  python:", a16)
            print("  ts    :", b)
    print(f"{len(texts)} texts, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MOD))
