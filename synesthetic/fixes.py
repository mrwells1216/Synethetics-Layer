"""Fixes and ideas the owner leaves inside the app, for the next Claude session to act on.

Developer mode in the app (Settings) lets the owner highlight text and press Fix/idea, or triple-click for a
screenshot window. Each entry lands in one of two places:

- running on this computer (`synesthetic serve`): a SQLite file and a folder of PNGs in the local data folder,
  outside the repo (`%LOCALAPPDATA%\\SynestheticLayer` on Windows, or $SYNESTHETIC_DATA);
- hosted on Vercel: the private Blob store connected to the project, readable only with the server's key.

Entries are append-only: nothing the owner wrote can change or be deleted. Only `status`, `review` and `reviewed`
change, once, from open to done or skipped. Every session sent in to fix or add something starts with:

    python fixes.py list            # pulls new hosted entries in first, then lists the open ones
    python fixes.py show 7
    python fixes.py done 7 "Moved the date under the title"
    python fixes.py skip 8 "Out of scope: needs a new data source"

These are instructions for the developer session. Nothing that talks to an AI model may read this store.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("text", "shot")
MARKS = ("good", "bad", "fix")
CLOSED = ("done", "skipped")
TEXT_MAX, NOTE_MAX, SHORT_MAX, CONTEXT_MAX, REVIEW_MAX = 4000, 2000, 200, 4000, 2000
PNG_MAX = 3_000_000  # decoded; the hosted request limit is 4.5 MB and base64 adds a third
PNG_SIG = b"\x89PNG\r\n\x1a\n"
DATA_URL = "data:image/png;base64,"
BLOB_ENTRIES, BLOB_IMAGES, BLOB_REVIEWS = "fixes/entries/", "fixes/images/", "fixes/reviews/"
BLOB_STYLE = "fixes/style.json"   # the Editor's looks for the chat add-on: one document, overwritten


class FixError(ValueError):
    """A plain-words reason an entry was refused (sent back as a 4xx)."""


# ---------------------------------------------------------------- cleaning what comes in

_SECRETS = [
    re.compile(r"\b(?:sk|pk|rk)-(?:[A-Za-z0-9_-]{8,})"),          # OpenAI / Anthropic / Stripe-style keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),                    # GitHub tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS access key ids
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),                  # Slack
    re.compile(r"\bvercel_blob_rw_[A-Za-z0-9_]{10,}"),              # Vercel Blob tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWTs
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)\b(password|passwd|secret|api[_ -]?key|token)\s*[:=]\s*\S{6,}"),
]


def redact(s: str) -> str:
    """Takes keys and tokens out of text before it is stored."""
    for p in _SECRETS:
        s = p.sub(lambda m: (m.group(1) + ": " if m.re.groups else "") + "[removed]", s)
    return s


def _short(v, cap: int) -> str:
    return redact(str(v or "").replace("\x00", "").strip())[:cap]


def decode_png(data_url) -> bytes | None:
    """A screenshot must be a PNG data URL; anything else is refused."""
    if not data_url:
        return None
    if not isinstance(data_url, str) or not data_url.startswith(DATA_URL):
        raise FixError("The picture must be a PNG.")
    b64 = data_url[len(DATA_URL):]
    if len(b64) > PNG_MAX * 4 // 3 + 8:
        raise FixError(f"The picture is larger than {PNG_MAX // 1_000_000} MB.")
    try:
        png = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise FixError("The picture could not be read.") from None
    if not png.startswith(PNG_SIG):
        raise FixError("The picture must be a PNG.")
    if len(png) > PNG_MAX:
        raise FixError(f"The picture is larger than {PNG_MAX // 1_000_000} MB.")
    return png


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_entry(data) -> tuple[dict, bytes | None]:
    """Checks one entry from the page. Returns the fields to store and the PNG bytes, if any."""
    if not isinstance(data, dict):
        raise FixError("Send the entry as a JSON object.")
    kind = data.get("kind")
    if kind not in KINDS:
        raise FixError("Kind must be text or shot.")
    mark = data.get("mark") or "fix"
    if mark not in MARKS:
        raise FixError("Mark must be good, bad or fix.")
    text, note = _short(data.get("text"), TEXT_MAX), _short(data.get("note"), NOTE_MAX)
    png = decode_png(data.get("image"))
    # the marked text says enough by itself; the comment is optional (the page offers Submit or Skip)
    if kind == "text" and not text:
        raise FixError("A highlight needs the highlighted text.")
    if kind == "shot" and not (png or text or note):
        raise FixError("A screenshot needs a picture, some text or a note.")
    if kind == "text" and png:
        raise FixError("A highlight has no picture.")
    ctx = data.get("context") or {}
    if not isinstance(ctx, dict):
        raise FixError("Context must be a JSON object.")
    ctx_s = redact(json.dumps(ctx, ensure_ascii=False, separators=(",", ":")))
    if len(ctx_s) > CONTEXT_MAX:
        raise FixError("The context is too long.")
    entry = {"made": now(), "kind": kind, "mark": mark, "section": _short(data.get("section"), SHORT_MAX),
             "page": _short(data.get("page"), SHORT_MAX), "text": text, "note": note, "context": ctx_s}
    return entry, png


def clean_review(status, review) -> tuple[str, str]:
    if status not in CLOSED:
        raise FixError("Close an entry as done or skipped.")
    review = _short(review, REVIEW_MAX)
    if not review:
        raise FixError("Say what was done (or why not).")
    return status, review


# ---------------------------------------------------------------- local store (SQLite)

def data_dir() -> Path:
    env = os.environ.get("SYNESTHETIC_DATA")
    if env:
        return Path(env)
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "SynestheticLayer"
    return Path.home() / ".local" / "share" / "synesthetic-layer"


SCHEMA = """
CREATE TABLE IF NOT EXISTS fixes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  made TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('text','shot')),
  mark TEXT NOT NULL CHECK(mark IN ('good','bad','fix')),
  section TEXT, page TEXT, text TEXT, note TEXT, context TEXT, image TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done','skipped')),
  review TEXT, reviewed TEXT,
  remote TEXT UNIQUE);
