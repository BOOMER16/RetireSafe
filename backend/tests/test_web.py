"""Web console: served by the API, strict CSP, self-contained assets, recorded-pilot import."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from retiresafe.paths import REPO_ROOT

from conftest import FIX, GEN

WEB = Path(__file__).resolve().parents[1] / "retiresafe" / "web"
PILOT = REPO_ROOT / "pilot" / "results"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("RETIRESAFE_DB", str(tmp_path / "t.db"))
    from retiresafe.api import app as appmod
    appmod._store = None
    return appmod, TestClient(appmod.app)


def test_console_is_served_with_strict_csp(api):
    _, c = api
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/ui/"
    r = c.get("/ui/")
    assert r.status_code == 200 and "RetireSafe Console" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe" not in csp
    assert r.headers["x-frame-options"] == "DENY"
    for asset in ("js/app.js", "js/api.js", "js/util.js", "js/charts.js", "css/app.css", "icon.svg",
                  "fonts/archivo-var.woff2", "fonts/jetbrains-mono-400.woff2", "fonts/jetbrains-mono-700.woff2"):
        assert c.get(f"/ui/{asset}").status_code == 200, asset


def test_assets_make_no_third_party_requests_and_use_no_inline_code():
    for f in WEB.rglob("*"):
        if f.suffix not in (".html", ".js", ".css"):
            continue
        text = f.read_text(encoding="utf-8")
        # every URL the console loads is same-origin; external links are only data shown to the user
        assert not re.search(r"""(src|href)=["']https?://""", text), f
        assert not re.search(r"""@import|url\(\s*["']?https?:""", text), f
        if f.suffix in (".html", ".js"):
            assert not re.search(r"""\son[a-z]+=["']""", text), f"inline event handler in {f.name}"
            assert 'style="' not in text, f"inline style attribute (blocked by CSP) in {f.name}"
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script> would be blocked by CSP"


def test_fonts_are_self_hosted_with_licences():
    css = (WEB / "css" / "app.css").read_text(encoding="utf-8")
    fonts = re.findall(r'url\("\.\./fonts/([^"]+)"\)', css)
    assert len(fonts) == 3
    for f in fonts:
        assert (WEB / "fonts" / f).is_file(), f
    assert (WEB / "fonts" / "OFL-Archivo.txt").is_file() and (WEB / "fonts" / "OFL-JetBrainsMono.txt").is_file()


def test_rendering_escapes_by_default():
    js = (WEB / "js" / "util.js").read_text(encoding="utf-8")
    assert "export const esc" in js and "return esc(v);" in js


def test_no_canned_data_endpoint(api):
    """The console starts empty: there is no endpoint that loads pre-recorded results."""
    _, c = api
    assert c.post("/v1/demo/pilot").status_code in (404, 405)
    assert "pilot_available" not in c.get("/v1/knowledge").json()
    assert c.get("/v1/assessments").json() == []


def test_label_and_several_views_of_one_log(api):
    """config.label names the run; one uploaded log can serve several (host, path prefix) views."""
    _, c = api
    log = (FIX / "nasa_jul95_first2000.log").read_bytes()
    cfg = {"label": "CHG-1 demo", "as_of": "1995-07-01T05:00:00Z",
           "logs": [{"filename": "nasa.log", "format": "clf", "host": "event.retiresafe-pilot.example", "path_prefix": "/shuttle/countdown/"},
                    {"filename": "nasa.log", "format": "clf", "host": "rs-pilot-event-assets-2025.s3.amazonaws.com", "path_prefix": "/images/"}]}
    r = c.post("/v1/assessments", files=[("plan", ("plan.json", (GEN / "plan_before.json").read_bytes())),
                                          ("logs", ("nasa.log", log))], data={"config": json.dumps(cfg)})
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["label"] == "CHG-1 demo"
    sources = {t["source"] for res in rec["resources"] for t in res["traffic"]}
    assert sources == {"nasa.log[/shuttle/countdown/]", "nasa.log[/images/]"}
    assert c.get("/v1/assessments").json()[0]["label"] == "CHG-1 demo"


@pytest.mark.skipif(not (PILOT / "before_balanced.json").is_file(), reason="needs a repository checkout")
def test_recorded_daily_counts_are_consistent():
    """The chart data must add up to the statistics it illustrates."""
    rec = json.loads((PILOT / "before_balanced.json").read_text(encoding="utf-8"))
    log = rec["parse_stats"]["nasa_jul_aug_1995.log"]
    assert sum(log["daily_lines"]) == log["parsed"]
    for r in rec["resources"]:
        for t in r["traffic"]:
            assert sum(t["daily_requests"]) == t["requests"]
            assert len(t["daily_requests"]) == len(log["daily_lines"])
            # a resource cannot have requests on a day the log recorded nothing
            assert all(n == 0 for n, lines in zip(t["daily_requests"], log["daily_lines"]) if lines == 0)
