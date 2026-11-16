"""Developer mode: the fixes store, its endpoint, the CLI sync and the change log."""
import base64
import json
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from synesthetic import changelog
from synesthetic import fixes as fx
from synesthetic.annotate import load_lens
from synesthetic.serve import make_handler

PNG = fx.PNG_SIG + b"\x00\x00\x00\rIHDR" + b"\x00" * 40
PNG_URL = fx.DATA_URL + base64.b64encode(PNG).decode()


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNESTHETIC_DATA", str(tmp_path))
    monkeypatch.delenv("SYNESTHETIC_DEV_KEY", raising=False)
    return tmp_path


# ---------------------------------------------------------------- what an entry must be

def test_highlight_needs_text_and_note():
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "text", "text": "Some words"})
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "text", "note": "Change this"})
    e, png = fx.clean_entry({"kind": "text", "text": "Some words", "note": "Change this", "section": "how"})
    assert e["mark"] == "fix" and png is None and e["section"] == "how"


def test_screenshot_needs_something():
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "shot", "mark": "good"})
    e, png = fx.clean_entry({"kind": "shot", "mark": "good", "image": PNG_URL})
    assert png == PNG and e["mark"] == "good"


@pytest.mark.parametrize("image", [
    "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff").decode(),  # not a PNG
    fx.DATA_URL + base64.b64encode(b"GIF89a....").decode(),                  # PNG label, other bytes
    fx.DATA_URL + "!!not base64!!",
    "https://example.com/a.png",
])
def test_only_a_png_is_kept(image):
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "shot", "note": "x", "image": image})


def test_picture_size_is_capped(monkeypatch):
    monkeypatch.setattr(fx, "PNG_MAX", 100)
    big = fx.DATA_URL + base64.b64encode(fx.PNG_SIG + b"\x00" * 200).decode()
    with pytest.raises(fx.FixError, match="larger"):
        fx.clean_entry({"kind": "shot", "image": big})


def test_unknown_kind_and_mark_are_refused():
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "video", "note": "x"})
    with pytest.raises(fx.FixError):
        fx.clean_entry({"kind": "shot", "mark": "meh", "note": "x"})


def test_secrets_are_taken_out():
    e, _ = fx.clean_entry({"kind": "text", "text": "key sk-ant-abc123def456ghi789 and ghp_" + "a" * 30,
                           "note": "password: hunter2hunter2 please"})
    assert "sk-ant" not in e["text"] and "ghp_" not in e["text"] and "[removed]" in e["text"]
    assert "hunter2" not in e["note"]


def test_long_text_is_capped():
    e, _ = fx.clean_entry({"kind": "text", "text": "a" * 9000, "note": "b" * 9000})
    assert len(e["text"]) == fx.TEXT_MAX and len(e["note"]) == fx.NOTE_MAX


# ---------------------------------------------------------------- the local store is append-only

def test_store_add_list_and_picture(data):
    s = fx.LocalStore()
    e, png = fx.clean_entry({"kind": "shot", "note": "Move the date", "image": PNG_URL})
    fid = s.add(e, png)
    got = s.get(fid)
    assert got["image"] == f"fix-{fid}.png" and Path(got["picture"]).read_bytes() == PNG
    assert got["status"] == "open" and s.public()[0]["picture"] is True
    assert s.root == data / "fixes"


def test_delete_and_edit_are_refused(data):
    s = fx.LocalStore()
    fid = s.add(*fx.clean_entry({"kind": "text", "text": "words", "note": "a note"}))
    with pytest.raises(sqlite3.DatabaseError):
        with s.db:
            s.db.execute("DELETE FROM fixes WHERE id=?", (fid,))
    with pytest.raises(sqlite3.DatabaseError):
        with s.db:
            s.db.execute("UPDATE fixes SET note='changed' WHERE id=?", (fid,))
    with pytest.raises(sqlite3.DatabaseError):
        with s.db:
            s.db.execute("UPDATE fixes SET status='done' WHERE id=?", (fid,))  # closing needs a review
    assert s.get(fid)["note"] == "a note"


def test_closed_entry_stays_closed(data):
    s = fx.LocalStore()
    fid = s.add(*fx.clean_entry({"kind": "text", "text": "words", "note": "a note"}))
    with pytest.raises(fx.FixError):
        s.close(fid, "done", "")
    assert s.close(fid, "done", "Moved it")["status"] == "done"
    with pytest.raises(fx.FixError):
        s.close(fid, "skipped", "again")
    with pytest.raises(sqlite3.DatabaseError):
        with s.db:
            s.db.execute("UPDATE fixes SET status='open', review=NULL WHERE id=?", (fid,))
    assert s.get(fid)["review"] == "Moved it"


def test_cli_list_show_done(data, capsys):
    s = fx.LocalStore()
    fid = s.add(*fx.clean_entry({"kind": "text", "text": "the header", "note": "bigger please"}))
    assert fx.main(["list", "--offline"]) == 0
    assert "bigger please" in capsys.readouterr().out
    assert fx.main(["show", str(fid)]) == 0
    assert fx.main(["done", str(fid), "Made it bigger"]) == 0
    assert fx.main(["skip", str(fid), "again"]) == 1
    fx.main(["list", "--offline"])
    assert "No open entries" in capsys.readouterr().out


