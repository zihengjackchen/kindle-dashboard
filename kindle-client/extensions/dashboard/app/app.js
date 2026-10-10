/* ES5 for Kindle Mesquite. No remote scripts, animation or persistent connections. */
(function () {
    'use strict';
    var config = window.DASHBOARD, active = true, busy = false, index = 0, timer, heartbeat, rotate, resizeTimer, battery=null, charging=false, initialized=false, imageWidth=0, imageHeight=0, lastRenderSize='';
    var settings = {pages: [{id:'overview',name:'Dashboard'},{id:'weather',name:'Weather'},{id:'markets-1',name:'Markets 1'},{id:'markets-2',name:'Markets 2'},{id:'nas',name:'Home server'}],refresh_minutes:60,night_minutes:240,rotation_minutes:0};
    function el(id) { return document.getElementById(id); }
    function message(text) { el('message').textContent = text; }
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
        if (binary) {
            var canvas=canvasSize();
            xhr.setRequestHeader('X-Dashboard-Viewport',canvas.width+'x'+canvas.height);
            if (action.indexOf('fetch=')===0) lastRenderSize=canvas.width+'x'+canvas.height;
            xhr.overrideMimeType('text/plain; charset=x-user-defined');
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
    function load(fetch) {
        if (busy || !active) return;
        busy=true;
        var page=settings.pages[index], wasActive=active;
        message(fetch ? 'Updating…' : page.name);
        function download() { request((fetch?'fetch=':'cached=')+page.id,true,function (error,url,xhr) {
            if (!active || !wasActive) { busy=false; return; }
            if (error) { busy=false; message(error); if (!fetch) load(true); else schedule(); return; }
            var candidate = new Image();
            candidate.onload=function () {
                busy=false;
                if (!active) return;
                imageWidth=candidate.width; imageHeight=candidate.height; fitImage();
                el('image').src=url; el('image').style.display='inline'; el('empty').style.display='none';
                var reported=xhr.getResponseHeader('X-Dashboard-Battery');
                battery=reported ? Number(reported) : null; charging=xhr.getResponseHeader('X-Dashboard-Charging')==='1';
                var revision=xhr.getResponseHeader('X-Dashboard-Revision');
                if (revision) request('commit='+page.id+':'+revision,false,function () {});
                message(page.name + (xhr.getResponseHeader('X-Dashboard-Stale')==='1'?' · Offline / cached':''));
                if (!fetch) load(true); else schedule();
            };
            candidate.onerror=function () { busy=false; message('Image could not be decoded; previous page retained'); schedule(); };
            candidate.src=url;
        }); }
        if (fetch) request('settings',false,function(error,value){
            if (!error && value.pages && value.pages.length) {
                settings=value;
                try { window.localStorage.setItem('dashboard-settings',JSON.stringify(settings)); } catch (ignored) {}
                var found=-1,j;for(j=0;j<settings.pages.length;j++)if(settings.pages[j].id===page.id)found=j;
                index=found<0?0:found;page=settings.pages[index];
            }
            download();
        }); else download();
    }
    function navigate(delta) { if (busy) return; index=(index+delta+settings.pages.length)%settings.pages.length; load(false); }
    function pause() { active=false; clearTimeout(timer); clearTimeout(rotate); clearTimeout(resizeTimer); clearInterval(heartbeat); }
    function enter() {
        var resumed=!active;
        active=true;
        request('enter',false,function () {});
        clearInterval(heartbeat);
        heartbeat=setInterval(function () { if (active) request('heartbeat',false,function (error) { if(error) {pause();message(error);} }); },20000);
        schedule();
        if (resumed && initialized) load(false);
    }
    el('previous').onclick=function () {navigate(-1);}; el('next').onclick=function () {navigate(1);};
    el('refresh').onclick=function () {load(true);};
    el('close').onclick=function () { pause(); request('close',false,function(error){message(error||'Closed');}); };
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
        resizeTimer=setTimeout(function resized() {
            if (!active) return;
            if (busy) {resizeTimer=setTimeout(resized,500);return;}
            var canvas=canvasSize();
            if (lastRenderSize!==canvas.width+'x'+canvas.height) load(true);
        },300);
    };
    document.addEventListener('visibilitychange',function(){if(document.hidden)pause();else enter();});
    try {
        var saved=JSON.parse(window.localStorage.getItem('dashboard-settings'));
        if (saved && saved.pages && saved.pages.length) settings=saved;
    } catch (ignored) {}
    enter();
    initialized=true;
    load(false);
}());
