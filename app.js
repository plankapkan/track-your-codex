// UI language is stored locally; source data and CSV values are preserved.
let language;
try { language = localStorage.getItem('codex-usage-language'); } catch {}
if (!['ru','en'].includes(language)) language = navigator.language?.startsWith('ru') ? 'ru' : 'en';
const EN = {
  "Тема": "Theme",
  "Тёмная тема": "Dark theme",
  "Значения на графике": "Chart values",
  "Остаток лимита — 100% минус расход по показаниям OpenAI. Сбросы отображаются отдельными линиями. Проект и модель этот график не фильтруют. Выбор периода сверху меняет интервал графика.": "Remaining limit is 100% minus OpenAI's usage reading. Resets appear as separate lines. Project and model filters do not affect this chart. Choosing a period above also changes the chart interval.",
  "Остаток лимита": "Remaining limit",
  "Остаток · слева": "Remaining · left axis",
  "Остаток лимита подписки и накопленные токены": "Remaining subscription limit and cumulative tokens",
  "Линии графика": "Chart series",
  "Токены · справа": "Tokens · right axis",
  "Токены · логарифмическая шкала": "Tokens · logarithmic scale",
  "Шкалы подстраиваются под видимые линии. Шкала токенов логарифмическая: небольшие значения различимы рядом с большими.": "Axes adjust to visible lines. The token scale is logarithmic so small values remain visible alongside large ones.",
  "Лимит · слева": "Limit · left axis",
  "Токенов за интервал в локальных журналах нет": "No tokens in local logs for this interval",
  "Токены накапливаются с начала выбранного интервала: общий объём и отдельно по моделям, включая помощников. Шкала токенов справа. Нажмите на подпись линии, чтобы скрыть или показать её.": "Tokens accumulate from the start of the selected interval: total and by model, including subagents. Token scale is on the right. Click a series label to hide or show it.",
  "Интервал графика": "Chart interval",
  "Формат времени": "Time format",
  "Не удалось загрузить график": "Could not load chart",
  "Расход Codex": "Codex Usage",
  "ЛОКАЛЬНЫЙ МОНИТОР": "LOCAL MONITOR",
  "Токены по моделям и чатам.": "Tokens by model and chat.",
  "Частота опроса": "Refresh interval",
  "30 с": "30 sec",
  "1 минута": "1 minute",
  "5 минут": "5 minutes",
  "15 минут": "15 minutes",
  "30 минут": "30 minutes",
  "1 час": "1 hour",
  "Загрузка…": "Loading…",
  "С даты": "From",
  "По дату": "To",
  "Проект": "Project",
  "Модель": "Model",
  "Все проекты": "All projects",
  "Все модели": "All models",
  "Показать": "Apply",
  "Период": "Period",
  "Количество": "Amount",
  "Единица периода": "Period unit",
  "Готовые периоды": "Quick periods",
  "Часы": "Hours",
  "Дни": "Days",
  "Недельный цикл": "Weekly cycle",
  "После сброса": "Since reset",
  "Сброс недельного лимита": "Weekly limit reset",
  "Произвольный период": "Custom period",
  "От": "From",
  "До": "To",
  "Время — Москва": "Moscow time",
  "Применить": "Apply",
  "Закрыть": "Close",
  "Укажите даты и время: конец должен быть позже начала": "Choose dates and times: the end must be after the start",
  "Последний проход": "Last scan",
  "Сегодня": "Today",
  "24ч": "24h",
  "5ч": "5h",
  "1ч": "1h",
  "Последние": "Last",
  "7 дней": "7 days",
  "30 дней": "30 days",
  "Включать подагентов в родительский чат": "Group subagents with their parent chat",
  "Текущий недельный цикл — после последнего сброса лимита": "Current weekly cycle — since the last limit reset",
  "Расход недельного лимита": "Weekly limit usage",
  "Расход по моделям, ≈ % лимита": "Usage by model, ≈ % of limit",
  "Оценочное распределение расхода лимита по моделям": "Estimated limit usage and token totals by model",
  "Доли распределены по токенам с весами тарифов Standard. Фильтр не перераспределяет расход других чатов. Токены — весь объём за выбранный период, включая токены без оценки лимита.": "Shares use Standard credit rates as token weights. Filters do not redistribute other chats’ usage. Token totals include all tokens for the selected period, including tokens without a limit estimate.",
  "Счётчик аккаунта": "Account usage",
  "Наблюдаемое значение недельного лимита": "Observed weekly limit usage",
  "Показания OpenAI из журналов. Сбросы отображаются отдельными линиями. Проект и модель этот график не фильтруют. Выбор периода сверху меняет интервал графика.": "OpenAI readings from local logs. Resets appear as separate lines. Project and model filters do not affect this chart. Choosing a period above also changes the chart interval.",
  "Итоги": "Totals",
  "Вход включает кеш. Рассуждения входят в выход и не прибавляются повторно. Один запрос пользователя может содержать много шагов модели.": "Input includes cached tokens. Reasoning is included in output and is not counted again. A user request may involve many model steps.",
  "По моделям": "By model",
  "Скачать CSV": "Download CSV",
  "Модель / рассуждение": "Model / reasoning",
  "Шаги": "Steps",
  "Новый вход": "Fresh input",
  "Кеш": "Cached",
  "Выход": "Output",
  "Всего": "Total",
  "Кредиты ≈": "Credits ≈",
  "Недельный лимит ≈": "Weekly limit ≈",
  "По чатам и моделям": "By chat and model",
  "Фильтр по таблице чатов": "Filter chats",
  "Фильтр по названию или ID": "Filter by title or ID",
  "Строк на странице": "Rows per page",
  "Страницы чатов": "Chat pages",
  "Все": "All",
  "Назад": "Previous",
  "Далее": "Next",
  "Строки {}–{} из {}": "Rows {}–{} of {}",
  "Чат / проект": "Chat / project",
  "основной / помощники": "main / subagents",
  "За этот период данных нет.": "No data for this period.",
  "Сравнение Astra и Sol 6.1": "Astra and Sol 6.1 comparison",
  "Пересчёт одинаковых токенов по тарифам кредитов Standard. Это оценка, а не денежный счёт и не измеренная экономия недельного лимита. При другой модели изменятся число шагов и качество результата.": "The same tokens recalculated using Standard credit rates. This estimate is not a monetary bill or measured weekly limit savings. Switching models can change the number of steps and result quality.",
  "Стоимость одинаковых токенов": "Cost of the same tokens",
  "Сравнение стоимости одинакового состава токенов": "Cost comparison for the same token mix",
  "Кредиты Standard; одинаковые новый вход, кеш и выход. Соотношение цен не доказывает такое же соотношение недельного лимита.": "Standard credits for the same fresh input, cache and output. The price ratio does not establish the same ratio for weekly limit usage.",
  "Журналы читаются локально. Монитор не обращается к моделям и не тратит токены. Облачные чаты и данные с других компьютеров могут отсутствовать.": "Logs are read locally. The monitor does not call models or spend tokens. Cloud chats and data from other computers may be missing.",
  "Лимит подписки": "Subscription usage",
  "Тарифы кредитов": "Credit rates",
  "Диагностика всей проиндексированной истории": "Diagnostics for all indexed history",
  "Вход из кеша": "Cached input",
  "Нет тарифа": "No rate",
  "Нет оценки": "No estimate",
  "≈ <0,1%": "≈ <0.1%",
  "Ошибка чтения отчёта": "Could not read report",
  "Выход, включая рассуждения": "Output, including reasoning",
  "Всего токенов": "Total tokens",
  "Выберите период с данными.": "Select a period with data.",
  "выполняется": "in progress",
  "Тарифы на ": "Rates as of ",
  " кредитов": " credits",
  "Замечаний к обработке счётчиков нет.": "No counter processing issues.",
  "Сброс накопительного счётчика: использован расход последнего шага": "Counter reset: used last_token_usage",
  "Пропущены записи с неполным или противоречивым составом токенов": "Inconsistent token counters: event not counted",
  "Модель не указана: токены отнесены к unknown": "Token event has unknown model",
  "Сброс части счётчика: использован расход последнего шага": "Component counter reset: used last_token_usage",
  "Начальный счётчик без расхода последнего шага: принят за исходную точку": "First counter lacks last_token_usage: treated as baseline",
  "Нет связи с монитором": "Cannot connect to monitor",
  "Не удалось выгрузить CSV": "CSV export failed",
  "Недостаточно данных для диаграммы": "Not enough data for this chart",
  "Снимков недельного счётчика за этот период нет": "No weekly limit snapshots for this period",
  "Аккаунт · последний снимок OpenAI": "Account · latest OpenAI snapshot",
  "Нет снимка": "No snapshot",
  "Прирост за период · аккаунт": "Account · increase during period",
  "Выбранные чаты · оценка": "Selected chats · estimate",
  "По показаниям OpenAI": "From OpenAI readings",
  "Остаток · аккаунт": "Remaining · account",
  "Потрачено за период": "Spent during period",
  "Остаток после выбранных чатов · оценка": "Remaining after selected chats · estimate",
  "С учётом сбросов · 100% = один недельный лимит": "Including resets · 100% = one weekly allowance",
  "100% минус оценка выбранных чатов": "100% minus estimated selected chat usage",
  "Расход превысил недельный лимит": "Usage exceeded one weekly allowance",
  "нет снимка": "no snapshot",
  "неизвестен": "unknown",
  "Последний блок предварительный; оценка меняется при новых снимках.": "The latest block is provisional; estimates change as new snapshots arrive.",
  "Период включает несколько циклов: расход суммируется и может превышать 100%.": "This period spans several cycles: usage is summed and may exceed 100%.",
  "Без проекта": "No project",
  " МСК": " MSK",
  "Индексация {} / {}": "Indexing {} / {}",
  "Монитор работает · {} записей": "Monitor running · {} events",
  "Этот же объём токенов: Astra ≈ {} кредитов; Sol 6.1 ≈ {} кредитов. Разница — {}%, или {} раза.": "The same tokens: Astra ≈ {} credits; Sol 6.1 ≈ {} credits. Difference: {}%, or {}×.",
  "Последний проход: {} · {} журналов. Период включает обе выбранные даты, время — Москва.": "Last scan: {} · {} logs. Both selected dates are included; times are Moscow time.",
  "Общий счётчик не зависит от фильтра проекта / модели. Последний снимок: {} МСК; сброс: {} МСК. Доли чатов приблизительные: токены взвешены по кредитным тарифам Standard, прямой формулы списания подписки нет. Покрытие оценкой: {} токенов. Без распределения: {} наблюдаемого прироста; до исходных снимков: {}. {} {} Ноль изменений счётчика не означает бесплатную работу.": "Account usage is independent of project / model filters. Latest snapshot: {} MSK; reset: {} MSK. Chat shares are approximate: tokens are weighted by Standard credit rates; the subscription usage formula is unknown. Estimate coverage: {} of tokens. Unassigned: {} of observed growth; before baseline snapshots: {}. {} {} An unchanged counter does not mean the work was free.",
  "Осталось {} недельного лимита": "{} of weekly limit remaining",
  "Нет снимка оставшегося лимита": "No snapshot of remaining limit",
  "{} токенов": "{} tokens"
};
const locale = () => language === 'en' ? 'en-US' : 'ru-RU';
function t(source, ...values) {
  const key = Array.isArray(source) ? source.join('{}') : source;
  const text = language === 'en' ? (EN[key] ?? key) : key;
  let index = 0;
  return text.replace(/\{\}/g, () => String(values[index++]));
}
const staticText = [];
const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node = walker.currentNode;
  if (node.parentElement?.closest('script,style')) continue;
  if (/[А-Яа-яЁё]/.test(node.textContent)) staticText.push([node, node.textContent]);
}
const staticAttrs = [...document.querySelectorAll('[aria-label],[placeholder]')].flatMap(element => ['aria-label','placeholder'].filter(attr => element.hasAttribute(attr)).map(attr => [element,attr,element.getAttribute(attr)]));
function applyLanguage() {
  document.documentElement.lang = language;
  for (const [node, text] of staticText) node.textContent = text.replace(/^(\s*)([\s\S]*?)(\s*)$/, (_,before,body,after) => before+t(body)+after);
  for (const [element,attr,text] of staticAttrs) element.setAttribute(attr,t(text));
  document.getElementById('language').value = language;
}
applyLanguage();
document.getElementById('language').addEventListener('change', event => {
  language = event.target.value;
  try { localStorage.setItem('codex-usage-language',language); } catch {}
  applyLanguage();
  if (current) render(current);
});
const $ = id => document.getElementById(id);
const number = value => new Intl.NumberFormat(locale()).format(value);
const credits = value => value == null ? t('Нет тарифа') : new Intl.NumberFormat(locale(), {maximumFractionDigits:2}).format(value);
let current = null;
let periodMode = 'cycle';
let periodHours = 168;
let customRange = null;
let chatPage = 1, chatPageSize = '10', chatFilterKey = null;
try { chatPageSize = localStorage.getItem('codex-chat-page-size') || '10'; } catch {}
if (!['10','50','100','all'].includes(chatPageSize)) chatPageSize = '10';
let refreshSerial = 0;
let curveSerial = 0;
let curveData = null;
let chartHours = 24, clockFormat = 24;
let chartFollowsPeriod = true;
try {chartHours = Number(localStorage.getItem('codex-chart-hours')) || 24; clockFormat = Number(localStorage.getItem('codex-clock-format')) || 24;} catch {}
if (![1,5,24,168,720].includes(chartHours)) chartHours = 24;
if (![12,24].includes(clockFormat)) clockFormat = 24;
const dateTime = date => date.toLocaleString(locale(), {timeZone:'Europe/Moscow',hour12:clockFormat===12});
const percent = value => new Intl.NumberFormat(locale(),{maximumFractionDigits:1}).format(value)+'%';
function quotaText(row) { return !row.quota_covered_tokens || !row.quota_pp ? t('Нет оценки') : row.quota_pp<0.05 ? t('≈ <0,1%') : '≈ '+percent(row.quota_pp); }
function localDate(date) { return new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Moscow'}).format(date); }
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
function svgNode(name,attrs={},text='') {const element=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [key,value] of Object.entries(attrs))element.setAttribute(key,String(value));if(text)element.textContent=text;return element;}
function drawBars(id,rows) {
  const svg=$(id);svg.replaceChildren();const height=Math.max(100,rows.length*(id==='quota-bars'?118:46)+20);svg.setAttribute('viewBox',`0 0 800 ${height}`);
  if(!rows.length){svg.append(svgNode('text',{x:20,y:45,class:'chart-label'},t('Недостаточно данных для диаграммы')));return;}
  const maximum=Math.max(...rows.map(r=>r.value),0.001);
  rows.forEach((row,i)=>{const y=16+i*(id==='quota-bars'?118:46);svg.append(svgNode('text',{x:8,y:y+18,class:'chart-label'},row.label));svg.append(svgNode('rect',{x:220,y,width:Math.max(1,row.value/maximum*395),height:27,rx:5,class:row.label.includes('astra')?'bar-astra':'bar-sol'}));svg.append(svgNode('text',{x:630,y:y+18,class:'chart-value'},row.display));if(row.detail){svg.append(svgNode('text',{x:220,y:y+47,class:'chart-label'},row.detail));if(row.components){row.components.forEach((part,index)=>{const x=220+index*190;svg.append(svgNode('text',{x,y:y+71,class:'chart-component-label'},part.label));svg.append(svgNode('text',{x,y:y+94,class:'chart-component-value'},number(part.value)));});}const title=svgNode('title',{},row.label+': '+row.display+'; '+row.detail+(row.components?'; '+row.components.map(part=>part.label+': '+number(part.value)).join('; '):''));svg.append(title);}});
}
const hiddenCurveSeries=new Set();
const themeColor = name => getComputedStyle(document.documentElement).getPropertyValue('--'+name).trim();
window.addEventListener('themechange', () => { if (curveData) drawCurve(curveData.curve, curveData); });
function curveModelColor(model) {
  if(model.includes('astra'))return themeColor('orange');
  if(model==='gpt-6.1-sol')return themeColor('purple');
  const palette=['curve-pink','curve-lime','curve-brown','curve-cyan','curve-red'].map(themeColor);
  let hash=0;for(const char of model)hash=(hash*31+char.charCodeAt(0))>>>0;
  return palette[hash%palette.length];
}
function smoothCurvePath(coords) {
  // Reduce subpixel jitter, preserving endpoints. Controls stay within each segment's
  // values so curves cannot overshoot the observed range or create negative tokens.
  const samples=[];
  for(let i=0;i<coords.length;i++){
    const point=coords[i],last=samples.at(-1);
    if(samples.length>1&&Math.floor((point[0]-coords[0][0])/5)===Math.floor((last[0]-coords[0][0])/5)&&i<coords.length-1)samples[samples.length-1]=point;
    else if(last&&point[0]===last[0])samples[samples.length-1]=point;
    else samples.push(point);
  }
  if(!samples.length)return '';
  let path=`M ${samples[0][0]} ${samples[0][1]}`;
  const slope=(a,b)=>(b[1]-a[1])/Math.max(0.001,b[0]-a[0]);
  const tangent=i=>{
    if(i===0)return slope(samples[0],samples[1]);
    if(i===samples.length-1)return slope(samples[i-1],samples[i]);
    const a=slope(samples[i-1],samples[i]),b=slope(samples[i],samples[i+1]);
    return a*b<=0?0:Math.sign(a)*Math.min(Math.abs((a+b)/2),3*Math.abs(a),3*Math.abs(b));
  };
  for(let i=1;i<samples.length;i++){
    const a=samples[i-1],b=samples[i],dx=(b[0]-a[0])/3;
    const clamp=value=>Math.max(Math.min(a[1],b[1]),Math.min(Math.max(a[1],b[1]),value));
    path+=` C ${a[0]+dx} ${clamp(a[1]+tangent(i-1)*dx)} ${b[0]-dx} ${clamp(b[1]-tangent(i)*dx)} ${b[0]} ${b[1]}`;
  }
  return path;
}
function drawCurve(points, bounds) {
  const svg=$('quota-curve');svg.replaceChildren();svg.setAttribute('viewBox','0 0 800 260');
  svg.onpointermove=null;svg.onpointerleave=null;
  const tooltip=$('curve-tooltip');tooltip.hidden=true;
  const legend=$('curve-legend');legend.replaceChildren();
  const tokenPoints=bounds?.tokens?.points||[],models=bounds?.tokens?.models||[];
  if(!points.length&&!tokenPoints.length){svg.append(svgNode('text',{x:20,y:45,class:'chart-label'},t('Недостаточно данных для диаграммы')));return;}
  const left=55,right=700,top=35,bottom=215;
  const first=bounds?.first_time??points[0]?.timestamp??tokenPoints[0].timestamp,last=bounds?.final_time??points.at(-1)?.timestamp??tokenPoints.at(-1).timestamp;
  const remaining=point=>Math.max(0,Math.min(100,100-point.used_percent));
  const quotaValues=hiddenCurveSeries.has('quota')?[]:points.map(remaining);
  const quotaLow=quotaValues.length?Math.min(...quotaValues):0;
  const quotaHigh=quotaValues.length?Math.max(...quotaValues):100;
  const quotaPadding=Math.max(1,(quotaHigh-quotaLow)*0.1);
  const quotaFloor=Math.max(0,Math.floor(quotaLow-quotaPadding));
  const quotaCeiling=Math.min(100,Math.ceil(quotaHigh+quotaPadding));
  const series=[{key:'tokens:total',label:t('Всего токенов'),color:themeColor('green'),get:p=>p.total},...models.map(model=>({key:'tokens:'+model,label:model,color:curveModelColor(model),get:p=>p.models[model]||0}))];
  let tokenMax=1;
  for(const row of series) if(!hiddenCurveSeries.has(row.key)) for(const point of tokenPoints) tokenMax=Math.max(tokenMax,row.get(point));
  // log1p preserves zero and remains linear near zero; all token lines share one scale.
  const tokenKnee=1000;
  const tokenTop=Math.log1p(tokenMax/tokenKnee)*1.04;
  const tokenValue=fraction=>tokenKnee*Math.expm1(fraction*tokenTop);
  const compact=value=>new Intl.NumberFormat(locale(),{notation:'compact',maximumFractionDigits:1}).format(value);
  const x=ts=>left+(ts-first)/Math.max(1,last-first)*(right-left),y=value=>bottom-(value-quotaFloor)/(quotaCeiling-quotaFloor)*(bottom-top),ty=value=>bottom-Math.log1p(value/tokenKnee)/tokenTop*(bottom-top);
  const defs=svgNode('defs'),areas=svgNode('g',{'aria-hidden':'true','pointer-events':'none'});svg.append(defs,areas);
  let gradientIndex=0;
  const shadedPath=(coords,color,opacity)=>{
    const path=smoothCurvePath(coords),id='curve-gradient-'+gradientIndex++;
    const gradient=svgNode('linearGradient',{id,gradientUnits:'userSpaceOnUse',x1:0,x2:0,y1:top,y2:bottom});
    gradient.append(svgNode('stop',{offset:'0%','stop-color':color,'stop-opacity':opacity}),svgNode('stop',{offset:'100%','stop-color':color,'stop-opacity':0.015}));defs.append(gradient);
    if(coords.length>1)areas.append(svgNode('path',{d:path+` L ${coords.at(-1)[0]} ${bottom} L ${coords[0][0]} ${bottom} Z`,fill:`url(#${id})`}));
    return path;
  };
  svg.append(svgNode('text',{x:left,y:16,class:'chart-axis-title'},t('Остаток · слева')));
  svg.append(svgNode('text',{x:right,y:16,'text-anchor':'end',class:'chart-axis-title'},t('Токены · логарифмическая шкала')));
  for(const fraction of [0,0.25,0.5,0.75,1]){const yy=bottom-fraction*(bottom-top);svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,class:'chart-grid'}));if(quotaValues.length)svg.append(svgNode('text',{x:3,y:yy+4,class:'chart-label'},percent(quotaFloor+(quotaCeiling-quotaFloor)*fraction)));if(tokenPoints.length)svg.append(svgNode('text',{x:right+12,y:yy+4,class:'chart-label'},compact(tokenValue(fraction))));}
  const addLegend=(key,label,color,value)=>{
    const button=document.createElement('button');button.type='button';button.className='curve-series';button.setAttribute('aria-pressed',String(!hiddenCurveSeries.has(key)));
    const swatch=document.createElement('span');swatch.className='curve-swatch';swatch.style.backgroundColor=color;
    const caption=document.createElement('span');caption.textContent=label;
    const amount=document.createElement('strong');amount.textContent=value;
    button.append(swatch,caption,amount);button.addEventListener('click',()=>{if(hiddenCurveSeries.has(key))hiddenCurveSeries.delete(key);else hiddenCurveSeries.add(key);drawCurve(points,bounds);});legend.append(button);
  };
  const hoverSeries=[];
  if(points.length){
    addLegend('quota',t('Остаток лимита'),themeColor('blue'),percent(remaining(points.at(-1))));
    if(!hiddenCurveSeries.has('quota')){
      const groups=new Map();for(const point of points){if(!groups.has(point.reset_at))groups.set(point.reset_at,[]);groups.get(point.reset_at).push(point);}
      for(let i=1;i<points.length;i++){
        const before=points[i-1],after=points[i];
        if(before.reset_at===after.reset_at || remaining(after)<=remaining(before))continue;
        const resetTime=before.reset_at>=before.timestamp && before.reset_at<=after.timestamp?before.reset_at:after.timestamp;
        const marker=svgNode('line',{x1:x(resetTime),x2:x(resetTime),y1:y(remaining(before)),y2:y(remaining(after)),class:'quota-reset'});
        marker.append(svgNode('title',{},t('Сброс недельного лимита')+' · '+dateTime(new Date(resetTime*1000))));
        svg.append(marker);
      }
      for(const values of groups.values()){const line=svgNode('path',{d:shadedPath(values.map(p=>[x(p.timestamp),y(remaining(p))]),themeColor('blue'),0.10),class:'quota-line'});svg.append(line);hoverSeries.push({line,label:t('Остаток лимита'),color:themeColor('blue'),first:x(values[0].timestamp),last:x(values.at(-1).timestamp),format:yy=>percent(quotaFloor+(bottom-yy)/(bottom-top)*(quotaCeiling-quotaFloor))});const lastPoint=values.at(-1);svg.append(svgNode('circle',{cx:x(lastPoint.timestamp),cy:y(remaining(lastPoint)),r:4,class:'quota-point'}));}
    }
  }else{const note=document.createElement('p');note.className='note';note.textContent=t('Снимков недельного счётчика за этот период нет');legend.append(note);}
  if(tokenPoints.length){
    for(const row of series){
      addLegend(row.key,row.label,row.color,number(row.get(tokenPoints.at(-1))));
      if(hiddenCurveSeries.has(row.key))continue;
      const line=svgNode('path',{d:shadedPath(tokenPoints.map(point=>[x(point.timestamp),ty(row.get(point))]),row.color,row.key==='tokens:total'?0.18:0.10),fill:'none',stroke:row.color,'stroke-width':row.key==='tokens:total'?2.7:2,class:'token-line'});
      svg.append(line);
      hoverSeries.push({line,label:row.label,color:row.color,first:x(tokenPoints[0].timestamp),last:x(tokenPoints.at(-1).timestamp),format:yy=>'≈ '+number(Math.max(0,Math.round(tokenValue((bottom-yy)/(bottom-top)))))});
    }
  }else{const note=document.createElement('p');note.className='note';note.textContent=t('Токенов за интервал в локальных журналах нет');legend.append(note);}
  const tickCount=5,shortRange=last-first<=86400;
  for(let i=0;i<=tickCount;i++){
    const ts=first+(last-first)*i/tickCount,xx=x(ts),date=new Date(ts*1000);
    svg.append(svgNode('line',{x1:xx,x2:xx,y1:top,y2:bottom,class:'chart-grid chart-time-grid'}));
    const options={timeZone:'Europe/Moscow',...(shortRange?{hour:'2-digit',minute:'2-digit',hour12:clockFormat===12}:{day:'2-digit',month:'2-digit'})};
    svg.append(svgNode('text',{x:xx,y:238,'text-anchor':i===0?'start':i===tickCount?'end':'middle',class:'chart-time-label'},date.toLocaleString(locale(),options)));
    if(shortRange&&[0,tickCount].includes(i))svg.append(svgNode('text',{x:xx,y:255,'text-anchor':i===0?'start':'end',class:'chart-time-date'},date.toLocaleDateString(locale(),{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit'})));
  }
  const crosshair=svgNode('g',{'pointer-events':'none',visibility:'hidden','aria-hidden':'true'});svg.append(crosshair);
  const hideHover=()=>{crosshair.setAttribute('visibility','hidden');tooltip.hidden=true;};
  svg.onpointerleave=hideHover;
  svg.onpointermove=event=>{
    const rect=svg.getBoundingClientRect(),xx=(event.clientX-rect.left)/rect.width*800,yy=(event.clientY-rect.top)/rect.height*260;
    if(xx<left||xx>right||yy<top||yy>bottom){hideHover();return;}
    crosshair.replaceChildren(svgNode('line',{x1:xx,x2:xx,y1:top,y2:bottom,class:'curve-crosshair'}));crosshair.setAttribute('visibility','visible');
    const stamp=first+(xx-left)/(right-left)*(last-first);
    const heading=document.createElement('div');heading.className='curve-tooltip-time';heading.textContent=new Date(stamp*1000).toLocaleString(locale(),{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:clockFormat===12});tooltip.replaceChildren(heading);
    let count=0;
    for(const row of hoverSeries){
      if(xx<row.first||xx>row.last)continue;
      let low=0,high=row.line.getTotalLength();
      for(let i=0;i<22;i++){const mid=(low+high)/2;if(row.line.getPointAtLength(mid).x<xx)low=mid;else high=mid;}
      const point=row.line.getPointAtLength((low+high)/2);
      crosshair.append(svgNode('circle',{cx:xx,cy:point.y,r:4,fill:row.color,stroke:'white','stroke-width':2}));
      const item=document.createElement('div');item.className='curve-tooltip-row';
      const swatch=document.createElement('span');swatch.className='curve-swatch';swatch.style.backgroundColor=row.color;
      const label=document.createElement('span');label.textContent=row.label;
      const value=document.createElement('strong');value.textContent=row.format(point.y);item.append(swatch,label,value);tooltip.append(item);count++;
    }
    if(!count){hideHover();return;}
    tooltip.hidden=false;
    const plot=svg.parentElement.getBoundingClientRect(),px=event.clientX-plot.left,py=event.clientY-plot.top;
    tooltip.style.left=Math.max(0,Math.min(plot.width-tooltip.offsetWidth,px+18+tooltip.offsetWidth>plot.width?px-tooltip.offsetWidth-18:px+18))+'px';
    tooltip.style.top=Math.max(0,Math.min(plot.height-tooltip.offsetHeight,py-tooltip.offsetHeight-12))+'px';
  };
}
function drawQuotaModels(rows) {
  const container=$('quota-bars');container.replaceChildren();
  if(!rows.length){const empty=document.createElement('p');empty.className='note';empty.textContent=t('Недостаточно данных для диаграммы');container.append(empty);return;}
  const maximum=Math.max(...rows.map(row=>row.value),0.001);
  for(const row of rows){
    const card=document.createElement('article');card.className='model-usage '+(row.label.includes('astra')?'model-astra':'model-sol');
    const header=document.createElement('div');header.className='model-usage-heading';
    const name=document.createElement('h3');name.textContent=row.label;
    const share=document.createElement('strong');share.className='model-usage-share';share.textContent=row.display;header.append(name,share);
    const track=document.createElement('div');track.className='model-usage-track';track.setAttribute('aria-hidden','true');
    const bar=document.createElement('div');bar.className='model-usage-fill';bar.style.width=(row.value/maximum*100)+'%';track.append(bar);
    const components=document.createElement('dl');components.className='model-usage-components';
    for(const part of [{label:t('Всего'),value:row.total},...row.components]){const cell=document.createElement('div');const label=document.createElement('dt');label.textContent=part.label;const value=document.createElement('dd');value.textContent=number(part.value);cell.append(label,value);components.append(cell);}
    card.append(header,track,components);container.append(card);
  }
}
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
$('refresh-interval').addEventListener('change', event => {
  refreshInterval = Number(event.target.value);
  try { localStorage.setItem('codex-refresh-interval', String(refreshInterval)); } catch {}
  scheduleRefresh();
});
updatePeriodControls();refresh();scheduleRefresh();
