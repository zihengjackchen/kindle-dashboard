/* ES5 for Kindle Mesquite. No remote scripts, animation or persistent connections. */
(function () {
    'use strict';
    var config = window.DASHBOARD, active = true, busy = false, index = 0, timer, noticeTimer, rotate, resizeTimer, battery=null, charging=false, initialized=false, imageWidth=0, imageHeight=0, lastRenderSize='', pages={}, stale=true;
    var settings = {pages: [{id:'overview',name:'Dashboard'},{id:'weather',name:'Weather'},{id:'markets-1',name:'Markets 1'},{id:'markets-2',name:'Markets 2'},{id:'nas',name:'Home server'}],refresh_minutes:60,night_minutes:240,rotation_minutes:0};
    function el(id) { return document.getElementById(id); }
    function message(text) {
        clearTimeout(noticeTimer);
        el('message').textContent=text; el('message').style.display=text?'block':'none';
        if (text) noticeTimer=setTimeout(function(){el('message').style.display='none';},8000);
    }
    function canvasSize() {
        // Mesquite's viewport already excludes native chrome. Measure only
        // the image container; never subtract an assumed native banner height.
        var w=el('screen').clientWidth, h=el('screen').clientHeight;
        // Legacy Mesquite maps CSS pixels to panel pixels but reports a density
        // multiplier (~1.8 on this Paperwhite). Applying it needlessly upsamples.
        var ratio=Math.min(window.kindle ? 1 : (window.devicePixelRatio || 1),2560/w,2560/h);
        return {width:Math.max(320,Math.round(w*ratio)),height:Math.max(320,Math.round(h*ratio))};
    }
    function fitImage() {
        if (!imageWidth || !imageHeight) return;
        var w=el('screen').clientWidth, h=el('screen').clientHeight;
        var scale=Math.min(w/imageWidth,h/imageHeight);
        var drawnWidth=Math.floor(imageWidth*scale), drawnHeight=Math.floor(imageHeight*scale);
        el('image').style.width=drawnWidth+'px'; el('image').style.height=drawnHeight+'px';
        el('image').style.left=Math.floor((w-drawnWidth)/2)+'px';
        el('image').style.top=Math.floor((h-drawnHeight)/2)+'px';
    }
    if (!config || !config.base || !config.key) {
        el('empty').textContent = 'Dashboard session setup is missing. Close and reopen.';
        return;
    }
    function request(action, binary, done) {
        var xhr = new XMLHttpRequest(), finished = false;
        var deadline = setTimeout(function () { xhr.abort(); finish('Bridge unavailable. Close and reopen Dashboard.'); }, 40000);
        function finish(error, value) { if (finished) return; finished = true; clearTimeout(deadline); done(error, value, xhr); }
        xhr.open('POST', config.base + '/cgi-bin/action?' + action, true);
        xhr.setRequestHeader('X-Dashboard-Session', config.key);
        if (binary || action === 'bundle') {
            var canvas=canvasSize();
            xhr.setRequestHeader('X-Dashboard-Viewport',canvas.width+'x'+canvas.height);
            if (action === 'bundle') lastRenderSize=canvas.width+'x'+canvas.height;
            if (binary) xhr.overrideMimeType('text/plain; charset=x-user-defined');
        }
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status !== 200) { finish('Session ended. Close and reopen Dashboard.'); return; }
            if (binary && (xhr.getResponseHeader('Content-Type') || '').indexOf('image/png') === 0) {
                var raw = '', i; for (i=0;i<xhr.responseText.length;i++) raw += String.fromCharCode(xhr.responseText.charCodeAt(i)&255);
                finish(null, 'data:image/png;base64,' + btoa(raw));
            } else {
                try { var value=JSON.parse(xhr.responseText); finish(value.error || null,value); }
                catch (error) { finish('Invalid bridge response'); }
            }
        };
        xhr.send('');
    }
    function schedule() {
        clearTimeout(timer); clearTimeout(rotate);
        if (!active) return;
        var hour = new Date().getHours(), minutes = hour >= 22 || hour < 7 ? settings.night_minutes : settings.refresh_minutes;
        if (battery !== null && battery < 20 && !charging) minutes=Math.max(minutes,settings.night_minutes,240);
        timer=setTimeout(function () { load(true); },Math.max(5,minutes)*60000);
        if (settings.rotation_minutes > 0) rotate=setTimeout(function () { navigate(1); }, Math.max(1,settings.rotation_minutes)*60000);
    }
    function showPage(last) {
        var page=settings.pages[index], image=pages[page.id];
        if (!image) { message('No cached page. Tap Refresh.'); return; }
        if(image.report) {
            el('image').style.display='none';el('empty').style.display='none';
            window.DashboardReport.show(image.report,last);message('');return;
        }
        if(window.DashboardReport)window.DashboardReport.hide();
        imageWidth=image.width; imageHeight=image.height; fitImage();
        el('image').src=image.url; el('image').style.display='inline'; el('empty').style.display='none';
        message('');
    }
    function validateBundle(value, fresh, done) {
        var next={}, seen={}, n=0, list=value && value.settings && value.settings.pages;
        function invalid() { done('Invalid image bundle; previous pages retained'); }
        if (!value || (value.version!==1 && value.version!==2) || !list || !list.length || list.length>32 || !value.images ||
            typeof value.width!=='number' || typeof value.height!=='number' ||
            value.width%1!==0 || value.height%1!==0 ||
            value.width<320 || value.width>2560 || value.height<320 || value.height>2560 ||
            (fresh && value.width+'x'+value.height!==lastRenderSize) ||
            !(value.settings.refresh_minutes>=5 && value.settings.refresh_minutes<=1440) ||
            !(value.settings.night_minutes>=15 && value.settings.night_minutes<=1440) ||
            !(value.settings.rotation_minutes>=0 && value.settings.rotation_minutes<=1440)) { invalid(); return; }
        function decode() {
            if (n===list.length) { done(null,next); return; }
            var page=list[n++], candidate=new Image();
            if (!page || typeof page.id!=='string') { invalid(); return; }
            if(page.id==='finance' && value.version===2) {
                if(seen.finance || typeof page.name!=='string' || !window.DashboardReport){invalid();return;}
                try {next.finance={report:window.DashboardReport.prepare(value.report)};}
                catch(reportError){invalid();return;}
                seen.finance=true;decode();return;
            }
            var data=value.images[page.id];
            if (!/^(overview|weather|markets-1|markets-2|nas|report-([1-9]|1[0-9]|2[0-7]))$/.test(page.id) || seen[page.id] ||
                typeof page.name!=='string' || typeof data!=='string' || data.length>8388608 ||
                data.slice(0,11)!=='iVBORw0KGgo') { invalid(); return; }
            seen[page.id]=true;
            candidate.onload=function () {
                if (candidate.width!==value.width || candidate.height!==value.height) { invalid(); return; }
                next[page.id]={url:'data:image/png;base64,'+data,width:candidate.width,height:candidate.height};
                decode();
            };
            candidate.onerror=invalid;
            candidate.src='data:image/png;base64,'+data;
        }
        decode();
    }
    function legacyFallback(done) {
        request('cached='+settings.pages[index].id,true,function(error,url) {
            if (error || !active) { done(); return; }
            var image=new Image();
            image.onload=function () {
                if (active) { pages[settings.pages[index].id]={url:url,width:image.width,height:image.height}; showPage(); }
                done();
            };
            image.onerror=done; image.src=url;
        });
    }
    function load(fetch) {
        if (busy || !active) return;
        busy=true;
        el('refresh').textContent=fetch?'Refreshing...':'Loading...'; el('refresh').disabled=true;
        request(fetch?'bundle':'cached-bundle',false,function(error,value,xhr) {
            if (!active) { busy=false; return; }
            function finish(error) {
                busy=false; el('refresh').textContent='Refresh'; el('refresh').disabled=false;
                if (error) { stale=true; message(error); }
                if (!fetch) load(true); else schedule();
            }
            if (error) {
                if (!fetch) { legacyFallback(function(){finish(error);}); return; }
                finish(error); return;
            }
            var revision=xhr.getResponseHeader('X-Dashboard-Revision');
            validateBundle(value,!!revision,function(error,next) {
                if (!active) { busy=false; return; }
                if (error) { finish(error); return; }
                function install(error) {
                    if (!active) { busy=false; return; }
                    if (error) { finish(error); return; }
                    var selected=settings.pages[index].id, j;
                    settings=value.settings; pages=next; index=0;
                    for(j=0;j<settings.pages.length;j++) if(settings.pages[j].id===selected) index=j;
                    battery=value.battery; charging=!!value.charging;
                    stale=!fetch || xhr.getResponseHeader('X-Dashboard-Stale')==='1';
                    showPage();
                    if (fetch && stale) message('Offline. Showing saved dashboards.');
                    finish(null);
                }
                // The shell atomically commits the entire bundle only after every
                // PNG decoded. A damaged page never replaces any working page.
                if (revision) request('commit-bundle='+revision,false,install);
                else install(null);
            });
        });
    }
    function navigate(delta) {
        if(!(settings.pages[index].id==='finance' && window.DashboardReport.step(delta))) {
            index=(index+delta+settings.pages.length)%settings.pages.length;
            if(settings.pages[index].id==='finance')window.DashboardReport.reset();
            showPage(delta<0 && settings.pages[index].id==='finance');
        }
        // Page navigation is entirely local and does not postpone refresh.
        clearTimeout(rotate);
        if (active && settings.rotation_minutes>0) rotate=setTimeout(function(){navigate(1);},Math.max(1,settings.rotation_minutes)*60000);
    }
    function pause() { active=false; clearTimeout(timer); clearTimeout(rotate); clearTimeout(resizeTimer); }
    function enter() {
        var resumed=!active;
        active=true;
        request('enter',false,function () {});


        schedule();
        if (resumed && initialized) load(false);
    }
    el('previous').onclick=function () {navigate(-1);}; el('next').onclick=function () {navigate(1);};
    el('refresh').onclick=function () {load(true);};
    if (window.kindle && window.kindle.appmgr) {
        window.kindle.appmgr.ongo=function () {
            window.kindle.messaging.sendMessage('com.lab126.chromebar','configureChrome',{appId:'org.kindledashboard.app',topNavBar:{template:'title',title:'Dashboard',buttons:[{id:'KPP_CLOSE',state:'enabled',handling:'system'}]}});
            enter();
        };
        window.kindle.appmgr.onpause=pause;
        window.kindle.appmgr.onstop=pause;
    }
    window.onunload=pause;
    window.onresize=function () {
        fitImage(); clearTimeout(resizeTimer);
        if(settings.pages[index].id==='finance' && window.DashboardReport)window.DashboardReport.layout();
        resizeTimer=setTimeout(function resized() {
            if (!active) return;
            if (busy) {resizeTimer=setTimeout(resized,500);return;}
            var canvas=canvasSize();
            if (lastRenderSize!==canvas.width+'x'+canvas.height) load(true);
        },300);
    };
    document.addEventListener('visibilitychange',function(){if(document.hidden)pause();else enter();});
    enter();
    initialized=true;
    load(false);
}());
