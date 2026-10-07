"""Optional real-browser smoke test: pip install playwright; playwright install chromium.

Uses an isolated local server and temporary preferences, never the NAS or Kindle.
Set DASHBOARD_TEST_BROWSER to a browser executable to use an installed browser.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="daylight-editor-") as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, API_TOKEN="local-editor-test", DASHBOARD_LAYOUT_PATH=str(Path(temp)/"layout.json"),
                   DASHBOARD_STATE_PATH=str(Path(temp)/"contacts.json"),
                   DASHBOARD_SNAPSHOT_PATH=str(ROOT/"docs/previews/sample-snapshot.json"))
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "server",
                                    "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                                   cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(base+"/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError("Local test server did not start")
            with sync_playwright() as pw:
                options = {"headless": True}
                if os.getenv("DASHBOARD_TEST_BROWSER"):
                    options["executable_path"] = os.environ["DASHBOARD_TEST_BROWSER"]
                browser = pw.chromium.launch(**options)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                page.locator("#token").fill("wrong-token")
                page.locator("#connect").click()
                page.wait_for_function("document.querySelector('#message').textContent.includes('Token rejected')")
                page.locator("#token").fill("local-editor-test")
                page.locator("#connect").click()
                page.locator("#preview").wait_for(state="visible")
                page.wait_for_function("!document.querySelector('#save').disabled")
                assert page.locator("#widgets .widget").count() == 5
                assert page.locator("#tickers input:checked").count() == 12
                page.locator("#title").fill("My quiet morning")
                page.locator("#notes").fill("Coffee at 8:00\nReview the week")
                page.get_by_role("button", name="Hide Home server", exact=True).click()
                page.get_by_role("button", name="Move Watchlist up", exact=True).click()
                page.locator("#tickers input[value='GOOG']").uncheck()
                page.locator("#preview-button").click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Draft preview'")
                assert not (Path(temp)/"layout.json").exists()
                page.locator("#save").click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Saved layout preview'")
                saved = json.loads((Path(temp)/"layout.json").read_text())
                assert saved["title"] == "My quiet morning"
                assert saved["widgets"][0]["id"] == "markets"
                assert "GOOG" not in saved["tickers"]
                assert not (Path(temp)/"contacts.json").exists()
                with page.expect_download() as download:
                    page.locator("#export").click()
                exported = Path(temp)/"exported.json"
                download.value.save_as(exported)
                assert "local-editor-test" not in exported.read_text()
                imported = json.loads(exported.read_text())
                imported["tickers"].reverse()
                exported.write_text(json.dumps(imported))
                page.locator("#reset").click()
                page.locator("#import-file").set_input_files(exported)
                page.wait_for_function("document.querySelector('#message').textContent.includes('Layout imported')")
                assert page.locator("#title").input_value() == "My quiet morning"
                page.locator("#save").click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Saved layout preview'")
                page.reload()
                page.locator("#token").fill("local-editor-test")
                page.locator("#connect").click()
                page.locator("#preview").wait_for(state="visible")
                assert page.locator("#title").input_value() == "My quiet morning"
                assert page.evaluate("draft.tickers") == imported["tickers"]
                page.locator("#token").fill("")
                out = ROOT/".tools/editor-tests"
                out.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out/"desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(out/"mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print("Editor browser checks passed: auth, reorder/hide, tickers, preview, save, export/import, reload, mobile.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
