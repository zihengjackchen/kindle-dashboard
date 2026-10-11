'use strict';
const $=id=>document.getElementById(id), names={weather:'Weather',nas:'Home server',markets:'Watchlist',backup:'Backblaze backup',device:'Kindle',notes:'Agenda & notes',markdown:'Markdown'};
let draft,defaults,saved,pageDefaults={},fields={},defaultFields={},symbols=[],devices={},nasInfo=null,imageUrl,connected=false,dirty=false,busy=false,canSave=false,editing='overview',dragged=null,previewTimer;
const clone=value=>JSON.parse(JSON.stringify(value));
function message(text,error=false){$('message').textContent=text;$('message').dataset.error=String(error)}
function headers(){return {Authorization:'Bearer '+$('token').value,'Content-Type':'application/json'}}
async function api(path,options={}){const response=await fetch(path,{...options,headers:headers()});if(!response.ok){let detail='Request failed ('+response.status+').';try{detail=(await response.json()).detail||detail}catch{}throw Error(response.status===401?'Token rejected. Check your dashboard token.':detail)}return response}
function controls(){$('connect').disabled=busy;$('editor').disabled=!connected||busy;$('save').disabled=!connected||busy||!canSave;$('preview-button').disabled=!connected||busy}
async function action(fn){if(busy)return;busy=true;controls();try{await fn()}catch(e){message(e.message,true)}finally{busy=false;controls()}}
function current(){if(editing==='overview')return draft;if(!draft.pages[editing]){const p=clone(pageDefaults[editing]),cut=Math.ceil(draft.tickers.length/2);p.tickers=editing==='markets-1'?draft.tickers.slice(0,cut):editing==='markets-2'?draft.tickers.slice(cut):clone(draft.tickers);if(!p.tickers.length)p.tickers=clone(draft.tickers);p.weather_units=draft.weather_units;draft.pages[editing]=p}return draft.pages[editing]}
function changed(){dirty=true;$('draft-state').textContent='Unsaved draft';clearTimeout(previewTimer);previewTimer=setTimeout(autoPreview,650)}
function autoPreview(){if(!connected)return;if(busy){previewTimer=setTimeout(autoPreview,300);return}action(preview)}
function collect(){const p=current();p.title=$('title').value;p.density=$('density').value;p.weather_units=$('weather-units').value;p.market_columns=Number($('market-columns').value);p.notes_title=$('notes-title').value;p.notes=$('notes').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);const selected=[...$('tickers').querySelectorAll('input:checked')].map(x=>x.value);p.tickers=[...p.tickers.filter(t=>selected.includes(t)),...selected.filter(t=>!p.tickers.includes(t))];draft.refresh_minutes=Number($('refresh-minutes').value);draft.night_minutes=Number($('night-minutes').value);draft.rotation_minutes=Number($('rotation-minutes').value);if(!p.title.trim()||!p.notes_title.trim())throw Error('Give the page and notes widget a name.');if(!p.tickers.length)throw Error('Select at least one ticker.');if(p.notes.length>5||p.notes.some(x=>x.length>100))throw Error('Use up to 5 notes, each no longer than 100 characters.');validateGrid(p);if(new TextEncoder().encode(JSON.stringify(draft)).length>65536)throw Error('Layout exceeds 64 KiB. Shorten Markdown or remove unused widgets.');return draft}
function option(value,label){const node=document.createElement('option');node.value=value;node.textContent=label;return node}
function button(label,title,fn){const node=document.createElement('button');node.textContent=label;node.title=title;node.setAttribute('aria-label',title);node.onclick=fn;return node}
function widgetSelect(label,values,current,onchange){const wrap=document.createElement('label');wrap.textContent=label;const select=document.createElement('select');select.setAttribute('aria-label',label);for(const[value,title]of values)select.append(option(value,title));select.value=current;select.onchange=()=>{onchange(select.value);changed();renderWidgets()};wrap.append(select);return wrap}
function move(from,to){if(from===to)return;current().widgets.forEach(w=>{w.row=null;w.column=1});const list=current().widgets;list.splice(to,0,list.splice(from,1)[0]);changed();renderWidgets()}
function renderWidgets(){
 const openDetails=new Map([...$('widgets').children].map(row=>[row.dataset.key,[...row.querySelectorAll('details')].map(d=>d.open)]));const widgets=current().widgets;$('watchlist-panel').hidden=!widgets.some(w=>w.id==='markets');$('notes-panel').hidden=!widgets.some(w=>w.id==='notes');$('widgets').replaceChildren();widgets.forEach((widget,i)=>{
  const row=document.createElement('div');row.className='widget';row.dataset.width=widget.width;row.draggable=true;row.dataset.id=widget.id;row.dataset.key=widget.key||widget.id;if(widget.row!=null){row.style.gridRow=widget.row;row.style.gridColumn=String(widget.column||1)+(widget.width==='full'?' / span 2':'')}
  row.ondragstart=event=>{if(event.target.closest('input,select,button,details')){event.preventDefault();return}dragged=i;event.dataTransfer.setData('text/plain',String(i));event.dataTransfer.effectAllowed='move'};
  row.ondragover=event=>{event.preventDefault();row.classList.add('drop-target')};row.ondragleave=()=>row.classList.remove('drop-target');
  row.ondrop=event=>{event.preventDefault();row.classList.remove('drop-target');if(dragged!==null)move(dragged,i);dragged=null};row.ondragend=()=>{dragged=null;document.querySelectorAll('.drop-target').forEach(n=>n.classList.remove('drop-target'))};
  const head=document.createElement('div');head.className='widget-head';const title=document.createElement('strong');title.textContent=names[widget.id];head.append(title);const buttons=document.createElement('div');
  const up=button('↑','Move '+names[widget.id]+' up',()=>move(i,i-1));up.disabled=i===0;
  const down=button('↓','Move '+names[widget.id]+' down',()=>move(i,i+1));down.disabled=i===widgets.length-1;
  const remove=button('×','Hide '+names[widget.id],()=>{widgets.splice(i,1);changed();renderWidgets()});remove.disabled=widgets.length===1;buttons.append(up,down,remove);head.append(buttons);row.append(head);
  const pair=document.createElement('div');pair.className='pair';pair.append(widgetSelect('Width',[['half','Half'],['full','Full']],widget.width,v=>{widget.width=v;if(v==='full')widget.column=1}),widgetSelect('Height',[['small','Small'],['medium','Medium'],['large','Large']],widget.size,v=>widget.size=v));row.append(pair);
  const detail=document.createElement('details'),summary=document.createElement('summary'),choices=document.createElement('div');summary.textContent='Fields to show ('+(widget.fields??defaultFields[widget.id]).length+')';choices.className='field-options';
  for(const key of fields[widget.id]){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.field=key;input.checked=(widget.fields??defaultFields[widget.id]).includes(key);input.onchange=()=>{widget.fields=[...choices.querySelectorAll('input:checked')].map(n=>n.dataset.field);summary.textContent='Fields to show ('+widget.fields.length+')';changed()};label.append(input,document.createTextNode(fieldLabel(key)));if(widget.id==='nas'&&nasInfo){const value=nasInfo[key]??nasInfo.metrics?.[key];label.title=value===undefined||value===null?'Not reported by this NAS':String(value)}choices.append(label)}
  detail.append(summary,choices);row.append(detail);widgetOptions(row,widget,i);const wasOpen=openDetails.get(row.dataset.key);if(wasOpen)[...row.querySelectorAll('details')].forEach((d,j)=>{d.open=wasOpen[j]??d.open});$('widgets').append(row);
 });
 $('add-widget').replaceChildren();for(const id of Object.keys(names))$('add-widget').append(option(id,names[id]));$('add').disabled=widgets.length>=12;$('add-widget').disabled=widgets.length>=12;

}
function renderForm(){const p=current();$('title').value=p.title;$('density').value=p.density;$('weather-units').value=p.weather_units;$('market-columns').value=p.market_columns;$('notes-title').value=p.notes_title;$('notes').value=p.notes.join('\n');$('refresh-minutes').value=draft.refresh_minutes;$('night-minutes').value=draft.night_minutes;$('rotation-minutes').value=draft.rotation_minutes;renderPages();$('tickers').replaceChildren();for(const symbol of symbols){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=symbol;input.checked=p.tickers.includes(symbol);input.onchange=changed;label.append(input,document.createTextNode(symbol));$('tickers').append(label)}renderWidgets()}
function query(){const [width,height]=$('size').value.split('x');const params=new URLSearchParams({width,height,page:editing,device:'web-preview'});const record=devices[$('device').value];if(record)for(const key of ['battery','charging','external_power','sleep_inhibited','power_policy','rssi','fetch_seconds','fetch_failures','last_success_epoch','frontlight','uptime_seconds','storage_free_mib','firmware'])if(record[key]!==undefined&&record[key]!==null)params.set(key,String(record[key]));return params}
async function preview(){clearTimeout(previewTimer);const response=await api('/preview.png?'+query(),{method:'POST',body:JSON.stringify(collect())});if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=URL.createObjectURL(await response.blob());$('preview').src=imageUrl;$('preview').hidden=false;$('empty').hidden=true;$('download').href=imageUrl;$('download').hidden=false;$('preview-label').textContent=current().title+' · '+$('size').value;$('draft-state').textContent=dirty?'Draft preview':'Saved layout preview'}
function deviceNote(){const record=devices[$('device').value];$('power-note').textContent=record?'Last report: '+(record.external_power===true?'external power connected':record.external_power===false?'on battery':'external power unknown')+'. Policy: '+(record.power_policy==='plugged-in'?'stay awake while plugged in':record.power_policy==='native-sleep'?'native sleep':'not reported')+'. Idle sleep hold: '+(record.sleep_inhibited===true?'active (may belong to another app)':record.sleep_inhibited===false?'inactive':'unknown')+'. Timed wake is not enabled.':'Power status appears after the Kindle fetches with the updated client.';$('device-note').textContent=record?'Last Kindle contact: '+new Date(record.last_seen).toLocaleString()+'. Values may be stale.':'No Kindle selected. Battery and radio values are unknown.'}
$('connect').onclick=()=>action(async()=>{if(connected&&dirty)throw Error('Save or discard changes before reconnecting.');const[lr,sr]=await Promise.all([api('/layout'),api('/status')]);const result=await lr.json(),status=await sr.json();draft=result.layout;saved=clone(draft);defaults=result.defaults;pageDefaults=result.page_defaults;fields=result.fields;defaultFields=result.default_fields;symbols=result.tickers;canSave=result.can_save;devices=status.devices;nasInfo=status.nas;connected=true;dirty=false;renderForm();$('device').replaceChildren(option('','No device / unknown battery'));const entries=Object.entries(devices).sort((a,b)=>b[1].last_seen.localeCompare(a[1].last_seen));for(const[id,record]of entries)$('device').append(option(id,id+' · '+(record.battery??'—')+'%'));if(entries.length){$('device').value=entries[0][0];const record=entries[0][1],size=record.width+'x'+record.height;if(![...$('size').options].some(o=>o.value===size))$('size').append(option(size,size));$('size').value=size}deviceNote();sourceBadges(status);$('status').textContent=JSON.stringify(status,null,2);await preview();message(canSave?'Connected. Drag widgets or choose fields; previews update automatically.':'Preview only: configure DASHBOARD_LAYOUT_PATH to save.')});
$('preview-button').onclick=()=>action(preview);
$('save').onclick=()=>action(async()=>{const response=await api('/layout',{method:'PUT',body:JSON.stringify(collect())});draft=await response.json();saved=clone(draft);dirty=false;message('Saved. Changes appear on the next Kindle refresh.');await preview()});
for(const id of ['title','density','weather-units','market-columns','notes-title','notes','refresh-minutes','night-minutes','rotation-minutes'])$(id).addEventListener('input',changed);
for(const id of ['size','device'])$(id).onchange=()=>{deviceNote();autoPreview()};
$('page').onchange=()=>{try{collect();editing=$('page').value;renderForm();autoPreview()}catch(e){$('page').value=editing;message(e.message,true)}};
$('add').onclick=()=>{const id=$('add-widget').value;if(!id||current().widgets.length>=12)return;current().widgets.push({id,key:newKey(),width:id==='markets'?'full':'half',size:id==='markets'?'large':'medium',fields:null});changed();renderWidgets()};
$('reset').onclick=()=>{draft=clone(defaults);renderForm();changed();message('Default layout loaded. Save when ready.')};
$('discard').onclick=()=>{draft=clone(saved);dirty=false;renderForm();autoPreview();message('Unsaved changes discarded.')};
$('export').onclick=()=>action(async()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(collect())],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='dashboard-layout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
$('import').onclick=()=>$('import-file').click();
$('import-file').onchange=()=>action(async()=>{const file=$('import-file').files[0];if(!file)return;try{if(file.size>65536)throw Error('Choose a layout smaller than 64 KiB.');const value=JSON.parse(await file.text());await api('/preview.png?'+query(),{method:'POST',body:JSON.stringify(value)});draft={...clone(defaults),...value};draft.widgets=draft.widgets.filter(w=>w.id!=='chatgpt').map(w=>({width:'half',size:'medium',fields:null,...w}));renderForm();changed();message('Layout imported into the draft.')}finally{$('import-file').value=''}});
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue=''}});

