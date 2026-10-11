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
                assert page.locator("#size").input_value() == "1056x1162"
                page.locator("#zoom").click()
                assert page.locator(".device-stage").evaluate("n=>n.classList.contains('actual')")
                page.locator("#zoom").click()
                page.get_by_role("button", name="Move Weather page up", exact=True).click()
                page.locator(".page-item[data-page=nas] input").uncheck()
                assert page.evaluate("draft.page_order") == ['weather', 'overview', 'markets-1', 'markets-2']
                page.locator("#title").fill("My quiet morning")
                page.locator("#add-widget").select_option("notes")
                page.locator("#add").click()
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
                assert saved['page_order'] == ['weather', 'overview', 'markets-1', 'markets-2']
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
                page.set_viewport_size({"width":1440,"height":1000})
                page.locator("#token").fill("local-editor-test")
                page.locator("#widgets .widget").first.drag_to(page.locator("#widgets .widget").last)
                page.wait_for_function("!document.querySelector('#save').disabled")
                page.locator("#page").select_option("nas")
                page.wait_for_function("document.querySelector('#title').value==='Home server'")
                page.wait_for_function("!document.querySelector('#save').disabled")
                page.locator(".widget[data-id=nas] summary").first.click()
                page.locator("input[data-field=uptime]").check()
                page.locator("#title").fill("Server details")
                page.locator("#save").click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Saved layout preview'")
                saved=json.loads((Path(temp)/"layout.json").read_text())
                assert saved['pages']['nas']['title']=='Server details'
                assert 'uptime' in saved['pages']['nas']['widgets'][0]['fields']
                assert saved['title']=='My quiet morning'
                # Reset applies to this page's arrangement only, and remains a draft.
                page.get_by_role("button", name="Hide Backblaze backup", exact=True).click()
                page.locator('#page-reset').click()
                assert page.locator('.widget[data-id=backup]').count() == 1
                assert page.evaluate('draft.title') == 'My quiet morning'
                assert page.evaluate('draft.page_order') == saved['page_order']
                assert json.loads((Path(temp)/'layout.json').read_text()) == saved
                # Every page cannot be disabled accidentally.
                for name in ('weather', 'markets-1', 'markets-2'):
                    page.locator('.page-item[data-page="'+name+'"] input').uncheck()
                assert page.locator('.page-item[data-page=overview] input').is_disabled()
                page.locator('#discard').click()
                page.wait_for_function("!document.querySelector('#save').disabled")
                page.locator('#add-widget').select_option('markdown')
                page.locator('#add').click()
                markdown=page.locator('.widget[data-id=markdown]').first
                markdown.get_by_label('Markdown',exact=True).fill('# Today\n- **Coffee**\n- Read the notes')
                markdown.get_by_label('Widget title (optional)',exact=True).fill('Daily plan')
                markdown.get_by_label('Row',exact=True).select_option('1')
                markdown.get_by_role('button',name='Duplicate Markdown',exact=True).click()
                assert page.locator('.widget[data-id=markdown]').count()==2
                second=page.locator('.widget[data-id=markdown]').nth(1)
                second.get_by_label('Markdown',exact=True).fill('## Later\nA different note')
                second.get_by_label('Row',exact=True).select_option('1')
                page.locator('#preview-button').click()
                page.wait_for_function("document.querySelector('#message').textContent.includes('overlap')")
                second.get_by_label('Column',exact=True).select_option('2')
                page.locator('#save').click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Saved layout preview'")
                saved=json.loads((Path(temp)/'layout.json').read_text())
                markdowns=[w for w in saved['pages']['nas']['widgets'] if w['id']=='markdown']
                assert len(markdowns)==2 and markdowns[0]['key']!=markdowns[1]['key']
                assert markdowns[0]['column']==1 and markdowns[1]['column']==2
                assert markdowns[0]['content']!=markdowns[1]['content']
                page.locator('#add-widget').select_option('codex')
                page.locator('#add').click()
                usage=page.locator('.widget[data-id=codex]')
                usage.locator('summary').first.click()
                usage.locator('input[data-field=lifetime_tokens]').check()
                page.locator('#save').click()
                page.wait_for_function("document.querySelector('#draft-state').textContent==='Saved layout preview'")
                saved=json.loads((Path(temp)/'layout.json').read_text())
                assert any(w['id']=='codex' and 'lifetime_tokens' in w['fields'] for w in saved['pages']['nas']['widgets'])
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
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
