"""Local Codex usage monitor. Python standard library only; no model/API calls."""
import argparse
import csv
import io
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from quota import build_quota, period_observation

MSK = timezone(timedelta(hours=3))
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'total_tokens')
METRICS = ('calls', 'input', 'cached', 'fresh', 'output', 'reasoning', 'total')
RATE_DATE = '2026-09-29'
RATES = {'gpt-6-astra': (250, 25, 1250), 'gpt-6.1-sol': (50, 2.5, 250),
         'gpt-6-sol': (50, 5, 250), 'gpt-6-luna': (2.5, .25, 12.5),
         'gpt-5.6-sol': (100, 10, 500), 'gpt-5.6-terra': (50, 5, 300),
         'gpt-5.6-luna': (5, .5, 30), 'gpt-5.5': (125, 12.5, 750)}

def epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()

def project(cwd):
    parts = cwd.replace('\\', '/').rstrip('/').split('/')
    for i, part in enumerate(parts):
        if part.lower() == 'ai_projects' and i + 1 < len(parts):
            return parts[i + 1]
    return 'Без проекта'

def parent_id(meta):
    source = meta.get('source')
    nested = source.get('subagent', {}) if isinstance(source, dict) else {}
    spawn = nested.get('thread_spawn', {}) if isinstance(nested, dict) else {}
    return meta.get('parent_thread_id') or spawn.get('parent_thread_id')

def blank():
    return {key: 0 for key in METRICS}

def add(target, values):
    for key in METRICS:
        target[key] += values[key]