const pageNames={overview:'Overview',weather:'Weather','markets-1':'Markets 1','markets-2':'Markets 2',nas:'Home server'};
function fieldLabel(key){return ({rssi:'Wi-Fi signal',cpu_percent:'CPU usage',memory_available_gib:'Available RAM',memory_total_gib:'Total RAM',used_percent:'Storage used',pool_free_gib:'Free storage',pool_size_gib:'Total storage',cpu_temperature_c:'CPU temperature',network_rx_mbps:'Network download',network_tx_mbps:'Network upload',disk_read_mbps:'Disk read',disk_write_mbps:'Disk write',uptime_seconds:'Uptime',storage_free_mib:'Free Kindle storage',fetch_seconds:'Download duration',fetch_failures:'Download failures',frontlight:'Frontlight level',high_low:'High / low',last_success:'Last successful update',external_power:'External power',sleep_inhibited:'Idle sleep held',power_policy:'Power policy'})[key]||key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase())}
function renderPages(){
 const root=$('page-order');root.replaceChildren();
 const order=[...draft.page_order,...Object.keys(pageNames).filter(id=>!draft.page_order.includes(id))];
 let from=null;
 function reorder(id,target){const list=draft.page_order,a=list.indexOf(id),b=list.indexOf(target);if(a<0||b<0||a===b)return;list.splice(b,0,list.splice(a,1)[0]);changed();renderPages()}
 for(const id of order){
  const enabled=draft.page_order.includes(id),row=document.createElement('div');row.className='page-item';row.dataset.page=id;row.draggable=enabled;
  const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=enabled;check.disabled=enabled&&draft.page_order.length===1;
  check.onchange=()=>{if(check.checked)draft.page_order.push(id);else draft.page_order=draft.page_order.filter(p=>p!==id);changed();renderPages()};label.append(check,document.createTextNode(pageNames[id]));row.append(label);
  const index=draft.page_order.indexOf(id);
  const up=button('↑','Move '+pageNames[id]+' page up',()=>reorder(id,draft.page_order[index-1]));up.disabled=!enabled||index===0;
  const down=button('↓','Move '+pageNames[id]+' page down',()=>reorder(id,draft.page_order[index+1]));down.disabled=!enabled||index===draft.page_order.length-1;row.append(up,down);
  row.ondragstart=e=>{from=id;e.dataTransfer.setData('text/plain',id)};
  row.ondragover=e=>{if(enabled){e.preventDefault();row.classList.add('drop-target')}};
  row.ondragleave=()=>row.classList.remove('drop-target');row.ondragend=()=>{from=null;root.querySelectorAll('.drop-target').forEach(n=>n.classList.remove('drop-target'))};
  row.ondrop=e=>{e.preventDefault();row.classList.remove('drop-target');if(from)reorder(from,id);from=null};root.append(row);
 }
}
function sourceBadges(status){
 const root=$('sources');root.replaceChildren();
 for(const [key,label] of [['weather','Weather'],['nas','Home server']]){const record=status.sources[key],node=document.createElement('span');node.className='source';node.dataset.state=record?.status||'UNKNOWN';node.textContent=label+': '+(record?.status==='CURRENT'?'current':record?.status==='STALE'?'older data':'unavailable');root.append(node)}
 const quotes=Object.entries(status.sources).filter(([k])=>!['weather','nas'].includes(k));
 if(quotes.length){const node=document.createElement('span'),count=quotes.filter(([,r])=>r?.status==='CURRENT').length;node.className='source';node.textContent='Markets: '+count+'/'+quotes.length+' current';node.dataset.state=count===quotes.length?'CURRENT':'STALE';root.append(node)}
}
$('page-reset').onclick=()=>{
 try{collect();const p=current(),base=editing==='overview'?defaults:pageDefaults[editing];
 // Keep personal content and global timers while restoring only this page's arrangement.
 p.widgets=clone(base.widgets);p.density=base.density;p.market_columns=base.market_columns;
 renderForm();changed();message('Page arrangement reset in the draft. Your symbols, notes and other pages are unchanged.');
 }catch(e){message(e.message,true)}
};
$('zoom').onclick=()=>{const actual=$('zoom').getAttribute('aria-pressed')!=='true';$('zoom').setAttribute('aria-pressed',String(actual));$('zoom').textContent=actual?'Fit preview':'Actual pixels';document.querySelector('.device-stage').classList.toggle('actual',actual)};

