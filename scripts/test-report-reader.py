"""Exercise the real ES5 app, Markdown DOM, pagination and offline navigation."""
import base64
from io import BytesIO
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'kindle-client/extensions/dashboard/app'
source = '# Finance\n\n' + ('**Keep this condition.** Text with *emphasis*, `code`, and [a link](https://example.invalid).\n\n' * 65)
source += '<img src="https://example.invalid/tracker" onerror="window.pwned=1">\n\n![No image request](https://example.invalid/image)\n\nEND OF REPORT'


def main():
    calls, errors = [], []
    malformed = [False]
    with sync_playwright() as pw:
        options = {'headless': True}
        if os.getenv('DASHBOARD_TEST_BROWSER'):
            options['executable_path'] = os.environ['DASHBOARD_TEST_BROWSER']
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={'width':1072,'height':1232})
        page.add_init_script("window.kindle={appmgr:{},messaging:{sendMessage:function(){}}};window.__Map=window.Map;window.Map=undefined;String.fromCodePoint=undefined;document.addEventListener('DOMContentLoaded',function(){window.Map=window.__Map;});")
        page.on('pageerror', lambda e: errors.append(str(e)))
        def route(request):
            url=request.request.url
            assert url.startswith('http://kindle.test/'), url
            path=url.split('http://kindle.test',1)[1]
            if path.startswith('/cgi-bin/action?'):
                action=path.split('?',1)[1];calls.append(action)
                if action=='cached-bundle':
                    request.fulfill(json={'error':'No saved data'})
                elif action=='bundle':
                    width,height=map(int,request.request.headers['x-dashboard-viewport'].split('x'))
                    out=BytesIO();Image.new('L',(width,height),240).save(out,format='PNG')
                    request.fulfill(json={'version':2,'width':width,'height':height,
                        'settings':{'pages':[{'id':'overview','name':'Main'},{'id':'finance','name':'Finance'}],
                                    'refresh_minutes':60,'night_minutes':240,'rotation_minutes':0},
                        'images':{'overview':base64.b64encode(out.getvalue()).decode()},
                        'report':{'day':'2026-11-02','font_size':30,'markdown':None if malformed[0] else source}},
                        headers={'X-Dashboard-Revision':'1234'})
                elif action.startswith('cached='):request.fulfill(json={'error':'No image'})
                else:request.fulfill(json={'ok':True})
            elif path=='/session.js':request.fulfill(body='window.DASHBOARD={base:"http://kindle.test",key:"test"}',content_type='application/javascript')
            else:
                name='index.html' if path=='/' else path[1:]
                request.fulfill(body=(APP/name).read_text(encoding='utf-8'),content_type='application/javascript' if name.endswith('.js') else 'text/html')
        page.route('**/*',route)
        page.goto('http://kindle.test/')
        page.wait_for_function("!document.getElementById('refresh').disabled")
        assert 'commit-bundle=1234' in calls
        count=len(calls)
        page.locator('#next').click()
        assert page.locator('#report').is_visible()
        assert page.locator('#report-content strong').count()==65
        assert page.locator('#report-content img, #report-content script, #report-content a').count()==0
        assert page.evaluate('window.pwned') is None
        assert 'END OF REPORT' in page.locator('#report-content').text_content()
        first_count=int(page.locator('#report-position').inner_text().split('/')[1])
        assert first_count>1
        page.locator('#next').click()
        assert page.locator('#report-position').inner_text().startswith('2 /')
        page.locator('#text-larger').click()
        assert int(page.evaluate("localStorage.getItem('dashboard-report-size')"))==32
        total=int(page.locator('#report-position').inner_text().split('/')[1])
        assert total>=first_count
        page.locator('#previous').click()
        while page.locator('#report').is_visible():page.locator('#previous').click()
        assert page.locator('#image').is_visible()
        assert len(calls)==count, 'Paging and text resizing must not fetch'
        page.locator('#next').click()
        total=int(page.locator('#report-position').inner_text().split('/')[1])
        for _ in range(total-1):page.locator('#next').click()
        assert page.locator('#report-position').inner_text().startswith(str(total)+' /')
        # Final text actually occupies the visible final column, not clipped or lost.
        assert page.locator('#report-content').evaluate("e=>{var r=document.createRange();r.selectNodeContents(e.lastChild);var a=r.getBoundingClientRect(),b=document.getElementById('report-window').getBoundingClientRect();return a.left>=b.left-2&&a.right<=b.right+2;}")
        malformed[0]=True
        commits=calls.count('commit-bundle=1234')
        page.locator('#refresh').click()
        page.wait_for_function("document.getElementById('message').textContent.indexOf('Invalid image bundle')===0")
        assert calls.count('commit-bundle=1234')==commits
        assert page.locator('#report').is_visible()
        assert not errors, errors
        browser.close()
    print('Markdown client checks passed: ES5 helpers, safe DOM, complete pages, font resizing, local navigation, malformed cache retention.')


if __name__=='__main__':main()