# ---------------------------------------------------------------- the hosted store (a stand-in for Vercel Blob)

class FakeBlob:
    class Got:
        def __init__(self, body):
            self.body = body

    class Item:
        def __init__(self, path):
            self.pathname = path

    def __init__(self):
        self.files = {}

    def put_blob(self, path, body, *, access, content_type=None, add_random_suffix=False, allow_overwrite=False):
        assert access == "private" and not add_random_suffix
        if path in self.files and not allow_overwrite:
            raise RuntimeError("This blob already exists")
        self.files[path] = bytes(body)

    def get_blob(self, path, *, access):
        if path not in self.files:
            raise KeyError(path)
        return self.Got(self.files[path])

    def head_blob(self, path):
        if path not in self.files:
            raise KeyError(path)

    def query_blobs(self, *, prefix=None):
        return [self.Item(p) for p in sorted(self.files) if p.startswith(prefix or "")]


def test_blob_store_is_append_only():
    api = FakeBlob()
    b = fx.BlobStore(api=api)
    key = b.add(*fx.clean_entry({"kind": "shot", "note": "n", "image": PNG_URL}))
    assert b.image(key) == PNG and b.entries()[0]["status"] == "open"
    b.close(key, "done", "Did it")
    with pytest.raises(fx.FixError, match="already closed"):
        b.close(key, "skipped", "no")
    assert b.public()[0]["review"] == "Did it"
    with pytest.raises(fx.FixError):
        b.close("../../etc", "done", "x")
    assert b.image("../x") is None


def test_blob_variables_with_a_custom_prefix_are_found():
    env = {"SYNESTHETIC_FIXES_READ_WRITE_TOKEN": " vercel_blob_rw_abc123 ", "OTHER_READ_WRITE_TOKEN": "nope",
           "SYNESTHETIC_FIXES_STORE_ID": "store_xyz"}
    fx.adopt_blob_env(env)
    assert env["BLOB_READ_WRITE_TOKEN"] == "vercel_blob_rw_abc123" and env["BLOB_STORE_ID"] == "store_xyz"
    env = {"BLOB_READ_WRITE_TOKEN": "vercel_blob_rw_keep", "X_READ_WRITE_TOKEN": "vercel_blob_rw_other"}
    fx.adopt_blob_env(env)
    assert env["BLOB_READ_WRITE_TOKEN"] == "vercel_blob_rw_keep"


# ---------------------------------------------------------------- the endpoint

def serve(hosted=False):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(load_lens(), hosted=hosted))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def call(base, route, payload, headers=None):
    hd = {"Content-Type": "application/json", "X-App": "1", **(headers or {})}
    req = urllib.request.Request(f"{base}/api/{route}", data=json.dumps(payload).encode(), method="POST", headers=hd)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def test_endpoint_round_trip_on_this_computer(data):
    srv, base = serve()
    try:
        got = json.loads(call(base, "fix-add", {"kind": "shot", "mark": "fix", "note": "Tabs too small",
                                                 "image": PNG_URL, "context": {"region": [1, 2, 3, 4]}}))
        ref = str(got["id"])
        lst = json.loads(call(base, "fix-list", {}))["entries"]
        assert lst[0]["note"] == "Tabs too small" and lst[0]["picture"]
        assert call(base, "fix-image", {"ref": ref}) == PNG
        assert json.loads(call(base, "fix-review", {"ref": ref, "status": "done", "review": "Bigger"}))["ok"]
        with pytest.raises(urllib.error.HTTPError) as e:
            call(base, "fix-review", {"ref": ref, "status": "done", "review": "Again"})
        assert e.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as e:
            call(base, "fix-add", {"kind": "text", "text": "only text"})
        assert e.value.code == 400 and b"note" in e.value.read()
    finally:
        srv.shutdown()


