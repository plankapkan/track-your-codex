const $ = id => document.getElementById(id);
let current = null;
window.addEventListener('themechange', () => { if (curveData) drawCurve(curveData.curve, curveData); });
window.addEventListener('languagechange', () => {
  if (current) render(current);
  renderProjectSettings();
});
let periodMode = 'cycle';
let periodHours = 168;
let customRange = null;
let chatPage = 1, chatPageSize = '10', chatFilterKey = null;
const expandedChatRows = new Set();
try { chatPageSize = localStorage.getItem('codex-chat-page-size') || '10'; } catch {}
if (!['10','50','100','all'].includes(chatPageSize)) chatPageSize = '10';
let refreshSerial = 0;
let curveSerial = 0;
let curveData = null;
let chartHours = 24;
let chartFollowsPeriod = true;
try {chartHours = Number(localStorage.getItem('codex-chart-hours')) || 24;} catch {}
if (![1,5,24,168,720].includes(chartHours)) chartHours = 24;
function updatePeriodControls() {
  for (const button of document.querySelectorAll('[data-period]')) {
    const value = button.dataset.period;
    const active = periodMode === 'rolling' ? !['cycle','custom'].includes(value) && periodHours === Number(value.slice(0,-1))*(value.endsWith('d')?24:1) : value === periodMode;
    button.setAttribute('aria-pressed',String(active));
  }
}
function closeCustomPeriod() {
  $('custom-period-panel').hidden=true;
  $('custom-period-button').setAttribute('aria-expanded','false');
}
function moscowInput(date) {
  return new Date(date.getTime()+3*3600000).toISOString().slice(0,16);
}
function query() {
  const today = localDate(new Date());
  const params = new URLSearchParams({from:today,to:today,project:$('project').value,model:$('model').value,grouped:$('grouped').checked?'1':'0',cycle:periodMode==='cycle'?'1':'0'});
  if (periodMode === 'rolling') params.set('hours',String(periodHours));
  if (periodMode === 'custom' && customRange) {params.set('start_time',customRange.from+'+03:00');params.set('end_time',customRange.to+'+03:00');}
  return params;
}
function options(id, values, label) {
  const select = $(id), selected = select.value;
  const modelOrder=['gpt-6.1-sol','gpt-6-astra','gpt-6-sol','gpt-6-luna','gpt-5.6-sol','gpt-5.6-terra','gpt-5.6-luna','gpt-5.5'];
  const alphabetical=(a,b)=>t(a).localeCompare(t(b),locale(),{sensitivity:'base',numeric:true});
  const rank=model=>{const index=modelOrder.indexOf(model);return index<0?modelOrder.length:index;};
  const sorted=[...values].sort(id==='model'?(a,b)=>rank(a)-rank(b)||alphabetical(a,b):alphabetical);
  select.replaceChildren(new Option(label, ''), ...sorted.map(value => new Option(t(value), value)));
  select.value = values.includes(selected) ? selected : '';
}
function cell(tr, text) { const td = document.createElement('td'); td.textContent = text; tr.append(td); return td; }
function compareWeeklyQuota(a, b) {
  // Match quotaText: rows without an estimate follow estimated rows.
  const rank = row => row.quota_covered_tokens && row.quota_pp > 0 ? row.quota_pp : -1;
  const identity = row => [row.id ?? row.thread ?? '', row.model ?? '', row.effort ?? ''].join('|');
  return rank(b)-rank(a) || b.total-a.total || identity(a).localeCompare(identity(b));
}
function renderChats() {
  if (!current) return;
  const term = $('search').value.toLocaleLowerCase(); $('chats').replaceChildren();
  const filterKey = query().toString()+'|'+term;
  if (filterKey !== chatFilterKey) { chatPage = 1; chatFilterKey = filterKey; }
  const rows = current.chats.filter(row => !term || (row.title+' '+row.thread+' '+row.project).toLocaleLowerCase().includes(term)).sort(compareWeeklyQuota);
  const size = chatPageSize === 'all' ? Math.max(1,rows.length) : Number(chatPageSize);
  const pages = Math.max(1,Math.ceil(rows.length/size));
  chatPage = Math.min(chatPage,pages);
  const start = (chatPage-1)*size;
  const chatModels = new Map();
  for (const row of current.chats) {
    if (!chatModels.has(row.thread)) chatModels.set(row.thread,new Map());
    const models = chatModels.get(row.thread);
    if (!models.has(row.model)) models.set(row.model,{model:row.model,total:0,fresh:0,cached:0,output:0,quota_pp:0,quota_covered_tokens:0});
    const model = models.get(row.model);
    for (const field of ['total','fresh','cached','output','quota_pp','quota_covered_tokens']) model[field] += row[field] ?? 0;
  }
  for (const row of rows.slice(start,start+size)) {
    const tr = document.createElement('tr'); const td = cell(tr, '');
    const key = JSON.stringify([row.thread,row.model,row.effort]);
    const button = document.createElement('button'); button.type='button'; button.textContent=row.title; button.className='chat-title chat-expand'; td.append(button);
    const meta = document.createElement('span'); meta.textContent = t(row.project)+' · '+row.thread; meta.className = 'chat-meta'; td.append(meta);
    cell(tr, row.model+' / '+row.effort); cell(tr,number(row.main_calls)+' / '+number(row.subagent_calls));
    for (const key of ['fresh','cached','output','total']) cell(tr,number(row[key]));
    cell(tr,credits(row.estimated_credits)); $('chats').append(tr);
    cell(tr,quotaText(row));
    const detail = document.createElement('tr'); detail.className='chat-detail';
    const reportCell = cell(detail,''); reportCell.colSpan=9;
    const link = document.createElement('a'); link.href='codex://threads/'+encodeURIComponent(row.thread); link.textContent=row.title+' ↗'; link.className='chat-open'; reportCell.append(link,modelReport(chatModels.get(row.thread).values()));
    detail.id='chat-models-'+(start+$('chats').querySelectorAll('.chat-expand').length);
    button.setAttribute('aria-controls',detail.id);
    const updateExpanded = () => {
      const open = expandedChatRows.has(key);
      button.setAttribute('aria-expanded',String(open)); detail.hidden=!open;
    };
    tr.className='chat-row';
    tr.addEventListener('click', () => {
      if (expandedChatRows.has(key)) expandedChatRows.delete(key); else expandedChatRows.add(key);
      updateExpanded();
    });
    updateExpanded(); $('chats').append(detail);
  }
  $('empty').hidden = $('chats').children.length > 0;
  $('chat-page-info').textContent = t`Строки ${number(rows.length?start+1:0)}–${number(Math.min(start+size,rows.length))} из ${number(rows.length)}`;
  for (const button of document.querySelectorAll('[data-chat-size]')) button.setAttribute('aria-pressed',String(button.dataset.chatSize===chatPageSize));
  const nav = $('chat-pages'); nav.replaceChildren();
  if (pages > 1) {
    const addButton = (label,page,disabled=false) => {
      const button = document.createElement('button'); button.type='button'; button.textContent=label; button.dataset.chatPage=String(page); button.disabled=disabled;
      if (page===chatPage && !disabled) button.setAttribute('aria-current','page');
      nav.append(button);
    };
    addButton(t('Назад'),chatPage-1,chatPage===1);
    const visible = [...new Set([1,pages,chatPage-1,chatPage,chatPage+1].filter(page=>page>=1&&page<=pages))].sort((a,b)=>a-b);
    let previous = 0;
    for (const page of visible) {
      if (previous && page-previous>1) { const dots=document.createElement('span'); dots.textContent='…'; nav.append(dots); }
      addButton(number(page),page); previous=page;
    }
    addButton(t('Далее'),chatPage+1,chatPage===pages);
  }
}
// Sum existing globally allocated shares; filters must not renormalize them.
function rankingGroups(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const id = row[key];
    if (!groups.has(id)) groups.set(id, {id, title:key==='project'?t(id):row.title, project:row.project, total:0, quota_pp:0, quota_covered_tokens:0, models:new Map()});
    const group = groups.get(id);
    if (!group.models.has(row.model)) group.models.set(row.model, {model:row.model,total:0,fresh:0,cached:0,output:0,quota_pp:0,quota_covered_tokens:0});
    const model = group.models.get(row.model);
    for (const field of ['total','quota_pp','quota_covered_tokens']) group[field] += row[field] ?? 0;
    for (const field of ['total','fresh','cached','output','quota_pp','quota_covered_tokens']) model[field] += row[field] ?? 0;
  }
  return [...groups.values()].sort(compareWeeklyQuota).slice(0,10);
}
function modelReport(models) {
  const report=document.createElement('div');report.className='ranking-report table-wrap';
  const table=document.createElement('table');const head=document.createElement('thead');const headers=document.createElement('tr');
  for(const label of [t('Модель'),t('Новый вход'),t('Кеш'),t('Выход'),t('Всего токенов'),t('Недельный лимит ≈')]) {const th=document.createElement('th');th.textContent=label;headers.append(th);}
  head.append(headers);table.append(head);
  const body=document.createElement('tbody');
  for(const model of [...models].sort(compareWeeklyQuota)) {
    const tr=document.createElement('tr');cell(tr,model.model);
    for(const field of ['fresh','cached','output','total']) cell(tr,number(model[field]));
    cell(tr,quotaText(model));body.append(tr);
  }
  table.append(body);report.append(table);
  return report;
}
function sizeRankings() {
  const section = document.querySelector('.usage-rankings');
  const panels = [...section.querySelectorAll('.ranking-panel')];
  if (getComputedStyle(section).gridTemplateColumns.split(' ').length < 2) {
    section.style.removeProperty('--ranking-height');
    return;
  }
  // Measure unconstrained content, including expanded model reports.
  const heights = panels.map(panel => {
    const viewport = panel.querySelector('.ranking-viewport');
    const list = viewport.firstElementChild;
    return list.getBoundingClientRect().height + panel.getBoundingClientRect().height - viewport.getBoundingClientRect().height;
  });
  section.style.setProperty('--ranking-height', Math.ceil(Math.min(...heights))+'px');
}
const rankingResizeObserver = new ResizeObserver(sizeRankings);
window.addEventListener('resize', sizeRankings);
function renderRankings(data) {
  rankingResizeObserver.disconnect();
  for (const [target,key] of [['top-projects','project'],['top-chats','thread']]) {
    const viewport = $(target);
    const opened = new Set([...viewport.querySelectorAll('details[open]')].map(item=>item.dataset.id));
    const scrollTop = viewport.scrollTop;
    const container = document.createElement('div'); container.className='ranking-list';
    viewport.replaceChildren(container);
    rankingResizeObserver.observe(container);
    const rows = rankingGroups(data.chats,key);
    if (!rows.length) {
      const empty=document.createElement('p'); empty.className='note'; empty.textContent=t('За этот период данных нет.'); container.append(empty); continue;
    }
    const headings=document.createElement('div'); headings.className='ranking-columns';
    for (const label of ['',t('Всего токенов'),t('Недельный лимит ≈')]) {const span=document.createElement('span');span.textContent=label;headings.append(span);}
    container.append(headings);
    rows.forEach((row,index)=>{
      const item=document.createElement('details');item.className='ranking-item';item.dataset.id=String(row.id);item.open=opened.has(String(row.id));
      const summary=document.createElement('summary');summary.className='ranking-row';
      const name=document.createElement('span');name.className='ranking-name';
      const rank=document.createElement('span');rank.className='ranking-position';rank.textContent=String(index+1);
      const title=document.createElement('span');title.className='ranking-title';title.textContent=row.title;
      if(key==='thread') {const meta=document.createElement('small');meta.textContent=t(row.project);title.append(meta);}
      name.append(rank,title);
      const tokens=document.createElement('strong');tokens.textContent=number(row.total);
      const quota=document.createElement('span');quota.className='ranking-quota';quota.textContent=quotaText(row);
      summary.append(name,tokens,quota);
      item.append(summary,modelReport(row.models.values()));container.append(item);
    });
    viewport.scrollTop = scrollTop;
  }
  sizeRankings();
}
async function refresh() {
  if (!$('filters').reportValidity()) return;
  const serial = ++refreshSerial;
  if (!chartFollowsPeriod) refreshCurve();
  try {
    const response = await fetch('/api/usage?'+query()); const data = await response.json();
    if (serial !== refreshSerial) return;
    if (!response.ok) throw new Error(data.error || t('Ошибка чтения отчёта'));
    current = data; render(data);
    if (chartFollowsPeriod) {updateChartControls();refreshCurve(data.range);}
  } catch(error) { if(serial!==refreshSerial)return; $('error').textContent=error.message; $('error').hidden=false; $('status').textContent=t('Нет связи с монитором'); }
}
function render(data) {
    $('error').hidden = true;
    updatePeriodControls();
    options('project',data.options.projects,t('Все проекты')); options('model',data.options.models,t('Все модели'));
    $('project-label').textContent = t('Проект') + ' (' + number(data.options.projects.filter(project => project !== 'Без проекта').length) + ')';
    $('status').textContent = data.index.indexing ? t`Индексация ${data.index.files_done} / ${data.index.files_total}` : t`Монитор работает · ${number(data.index.events)} записей`;
    $('cards').replaceChildren();
    for (const [label,key] of [[t('Новый вход'),'fresh'],[t('Вход из кеша'),'cached'],[t('Выход, включая рассуждения'),'output'],[t('Всего токенов'),'total']]) {
      const card = document.createElement('div'); card.className='card'; const caption=document.createElement('span'); caption.textContent=label;
      const value=document.createElement('strong'); value.textContent=number(data.summary[key]); card.append(caption,value); $('cards').append(card);
    }
    $('models').replaceChildren();
    for (const row of data.models) { const tr=document.createElement('tr'); cell(tr,row.model+' / '+row.effort); for (const key of ['calls','fresh','cached','output','total']) cell(tr,number(row[key])); cell(tr,credits(row.estimated_credits));cell(tr,quotaText(row)); $('models').append(tr); }
    renderChats();
    renderRankings(data);
    renderQuota(data);
    const pricing=data.pricing;
    $('snapshot').textContent=t('Период')+': '+dateTime(new Date(data.range.first_time*1000))+' — '+dateTime(new Date(data.range.final_time*1000))+t(' МСК')+' · '+t('Последний проход')+': '+(data.snapshot?dateTime(new Date(data.snapshot)):t('выполняется'));
    $('rate-date').textContent=t('Тарифы на ')+pricing.date;
    $('diagnostics').replaceChildren();
    const notes=data.diagnostics.length ? data.diagnostics : [{message:t('Замечаний к обработке счётчиков нет.'),count:0}];
    const translations = {'Counter reset: used last_token_usage':t('Сброс накопительного счётчика: использован расход последнего шага'), 'Inconsistent token counters: event not counted':t('Пропущены записи с неполным или противоречивым составом токенов'), 'Token event has unknown model':t('Модель не указана: токены отнесены к unknown'), 'Component counter reset: used last_token_usage':t('Сброс части счётчика: использован расход последнего шага'), 'First counter lacks last_token_usage: treated as baseline':t('Начальный счётчик без расхода последнего шага: принят за исходную точку')};
    for (const note of notes) {const p=document.createElement('p'); p.textContent=(translations[note.message] || note.message)+(note.count ? ' — '+number(note.count) : ''); $('diagnostics').append(p);}
    if(data.index.error){const p=document.createElement('p');p.textContent=data.index.error;$('diagnostics').append(p);}
}
async function download(table) {
  const response=await fetch('/api/export?'+query()+'&table='+table);
  if(!response.ok){$('error').textContent=t('Не удалось выгрузить CSV');$('error').hidden=false;return;}
  const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='codex-'+table+'-'+localDate(new Date())+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('filters').addEventListener('submit',event=>{event.preventDefault();refresh();});
for(const id of ['project','model','grouped']) $(id).addEventListener('change',refresh);

$('search').addEventListener('input',renderChats);
$('chat-page-sizes').addEventListener('click',event=>{
  const button = event.target.closest('[data-chat-size]'); if (!button) return;
  chatPageSize = button.dataset.chatSize; chatPage = 1;
  try { localStorage.setItem('codex-chat-page-size',chatPageSize); } catch {}
  renderChats();
});
$('chat-pages').addEventListener('click',event=>{
  const button = event.target.closest('[data-chat-page]'); if (!button || button.disabled) return;
  chatPage = Number(button.dataset.chatPage); renderChats();
});
document.querySelectorAll('[data-period]').forEach(button=>button.addEventListener('click',()=>{
  const value=button.dataset.period;
  if (value==='custom') {
    const opening=$('custom-period-panel').hidden;
    $('custom-period-panel').hidden=!opening;
    button.setAttribute('aria-expanded',String(opening));
    if (opening) {
      $('custom-from').value=customRange?.from || moscowInput(new Date(Date.now()-86400000));
      $('custom-to').value=customRange?.to || moscowInput(new Date());
      $('custom-period-error').hidden=true;
      $('custom-from').focus();
    }
    return;
  }
  periodMode=value==='cycle'?'cycle':'rolling';
  chartFollowsPeriod=true;
  ++curveSerial;
  chartHours=periodMode==='rolling'?Number(value.slice(0,-1))*(value.endsWith('d')?24:1):null;
  if (periodMode==='rolling') periodHours=Number(value.slice(0,-1))*(value.endsWith('d')?24:1);
  closeCustomPeriod();updatePeriodControls();refresh();
}));
$('custom-cancel').addEventListener('click',closeCustomPeriod);
$('custom-period-panel').addEventListener('keydown',event=>{
  if(event.key==='Escape') {closeCustomPeriod();$('custom-period-button').focus();}
  if(event.key==='Enter') {event.preventDefault();$('custom-apply').click();}
});
$('custom-apply').addEventListener('click',()=>{
  const from=$('custom-from').value, to=$('custom-to').value;
  if (!from || !to || to<=from || !$('custom-from').checkValidity() || !$('custom-to').checkValidity()) {
    $('custom-period-error').textContent=t('Укажите даты и время: конец должен быть позже начала');
    $('custom-period-error').hidden=false;return;
  }
  customRange={from,to};periodMode='custom';
  chartFollowsPeriod=true;chartHours=null;++curveSerial;
  closeCustomPeriod();updatePeriodControls();refresh();
});
$('export-chats').addEventListener('click',()=>download('chats'));$('export-models').addEventListener('click',()=>download('models'));
function paceDuration(seconds) {
  const minutes=Math.max(1,Math.round(seconds/60));
  if(minutes<60)return t`${number(minutes)} мин`;
  const hours=Math.floor(minutes/60), rest=minutes%60;
  if(hours<24)return rest?t`${number(hours)} ч ${number(rest)} мин`:t`${number(hours)} ч`;
  const days=Math.floor(hours/24);
  return t`${number(days)} д ${number(hours%24)} ч`;
}
function quotaDial(value, maximum, mode='speed') {
  const fuel=mode!=='speed', remaining=mode==='remaining';
  const known=Number.isFinite(value);
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 220 120');svg.setAttribute('aria-hidden','true');
  if(fuel)svg.classList.add('fuel-dial');
  const shape=(tag,attrs)=>{
    const node=document.createElementNS(svg.namespaceURI,tag);
    for(const [key,attribute] of Object.entries(attrs))node.setAttribute(key,String(attribute));
    svg.append(node);return node;
  };
  const point=(ratio,radius)=>{const angle=Math.PI*(1-ratio);return [110+Math.cos(angle)*radius,110-Math.sin(angle)*radius];};
  const ticks=remaining?[0,25,50,75,100]:fuel?[0,.1,.3,.6,1,2,3,4,5,6,7]:[0,1,2,3,4,5,10,20,30,40,50,100];
  const halfway=fuel?4:5;
  const tickPosition=index=>remaining?index/(ticks.length-1):index<=halfway?index/halfway*.5:.5+(index-halfway)/(ticks.length-1-halfway)*.5;
  const position=amount=>{
    if(amount<=0)return 0;
    if(amount>=maximum)return 1;
    const upper=ticks.findIndex(tick=>tick>=amount),lower=upper-1;
    const fraction=(amount-ticks[lower])/(ticks[upper]-ticks[lower]);
    return tickPosition(lower)+fraction*(tickPosition(upper)-tickPosition(lower));
  };
  shape('path',{d:'M 22 110 A 88 88 0 0 1 198 110',class:'speed-dial-track'});
  if(known&&value>0){
    const ratio=position(value),[x,y]=point(ratio,88);
    shape('path',{d:`M 22 110 A 88 88 0 0 1 ${x} ${y}`,class:'speed-dial-fill'});
  }
  if(fuel){
    const [x,y]=point(position(remaining?15:.3),88);
    shape('path',{d:`M 22 110 A 88 88 0 0 1 ${x} ${y}`,class:'fuel-dial-reserve'});
  }else{
    const [x,y]=point(position(40),88);
    shape('path',{d:`M ${x} ${y} A 88 88 0 0 1 198 110`,class:'speed-dial-cutoff'});
  }
  for(const amount of ticks){
    const ratio=position(amount),[x1,y1]=point(ratio,76),[x2,y2]=point(ratio,83),[x,y]=point(ratio,102);
    shape('line',{x1,y1,x2,y2,class:'speed-dial-tick'});
    const label=shape('text',{x,y:y+4,'text-anchor':'middle',class:'speed-dial-label'});
    label.textContent=remaining?percent(amount):number(amount);
  }
  if(known){
    const [x,y]=point(position(value),65);
    shape('line',{x1:110,y1:110,x2:x,y2:y,class:'speed-dial-needle'});
    shape('circle',{cx:110,cy:110,r:6,class:'speed-dial-hub'});
  }else{
    const missing=shape('text',{x:110,y:90,'text-anchor':'middle',class:'speed-dial-missing'});missing.textContent='—';
  }
  const unit=shape('text',{x:110,y:60,'text-anchor':'middle',class:'speed-dial-unit'});
  unit.textContent=remaining?'%':fuel?t('дни'):t('%/час');
  return svg;
}
function renderPace(quota) {
  const pace=quota.pace;
  const forecastStatus=pace?.status==='ok'?pace.forecast_status:pace?.status;
  const row=document.createElement('article');row.className='quota-meter quota-speedometer';
  const heading=document.createElement('div');heading.className='quota-speed-heading';heading.textContent=t('Лимит и темп расхода');
  const body=document.createElement('div');body.className='quota-speed-body';
  const readout=document.createElement('div');readout.className='quota-speed-readout';
  const speed=document.createElement('strong'), forecast=document.createElement('strong');
  const forecastNote=document.createElement('span');forecastNote.className='quota-range-note';
  speed.textContent='—';
  const messages={
    insufficient:'Мало данных',
    below_resolution:'Ниже точности счётчика',
    quiet:'Пауза',
    stale:'Снимок устарел',
    reset_due:'Нет свежего снимка',
    inconsistent:'Противоречивые снимки',
    exhausted:'Лимит исчерпан',
  };
  forecast.textContent='—';
  forecastNote.textContent=t(messages[forecastStatus]||messages.insufficient);
  if(pace?.status==='ok'){
    const value=new Intl.NumberFormat(locale(),{maximumFractionDigits:2}).format(pace.pp_per_hour);
    speed.textContent='≈ '+value;
    if(forecastStatus==='ok'){
      forecast.textContent='≈ '+paceDuration(pace.eta_seconds);
      forecastNote.textContent=t('до 0%');
      if(pace.reset_before_exhaustion)forecastNote.textContent+=' · '+t('сброс раньше');
    }
  }
  if(forecastStatus==='exhausted'){
    forecast.textContent=t('0 мин');
  }
  row.title=t('Средний расход за выбранный период: прирост счётчика / время наблюдений. Паузы учтены; короткие пики сглаживаются усреднением. Минимум 15 минут и 2 п.п. расхода. Пробелы более 30 минут, сбросы и понижения не соединяются. Прогноз требует свежего снимка. %/час — процентные пункты лимита в час.');
  const known=pace?.status==='ok'&&Number.isFinite(pace.pp_per_hour);
  const rate=known?pace.pp_per_hour:null;
  const maximum=100;
  const speedInstrument=document.createElement('div');speedInstrument.className='quota-instrument';
  const speedCaption=document.createElement('span');speedCaption.className='quota-instrument-caption';speedCaption.textContent=t('Средний расход за период');
  speedInstrument.title=t('Шкала 0–100 %/час, отсечка на 100. Первая половина дуги: 0–1–2–3–4–5; вторая: 10–20–30–40–50–100. Число показывает фактическую оценку, даже выше отсечки.');
  const coverageNote=pace?.span_seconds>0?t`Наблюдения: ${paceDuration(pace.span_seconds)} · ${percent(pace.coverage_percent)} периода`:t('Нет интервалов наблюдений');
  speedInstrument.title+='\n'+row.title+'\n'+coverageNote;
  readout.append(speed);
  speedInstrument.append(speedCaption,quotaDial(rate,maximum),readout);
  const fuelInstrument=document.createElement('div');fuelInstrument.className='quota-instrument quota-fuel-instrument';
  const fuelCaption=document.createElement('span');fuelCaption.className='quota-instrument-caption';fuelCaption.textContent=t('Запас времени');
  const reserveDays=(forecastStatus==='ok'||forecastStatus==='exhausted')&&Number.isFinite(pace.eta_seconds)&&pace.eta_seconds>=0?pace.eta_seconds/86400:null;
  const fuelReadout=document.createElement('div');fuelReadout.className='quota-speed-readout quota-range-readout';
  fuelReadout.append(forecast);
  fuelInstrument.title=t('Шкала запаса времени: 0–7 дней до 0% при текущем темпе. Первая половина дуги: 0–0,1–0,3–0,6–1; вторая: 2–3–4–5–6–7. Прогноз больше недели: стрелка на 7, число показывает полное время. Без прогноза стрелка скрыта.');
  fuelInstrument.title+='\n'+forecastNote.textContent;
  fuelInstrument.append(fuelCaption,quotaDial(reserveDays,7,'time'),fuelReadout);
  const balanceInstrument=document.createElement('div');balanceInstrument.className='quota-instrument quota-balance-instrument';
  const balanceCaption=document.createElement('span');balanceCaption.className='quota-instrument-caption';balanceCaption.textContent=t('Остаток 7-дневного лимита');
  const used=quota.latest?.used_percent;
  const remaining=Number.isFinite(used)?Math.max(0,Math.min(100,100-used)):null;
  const balanceReadout=document.createElement('div');balanceReadout.className='quota-speed-readout';
  const balanceValue=document.createElement('strong');balanceValue.textContent=remaining==null?'—':percent(remaining);
  balanceInstrument.title=quota.latest?t`За период: ${percent(quota.period.observed_growth_pp)}`:t('Нет снимка');
  balanceReadout.append(balanceValue);
  balanceInstrument.append(balanceCaption,quotaDial(remaining,100,'remaining'),balanceReadout);
  body.append(balanceInstrument,speedInstrument,fuelInstrument);row.append(heading,body);return row;
}
function renderQuota(data) {
  const quota=data.quota;$('quota-cards').replaceChildren();
  $('quota-cards').append(renderPace(quota));
  const coverage=data.summary.total?data.summary.quota_covered_tokens/data.summary.total*100:0;
  const latestTime=quota.latest?dateTime(new Date(quota.latest.timestamp*1000)):t('нет снимка');
  const resetTime=quota.latest?dateTime(new Date(quota.latest.reset_at*1000)):t('неизвестен');
  $('quota-info').textContent=t`Общий счётчик не зависит от фильтра проекта / модели. Последний снимок: ${latestTime} МСК; сброс: ${resetTime} МСК. Доли чатов приблизительные: токены взвешены по кредитным тарифам Standard, прямой формулы списания подписки нет. Покрытие оценкой: ${percent(coverage)} токенов. Без распределения: ${percent(quota.unassigned_block_pp)} наблюдаемого прироста; до исходных снимков: ${percent(quota.period.baseline_not_attributed_pp)}. ${quota.preliminary?t('Последний блок предварительный; оценка меняется при новых снимках.'):''} ${quota.period.windows.length>1?t('Период включает несколько циклов: расход суммируется и может превышать 100%.'):''} Ноль изменений счётчика не означает бесплатную работу.`;
  const models=new Map();
  for(const row of data.models){const model=models.get(row.model)||{label:row.model,value:0,total:0,covered:0,fresh:0,output:0,cached:0};model.value+=row.quota_pp||0;model.total+=row.total;for(const key of ['fresh','output','cached'])model[key]+=row[key];model.covered+=row.quota_covered_tokens||0;models.set(row.model,model);}
  drawQuotaModels([...models.values()].sort((a,b)=>b.value-a.value).map(row=>({...row,display:quotaText({quota_pp:row.value,quota_covered_tokens:row.covered}),detail:t`${number(row.total)} токенов`,components:[{label:t('Новый вход'),value:row.fresh},{label:t('Выход'),value:row.output},{label:t('Кеш'),value:row.cached}]})));
  if(curveData) drawCurve(curveData.curve,curveData);
}
function updateChartControls() {
  for(const button of document.querySelectorAll('[data-hours]')) button.setAttribute('aria-pressed',String((!chartFollowsPeriod || periodMode==='rolling') && Number(button.dataset.hours)===chartHours));
  for(const button of document.querySelectorAll('[data-clock]')) button.setAttribute('aria-pressed',String(Number(button.dataset.clock)===clockFormat));
}
async function refreshCurve(range) {
  const serial=++curveSerial;
  try {
    const params=range?new URLSearchParams({first_time:range.first_time,final_time:range.final_time}):new URLSearchParams({hours:chartHours});
    const response=await fetch('/api/curve?'+params);
    if(!response.ok) throw new Error();
    const data=await response.json();
    if(serial!==curveSerial) return;
    curveData=data; $('curve-error').hidden=true; drawCurve(data.curve,data);
  } catch {
    if(serial!==curveSerial)return;
    curveData=null; drawCurve([]); $('curve-error').textContent=t('Не удалось загрузить график'); $('curve-error').hidden=false;
  }
}
for(const button of document.querySelectorAll('[data-hours]')) button.addEventListener('click',()=>{
  chartFollowsPeriod=false;chartHours=Number(button.dataset.hours);try{localStorage.setItem('codex-chart-hours',String(chartHours));}catch{}updateChartControls();refreshCurve();
});
for(const button of document.querySelectorAll('[data-clock]')) button.addEventListener('click',()=>{
  clockFormat=Number(button.dataset.clock);try{localStorage.setItem('codex-clock-format',String(clockFormat));}catch{}updateChartControls();if(current)render(current);
});
updateChartControls();
let refreshInterval = 30;
try { refreshInterval = Number(localStorage.getItem('codex-refresh-interval')) || 30; } catch {}
if (![30,60,300,900,1800,3600].includes(refreshInterval)) refreshInterval = 30;
$('refresh-interval').value = String(refreshInterval);
let refreshTimer;
function scheduleRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(refresh, refreshInterval * 1000);
}
// The server owns this setting; null means automatic project detection.
let projectsRoot = null, settingsLoaded = false, settingsBusy = true;
let settingsMessage = 'Загрузка…', settingsError = '', settingsErrorDetail = '';
function renderProjectSettings() {
  $('project-settings').setAttribute('aria-busy', String(settingsBusy));
  const currentPath = settingsLoaded
    ? (projectsRoot ?? t('Включено автоопределение')) : t('Путь пока неизвестен');
  $('project-root-current').textContent = settingsBusy ? t(settingsMessage)
    : settingsMessage === 'Выбор отменён' ? t(settingsMessage) + ' · ' + currentPath : currentPath;
  for (const id of ['project-root-pick','project-root-reset','project-root-save']) $(id).disabled = settingsBusy;
  $('project-root-input').disabled = settingsBusy;
  $('project-root-close').disabled = settingsBusy;
  $('project-root-error').textContent = t(settingsError) + (settingsErrorDetail ? ': ' + t(settingsErrorDetail) : '');
  $('project-root-error').hidden = !settingsError;
}
function openProjectPath() {
  $('project-root-form').hidden = false;
  $('project-root-input').value = projectsRoot ?? '';
  $('project-root-input').focus();
}
function closeProjectPath() {
  $('project-root-form').hidden = true;
  $('project-root-pick').focus();
}
async function settingsRequest(url, body) {
  const response = await fetch(url, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || response.statusText);
    error.code = data.code;
    throw error;
  }
  if (data.projects_root !== null && typeof data.projects_root !== 'string') throw new Error(t('Некорректный ответ монитора'));
  return data;
}
async function loadProjectSettings() {
  try {
    const data = await settingsRequest('/api/settings');
    projectsRoot = data.projects_root; settingsLoaded = true; settingsMessage = '';
  } catch (error) {
    settingsError = 'Не удалось загрузить настройку папки'; settingsErrorDetail = error.message; settingsMessage = '';
  } finally { settingsBusy = false; renderProjectSettings(); }
}
async function changeProjectRoot(action, value) {
  if (settingsBusy) return;
  settingsBusy = true; settingsError = ''; settingsErrorDetail = '';
  settingsMessage = action === 'pick' ? 'Выберите папку в системном диалоге…' : 'Сохранение…';
  renderProjectSettings();
  let changed = false, showManual = false;
  try {
    const data = await settingsRequest(action === 'pick' ? '/api/projects/pick' : '/api/settings', action === 'pick' ? {} : {projects_root:value});
    if (action === 'pick' && data.cancelled) { settingsMessage = 'Выбор отменён'; }
    else {
      projectsRoot = data.projects_root; settingsLoaded = true;
      settingsMessage = projectsRoot === null ? 'Включено автоопределение' : 'Папка сохранена';
      // Invalidate a pending report before it can restore the old project list.
      ++refreshSerial; ++curveSerial;
      options('project', [], t('Все проекты')); $('project-label').textContent = t('Проект'); chatPage = 1; chatFilterKey = null;
      changed = true;
      $('project-root-form').hidden = true;
    }
  } catch (error) {
    settingsMessage = '';
    showManual = error.code === 'folder_picker_unavailable';
    settingsError = showManual ? 'Системный выбор папки недоступен. Введите путь вручную.' : 'Не удалось изменить папку';
    settingsErrorDetail = showManual ? '' : error.message;
  } finally { settingsBusy = false; renderProjectSettings(); }
  if (showManual) openProjectPath();
  if (changed) { $('project-root-pick').focus(); await refresh(); }
}
$('project-root-pick').addEventListener('click', () => changeProjectRoot('pick'));
$('project-root-reset').addEventListener('click', () => changeProjectRoot('save', null));
$('project-root-close').addEventListener('click', closeProjectPath);
$('project-root-form').addEventListener('keydown', event => {
  if (event.key === 'Escape' && !settingsBusy) { event.preventDefault(); closeProjectPath(); }
});
$('project-root-form').addEventListener('submit', event => {
  event.preventDefault();
  const value = $('project-root-input').value.trim();
  if (!value) { $('project-root-input').value = ''; $('project-root-input').reportValidity(); return; }
  changeProjectRoot('save', value);
});
$('refresh-interval').addEventListener('change', event => {
  refreshInterval = Number(event.target.value);
  try { localStorage.setItem('codex-refresh-interval', String(refreshInterval)); } catch {}
  scheduleRefresh();
});
renderProjectSettings();loadProjectSettings();updatePeriodControls();refresh();scheduleRefresh();
