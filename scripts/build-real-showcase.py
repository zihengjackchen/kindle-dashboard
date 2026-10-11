"""Compose the reviewed real screenshots in a code-drawn Kindle casing.

This does not contact hardware or regenerate data. Inputs are the reviewed PNGs
in docs/showcase/live. The casing is an illustration, not a physical-device photo.
"""
from pathlib import Path
import base64
import os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/showcase/live"

DEVICE_CSS = """
.kindle{position:relative;width:600px;padding:60px 38px 115px;border-radius:26px;
 background:linear-gradient(105deg,#303131,#151616 18%,#1d1e1e 84%,#303131);
 border:2px solid #424343;box-shadow:inset 0 0 0 3px #1b1c1c,inset 0 0 0 5px #353636,
  0 30px 50px #16201735,3px 6px 0 #101111}
.display{overflow:hidden;background:#ecece9;box-shadow:0 0 0 2px #080909,inset 0 0 9px #0008}
.display img{display:block;width:100%;height:auto}
.wordmark{position:absolute;bottom:38px;left:0;right:0;text-align:center;color:#9b9d9b;
 font:38px sans-serif;letter-spacing:-2px;text-shadow:0 1px 1px #000}
"""


def uri(name):
    return "data:image/png;base64," + base64.b64encode((OUT / name).read_bytes()).decode()


def device():
    return f'<div class="kindle"><div class="display"><img src="{uri("kindle-overview.png")}"></div><div class="wordmark">kindle</div></div>'


def main():
    options = {"headless": True}
    if os.getenv("DASHBOARD_TEST_BROWSER"):
        options["executable_path"] = os.environ["DASHBOARD_TEST_BROWSER"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={"width":1800,"height":1050}, device_scale_factor=1)
        page.set_content(f'''<!doctype html><html><meta charset="utf-8"><style>
        *{{box-sizing:border-box}}body{{margin:0;background:#f4f5ef;color:#23332c;font-family:sans-serif}}
        {DEVICE_CSS}.kindle{{position:absolute;right:120px;top:74px}}
        .copy{{position:absolute;left:105px;top:260px;width:780px}}
        .eyebrow{{font-size:21px;letter-spacing:4px;font-weight:700}}
        h1{{font-size:96px;letter-spacing:-5px;line-height:1.05;margin:38px 0 32px}}
        p{{font-size:29px;line-height:1.5;color:#536358;max-width:680px}}
        .rule{{width:130px;height:5px;background:#9aaa91;margin-top:36px}}
        .caption{{position:absolute;bottom:38px;left:105px;font-size:18px;color:#536358}}
        </style><div class="copy"><div class="eyebrow">KINDLE DASHBOARD</div>
        <h1>Your dashboard.<br>On your Kindle.</h1><p>Weather, markets and your home server.<br>A real app. A quieter screen.</p><div class="rule"></div></div>
        {device()}<div class="caption">Actual Kindle screen capture, Oct 10, 2026. Illustrated casing. SSH banner cropped.</div></html>''')
        page.wait_for_function("Array.from(document.images).every(i=>i.complete)")
        page.screenshot(path=str(OUT / "hero.png"))
        page.set_viewport_size({"width":750,"height":1030})
        page.set_content(f'''<!doctype html><html><style>*{{box-sizing:border-box}}body{{margin:0;background:#f4f5ef}}
        {DEVICE_CSS}.kindle{{position:absolute;left:75px;top:65px}}</style>{device()}</html>''')
        page.wait_for_function("Array.from(document.images).every(i=>i.complete)")
        page.screenshot(path=str(OUT / "kindle-frame.png"))
        browser.close()
    print("Built hero and Kindle casing from the reviewed framebuffer capture.")


if __name__ == "__main__":
    main()
