"""What changed, newest first: every change that reached main, for the change log in Settings.

Read from `git log` when the repo is here (running on this computer), so it can't fall behind. The hosted app has
no .git, so it reads static/changelog.json (written by tools/build_changelog.py before each push) and puts the
deployed commit on top from Vercel's own variables when that file doesn't have it yet.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/mrwells1216/Synethetics-Layer"
ROOT = Path(__file__).resolve().parent.parent
STATIC_FILE = Path(__file__).resolve().parent / "static" / "changelog.json"
TAGS = ("Added", "Changed", "Fixed", "Removed")
_TRAILER = re.compile(r"^(Co-Authored-By|Signed-off-by|Reviewed-by|Change-Id):", re.I)
_MERGE = re.compile(r"^Merge pull request #(\d+)")


def tags_for(title: str, body: str = "") -> list[str]:
    """The kind of change, from its words. The first tag is the main one."""
    t = title.lower()
    first = t.split(" ", 1)[0]
    if first in ("remove", "removes", "removed", "drop", "drops", "delete", "deletes", "retire", "retires"):
        main = "Removed"
    elif first in ("fix", "fixes", "fixed", "repair", "correct") or re.search(r"\b(bug|broken|crash|regression)\b", t):
        main = "Fixed"
    elif re.search(r"\b(add|adds|added|new|introduce)\b", t) or t.startswith("initial"):
        main = "Added"
    elif first in ("redesign", "rename", "change", "changes", "update", "updates", "move", "moves", "make",
                   "makes", "keep", "restyle", "rework", "replace", "serve", "use", "switch", "speed"):
        main = "Changed"
    else:
        main = "Added"
    out = [main]
    # a sentence in the description that starts with Fix... or Remove... adds that tag too
    starts = re.findall(r"(?:^|[.;:!?]\s+|\n\s*)(fix(?:es|ed)?|remove[sd]?|drop(?:s|ped)?)\b", body, re.I)
    words = {w.lower() for w in starts}
    if main != "Fixed" and words & {"fix", "fixes", "fixed"}:
        out.append("Fixed")
    if main != "Removed" and words & {"remove", "removes", "removed", "drop", "drops", "dropped"}:
        out.append("Removed")
    return out


def _body(raw: str) -> str:
    """Commit body as paragraphs, without trailers like Co-Authored-By."""
    lines = [ln for ln in raw.strip().splitlines() if not _TRAILER.match(ln.strip())]
    paras, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def parse(raw: str) -> list[dict]:
    """Parses `git log --first-parent --format=%H%x1f%cI%x1f%s%x1f%b%x1e`."""
    out = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        sha, date, subject, body = (rec.split("\x1f") + ["", "", ""])[:4]
        sha = sha.strip()
        m = _MERGE.match(subject)
        if m:  # a merged pull request: its title is the first line of the body
            first, _, rest = body.strip().partition("\n")
            title, body, url = first.strip() or subject, rest, f"{REPO_URL}/pull/{m.group(1)}"
        else:
            title, url = subject.strip(), f"{REPO_URL}/commit/{sha}"
        body = _body(body)
        out.append({"sha": sha, "short": sha[:7], "date": date.strip(), "title": title, "body": body,
                    "tags": tags_for(title, body), "url": url})
    return out


def git_log(root: Path = ROOT) -> list[dict] | None:
    if not (root / ".git").exists() or not shutil.which("git"):
        return None
    try:
        raw = subprocess.run(["git", "log", "--first-parent", "--format=%H%x1f%cI%x1f%s%x1f%b%x1e"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", timeout=15, check=True).stdout
    except Exception:
        return None
    return parse(raw)


def head(root: Path = ROOT) -> str:
    """The commit this copy runs: Vercel says which it deployed; here, ask git."""
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
    if sha:
        return sha
    if (root / ".git").exists() and shutil.which("git"):
        try:
            return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                                  timeout=5).stdout.strip()
        except Exception:
            return ""
    return ""


def load(root: Path = ROOT, static_file: Path = STATIC_FILE) -> list[dict]:
    live = git_log(root)
    if live is not None:
        return live
    try:
        entries = json.loads(static_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = []
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
    if sha and all(e.get("sha") != sha for e in entries):
        msg = os.environ.get("VERCEL_GIT_COMMIT_MESSAGE", "").strip()
        title, _, body = msg.partition("\n")
        title = title.strip() or "Latest update"
        body = _body(body)
        entries.insert(0, {"sha": sha, "short": sha[:7], "date": "", "title": title, "body": body,
                           "tags": tags_for(title, body), "url": f"{REPO_URL}/commit/{sha}"})
    return entries


class Cached:
    """Read again only when the commit on disk changes."""

    def __init__(self):
        self.key, self.data = None, b"[]"

    def get(self) -> bytes:
        k = head() or "-"
        if k != self.key:
            self.data, self.key = json.dumps(load(), ensure_ascii=False, separators=(",", ":")).encode(), k
        return self.data