def cost(values, rates):
    return (values['fresh'] * rates[0] + values['cached'] * rates[1] + values['output'] * rates[2]) / 1_000_000

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class Index:
    def __init__(self, home, data):
        self.home, self.data = Path(home), Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        self.db = self.data / 'usage.sqlite'
        self.status = dict(indexing=False, files_done=0, files_total=0, last_scan=None, error=None)
        self.quota_cache = None
        con = self.connect()
        con.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, offset INTEGER, size INTEGER,
                mtime INTEGER, inode TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY, title TEXT, cwd TEXT,
                project TEXT, parent TEXT, source TEXT, archived INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(file TEXT, offset INTEGER, timestamp REAL,
                thread TEXT, turn TEXT, model TEXT, effort TEXT, calls INTEGER,
                input INTEGER, cached INTEGER, fresh INTEGER, output INTEGER, reasoning INTEGER,
                total INTEGER, event_key TEXT, PRIMARY KEY(file,offset));
            CREATE INDEX IF NOT EXISTS events_time ON events(timestamp);
            CREATE INDEX IF NOT EXISTS events_thread ON events(thread);
            CREATE TABLE IF NOT EXISTS diagnostics(file TEXT, offset INTEGER, message TEXT,
                PRIMARY KEY(file,offset,message));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS quota_samples(file TEXT,offset INTEGER,timestamp REAL,
                limit_id TEXT,reset_at INTEGER,used_percent REAL,plan TEXT,
                PRIMARY KEY(file,offset,limit_id,reset_at));
            CREATE INDEX IF NOT EXISTS quota_time ON quota_samples(timestamp);
        ''')
        version = con.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        if not version or version['value'] != '2':
            con.execute('DELETE FROM files')
            con.execute("INSERT OR REPLACE INTO settings VALUES ('schema_version','2')")
        con.commit()
        con.close()

    def connect(self):
        con = sqlite3.connect(self.db, timeout=30, factory=ClosingConnection)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def warning(con, path, offset, message):
        con.execute('INSERT OR IGNORE INTO diagnostics VALUES (?,?,?)', (str(path), offset, message))

    def ingest(self, path):
        stat = path.stat()
        with self.connect() as con:
            old = con.execute('SELECT * FROM files WHERE path=?', (str(path),)).fetchone()
            offset, state = (old['offset'], json.loads(old['state'])) if old else (0, {})
            replaced = old and (stat.st_size < offset or str(stat.st_ino) != old['inode'] or
                        (stat.st_size == old['size'] and stat.st_mtime_ns != old['mtime']))
            if replaced:
                con.execute('DELETE FROM events WHERE file=?', (str(path),))
                con.execute('DELETE FROM diagnostics WHERE file=?', (str(path),))
                con.execute('DELETE FROM quota_samples WHERE file=?', (str(path),))
                offset, state = 0, {}
            if old and not replaced and stat.st_size == old['size'] and stat.st_mtime_ns == old['mtime']:
                return
            with path.open('rb') as stream:
                stream.seek(offset)
                while stream.tell() < stat.st_size:
                    start = stream.tell()
                    line = stream.readline()
                    if not line.endswith(b'\n'):
                        # Keep the offset before a partial UTF-8 / JSON record.
                        offset = start
                        break
                    offset = stream.tell()
                    if not any(key in line for key in (b'"session_meta"', b'"turn_context"', b'"token_count"')):
                        continue
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeError):
                        self.warning(con, path, start, 'Invalid complete JSON record skipped')
                        continue
                    payload = event.get('payload', {})
                    if event.get('type') == 'session_meta':
                        sid = payload.get('id')
                        if not sid:
                            self.warning(con, path, start, 'Session metadata has no thread id')
                            continue
                        cwd = payload.get('cwd', '')
                        parent = parent_id(payload)
                        source = 'subagent' if parent else 'chat-or-fork'
                        state.update(thread=sid, model='unknown', effort='unknown', turn='unknown',
                                     created=epoch(payload.get('timestamp') or event['timestamp']))
                        con.execute('''INSERT INTO threads(id,title,cwd,project,parent,source)
                            VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                            cwd=excluded.cwd, project=excluded.project,
                            parent=COALESCE(excluded.parent,threads.parent), source=excluded.source''',
                            (sid, sid, cwd, project(cwd), parent, source))
                        continue
                    if event.get('type') == 'turn_context':
                        state.update(model=payload.get('model') or state.get('model', 'unknown'),
                            effort=payload.get('effort') or (payload.get('collaboration_mode', {}).get('settings') or {}).get('reasoning_effort') or 'unknown',
                            turn=payload.get('turn_id') or state.get('turn', 'unknown'))
                        continue
                    if event.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                        continue
                    rate = payload.get('rate_limits') or {}
                    for which in ('primary','secondary'):
                        window = rate.get(which) or {}
                        if window.get('window_minutes',window.get('windowDurationMins')) != 10080:
                            continue
                        used = window.get('used_percent',window.get('usedPercent'))
                        reset = window.get('resets_at',window.get('resetsAt'))
                        if used is None or reset is None or not 0 <= float(used) <= 100:
                            continue
                        try:
                            stamp = epoch(event['timestamp'])
                            con.execute('INSERT OR IGNORE INTO quota_samples VALUES (?,?,?,?,?,?,?)',
                                (str(path),start,stamp,rate.get('limit_id',rate.get('limitId')) or 'codex',
                                 int(reset),float(used),rate.get('plan_type',rate.get('planType')) or 'unknown'))
                        except (ValueError,KeyError):
                            self.warning(con,path,start,'Invalid weekly quota snapshot')
                    info = payload.get('info') or {}
                    raw_total, raw_last = info.get('total_token_usage'), info.get('last_token_usage')
                    if not raw_total:
                        continue
                    try:
                        total = {key: int(raw_total.get(key, 0)) for key in FIELDS}
                        last = {key: int(raw_last.get(key, 0)) for key in FIELDS} if raw_last else None
                    except (TypeError, ValueError):
                        self.warning(con, path, start, 'Non-numeric token counter skipped')
                        continue
                    previous = state.get('previous')
                    if total == previous:
                        continue
                    state['previous'] = total
                    if previous is None or total['total_tokens'] < previous['total_tokens']:
                        delta = last
                        if previous is not None:
                            self.warning(con, path, start, 'Counter reset: used last_token_usage')
                    else:
                        delta = {key: total[key] - previous[key] for key in FIELDS}
                    if delta is None:
                        self.warning(con, path, start, 'First counter lacks last_token_usage: treated as baseline')
                        continue
                    if any(value < 0 for value in delta.values()):
                        self.warning(con, path, start, 'Component counter reset: used last_token_usage')
                        delta = last
                    if not delta or not delta['total_tokens']:
                        continue
                    if (any(value < 0 for value in delta.values()) or
                        delta['cached_input_tokens'] > delta['input_tokens'] or
                        delta['reasoning_output_tokens'] > delta['output_tokens'] or
                        delta['total_tokens'] != delta['input_tokens'] + delta['output_tokens']):
                        self.warning(con, path, start, 'Inconsistent token counters: event not counted')
                        continue
                    sid = state.get('thread')
                    if not sid:
                        self.warning(con, path, start, 'Tokens without session metadata: event not counted')
                        continue
                    try:
                        timestamp = epoch(event['timestamp'])
                    except (KeyError, ValueError):
                        self.warning(con, path, start, 'Token event has no valid timestamp')
                        continue
                    if timestamp < state.get('created', 0):
                        # Historical token events copied into a fork are not new spending.
                        continue
                    model = state.get('model', 'unknown')
                    if model == 'unknown':
                        self.warning(con, path, start, 'Token event has unknown model')
                    identity = json.dumps((sid, event['timestamp'], total), sort_keys=True)
                    event_key = hashlib.sha256(identity.encode()).hexdigest()
                    con.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (str(path), start, timestamp, sid, state.get('turn', 'unknown'), model,
                         state.get('effort', 'unknown'), 1, delta['input_tokens'],
                         delta['cached_input_tokens'], delta['input_tokens'] - delta['cached_input_tokens'],
                         delta['output_tokens'], delta['reasoning_output_tokens'], delta['total_tokens'], event_key))
            con.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)',
                (str(path), offset, stat.st_size, stat.st_mtime_ns, str(stat.st_ino), json.dumps(state)))

    def refresh_titles(self):
        paths = sorted(self.home.glob('state_*.sqlite'),
                       key=lambda p: int(re.search(r'state_(\d+)', p.name)[1]), reverse=True)
        for path in paths:
            try:
                external = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
                columns = {r[1] for r in external.execute('PRAGMA table_info(threads)')}
                display = "COALESCE(NULLIF(name,''),title)" if 'name' in columns else 'title'
                rows = external.execute(f'SELECT id,{display},cwd,archived FROM threads').fetchall()
                external.close()
                with self.connect() as con:
                    for sid, title, cwd, archived in rows:
                        con.execute('UPDATE threads SET title=?,archived=? WHERE id=?', (title or sid, archived, sid))
                return
            except sqlite3.Error:
                continue
        # Old Codex versions can have a JSONL index instead of SQLite.
        path = self.home / 'session_index.jsonl'
        if path.exists():
            with self.connect() as con, path.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        con.execute('UPDATE threads SET title=? WHERE id=?',
                            (row.get('thread_name') or row.get('title') or row['id'], row['id']))
                    except (ValueError, KeyError):
                        continue

    def prepare_quota(self):
        with self.connect() as con:
            samples=[dict(r) for r in con.execute('''SELECT timestamp,limit_id,reset_at,used_percent,plan
                FROM quota_samples GROUP BY timestamp,limit_id,reset_at,used_percent''')]
            events=[dict(r) for r in con.execute('SELECT * FROM events GROUP BY event_key')]
        quota=build_quota(samples,events,RATES)
        quota['events']=events
        self.quota_cache=quota

    def scan(self):
        self.status.update(indexing=True, files_done=0, error=None)
        try:
            paths = sorted({p for folder in ('sessions', 'archived_sessions')
                            for p in (self.home / folder).rglob('*.jsonl')})
            self.status['files_total'] = len(paths)
            for i, path in enumerate(paths):
                if (self.data / 'stop').exists():
                    break
                try:
                    self.ingest(path)
                except (OSError, sqlite3.Error, ValueError) as exc:
                    with self.connect() as con:
                        self.warning(con, path, -1, f'Read/index error: {type(exc).__name__}: {exc}')
                self.status['files_done'] = i + 1
            self.refresh_titles()
            self.prepare_quota()
            self.status['last_scan'] = datetime.now(MSK).isoformat(timespec='seconds')
            with self.connect() as con:
                con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('last_scan', self.status['last_scan']))
        except Exception as exc:
            self.status['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            self.status['indexing'] = False

    def token_curve(self, first, final):
        """Cumulative local token totals, deduplicated before selecting the interval."""
        with self.connect() as con:
            rows = con.execute('''WITH unique_events AS (SELECT * FROM events GROUP BY event_key)
                SELECT timestamp,model,total FROM unique_events
                WHERE timestamp>=? AND timestamp<=? ORDER BY timestamp''', (first, final)).fetchall()
        if not rows:
            return dict(points=[], models=[])
        models = sorted({row['model'] for row in rows})
        totals = {model: 0 for model in models}
        points = [dict(timestamp=first, total=0, models=totals.copy())]
        # Bound the drawing size without dropping tokens or mixing model identities.
        buckets = {}
        for row in rows:
            bucket = min(399, int((row['timestamp']-first)/max(1, final-first)*400))
            entry = buckets.setdefault(bucket, dict(timestamp=row['timestamp'], models=defaultdict(int)))
            entry['timestamp'] = max(entry['timestamp'], row['timestamp'])
            entry['models'][row['model']] += row['total']
        for entry in buckets.values():
            for model, value in entry['models'].items():
                totals[model] += value
            points.append(dict(timestamp=entry['timestamp'], total=sum(totals.values()), models=totals.copy()))
        if points[-1]['timestamp'] < final:
            points.append(dict(timestamp=final, total=sum(totals.values()), models=totals.copy()))
        return dict(points=points, models=sorted(models, key=lambda model: (-totals[model], model)))

    def report(self, start, end, selected_project='', model='', grouped=True, cycle=False, hours=None, start_time=None, end_time=None):
        first = datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=MSK)
        final = datetime.strptime(end, '%Y-%m-%d').replace(tzinfo=MSK) + timedelta(days=1)
        if final <= first:
            raise ValueError('Начало периода должно быть не позже конца')
        if hours is not None:
            hours = int(hours)
            if not 1 <= hours <= 365 * 24:
                raise ValueError('Период должен быть от 1 часа до 365 дней')
            cycle = False
            final = datetime.now(MSK)
            first = final - timedelta(hours=hours)
            start, end = first.date().isoformat(), final.date().isoformat()
        if start_time is not None or end_time is not None:
            if not start_time or not end_time:
                raise ValueError('Укажите начало и конец периода')
            first = datetime.fromisoformat(start_time)
            final = datetime.fromisoformat(end_time)
            first = first.replace(tzinfo=MSK) if first.tzinfo is None else first.astimezone(MSK)
            final = final.replace(tzinfo=MSK) if final.tzinfo is None else final.astimezone(MSK)
            if final <= first:
                raise ValueError('Конец периода должен быть позже начала')
            cycle = False
            start, end = first.date().isoformat(), final.date().isoformat()
        con = self.connect()
        try:
            cache=self.quota_cache
            if cycle and cache and cache['latest']:
                first=datetime.fromtimestamp(cache['latest']['reset_at']-10080*60,MSK)
                final=datetime.now(MSK)
                start,end=first.date().isoformat(),final.date().isoformat()
            meta = {r['id']: dict(r) for r in con.execute('SELECT * FROM threads')}
            where, params = 'timestamp>=? AND timestamp<?', [first.timestamp(), final.timestamp()]
            if model:
                where += ' AND model=?'
                params.append(model)
            rows = con.execute(f'''WITH unique_events AS (SELECT * FROM events GROUP BY event_key)
                SELECT thread,model,effort,SUM(calls) AS calls,
                SUM(input) AS input,SUM(cached) AS cached,SUM(fresh) AS fresh,
                SUM(output) AS output,SUM(reasoning) AS reasoning,SUM(total) AS total
                FROM unique_events WHERE {where} GROUP BY thread,model,effort''', params).fetchall()
            summary, models, chats, projects = blank(), {}, {}, {}
            quota=self.quota_cache or dict(allocations={},windows=[],blocks=[],latest=None,curve=[],notes=[],covered=set(),events=[])
            pp_by_group=defaultdict(float)
            covered_by_group=defaultdict(int)
            for event in quota['events']:
                if not first.timestamp() <= event['timestamp'] < final.timestamp():
                    continue
                key=(event['thread'],event['model'],event['effort'])
                pp_by_group[key]+=quota['allocations'].get(event['event_key'],0.)
                if event['event_key'] in quota['covered']:
                    covered_by_group[key]+=event['total']
            summary.update(quota_pp=0.,quota_covered_tokens=0)
            estimated, priced_tokens = 0., 0
            for raw in rows:
                row = dict(raw)
                sid = row['thread']
                own = meta.get(sid, dict(id=sid, title=sid, project='Без проекта', parent=None, source='unknown'))
                root = sid
                seen = set()
                while grouped and root in meta and meta[root]['parent'] and root not in seen:
                    seen.add(root)
                    root = meta[root]['parent']
                owner = meta.get(root, own)
                proj = owner['project'] if grouped else own['project']
                if selected_project and proj != selected_project:
                    continue
                quota_key=(sid,row['model'],row['effort'])
                pp=pp_by_group[quota_key]
                covered_tokens=covered_by_group[quota_key]
                summary['quota_pp']+=pp
                summary['quota_covered_tokens']+=covered_tokens
                add(summary, row)
                mk = (row['model'], row['effort'])
                if mk not in models:
                    models[mk] = dict(model=mk[0], effort=mk[1], **blank(),quota_pp=0.,quota_covered_tokens=0, estimated_credits=0 if mk[0] in RATES else None)
                add(models[mk], row)
                models[mk]['quota_pp']+=pp
                models[mk]['quota_covered_tokens']+=covered_tokens
                if row['model'] in RATES:
                    value = cost(row, RATES[row['model']])
                    estimated += value
                    priced_tokens += row['total']
                    models[mk]['estimated_credits'] += value
                if proj not in projects:
                    projects[proj] = dict(project=proj, **blank(),quota_pp=0.,quota_covered_tokens=0)
                add(projects[proj], row)
                projects[proj]['quota_pp']+=pp
                projects[proj]['quota_covered_tokens']+=covered_tokens
                ck = (root if grouped else sid, row['model'], row['effort'])
                if ck not in chats:
                    chats[ck] = dict(thread=ck[0], title=owner['title'], project=proj,
                        model=row['model'], effort=row['effort'], **blank(),
                        main_calls=0, subagent_calls=0,quota_pp=0.,quota_covered_tokens=0, estimated_credits=0 if row['model'] in RATES else None)
                add(chats[ck], row)
                chats[ck]['quota_pp']+=pp
                chats[ck]['quota_covered_tokens']+=covered_tokens
                chats[ck]['subagent_calls' if own.get('parent') else 'main_calls'] += row['calls']
                if row['model'] in RATES:
                    chats[ck]['estimated_credits'] += cost(row, RATES[row['model']])
            diagnostics = [dict(r) for r in con.execute('SELECT message,COUNT(*) AS count FROM diagnostics GROUP BY message')]
            last = con.execute("SELECT value FROM settings WHERE key='last_scan'").fetchone()
            observation=period_observation(quota,first.timestamp(),final.timestamp())
            blocks=[b for b in quota['blocks'] if b['end']>=first.timestamp() and b['start']<final.timestamp()]
            quota_view=dict(latest=quota['latest'],period=observation,
                account_scope='all_local_account_observations',estimated_selected_pp=summary['quota_pp'],
                unassigned_block_pp=sum(b['unassigned_pp'] for b in blocks),
                curve=[p for p in quota['curve'] if first.timestamp()<=p['timestamp']<final.timestamp()],
                preliminary=any(b['preliminary'] and b['assigned_pp'] for b in blocks),
                notes=quota['notes'],windows=quota['windows'],
                assumptions=['credit_weights_standard','concurrent_chats','rounded_shared_account_counter','local_logs_only'])
            # Compress flat portions for the graph only; full samples remain in the database.
            raw_curve=quota_view['curve']
            short=[]
            previous=None
            for point in raw_curve:
                if previous is None or (point['used_percent'],point['reset_at'])!=(previous['used_percent'],previous['reset_at']):
                    if previous is not None and (not short or short[-1]!=previous):short.append(previous)
                    short.append(point)
                previous=point
            if previous is not None and (not short or short[-1]!=previous):short.append(previous)
            quota_view['curve']=short
            return dict(range=dict(start=start, end=end,cycle=cycle,first_time=first.timestamp(),final_time=final.timestamp()), summary=summary,quota=quota_view,
                models=sorted(models.values(), key=lambda r: -r['total']),
                chats=sorted(chats.values(), key=lambda r: -r['total']),
                projects=sorted(projects.values(), key=lambda r: -r['total']),
                options=dict(projects=sorted({r['project'] for r in meta.values()}),
                             models=[r[0] for r in con.execute('SELECT DISTINCT model FROM events ORDER BY model')]),
                index=dict(**self.status, indexed_files=con.execute('SELECT COUNT(*) FROM files').fetchone()[0],
                           events=con.execute('SELECT COUNT(DISTINCT event_key) FROM events').fetchone()[0]),
                snapshot=self.status['last_scan'] or (last['value'] if last else None),
                diagnostics=diagnostics,
                pricing=dict(date=RATE_DATE, source='https://learn.chatgpt.com/docs/pricing#token-rates',
                    estimated_credits=estimated, priced_tokens=priced_tokens,
                    astra_same_tokens=cost(summary, RATES['gpt-6-astra']),
                    sol61_same_tokens=cost(summary, RATES['gpt-6.1-sol']),
                    comparison=[dict(model=name,credits=cost(summary,RATES[name])) for name in
                        sorted({'gpt-6-astra','gpt-6.1-sol',*[r['model'] for r in models.values()]}) if name in RATES]))
        finally:
            con.close()

def csv_text(rows):
    if not rows:
        return '\ufeff'
    stream = io.StringIO(newline='')
    keys = list(rows[0])
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    for row in rows:
        safe = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                for k, v in row.items()}
        writer.writerow(safe)
    return '\ufeff' + stream.getvalue()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, content_type):
        encoded = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or self.headers.get('Host') not in self.server.allowed_hosts:
            self.send(403, 'Local access only', 'text/plain; charset=utf-8')
            return
        url = urlparse(self.path)
        assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/theme.js': ('theme.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if url.path in assets:
            name, mime = assets[url.path]
            self.send(200, (Path(__file__).parent / name).read_bytes(), mime + '; charset=utf-8')
            return
        if url.path == '/api/health':
            self.send(200, json.dumps(dict(service='codex-usage-monitor', index=self.server.index.status)), 'application/json; charset=utf-8')
            return
        if url.path == '/api/curve':
            args = parse_qs(url.query)
            try:
                hours = int(args.get('hours', ['24'])[0])
                if hours not in (1, 5, 24, 168, 720):
                    raise ValueError('Unsupported chart interval')
                final = datetime.now(MSK).timestamp()
                first = final - hours * 3600
                if 'first_time' in args or 'final_time' in args:
                    if 'first_time' not in args or 'final_time' not in args:
                        raise ValueError('Both chart boundaries are required')
                    first = float(args['first_time'][0])
                    final = float(args['final_time'][0])
                    if not (0 <= first < final <= 253402300799):
                        raise ValueError('Invalid chart boundaries')
                cache = self.server.index.quota_cache
                raw = [p for p in (cache or {}).get('curve', []) if first <= p['timestamp'] <= final]
                # Preserve endpoints of flat stretches and every observed change / reset.
                curve = []
                previous = None
                for point in raw:
                    if previous is None or (point['used_percent'], point['reset_at']) != (previous['used_percent'], previous['reset_at']):
                        if previous is not None and (not curve or curve[-1] != previous):
                            curve.append(previous)
                        curve.append(point)
                    previous = point
                if previous is not None and (not curve or curve[-1] != previous):
                    curve.append(previous)
                self.send(200, json.dumps(dict(curve=curve, first_time=first, final_time=final,
                    tokens=self.server.index.token_curve(first, final))), 'application/json; charset=utf-8')
            except ValueError as exc:
                self.send(400, json.dumps(dict(error=str(exc))), 'application/json; charset=utf-8')
            return
        if url.path not in ('/api/usage', '/api/export'):
            self.send(404, 'Not found', 'text/plain')
            return
        args = {k: v[0] for k, v in parse_qs(url.query).items()}
        today = datetime.now(MSK).date()
        try:
            data = self.server.index.report(args.get('from', (today-timedelta(days=6)).isoformat()),
                args.get('to', today.isoformat()), args.get('project', ''), args.get('model', ''),
                args.get('grouped', '1') != '0',args.get('cycle','0')=='1', hours=args.get('hours'),
                start_time=args.get('start_time'), end_time=args.get('end_time'))
            if url.path == '/api/export':
                self.send(200, csv_text(data['models'] if args.get('table') == 'models' else data['chats']), 'text/csv; charset=utf-8')
            else:
                self.send(200, json.dumps(data, ensure_ascii=False), 'application/json; charset=utf-8')
        except ValueError as exc:
            self.send(400, json.dumps(dict(error=str(exc)), ensure_ascii=False), 'application/json; charset=utf-8')
        except Exception as exc:
            self.send(500, json.dumps(dict(error=f'{type(exc).__name__}: {exc}')), 'application/json; charset=utf-8')

class RunLock:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        self.stream.seek(0)
        if not self.stream.read(1):
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def close(self):
        self.stream.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home()/'.codex')
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parent/'data')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--from', dest='start')
    parser.add_argument('--to', dest='end')
    args = parser.parse_args()
    if args.interval < 5:
        parser.error('--interval must be at least 5 seconds')
    try:
        lock = RunLock(args.data / 'run.lock')
    except OSError:
        parser.error('Monitor already running for this data directory')
    index = Index(args.home, args.data)
    stop_file = args.data / 'stop'
    stop_file.unlink(missing_ok=True)
    if args.once:
        try:
            index.scan()
            today = datetime.now(MSK).date()
            result = index.report(args.start or (today-timedelta(days=6)).isoformat(), args.end or today.isoformat())
            (args.data / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            (args.data / 'chats.csv').write_text(csv_text(result['chats']), encoding='utf-8')
            print(json.dumps(dict(summary=result['summary'], index=result['index'], diagnostics=result['diagnostics']), ensure_ascii=True))
        finally:
            lock.close()
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    server.index = index
    server.allowed_hosts = {f'127.0.0.1:{args.port}', f'localhost:{args.port}'}
    stopping = threading.Event()
    def poll():
        while not stopping.is_set() and not stop_file.exists():
            try:
                index.scan()
            except Exception:
                pass  # Error remains visible in /api/usage.
            for _ in range(args.interval):
                if stopping.wait(1) or stop_file.exists():
                    return
    watcher = threading.Thread(target=poll, daemon=True)
    watcher.start()
    (args.data / 'running.json').write_text(json.dumps(dict(pid=os.getpid(), url=f'http://127.0.0.1:{args.port}/')), encoding='utf-8')
    print(f'Usage monitor: http://127.0.0.1:{args.port}/', flush=True)
    server.timeout = 1
    try:
        while not stop_file.exists():
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        stopping.set()
        server.server_close()
        watcher.join(timeout=5)
        (args.data / 'running.json').unlink(missing_ok=True)
        lock.close()

if __name__ == '__main__':
    main()
