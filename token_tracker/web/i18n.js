// UI language is stored locally; source data and CSV values are preserved.
let language;
try { language = localStorage.getItem('codex-usage-language'); } catch {}
if (!['ru','en'].includes(language)) language = navigator.language?.startsWith('ru') ? 'ru' : 'en';
const EN = {
  "Папка с проектами": "Projects folder",
  "Выбрать папку с проектами": "Choose projects folder",
  "Ввести путь": "Enter path",
  "Автоопределение": "Detect automatically",
  "Абсолютный путь к папке": "Absolute folder path",
  "Сохранить": "Save",
  "Укажите папку, в которой находятся ваши проекты. Сброс включает автоматическое определение проектов по журналам.": "Enter the folder containing your projects. Reset enables automatic project detection from logs.",
  "Автоопределение по журналам": "Automatic detection from logs",
  "Путь пока неизвестен": "Path not yet known",
  "Выберите папку в системном диалоге…": "Choose a folder in the system dialog…",
  "Сохранение…": "Saving…",
  "Выбор отменён": "Selection cancelled",
  "Включено автоопределение": "Automatic detection enabled",
  "Папка сохранена": "Folder saved",
  "Не удалось загрузить настройку папки": "Could not load folder setting",
  "Не удалось изменить папку": "Could not change folder",
  "Некорректный ответ монитора": "Invalid monitor response",
  "Системный выбор папки недоступен. Введите путь вручную.": "System folder picker is unavailable. Enter the path manually.",
  "Укажите существующую папку или null": "Enter an existing folder, or reset to automatic detection",
  "Папка проектов должна быть существующим абсолютным путём": "Projects folder must be an existing absolute path",
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
  window.dispatchEvent(new Event('languagechange'));
});

const number = value => new Intl.NumberFormat(locale()).format(value);

const credits = value => value == null ? t('Нет тарифа') : new Intl.NumberFormat(locale(), {maximumFractionDigits:2}).format(value);

const dateTime = date => date.toLocaleString(locale(), {timeZone:'Europe/Moscow',hour12:clockFormat===12});

const percent = value => new Intl.NumberFormat(locale(),{maximumFractionDigits:1}).format(value)+'%';

function quotaText(row) { return !row.quota_covered_tokens || !row.quota_pp ? t('Нет оценки') : row.quota_pp<0.05 ? t('≈ <0,1%') : '≈ '+percent(row.quota_pp); }

function localDate(date) { return new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Moscow'}).format(date); }

let clockFormat = 24;
try { clockFormat = Number(localStorage.getItem("codex-clock-format")) || 24; } catch {}
if (![12,24].includes(clockFormat)) clockFormat = 24;