function newKey(){return 'w_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,8)}
function widgetOptions(row,w,index){
 const detail=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Placement & content';detail.append(summary);
 function input(label,value,callback,multiline=false,max=40){const wrap=document.createElement('label'),el=document.createElement(multiline?'textarea':'input');wrap.textContent=label;el.value=value;el.maxLength=max;el.oninput=()=>{callback(el.value);changed()};wrap.append(el);detail.append(wrap);return el}
 input('Widget title (optional)',w.title||'',v=>w.title=v);
 const placement=document.createElement('div');placement.className='pair';
 placement.append(widgetSelect('Row',[['','Auto'],...Array.from({length:12},(_,i)=>[String(i+1),String(i+1)])],w.row??'',v=>{w.row=v?Number(v):null;if(w.width==='full')w.column=1}),widgetSelect('Column',[['1','Left'],['2','Right']],w.column||1,v=>{w.column=Number(v);if(w.column===2)w.width='half'}));detail.append(placement);
 const note=document.createElement('p');note.className='hint';note.textContent='Explicit positions reserve grid cells. Dragging or arrows returns the page to automatic placement.';detail.append(note);
 if(w.id==='markdown'){
  const text=input('Markdown',w.content||'',v=>w.content=v,true,4000);text.placeholder='# Today\n- **Important:** your note\n- Another item';text.rows=7;
  detail.append(widgetSelect('Long content',[['shrink','Shrink, then truncate'],['truncate','Keep text size, truncate']],w.overflow||'shrink',v=>w.overflow=v));
  const hint=document.createElement('p');hint.className='hint';hint.textContent='Headings, bold, lists, quotes, code and link labels. 4,000 characters. Images and HTML are not rendered. Preview shows the final fit.';detail.append(hint);detail.open=true;
 }
 if(w.id==='markets'){
  input('Symbols, comma-separated (blank inherits page)',(w.tickers||[]).join(', '),v=>w.tickers=v.trim()?v.split(',').map(t=>t.trim().toUpperCase()).filter(Boolean):null,false,400);
  detail.append(widgetSelect('Watchlist columns',[['','Page setting'],['2','Two'],['3','Three']],w.market_columns??'',v=>w.market_columns=v?Number(v):null));
 }
 if(w.id==='weather')detail.append(widgetSelect('Temperatures',[['','Page setting'],['both','Celsius + Fahrenheit'],['source','Source unit']],w.weather_units||'',v=>w.weather_units=v||null));
 if(w.id==='notes')input('Notes (blank inherits page notes)',(w.notes||[]).join('\n'),v=>w.notes=v.trim()?v.split(/\r?\n/).filter(Boolean):null,true,505);
 if(w.id==='backup'){
  const backups=nasInfo?.backups||[];
  detail.append(widgetSelect('Backup job',Array.from({length:Math.max(1,backups.length)},(_,i)=>[String(i),backups[i]?.name||'First job']),w.backup_index||0,v=>w.backup_index=Number(v)));
 }
 const duplicate=button('Duplicate','Duplicate '+names[w.id],()=>{const copy=clone(w);copy.key=newKey();copy.row=null;copy.column=1;current().widgets.splice(index+1,0,copy);changed();renderWidgets()});duplicate.disabled=current().widgets.length>=12;detail.append(duplicate);row.append(detail);
}

function validateGrid(page){
 const cells=new Set();for(const w of page.widgets){if(w.row==null)continue;for(const c of w.width==='full'?[1,2]:[w.column||1]){const key=w.row+':'+c;if(cells.has(key))throw Error('Two widgets overlap in row '+w.row+'. Choose another row/column or Auto.');cells.add(key)}}
}
