"""Pre-render the "How it works" examples into synesthetic/static/showcase.json.

Each example is rendered once with the grammar layer included, so the web app can switch the
grammar layer, palette and highlight style on and off instantly (and without spaCy on the server).
Run again after changing the lens or the examples:
`.venv\\Scripts\\python.exe tools\\build_showcase.py`
"""
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synesthetic.annotate import load_lens  # noqa: E402
from synesthetic.extract import extract  # noqa: E402
from synesthetic.render import render_document  # noqa: E402

EXAMPLES = ROOT / "synesthetic" / "examples"
OUT = ROOT / "synesthetic" / "static" / "showcase.json"


def main():
    lens = load_lens()
    meta = tomllib.loads((EXAMPLES / "examples.toml").read_text(encoding="utf-8"))["example"]
    out = []
    for ex in meta:
        page = render_document(extract(EXAMPLES / ex["file"]), lens, grammar=True, theme="dark",
                               log=lambda *a, **k: None)
        # the app supplies its own controls: drop the page's bar and script
        page = re.sub(r'<div class="bar".*?</div>\n<main>', "<main>", page, count=1, flags=re.S)
        page = re.sub(r"<script>.*?</script>", "", page, count=1, flags=re.S)
        page = page.replace('<p class="file">' + ex["file"] + "</p>\n", "")
        body = page.split("<main>", 1)[1]
        counts = Counter(re.findall(r'data-cat="([\w-]+)"', body))
        out.append({"key": Path(ex["file"]).stem, "title": ex["title"], "blurb": ex["blurb"],
                    "group": ex.get("group", "everyday"), "html": page,
                    "counts": {c.name: counts[c.name] for c in lens.categories if counts[c.name]}})
        print(f"{ex['title']:32} {sum(counts.values()):4} marks")
    OUT.write_text(json.dumps({"examples": out}, separators=(",", ":")), encoding="utf-8")
    print(OUT.name, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
