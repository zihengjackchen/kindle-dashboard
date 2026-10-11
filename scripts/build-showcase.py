"""Rebuild public screenshots from synthetic data, with no NAS/account access.

Requires server dev dependencies plus Playwright. DASHBOARD_TEST_BROWSER can point
to Edge/Chromium. Run from any directory; output is docs/showcase/.
"""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from app.config import Settings
from app.layout import Layout, Widget
from app.models import DashboardRequest
from app.renderer import render_dashboard
from app.snapshots import Snapshot
from demo_snapshot import demo_snapshot
from playwright.sync_api import sync_playwright

OUT = ROOT / "docs/showcase"
NOW = datetime(2026, 10, 1, 16, 41, tzinfo=timezone.utc)


def examples():
    fixture = demo_snapshot().model_dump(mode="json")
    fixture["nas"]["metrics"].update(pool_free_gib=3040, pool_size_gib=8000,
        memory_total_gib=32, cpu_temperature_c=42, network_rx_mbps=12.4,
        network_tx_mbps=3.2, apps_running=8, scrub_state="FINISHED", disk_count=4)
    fixture["codex"] = dict(source="Codex account", as_of="2026-10-01T16:35:00Z",
        valid_until="2026-10-01T18:35:00Z", primary=dict(used_percent=28,
        window_minutes=10080, resets_at="2026-10-06T16:00:00Z"),
        latest_day="2026-10-01", latest_day_tokens=125000, lifetime_tokens=4200000,
        current_streak_days=12, longest_streak_days=24)
    snapshot = Snapshot.model_validate(fixture)
    W = Widget
    layouts = {
        "overview": Layout(),
        "weather": Layout(widgets=[W(id="weather", width="full", size="large"),
            W(id="notes", width="full", title="Out the door", notes=["Light jacket for the morning", "Take the scenic route", "Sunset walk at 6:45"])]),
        "markets": Layout(market_columns=3, widgets=[W(id="markets", width="full", size="large"),
            W(id="markdown", width="full", size="small", title="Research notebook",
              content="**Watch, then decide.**\n- Review allocation at the end of the month.\n- Keep a separate emergency fund.")]),
        "home-server": Layout(widgets=[W(id="nas", width="full", size="large", fields=["pool_health","used_percent","pool_free_gib","cpu_percent","cpu_temperature_c","memory_available_gib","network_rx_mbps","network_tx_mbps","apps_running","alerts","uptime","scrub_state"]),
            W(id="backup", width="full", fields=["name","state","last_success","duration","schedule"]),
            W(id="device", width="full", size="small", fields=["battery","charging","rssi","frontlight"])]),
        "markdown": Layout(widgets=[W(id="markdown", width="full", size="large", title="A slower Sunday",
            content="# Make room for the good stuff\nA small plan for a **quiet weekend**.\n\n## Morning\n- Coffee, then a walk by the water\n- Read one chapter\n- Call someone you miss\n\n## One useful thing\nBack up the photos. Put the phone away.\n\n> Leave a little room for nothing.\n\n`Next refresh: whenever you need it.`"),
            W(id="weather", size="small", fields=["temperature","condition"]),
            W(id="notes", size="small", title="Bring along", notes=["Book + notebook", "Water + a warm layer"])]),
        "codex": Layout(widgets=[W(id="codex", width="full", size="large", fields=["primary_remaining","primary_reset","latest_day_tokens","lifetime_tokens","current_streak_days","longest_streak_days"]),
            W(id="markdown", width="full", title="Today's build", content="## Small steps, shipped\n- Finish the dashboard layout\n- Review the tests\n- Write down what changed\n\n**Account usage stays on your NAS.**")]),
    }
    return snapshot, layouts


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot, layouts = examples()
    font = os.getenv("DASHBOARD_FONT_PATH", "")
    if not font and Path("C:/Windows/Fonts/arial.ttf").exists():
        font = "C:/Windows/Fonts/arial.ttf"
    settings = Settings(timezone="America/Los_Angeles", font_path=font)
    data = DashboardRequest(width=1056, height=1162, battery=73, charging=True,
        device="paperwhite", rssi=-48, frontlight=0, storage_free_mib=2800,
        firmware="5.16.2.1.1", uptime_seconds=86400, external_power=True)
    for name, layout in layouts.items():
        (OUT / f"{name}.png").write_bytes(render_dashboard(data, settings, NOW, snapshot, layout))
        (OUT / f"{name}.json").write_text(layout.model_dump_json(indent=2), encoding="utf-8")
    # Retain original source dates: a stale screenshot demonstrates the real warning.
    (OUT / "stale.png").write_bytes(render_dashboard(data, settings,
        datetime(2026, 10, 2, 16, 41, tzinfo=timezone.utc), snapshot, layouts["overview"]))
    (OUT / "sample-snapshot.json").write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="dashboard-showcase-") as tmp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        # Freshness in the browser is relative to real time; the sample marker stays visible.
        browser_snapshot = snapshot.model_dump(mode="json")
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        for record in [browser_snapshot["weather"], browser_snapshot["nas"], browser_snapshot["codex"], *browser_snapshot["quotes"]]:
            record["as_of"] = now.isoformat(); record["valid_until"] = (now + timedelta(hours=2)).isoformat()
        Path(tmp, "snapshot.json").write_text(json.dumps(browser_snapshot), encoding="utf-8")
        env = dict(os.environ, API_TOKEN="public-demo-only", DASHBOARD_FONT_PATH=font,
            DASHBOARD_TIMEZONE="America/Los_Angeles", CODEX_USAGE_PATH="",
            DASHBOARD_SNAPSHOT_PATH=str(Path(tmp, "snapshot.json")),
            DASHBOARD_LAYOUT_PATH=str(Path(tmp, "layout.json")), DASHBOARD_STATE_PATH=str(Path(tmp, "contacts.json")))
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "server", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(80):
                try:
                    urllib.request.urlopen(base + "/health", timeout=1).close(); break
                except OSError: time.sleep(.2)
            else: raise RuntimeError("Showcase server failed to start")
            with sync_playwright() as pw:
                options = {"headless": True}
                if os.getenv("DASHBOARD_TEST_BROWSER"): options["executable_path"] = os.environ["DASHBOARD_TEST_BROWSER"]
                browser = pw.chromium.launch(**options)
                page = browser.new_page(viewport={"width":1600, "height":1100}, device_scale_factor=1)
                page.goto(base); page.locator("#token").fill("public-demo-only"); page.locator("#connect").click()
                page.locator("#preview").wait_for(state="visible")
                page.wait_for_function("document.querySelector('#preview').complete && document.querySelector('#preview').naturalWidth > 0")
                page.locator("#token").fill("")
                page.screenshot(path=str(OUT / "editor-desktop.png"))
                page.locator(".controls").evaluate("e => e.scrollTop = document.querySelector('#widgets').offsetTop - e.offsetTop - 45")
                page.screenshot(path=str(OUT / "editor-widgets.png"))
                page.set_viewport_size({"width":390,"height":844})
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=str(OUT / "editor-mobile.png"))
                # Actual client HTML and JS with a synthetic local CGI, not a hardware screenshot.
                app = ROOT / "kindle-client/extensions/dashboard/app"
                names = ["overview", "weather", "markets", "home-server", "markdown"]
                ids = ["overview", "weather", "markets-1", "nas", "markets-2"]
                def route(r):
                    path = r.request.url.split("http://kindle.test",1)[1]
                    if path.startswith('/cgi-bin/action?'):
                        action=path.split('?',1)[1]
                        if action in ('bundle','cached-bundle'):
                            r.fulfill(json={"version":1,"width":1056,"height":1162,"battery":73,"charging":True,
                                "settings":{"pages":[{"id":i,"name":n} for i,n in zip(ids,names)],"refresh_minutes":60,"night_minutes":240,"rotation_minutes":0},
                                "images":{i:base64.b64encode((OUT/f'{n}.png').read_bytes()).decode() for i,n in zip(ids,names)}}, headers={"X-Dashboard-Revision":"3000000000"})
                        else: r.fulfill(json={"ok":True})
                    elif path=='/session.js': r.fulfill(body='window.DASHBOARD={base:"http://kindle.test",key:"demo"}',content_type='application/javascript')
                    else:
                        name='index.html' if path=='/' else path[1:]
                        r.fulfill(body=(app/name).read_text(encoding='utf-8'),content_type='application/javascript' if name.endswith('.js') else 'text/html')
                native = browser.new_page(viewport={"width":1072,"height":1232})
                native.route('http://kindle.test/**',route)
                native.goto('http://kindle.test/')
                native.locator('#image').wait_for(state='visible')
                native.wait_for_function("document.querySelector('#refresh').textContent==='Refresh' && !document.querySelector('#refresh').disabled")
                native.screenshot(path=str(OUT / "kindle-app.png"))
                # Hero uses real rendered images, placed in a designed web composition.
                hero = browser.new_page(viewport={"width":1800,"height":1000})
                src = lambda n: 'data:image/png;base64,' + base64.b64encode((OUT/f'{n}.png').read_bytes()).decode()
                hero.set_content('''<html><style>*{box-sizing:border-box}body{margin:0;background:#f4f5ef;color:#23332c;font-family:Arial,sans-serif}.copy{position:absolute;left:100px;top:195px;width:640px}.eyebrow{font-size:20px;letter-spacing:5px}h1{font-size:98px;line-height:1.04;letter-spacing:-5px;margin:35px 0}p{font-size:28px;line-height:1.5;color:#627268;width:570px}.pill{display:inline-block;margin:22px 10px 0 0;padding:13px 20px;border:1px solid #bcc6b9;border-radius:30px;font-size:18px}.device{position:absolute;left:830px;top:65px;width:650px;background:#252c28;border-radius:40px;padding:28px 20px 60px;box-shadow:0 30px 65px #23332c25}.device img{width:100%;border-radius:5px}.mini{position:absolute;left:1410px;top:330px;width:310px;background:white;padding:12px;box-shadow:0 15px 45px #23332c25;transform:rotate(5deg)}.mini img{width:100%}.foot{position:absolute;bottom:40px;left:100px;font-size:17px;color:#627268}</style><div class=copy><div class=eyebrow>KINDLE DASHBOARD</div><h1>A quieter place<br>for your day.</h1><p>Weather. Markets. Your home server.<br>Arrange it in a browser. Read it on e-ink.</p><span class=pill>Self-hosted</span><span class=pill>Customizable</span><span class=pill>Cached offline</span></div><div class=device><img src="'''+src('overview')+'''"></div><div class=mini><img src="'''+src('markdown')+'''"></div><div class=foot>Actual renderer output · Sample data · Device frame is an illustration</div></html>''')
                hero.wait_for_function("Array.from(document.images).every(i=>i.complete)")
                hero.screenshot(path=str(OUT / "hero.png"))
                browser.close()
        finally:
            process.terminate(); process.wait(timeout=10)
    print(f"Generated 12 public images and 6 importable layouts in {OUT}")


if __name__ == "__main__": main()
