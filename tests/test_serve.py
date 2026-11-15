import threading
import urllib.error
import urllib.request

import pytest

from synesthetic.annotate import load_lens
from synesthetic.serve import make_handler, make_server


@pytest.fixture()
def server():
    srv = make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def post(base, name, data, extra=""):
    req = urllib.request.Request(f"{base}/convert?name={name}{extra}", data=data, method="POST")
    return urllib.request.urlopen(req, timeout=30)


def test_upload_page(server):
    html = urllib.request.urlopen(server + "/", timeout=10).read().decode()
    assert "Synesthetic Layer" in html and ".pdf" in html


def test_convert_markdown(server):
    r = post(server, "note.md", b"# Title\n\nPay $1,250 by Aug 14, 2026.\n")
    html = r.read().decode()
    assert r.status == 200 and 'data-cat="number"' in html and 'data-cat="date"' in html


def test_rejects_unknown_type_and_empty(server):
    for name, data, code in (("a.exe", b"x", 400), ("a.md", b"", 413)):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(server, name, data)
        assert e.value.code == code


def test_cross_site_post_is_refused(server):
    req = urllib.request.Request(f"{server}/convert?name=a.md", data=b"# hi\n", method="POST",
                                 headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403
    host = server.split("//", 1)[1]
    req = urllib.request.Request(f"{server}/convert?name=a.md", data=b"# hi\n", method="POST",
                                 headers={"Sec-Fetch-Site": "same-origin", "Origin": f"http://{host}"})
    assert urllib.request.urlopen(req, timeout=10).status == 200


def test_page_has_config_and_any_get_serves_it(server):
    import json
    import re

    for path in ("/", "/api/index"):
        html = urllib.request.urlopen(server + path, timeout=10).read().decode()
        cfg = json.loads(re.search(r'<script id="cfg" type="application/json">(.*?)</script>', html).group(1))
        assert ".pdf" in cfg["exts"] and cfg["maxBytes"] > 0 and cfg["hosted"] is False
        assert cfg["showcase"] is True and set(cfg["hlCss"]) == {"sm", "md", "lg"}
        # the page colors its own text with the content patterns
        cats = {c["name"]: c for c in cfg["categories"]}
        assert cats["number"]["patterns"] and cats["warning"]["flags"] == "i"
        assert cats["noun"]["patterns"] == []
        assert cats["warning"]["case"] == "upper" and cats["number"]["scale"] > 1 and cats["date"]["cbDark"]


def test_showcase_examples(server):
    import json

    d = json.loads(urllib.request.urlopen(server + "/showcase.json", timeout=10).read())["examples"]
    groups = {e["group"] for e in d}
    assert groups == {"famous", "everyday"} and len(d) >= 12
    for e in d:
        assert "<main>" in e["html"] and 'class="bar"' not in e["html"] and "<script" not in e["html"]
        assert sum(e["counts"].values()) > 20
    # the famous writing is pre-rendered with the grammar layer, so it can be switched on in the app
    assert any(e["counts"].get("noun") for e in d if e["group"] == "famous")


def test_thumb_units_and_rolled_parts(server, fixtures):
    import json
    from urllib.parse import quote, unquote

    for name in ("sample.pdf", "sample.docx", "sample.xlsx"):
        data = (fixtures / name).read_bytes()
        r = urllib.request.urlopen(urllib.request.Request(f"{server}/api/thumb", data=data, method="POST",
                                                          headers={"X-File-Name": name}), timeout=30)
        assert r.headers["Content-Type"] == "image/jpeg" and r.read()[:2] == b"\xff\xd8"
        u = json.loads(urllib.request.urlopen(urllib.request.Request(f"{server}/api/units", data=data, method="POST",
                                                                     headers={"X-File-Name": name}), timeout=30).read())
        assert u["texts"]

        def colored(only=None):
            h = {"X-File-Name": name}
            if only is not None:
                h["X-Only"] = quote(only)
            req = urllib.request.Request(f"{server}/api/convert?keep=1", data=data, method="POST", headers=h)
            return json.loads(unquote(urllib.request.urlopen(req, timeout=30).headers["X-Overlay"]))["count"]
        everything = colored()
        assert everything > 0 and colored("-") == 0
        assert 0 < colored(";".join(str(i) for i in range(len(u["texts"])))) == everything
    # behind Vercel the route comes in the query
    req = urllib.request.Request(f"{server}/api/index?_p=api/thumb", data=(fixtures / "sample.pdf").read_bytes(),
                                 method="POST", headers={"X-File-Name": "sample.pdf"})
    assert urllib.request.urlopen(req, timeout=30).headers["Content-Type"] == "image/jpeg"


def test_name_from_header_and_any_post_path(server):
    req = urllib.request.Request(f"{server}/api/convert", data=b"# T\n\nPay $5 today.\n", method="POST",
                                 headers={"X-File-Name": "my%20notes.md"})
    html = urllib.request.urlopen(req, timeout=10).read().decode()
    assert "my notes.md" in html and 'data-cat="number"' in html


def test_style_header_is_applied(server):
    import json
    from urllib.parse import quote

    style = quote(json.dumps({"colors": {"date": {"dark": "#010203"}}, "heading": "young"}))
    req = urllib.request.Request(f"{server}/api/convert", data=b"Due Aug 14, 2026.\n", method="POST",
                                 headers={"X-File-Name": "a.md", "X-Style": style})
    html = urllib.request.urlopen(req, timeout=10).read().decode()
    assert "--c-date:#010203" in html and "family=Young+Serif" in html
    bad = urllib.request.Request(f"{server}/api/convert", data=b"x\n", method="POST",
                                 headers={"X-File-Name": "a.md", "X-Style": "%7Bnot json"})
    assert urllib.request.urlopen(bad, timeout=10).status == 200


def test_keep_returns_the_same_kind_of_file(server, fixtures):
    import json
    from urllib.parse import unquote

    for name, magic in (("sample.pdf", b"%PDF"), ("sample.docx", b"PK"), ("sample.xlsx", b"PK")):
        req = urllib.request.Request(f"{server}/api/convert?keep=1", data=(fixtures / name).read_bytes(),
                                     method="POST", headers={"X-File-Name": name})
        r = urllib.request.urlopen(req, timeout=30)
        info = json.loads(unquote(r.headers["X-Overlay"]))
        assert r.read().startswith(magic) and info["count"] > 0 and info["name"].endswith("(colored)" + name[6:])
    # types without a layout of their own still get the styled page
    req = urllib.request.Request(f"{server}/api/convert?keep=1", data=b"Pay $5.\n", method="POST",
                                 headers={"X-File-Name": "a.md"})
    r = urllib.request.urlopen(req, timeout=10)
    assert r.headers.get("X-Overlay") is None and b'data-cat="number"' in r.read()


def test_app_can_be_installed(server):
    import json

    html = urllib.request.urlopen(server + "/", timeout=10).read().decode()
    assert 'rel="manifest"' in html and 'rel="apple-touch-icon"' in html
    r = urllib.request.urlopen(server + "/manifest.webmanifest", timeout=10)
    m = json.loads(r.read())
    assert r.headers["Content-Type"] == "application/manifest+json" and m["display"] == "standalone"
    assert {"192x192", "512x512"} <= {i["sizes"] for i in m["icons"]}
    assert any(i["purpose"] == "maskable" for i in m["icons"])
    assert ".pdf" in m["file_handlers"][0]["accept"]["application/pdf"]
    for i in m["icons"] + [{"src": "/apple-touch-icon.png"}, {"src": "/favicon.ico"}, {"src": "/api/icon-192.png"},
                             {"src": "/api/index?_p=icon-512.png"}]:
        r = urllib.request.urlopen(server + i["src"], timeout=10)
        body = r.read()
        assert r.headers["Content-Type"].startswith("image/") and (body[:4] == b"\x89PNG" or b"<svg" in body)


def test_size_limit_is_per_server():
    srv = make_server("127.0.0.1", 0)
    srv.RequestHandlerClass = make_handler(load_lens(), max_bytes=10)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            post(f"http://127.0.0.1:{srv.server_address[1]}", "a.md", b"# more than ten bytes\n")
        assert e.value.code == 413
    finally:
        srv.shutdown()


def test_vercel_entry_point_imports():
    import importlib.util
    from http.server import BaseHTTPRequestHandler
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "api" / "index.py"
    spec = importlib.util.spec_from_file_location("vercel_index", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert issubclass(mod.handler, BaseHTTPRequestHandler)


def test_path_traversal_name_is_flattened(server):
    r = post(server, "..%2F..%2Fevil.md", b"# hi\n")
    assert r.status == 200
