import threading
import urllib.error
import urllib.request

import pytest

from synesthetic.serve import make_server


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


def test_path_traversal_name_is_flattened(server):
    r = post(server, "..%2F..%2Fevil.md", b"# hi\n")
    assert r.status == 200
