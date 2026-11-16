"""Write synesthetic/static/changelog.json from git, for the hosted app (which has no .git).

Run before each push: `.venv\\Scripts\\python.exe tools\\build_changelog.py`. The commit being pushed isn't in the
file yet; the hosted app adds it on top from Vercel's VERCEL_GIT_COMMIT_SHA / _MESSAGE.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from synesthetic.changelog import STATIC_FILE, git_log  # noqa: E402


def main():
    entries = git_log(ROOT)
    if entries is None:
        print("No git history here.", file=sys.stderr)
        return 1
    STATIC_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(entries)} changes -> {STATIC_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
