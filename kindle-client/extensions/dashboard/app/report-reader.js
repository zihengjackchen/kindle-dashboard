/* ES5 local Markdown reader. DOM nodes come from an allowlist, never raw HTML. */
(function () {
    'use strict';
    // Punycode normalization in markdown-it uses this ES2015 helper.
    if (!String.fromCodePoint) String.fromCodePoint=function () {
        var out='', i, n;
        for(i=0;i<arguments.length;i++) {
            n=Number(arguments[i]);
            if(n<0 || n>1114111 || n%1 || !isFinite(n)) throw RangeError('Invalid code point');
            if(n<=65535) out+=String.fromCharCode(n);
            else {n-=65536;out+=String.fromCharCode((n>>10)+55296,(n%1024)+56320);}
        }
        return out;
    };
    var parser=window.markdownit({html:false,linkify:false,typographer:false,maxNesting:20});
    var allowed=/^(p|h[1-6]|ul|ol|li|blockquote|strong|em|s|table|thead|tbody|tr|th|td)$/;
    function nodes(tokens, root) {
        var stack=[root], i,t,node,parent;
        for(i=0;i<tokens.length;i++) {
            t=tokens[i];parent=stack[stack.length-1];
            if(t.hidden) continue;
            if(t.type==='inline') {nodes(t.children || [],parent);continue;}
            if(t.nesting===-1) {if(stack.length>1)stack.pop();continue;}
            if(t.nesting===1) {
                node=document.createElement(allowed.test(t.tag)?t.tag:'span');
                if(t.type==='link_open')node.className='report-link';
                if(t.tag==='ol' && /^\d{1,6}$/.test(String(t.attrGet('start'))))node.setAttribute('start',t.attrGet('start'));
                parent.appendChild(node);stack.push(node);continue;
            }
            if(t.type==='softbreak')node=document.createTextNode(' ');
            else if(t.type==='hardbreak'||t.type==='hr')node=document.createElement(t.type==='hr'?'hr':'br');
            else if(t.type==='fence'||t.type==='code_block'||t.type==='code_inline') {
                node=document.createElement(t.type==='code_inline'?'code':'pre');node.textContent=t.content;
            } else node=document.createTextNode(t.content || '');
            parent.appendChild(node);
        }
    }
    var container=document.getElementById('report'), flow=document.getElementById('report-content');
    var viewport=document.getElementById('report-window'), current=null, page=0, count=1, step=0, size=30;
    try {size=Number(localStorage.getItem('dashboard-report-size'))||30;} catch(ignore) {}
    size=Math.max(24,Math.min(40,size));
    function position() {
        page=Math.max(0,Math.min(page,count-1));
        flow.style.webkitTransform='translateX('+(-page*step)+'px)';
        flow.style.transform='translateX('+(-page*step)+'px)';
        document.getElementById('report-position').textContent=(page+1)+' / '+count;
        document.getElementById('text-smaller').disabled=size<=24;
        document.getElementById('text-larger').disabled=size>=40;
    }
    function layout() {
        if(!current)return;
        flow.style.fontSize=Math.max(14,Math.round(size*container.clientWidth/1056))+'px';
        flow.style.webkitTransform='none';flow.style.transform='none';
        flow.style.webkitColumnWidth=viewport.clientWidth+'px';
        flow.style.columnWidth=viewport.clientWidth+'px';
        step=viewport.clientWidth+24;
        count=Math.max(1,Math.ceil((flow.scrollWidth+24)/step));
        position();
    }
    function prepare(value) {
        if(!value || typeof value.markdown!=='string' || value.markdown.length>40000 ||
            !value.markdown.replace(/\s/g,'') || typeof value.day!=='string' ||
            !/^(\d{4}-\d{2}-\d{2}|unavailable)$/.test(value.day) ||
            !(value.font_size>=24 && value.font_size<=40)) throw Error('Invalid report');
        var result=document.createElement('div');nodes(parser.parse(value.markdown,{}),result);
        return {node:result,day:value.day,font_size:value.font_size,source:value.markdown};
    }
    function show(value,last) {
        container.style.display='block';
        if(!current || current.source!==value.source) {
            current=value;page=0;flow.innerHTML='';
            var children=value.node.childNodes,i;
            for(i=0;i<children.length;i++)flow.appendChild(children[i].cloneNode(true));
            try {if(!localStorage.getItem('dashboard-report-size'))size=value.font_size;}catch(ignore) {size=value.font_size;}
            document.getElementById('report-date').textContent=value.day==='unavailable'?'No saved report':value.day;
        }
        layout();if(last){page=count-1;position();}
    }
    function change(delta) {
        var ratio=page/Math.max(1,count);
        size=Math.max(24,Math.min(40,size+delta));
        try {localStorage.setItem('dashboard-report-size',String(size));}catch(ignore) {}
        layout();page=Math.floor(ratio*count);position();
    }
    document.getElementById('text-smaller').onclick=function(){change(-2);};
    document.getElementById('text-larger').onclick=function(){change(2);};
    window.DashboardReport={prepare:prepare,show:show,hide:function(){container.style.display='none';},
        step:function(delta){if(page+delta<0||page+delta>=count)return false;page+=delta;position();return true;},
        reset:function(){page=0;},layout:layout};
}());