def test_missing_header_and_cross_site_are_refused(data):
    srv, base = serve()
    try:
        req = urllib.request.Request(f"{base}/api/fix-list", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as e:
            call(base, "fix-list", {}, {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        assert e.value.code == 403
    finally:
        srv.shutdown()


def test_hosted_needs_the_dev_key(data, monkeypatch):
    api, real = FakeBlob(), fx.BlobStore
    monkeypatch.setattr(fx, "BlobStore", lambda: real(api=api))
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test")
    srv, base = serve(hosted=True)
    try:  # no key on the server: refused
        with pytest.raises(urllib.error.HTTPError) as e:
            call(base, "fix-list", {})
        assert e.value.code == 403
        monkeypatch.setenv("SYNESTHETIC_DEV_KEY", "k" * 24)
        with pytest.raises(urllib.error.HTTPError) as e:
            call(base, "fix-list", {}, {"X-Dev-Key": "wrong"})
        assert e.value.code == 403
        key = {"X-Dev-Key": "k" * 24}
        ref = json.loads(call(base, "fix-add", {"kind": "text", "text": "Hi", "note": "Bigger"}, key))["id"]
        assert any(p.startswith(fx.BLOB_ENTRIES) for p in api.files)
        exported = json.loads(call(base, "fix-export", {}, key))["entries"]
        assert exported[0]["key"] == ref and exported[0]["note"] == "Bigger"
        call(base, "fix-review", {"ref": ref, "status": "skipped", "review": "Not now"}, key)
        assert json.loads(call(base, "fix-list", {}, key))["entries"][0]["status"] == "skipped"
    finally:
        srv.shutdown()


def test_cli_pulls_hosted_entries_in(data, monkeypatch):
    api = FakeBlob()
    hosted = fx.BlobStore(api=api)
    k1 = hosted.add(*fx.clean_entry({"kind": "shot", "note": "one", "image": PNG_URL}))
    hosted.add(*fx.clean_entry({"kind": "text", "text": "t", "note": "two"}))

    def remote(cfg, route, payload):
        if route == "fix-export":
            return json.dumps({"entries": hosted.entries(limit=500)}).encode()
        if route == "fix-image":
            return hosted.image(payload["ref"])
        if route == "fix-review":
            hosted.close(payload["ref"], payload["status"], payload["review"])
            return b"{}"
        raise AssertionError(route)

    monkeypatch.setattr(fx, "_remote_call", remote)
    monkeypatch.setattr(fx, "remote_config", lambda: {"url": "https://site.example", "key": "k"})
    local = fx.LocalStore()
    assert fx.sync(local, fx.remote_config()) == 2
    assert fx.sync(local, fx.remote_config()) == 0  # already here
    one = local.by_remote(k1)
    assert local.image(one["id"]) == PNG
    assert fx.main(["done", str(one["id"]), "Fixed it"]) == 0
    assert {e["key"]: e["status"] for e in hosted.entries()}[k1] == "done"  # the review reached the site too


# ---------------------------------------------------------------- the page script

def test_page_script_builds_without_html_strings():
    js = (Path(fx.__file__).parent / "static" / "dev.js").read_text(encoding="utf-8")
    assert not re.search(r"\.(innerHTML|outerHTML)\b|insertAdjacentHTML|document\.write", js)


def test_page_loads_the_dev_script_and_config(data):
    srv, base = serve()
    try:
        html = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        assert re.search(r'<script src="/dev\.js\?v=[0-9a-f]{10}">', html)
        assert 'id="set-dev"' in html and 'id="log-card"' in html
        cfg = json.loads(re.search(r'<script id="cfg" type="application/json">(.*?)</script>', html, re.S).group(1))
        assert cfg["dev"]["store"] == "local"
        js = urllib.request.urlopen(base + "/dev.js", timeout=10)
        assert js.headers["Content-Type"].startswith("text/javascript")
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- the change log

def test_changelog_parse_and_tags():
    raw = ("aaaa111\x1f2026-11-15T10:00:00-06:00\x1fMerge pull request #4 from x/y\x1fRemove the old picker\n\nIt was slow.\n\nCo-Authored-By: C <c@x>\x1e\n"
           "bbbb222\x1f2026-11-14T10:00:00-06:00\x1fFix stale examples\x1f\x1e\n"
           "cccc333\x1f2026-11-13T10:00:00-06:00\x1fSix tabs and a Word Bank\x1fNew tabs. Fixes the date bug too.\n\nCo-Authored-By: C <c@x>\x1e")
    got = changelog.parse(raw)
    assert [g["tags"][0] for g in got] == ["Removed", "Fixed", "Added"]
    assert got[0]["title"] == "Remove the old picker" and got[0]["url"].endswith("/pull/4")
    assert got[0]["body"] == "It was slow." and "Co-Authored" not in got[2]["body"]
    assert got[2]["tags"] == ["Added", "Fixed"] and got[1]["url"].endswith("/commit/bbbb222")
    # words merely mentioned in a sentence don't add tags
    assert changelog.tags_for("Add a change log", "Each change is tagged Added, Changed, Fixed or Removed.") == ["Added"]
    assert changelog.tags_for("New samples", "Better PDFs. Fixes: dates, ligatures.") == ["Added", "Fixed"]


def test_changelog_hosted_puts_the_deployed_commit_on_top(tmp_path, monkeypatch):
    f = tmp_path / "changelog.json"
    f.write_text(json.dumps([{"sha": "old", "title": "Older", "tags": ["Added"]}]))
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abcdef1234")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_MESSAGE", "Change log in Settings\n\nAnd developer mode.")
    got = changelog.load(root=tmp_path, static_file=f)  # no .git here
    assert got[0]["short"] == "abcdef1" and got[0]["title"] == "Change log in Settings" and got[1]["sha"] == "old"
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "old")
    assert len(changelog.load(root=tmp_path, static_file=f)) == 1


def test_changelog_is_served(data):
    srv, base = serve()
    try:
        got = json.loads(urllib.request.urlopen(base + "/changelog.json", timeout=20).read())
        assert got and {"sha", "title", "tags", "date", "url"} <= set(got[0])
    finally:
        srv.shutdown()