CREATE TRIGGER IF NOT EXISTS fixes_no_delete BEFORE DELETE ON fixes
BEGIN SELECT RAISE(ABORT, 'fixes are append-only: entries cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS fixes_keep_words BEFORE UPDATE ON fixes
WHEN NEW.id IS NOT OLD.id OR NEW.made IS NOT OLD.made OR NEW.kind IS NOT OLD.kind OR NEW.mark IS NOT OLD.mark
  OR NEW.section IS NOT OLD.section OR NEW.page IS NOT OLD.page OR NEW.text IS NOT OLD.text
  OR NEW.note IS NOT OLD.note OR NEW.context IS NOT OLD.context OR NEW.remote IS NOT OLD.remote
  OR (OLD.image IS NOT NULL AND NEW.image IS NOT OLD.image)
BEGIN SELECT RAISE(ABORT, 'what the owner wrote cannot change'); END;
CREATE TRIGGER IF NOT EXISTS fixes_close_once BEFORE UPDATE ON fixes
WHEN (NEW.status IS NOT OLD.status OR NEW.review IS NOT OLD.review OR NEW.reviewed IS NOT OLD.reviewed)
  AND (OLD.status <> 'open' OR NEW.status = 'open' OR NEW.review IS NULL OR NEW.review = '')
BEGIN SELECT RAISE(ABORT, 'an entry closes once, from open, with what was done'); END;
"""
COLS = ("id", "made", "kind", "mark", "section", "page", "text", "note", "context", "image", "status", "review",
        "reviewed", "remote")


class LocalStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else data_dir() / "fixes"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "fixes.db", check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def _row(self, r) -> dict:
        d = dict(zip(COLS, r))
        d["picture"] = str(self.root / d["image"]) if d["image"] else None
        return d

    def add(self, entry: dict, png: bytes | None, *, remote: str | None = None, status: str = "open",
            review: str | None = None, reviewed: str | None = None) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO fixes(made,kind,mark,section,page,text,note,context,status,review,reviewed,remote)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (entry["made"], entry["kind"], entry["mark"], entry.get("section"), entry.get("page"),
                 entry.get("text"), entry.get("note"), entry.get("context"), status, review, reviewed, remote))
            fid = cur.lastrowid
            if png:
                name = f"fix-{fid}.png"
                (self.root / name).write_bytes(png)
                self.db.execute("UPDATE fixes SET image=? WHERE id=?", (name, fid))
        return fid

    def get(self, fid: int) -> dict | None:
        r = self.db.execute(f"SELECT {','.join(COLS)} FROM fixes WHERE id=?", (fid,)).fetchone()
        return self._row(r) if r else None

    # the Editor's looks for the chat add-on, which reads the same file on this computer
    def put_style(self, style: dict) -> None:
        (self.root.parent / "style.json").write_text(json.dumps(style), encoding="utf-8")

    def style(self) -> dict | None:
        try:
            return json.loads((self.root.parent / "style.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def by_remote(self, key: str) -> dict | None:
        r = self.db.execute(f"SELECT {','.join(COLS)} FROM fixes WHERE remote=?", (key,)).fetchone()
        return self._row(r) if r else None

    def entries(self, status: str | None = None, limit: int = 200) -> list[dict]:
        q, args = f"SELECT {','.join(COLS)} FROM fixes", []
        if status:
            q += " WHERE status=?"
            args.append(status)
        rows = self.db.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [self._row(r) for r in rows]

    def close(self, fid: int, status: str, review: str) -> dict:
        status, review = clean_review(status, review)
        e = self.get(fid)
        if not e:
            raise FixError(f"There is no entry {fid}.")
        if e["status"] != "open":
            raise FixError(f"Entry {fid} is already {e['status']}.")
        with self.db:
            self.db.execute("UPDATE fixes SET status=?, review=?, reviewed=? WHERE id=?", (status, review, now(), fid))
        return self.get(fid)

    def image(self, fid: int) -> bytes | None:
        e = self.get(fid)
        return (self.root / e["image"]).read_bytes() if e and e["image"] else None

    # what the page's list shows
    def public(self, limit: int = 60) -> list[dict]:
        return [_public(e, e["id"]) for e in self.entries(limit=limit)]


def _public(e: dict, ref) -> dict:
    return {"ref": str(ref), "made": e["made"], "kind": e["kind"], "mark": e["mark"], "section": e.get("section"),
            "text": e.get("text"), "note": e.get("note"), "picture": bool(e.get("image")), "status": e["status"],
            "review": e.get("review"), "reviewed": e.get("reviewed")}


# ---------------------------------------------------------------- hosted store (private Vercel Blob)

def adopt_blob_env(env=None) -> None:
    """Connecting a Blob store in Vercel can give its variables a custom prefix (MYSTORE_READ_WRITE_TOKEN);
    the SDK only reads the BLOB_ names, so take the store's own values from whatever they are called."""
    env = os.environ if env is None else env
    if not (env.get("BLOB_READ_WRITE_TOKEN") or env.get("VERCEL_BLOB_READ_WRITE_TOKEN")):
        for k, v in sorted(env.items()):
            if k.endswith("_READ_WRITE_TOKEN") and str(v).strip().startswith("vercel_blob_rw_"):
                env["BLOB_READ_WRITE_TOKEN"] = str(v).strip()
                break
    if not env.get("BLOB_STORE_ID"):
        for k, v in sorted(env.items()):
            if k.endswith("STORE_ID") and str(v).strip().startswith("store_"):
                env["BLOB_STORE_ID"] = str(v).strip()
                break


def blob_ready() -> bool:
    adopt_blob_env()
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN") or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN")
                or os.environ.get("BLOB_STORE_ID"))


