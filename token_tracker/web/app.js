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
function renderChats() {
  if (!current) return;
  const term = $('search').value.toLocaleLowerCase(); $('chats').replaceChildren();
  const filterKey = query().toString()+'|'+term;
  if (filterKey !== chatFilterKey) { chatPage = 1; chatFilterKey = filterKey; }
  const rows = current.chats.filter(row => !term || (row.title+' '+row.thread+' '+row.project).toLocaleLowerCase().includes(term));
  const size = chatPageSize === 'all' ? Math.max(1,rows.length) : Number(chatPageSize);
  const pages = Math.max(1,Math.ceil(rows.length/size));
  chatPage = Math.min(chatPage,pages);
  const start = (chatPage-1)*size;
  for (const row of rows.slice(start,start+size)) {
    const tr = document.createElement('tr'); const td = cell(tr, '');
    const link = document.createElement('a'); link.href = 'codex://threads/'+encodeURIComponent(row.thread); link.textContent = row.title; link.className = 'chat-title'; td.append(link);
    const meta = document.createElement('span'); meta.textContent = t(row.project)+' · '+row.thread; meta.className = 'chat-meta'; td.append(meta);
    cell(tr, row.model+' / '+row.effort); cell(tr,number(row.main_calls)+' / '+number(row.subagent_calls));
    for (const key of ['fresh','cached','output','total']) cell(tr,number(row[key]));
    cell(tr,credits(row.estimated_credits)); $('chats').append(tr);
    cell(tr,quotaText(row));
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
function renderQuota(data) {
  const quota=data.quota;$('quota-cards').replaceChildren();$('chat-quota-card').replaceChildren();
  const currentUsed=quota.latest?.used_percent;
  const remainingText=amount=>percent(Math.max(0,100-amount));
  const cards=[
    {kind:'account',label:t('Остаток · аккаунт'),amount:currentUsed,text:currentUsed==null?t('Нет снимка'):remainingText(currentUsed),detail:currentUsed==null?t('Нет снимка оставшегося лимита'):t('По показаниям OpenAI')},
    {kind:'period',label:t('Потрачено за период'),amount:quota.latest?quota.period.observed_growth_pp:null,text:quota.latest?percent(quota.period.observed_growth_pp):t('Нет снимка'),detail:t('С учётом сбросов · 100% = один недельный лимит')},
    {kind:'estimate',label:t('Остаток после выбранных чатов · оценка'),amount:data.summary.quota_covered_tokens&&data.summary.quota_pp?data.summary.quota_pp:null,text:data.summary.quota_covered_tokens&&data.summary.quota_pp?'≈ '+remainingText(data.summary.quota_pp):t('Нет оценки'),detail:t('100% минус оценка выбранных чатов')}
  ];
  for(const [index,item] of cards.entries()){
    const card=document.createElement('article');card.className='quota-meter quota-meter-'+item.kind;
    const heading=document.createElement('div');heading.className='quota-meter-heading';
    const caption=document.createElement('span');caption.id='quota-caption-'+index;caption.textContent=item.label;
    const value=document.createElement('strong');value.textContent=item.text;heading.append(caption,value);
    const known=item.amount!=null&&Number.isFinite(item.amount);
    const spent=item.kind==='period';
    const maximum=spent&&known?Math.max(100,Math.ceil(item.amount/100)*100):100;
    const track=document.createElement('div');track.className='quota-meter-track';track.setAttribute('role','progressbar');track.setAttribute('aria-labelledby',caption.id);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(maximum));
    track.setAttribute('aria-valuetext',item.text);
    if(known){
      const progress=spent?Math.max(0,item.amount):Math.max(0,Math.min(100,100-item.amount));
      const fill=document.createElement('div');fill.className='quota-meter-fill';fill.style.width=(progress/maximum*100)+'%';track.append(fill);
      track.setAttribute('aria-valuenow',String(progress));
    }else{card.classList.add('quota-meter-unknown');}
    const footer=document.createElement('div');footer.className='quota-meter-footer';
    const detail=document.createElement('span');detail.textContent=!spent&&known&&item.amount>100?t('Расход превысил недельный лимит'):item.detail;
    const scale=document.createElement('span');scale.textContent='0–'+maximum+'%';scale.setAttribute('aria-hidden','true');footer.append(detail,scale);
    card.append(heading,track,footer);$(item.kind==='estimate'?'chat-quota-card':'quota-cards').append(card);
  }
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
