"""Browser contract tests for app navigation, decoding, timers and lifecycle.

Uses a mocked local CGI service, not Kindle hardware. Shell CGI has separate tests.
"""
import json
import os
from pathlib import Path
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'kindle-client/extensions/dashboard/app'


def main():
    calls=[]
    session_available=[True]
    requested_sizes=[]
    out=BytesIO(); Image.new('L',(600,800),240).save(out,format='PNG'); png=out.getvalue()
    with sync_playwright() as pw:
        options={'headless':True}
        if os.getenv('DASHBOARD_TEST_BROWSER'): options['executable_path']=os.environ['DASHBOARD_TEST_BROWSER']
        browser=pw.chromium.launch(**options)
        page=browser.new_page(viewport={'width':600,'height':800})
        page.clock.install()
        errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        def route(request):
            path=request.request.url.split('http://kindle.test',1)[1]
            if path.startswith('/cgi-bin/action?'):
                action=path.split('?',1)[1];calls.append(action)
                assert request.request.headers.get('x-dashboard-session')=='test'
                if action=='settings':
                    request.fulfill(json={'pages':[{'id':'overview','name':'Overview'},{'id':'nas','name':'Server'}],
                                          'refresh_minutes':5,'night_minutes':15,'rotation_minutes':0})
                elif action.startswith(('fetch=','cached=')):
                    size=tuple(map(int,request.request.headers['x-dashboard-viewport'].split('x')))
                    requested_sizes.append(size)
                    # Old cache can have a different aspect ratio. Fresh images
                    # must use the canvas dimensions requested by the browser.
                    payload=png
                    if action.startswith('fetch='):
                        rendered=BytesIO();Image.new('L',size,240).save(rendered,format='PNG');payload=rendered.getvalue()
                    request.fulfill(body=payload,headers={'Content-Type':'image/png','X-Dashboard-Revision':'3000000000','X-Dashboard-Battery':'90'})
                else: request.fulfill(json={'ok':True})
            elif path=='/session.js': request.fulfill(body='window.DASHBOARD={base:"http://kindle.test",key:"test"}' if session_available[0] else '',content_type='application/javascript')
            else:
                name='index.html' if path=='/' else path[1:]
                request.fulfill(body=(APP/name).read_text(encoding='utf-8'),content_type='application/javascript' if name.endswith('.js') else 'text/html')
        page.route('http://kindle.test/**',route)
        page.add_init_script('window.kindle={appmgr:{},messaging:{sendMessage:function(){}}}')
        page.goto('http://kindle.test/')
        page.locator('#image').wait_for(state='visible')
        page.wait_for_function("document.querySelector('#message').textContent==='Overview'")
        page.wait_for_timeout(300)
        assert 'fetch=overview' in calls and 'commit=overview:3000000000' in calls
        assert page.locator('#image').bounding_box()['height'] < 800
        assert requested_sizes[-1] == (584,686)
        def assert_fills_canvas():
            canvas=page.locator('#screen').bounding_box(); drawn=page.locator('#image').bounding_box()
            for k in ('x','y','width','height'): assert abs(canvas[k]-drawn[k])<=1,(canvas,drawn)
            assert drawn['y']+drawn['height'] < page.locator('#controls').bounding_box()['y']
            status=page.locator('#message').bounding_box(); controls=page.locator('#controls').bounding_box()
            assert status['y']+status['height'] < controls['y']
        assert_fills_canvas()
        page.locator('#next').click()
        page.wait_for_function("document.querySelector('#message').textContent==='Server'")
        page.wait_for_timeout(300)
        assert 'fetch=nas' in calls
        page.set_viewport_size({'width':800,'height':600})
        page.clock.fast_forward(1000)
        page.wait_for_function("document.querySelector('#image').naturalWidth===784")
        assert requested_sizes[-1] == (784,486)
        assert_fills_canvas()
        page.evaluate('Object.defineProperty(window,"devicePixelRatio",{value:2,configurable:true})')
        page.set_viewport_size({'width':640,'height':900})
        page.clock.fast_forward(1000)
        page.wait_for_function("document.querySelector('#image').naturalWidth===624")
        assert requested_sizes[-1] == (624,786)  # Mesquite density must not upsample.
        assert_fills_canvas()
        count=calls.count('fetch=nas')
        page.clock.fast_forward(16*60000)
        page.wait_for_timeout(500)
        assert calls.count('fetch=nas')>count
        page.evaluate('window.kindle.appmgr.onpause()')
        count=len(calls); page.clock.fast_forward(16*60000); page.wait_for_timeout(100)
        assert len(calls)==count
        page.evaluate('window.kindle.appmgr.ongo()')
        page.locator('#close').click()
        page.wait_for_function("document.querySelector('#message').textContent==='Closed'")
        assert 'close' in calls and calls.count('enter')>=2
        assert not errors, errors
        folder=ROOT/'.tools/app-tests';folder.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(folder/'app.png'))
        # Old Mesquite may resolve session.js from the native app directory.
        # A missing bootstrap must produce a visible error, not an exception.
        session_available[0]=False
        page.reload()
        assert 'session setup is missing' in page.locator('#empty').inner_text()
        assert not errors, errors
        browser.close()
    print('Kindle app browser checks passed: entry, image decode/commit, navigation, auto refresh, pause/resume, Close.')


if __name__=='__main__': main()