class BlobStore:
    """Each entry is its own JSON blob, written once (no overwrite); a review is a second blob beside it, so
    the owner's words are never rewritten and an entry can only be closed once."""

    def __init__(self, api=None):
        if api is None:
            from vercel.blob import sync as api  # noqa: N813 (the official SDK; only needed when hosted)
        self.api = api
        self._seen: dict[str, dict] = {}  # entries and reviews never change once written, so a warm server keeps them

    def _put(self, path: str, body: bytes, ctype: str):
        return self.api.put_blob(path, body, access="private", content_type=ctype, add_random_suffix=False,
                                 allow_overwrite=False)

    def _json(self, path: str) -> dict:
        if path not in self._seen:
            self._seen[path] = json.loads(self.api.get_blob(path, access="private").body)
        return self._seen[path]

    def add(self, entry: dict, png: bytes | None) -> str:
        key = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)
        if png:
            self._put(f"{BLOB_IMAGES}{key}.png", png, "image/png")
        self._put(f"{BLOB_ENTRIES}{key}.json", json.dumps({**entry, "image": bool(png)}).encode(),
                  "application/json")
        return key

    def put_style(self, style: dict) -> None:
        self.api.put_blob(BLOB_STYLE, json.dumps(style).encode(), access="private", content_type="application/json",
                          add_random_suffix=False, allow_overwrite=True)

    def style(self) -> dict | None:
        try:
            return json.loads(self.api.get_blob(BLOB_STYLE, access="private").body)
        except Exception:
            return None

    def _keys(self, prefix: str) -> list[str]:
        return sorted((b.pathname[len(prefix):].rsplit(".", 1)[0] for b in self.api.query_blobs(prefix=prefix)),
                      reverse=True)

    def entries(self, limit: int = 60, since: str | None = None) -> list[dict]:
        """Newest first, with reviews merged in. `since` skips keys at or before it (the CLI's sync)."""
        from concurrent.futures import ThreadPoolExecutor

        keys = [k for k in self._keys(BLOB_ENTRIES) if not since or k > since][:limit]
        reviewed = set(self._keys(BLOB_REVIEWS))
        with ThreadPoolExecutor(4) as pool:
            got = list(pool.map(lambda k: self._json(f"{BLOB_ENTRIES}{k}.json"), keys))
            revs = dict(zip([k for k in keys if k in reviewed], pool.map(
                lambda k: self._json(f"{BLOB_REVIEWS}{k}.json"), [k for k in keys if k in reviewed])))
        out = []
        for k, e in zip(keys, got):
            r = revs.get(k) or {}
            out.append({**e, "key": k, "image": f"{BLOB_IMAGES}{k}.png" if e.get("image") else None,
                        "status": r.get("status", "open"), "review": r.get("review"), "reviewed": r.get("reviewed")})
        return out

    def public(self, limit: int = 60) -> list[dict]:
        return [_public(e, e["key"]) for e in self.entries(limit=limit)]

    def image(self, key: str) -> bytes | None:
        if not re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{6}", key or ""):
            return None
        try:
            return self.api.get_blob(f"{BLOB_IMAGES}{key}.png", access="private").body
        except Exception:
            return None

    def close(self, key: str, status: str, review: str) -> dict:
        status, review = clean_review(status, review)
        if not re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{6}", key or ""):
            raise FixError("Unknown entry.")
        try:
            self.api.head_blob(f"{BLOB_ENTRIES}{key}.json")
        except Exception:
            raise FixError("Unknown entry.") from None
        rec = {"status": status, "review": review, "reviewed": now()}
        try:
            self._put(f"{BLOB_REVIEWS}{key}.json", json.dumps(rec).encode(), "application/json")
        except Exception as e:
            if "exist" in str(e).lower() or type(e).__name__ in ("BlobPreconditionFailedError",):
                raise FixError("This entry is already closed.") from None
            raise
        return rec


