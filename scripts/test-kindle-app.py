"""Browser contract tests for app navigation, decoding, timers and lifecycle.

Uses a mocked local CGI service, not Kindle hardware. Shell CGI has separate tests.
"""
import json
import base64
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
    corrupt=[False]
    offline=[False]
    saved=[None]
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
                if action in ('bundle','cached-bundle'):
                    if action=='cached-bundle' or offline[0]:
                        if saved[0]: request.fulfill(json=saved[0],headers={'X-Dashboard-Stale':'1'})
                        else: request.fulfill(json={'error':'No cached bundle'})
                        return
                    size=tuple(map(int,request.request.headers['x-dashboard-viewport'].split('x')))
                    requested_sizes.append(size)
                    rendered=BytesIO();Image.new('L',size,240).save(rendered,format='PNG')
                    encoded=base64.b64encode(rendered.getvalue()).decode()
                    value={'version':1,'width':size[0],'height':size[1],'battery':90,'charging':False,
                           'settings':{'pages':[{'id':'overview','name':'Overview'},{'id':'nas','name':'Server'}],
                                       'refresh_minutes':5,'night_minutes':15,'rotation_minutes':0},
                           'images':{'overview':encoded,'nas':encoded}}
                    for report in range(1,7):
                        key='report-'+str(report)
                        value['settings']['pages'].append({'id':key,'name':'Stock update '+str(report)})
                        value['images'][key]='iVBORw0KGgoBROKEN' if corrupt[0] and report==6 else encoded
                    if not corrupt[0]: saved[0]=value
                    request.fulfill(json=value,headers={'X-Dashboard-Revision':'3000000000'})
                elif action.startswith('cached='):
                    request.fulfill(body=png,headers={'Content-Type':'image/png'})
                else: request.fulfill(json={'ok':True})
            elif path=='/session.js': request.fulfill(body='window.DASHBOARD={base:"http://kindle.test",key:"test"}' if session_available[0] else '',content_type='application/javascript')
            else:
                name='index.html' if path=='/' else path[1:]
                request.fulfill(body=(APP/name).read_text(encoding='utf-8'),content_type='application/javascript' if name.endswith('.js') else 'text/html')
        page.route('http://kindle.test/**',route)
        page.add_init_script('window.kindle={appmgr:{},messaging:{sendMessage:function(){}}}')
        page.goto('http://kindle.test/')
        page.locator('#image').wait_for(state='visible')
        page.wait_for_function("document.querySelector('#refresh').textContent==='Refresh' && !document.querySelector('#refresh').disabled")
        page.wait_for_timeout(300)
        assert calls.count('bundle')==1 and 'commit-bundle=3000000000' in calls
        assert page.locator('#close').count()==0
        assert page.locator('#image').bounding_box()['height'] < 800
        assert requested_sizes[-1] == (584,730)
        def assert_fills_canvas():
            canvas=page.locator('#screen').bounding_box(); drawn=page.locator('#image').bounding_box()
            for k in ('x','y','width','height'): assert abs(canvas[k]-drawn[k])<=1,(canvas,drawn)
            assert page.locator('#controls').bounding_box()['y'] < drawn['y']
            assert not page.locator('#message').is_visible()
        assert_fills_canvas()
        count=len(calls)
        page.locator('#next').click()
        page.wait_for_function("document.querySelector('#refresh').textContent==='Refresh' && !document.querySelector('#refresh').disabled")
        page.wait_for_timeout(300)
        assert len(calls)==count  # Navigation makes no bridge or NAS requests.
        for _ in range(7): page.locator('#next').click()
        assert len(calls)==count  # Six report pages also navigate entirely offline.
        page.set_viewport_size({'width':800,'height':600})
        page.clock.fast_forward(1000)
        page.wait_for_function("document.querySelector('#image').naturalWidth===784")
        assert requested_sizes[-1] == (784,530)
        assert_fills_canvas()
        page.evaluate('Object.defineProperty(window,"devicePixelRatio",{value:2,configurable:true})')
        page.set_viewport_size({'width':640,'height':900})
        page.clock.fast_forward(1000)
        page.wait_for_function("document.querySelector('#image').naturalWidth===624")
        assert requested_sizes[-1] == (624,830)  # Mesquite density must not upsample.
        assert_fills_canvas()
        count=calls.count('bundle')
        page.clock.fast_forward(16*60000)
        page.wait_for_timeout(500)
        assert calls.count('bundle')>count
        page.evaluate('window.kindle.appmgr.onpause()')
        count=len(calls); page.clock.fast_forward(16*60000); page.wait_for_timeout(100)
        assert len(calls)==count
        page.evaluate('window.kindle.appmgr.ongo()')
        page.wait_for_function("document.querySelector('#refresh').textContent==='Refresh' && !document.querySelector('#refresh').disabled")
        # A corrupt page must prevent the entire bundle from being committed.
        page.wait_for_timeout(500)
        previous=page.locator('#image').get_attribute('src')
        count=calls.count('commit-bundle=3000000000'); corrupt[0]=True
        page.locator('#refresh').click()
        page.wait_for_function("document.querySelector('#message').textContent.indexOf('Invalid image bundle')===0")
        assert calls.count('commit-bundle=3000000000')==count
        assert page.locator('#image').get_attribute('src')==previous
        corrupt[0]=False;offline[0]=True
        page.locator('#refresh').click()
        page.wait_for_function("document.querySelector('#message').textContent.indexOf('Offline')===0")
        count=len(calls);page.locator('#previous').click()
        assert len(calls)==count
        assert calls.count('enter')>=2
        assert 'heartbeat' not in calls
        page.clock.fast_forward(9000)
        assert not page.locator('#message').is_visible()
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
    print('Kindle app browser checks passed: entry, image decode/commit, local navigation, bundle validation, offline retention, auto refresh, pause/resume.')


if __name__=='__main__': main()