# ---------------------------------------------------------------- the CLI (python fixes.py ...)

def remote_config() -> dict:
    p = data_dir() / "remote.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remote_call(cfg: dict, route: str, payload: dict) -> bytes:
    import urllib.request

    req = urllib.request.Request(cfg["url"].rstrip("/") + "/api/" + route, data=json.dumps(payload).encode(),
                                 method="POST", headers={"Content-Type": "application/json", "X-App": "1",
                                                         "X-Dev-Key": cfg["key"], "User-Agent": "synesthetic-fixes"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise FixError(f"{route}: {e.code} {e.read().decode('utf-8', 'replace')[:200]}") from None


def sync(store: LocalStore, cfg: dict, log=print) -> int:
    """Copies hosted entries this computer has not seen yet into the local store, with their pictures, and
    brings over reviews made elsewhere. Returns how many were new."""
    if not cfg.get("url") or not cfg.get("key"):
        return 0
    got = json.loads(_remote_call(cfg, "fix-export", {}))
    new = 0
    for e in sorted(got.get("entries", []), key=lambda x: x["key"]):
        mine = store.by_remote(e["key"])
        if mine:
            if mine["status"] == "open" and e.get("status") in CLOSED:
                store.close(mine["id"], e["status"], e.get("review") or "(closed on the site)")
            continue
        png = None
        if e.get("image"):
            try:
                png = _remote_call(cfg, "fix-image", {"ref": e["key"]})
                png = png if png.startswith(PNG_SIG) else None
            except FixError as err:
                log(f"  picture for {e['key']} not fetched: {err}")
        entry = {k: e.get(k) for k in ("made", "kind", "mark", "section", "page", "text", "note", "context")}
        status = e.get("status") if e.get("status") in CLOSED else "open"
        store.add(entry, png, remote=e["key"], status=status, review=e.get("review") if status != "open" else None,
                  reviewed=e.get("reviewed") if status != "open" else None)
        new += 1
    return new


def _print_entry(e: dict, full: bool = False):
    mark = {"good": "Good", "bad": "Not good", "fix": "Fix/idea"}[e["mark"]]
    head = f"#{e['id']}  {e['made'][:16].replace('T', ' ')}  {mark}  {e['kind']}  [{e['status']}]"
    if e.get("section"):
        head += f"  in {e['section']}"
    print(head)
    if e.get("note"):
        print("   note:", e["note"])
    if e.get("text"):
        t = e["text"] if full else (e["text"][:240] + ("..." if len(e["text"]) > 240 else ""))
        print("   text:", t.replace("\n", " / "))
    if e.get("picture"):
        print("   picture:", e["picture"])
    if full:
        print("   page:", e.get("page") or "-")
        try:
            print("   context:", json.dumps(json.loads(e.get("context") or "{}"), indent=2).replace("\n", "\n   "))
        except ValueError:
            print("   context:", e.get("context"))
        if e.get("remote"):
            print("   hosted key:", e["remote"])
    if e.get("review"):
        print(f"   review ({e.get('reviewed', '')[:16]}):", e["review"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fixes", description="Fixes and ideas left in the app's developer mode.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="open entries, newest first (pulls new hosted ones in first)")
    ls.add_argument("--all", action="store_true", help="include done and skipped")
    ls.add_argument("--offline", action="store_true", help="do not contact the hosted app")
    sh = sub.add_parser("show", help="one entry in full")
    sh.add_argument("id", type=int)
    for name in ("done", "skip"):
        p = sub.add_parser(name, help=f"close an entry as {'done' if name == 'done' else 'skipped'}, saying why")
        p.add_argument("id", type=int)
        p.add_argument("review")
    pr = sub.add_parser("pair", help="make the dev key and the link that turns on saving for a device")
    pr.add_argument("url", nargs="?", help="the hosted app's address")
    args = ap.parse_args(argv)

    if args.cmd == "pair":
        cfg = remote_config()
        cfg["url"] = (args.url or cfg.get("url") or "").rstrip("/")
        if not cfg["url"]:
            print("Give the hosted app's address the first time: python fixes.py pair https://...", file=sys.stderr)
            return 2
        cfg.setdefault("key", secrets.token_urlsafe(24))
        p = data_dir() / "remote.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"Saved in {p}.")
        print("Set SYNESTHETIC_DEV_KEY on the hosted app to the key in that file. Open this on each device:")
        print(f"  {cfg['url']}/#dev={cfg['key']}")
        return 0

    store = LocalStore()
    if args.cmd == "list":
        cfg = remote_config()
        if cfg and not args.offline:
            try:
                n = sync(store, cfg)
                print(f"Pulled {n} new from {cfg['url']}." if n else f"Nothing new on {cfg['url']}.")
            except Exception as e:  # still show what is here
                print(f"Could not reach {cfg.get('url')}: {e}", file=sys.stderr)
        rows = store.entries(None if args.all else "open")
        if not rows:
            print("No open entries." if not args.all else "No entries yet.")
        for e in rows:
            _print_entry(e)
        return 0
    if args.cmd == "show":
        e = store.get(args.id)
        if not e:
            print(f"There is no entry {args.id}.", file=sys.stderr)
            return 1
        _print_entry(e, full=True)
        return 0
    status = "done" if args.cmd == "done" else "skipped"
    try:
        e = store.get(args.id)
        if e and e.get("remote") and e["status"] == "open":
            cfg = remote_config()
            if cfg.get("url"):
                try:
                    _remote_call(cfg, "fix-review", {"ref": e["remote"], "status": status, "review": args.review})
                except FixError as err:
                    if "already closed" not in str(err):
                        raise
        store.close(args.id, status, args.review)
    except FixError as err:
        print(err, file=sys.stderr)
        return 1
    print(f"#{args.id} {status}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
