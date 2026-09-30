"""Incremental local JSONL index and metadata."""
import hashlib
import json
import math
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from common import ClosingConnection, FIELDS, MSK, RATES, epoch, parent_id, synchronized
from quota import build_quota
from reports import Reports
from projects import ProjectResolver, validate_root

def validate_record(event):
    """Validate data shapes at the boundary; programming errors still propagate."""
    if not isinstance(event, dict) or not isinstance(event.get('payload', {}), dict):
        raise ValueError('Event and payload must be objects')
    payload = event.get('payload', {})
    kind = event.get('type')
    if kind == 'session_meta':
        for key in ('id', 'cwd', 'parent_thread_id'):
            if key in payload and payload[key] is not None and not isinstance(payload[key], str):
                raise ValueError(f'Metadata {key} must be a string')
        source = payload.get('source')
        if source is not None and not isinstance(source, (str, dict)):
            raise ValueError('Invalid session source')
        if isinstance(source, dict):
            sub = source.get('subagent', {})
            if isinstance(sub, dict):
                spawn = sub.get('thread_spawn', {})
                if not isinstance(spawn, dict):
                    raise ValueError('Invalid thread spawn metadata')
                parent = spawn.get('parent_thread_id')
                if parent is not None and not isinstance(parent, str):
                    raise ValueError('Invalid parent id')
        epoch(payload.get('timestamp') or event.get('timestamp'))
    elif kind == 'turn_context':
        for key in ('model', 'effort', 'turn_id'):
            if payload.get(key) is not None and not isinstance(payload[key], str):
                raise ValueError(f'Context {key} must be a string')
        mode = payload.get('collaboration_mode', {})
        if not isinstance(mode, dict):
            raise ValueError('Invalid collaboration settings')
        settings = mode.get('settings') if mode.get('settings') is not None else {}
        if not isinstance(settings, dict):
            raise ValueError('Invalid collaboration settings')
        effort = settings.get('reasoning_effort')
        if effort is not None and not isinstance(effort, str):
            raise ValueError('Invalid reasoning effort')
    elif kind == 'event_msg' and payload.get('type') == 'token_count':
        epoch(event.get('timestamp'))
        info = payload.get('info') if payload.get('info') is not None else {}
        rate = payload.get('rate_limits') if payload.get('rate_limits') is not None else {}
        if not isinstance(info, dict) or not isinstance(rate, dict):
            raise ValueError('Token info and rate limits must be objects')
        for key in ('primary', 'secondary'):
            if rate.get(key) is not None and not isinstance(rate[key], dict):
                raise ValueError('Quota window must be an object')
            window = rate.get(key) or {}
            duration = window.get('window_minutes', window.get('windowDurationMins'))
            if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float))
                                         or not math.isfinite(duration) or duration <= 0):
                raise ValueError('Invalid quota window duration')
        for key in ('limit_id', 'limitId', 'plan_type', 'planType'):
            if rate.get(key) is not None and not isinstance(rate[key], str):
                raise ValueError('Invalid quota metadata')
        for key in ('total_token_usage', 'last_token_usage'):
            counters = info.get(key)
            if counters is None:
                continue
            if not isinstance(counters, dict):
                raise ValueError('Token counters must be an object')
            for field in FIELDS:
                raw = counters.get(field, 0)
                if isinstance(raw, bool):
                    raise ValueError('Boolean token counter')
                number = int(raw)
                if not -(2**63) <= number < 2**63:
                    raise ValueError('Token counter outside SQLite integer range')

class Index(Reports):
    def __init__(self, home, data):
        self.lock = threading.RLock()
        self._quota_dirty = False
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
        setting = con.execute("SELECT value FROM settings WHERE key='projects_root'").fetchone()
        self.projects_root = json.loads(setting['value']) if setting else None
        self.project_resolver = ProjectResolver(self.projects_root)
        grouping = con.execute("SELECT value FROM settings WHERE key='project_grouping_version'").fetchone()
        if not grouping or grouping['value'] != '1':
            # Migrate saved cwd metadata independently of journal offsets/cache.
            for row in con.execute('SELECT id,cwd FROM threads').fetchall():
                con.execute('UPDATE threads SET project=? WHERE id=?',
                            (self.project_resolver.resolve(row['cwd']), row['id']))
            con.execute("INSERT OR REPLACE INTO settings VALUES ('project_grouping_version','1')")
            con.commit()
        con.close()

    @synchronized
    def get_settings(self):
        return dict(projects_root=self.projects_root)

    @synchronized
    def set_settings(self, root):
        root = validate_root(root)
        resolver = ProjectResolver(root)
        with self.connect() as con:
            for row in con.execute('SELECT id,cwd FROM threads').fetchall():
                con.execute('UPDATE threads SET project=? WHERE id=?',
                            (resolver.resolve(row['cwd']), row['id']))
            con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',
                        ('projects_root', json.dumps(root)))
        self.projects_root, self.project_resolver = root, resolver
        return self.get_settings()

    def connect(self):
        con = sqlite3.connect(self.db, timeout=30, factory=ClosingConnection)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def warning(con, path, offset, message):
        con.execute('INSERT OR IGNORE INTO diagnostics VALUES (?,?,?)', (str(path), offset, message))

    @synchronized
    def ingest(self, path):
        stat = path.stat()
        with self.connect() as con:
            old = con.execute('SELECT * FROM files WHERE path=?', (str(path),)).fetchone()
            offset, state = (old['offset'], json.loads(old['state'])) if old else (0, {})
            replaced = old and (stat.st_size < offset or str(stat.st_ino) != old['inode'] or
                        (stat.st_size == old['size'] and stat.st_mtime_ns != old['mtime']))
            if old and not replaced and stat.st_size == old['size'] and stat.st_mtime_ns == old['mtime']:
                return
            digest = hashlib.sha256()
            # Stat cannot distinguish an append from a growing in-place rewrite.
            # Verify committed bytes only in this changed file; unchanged files
            # are never opened. Legacy states without a digest reread once when
            # their file next changes, not when an old database is opened.
            if old and not replaced:
                with path.open('rb') as check:
                    remaining = offset
                    while remaining:
                        chunk = check.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            break
                        digest.update(chunk)
                        remaining -= len(chunk)
                replaced = remaining != 0 or digest.hexdigest() != state.get('_content_hash')
            if replaced:
                self._quota_dirty = True
                con.execute('DELETE FROM events WHERE file=?', (str(path),))
                con.execute('DELETE FROM diagnostics WHERE file=?', (str(path),))
                con.execute('DELETE FROM quota_samples WHERE file=?', (str(path),))
                offset, state = 0, {}
                digest = hashlib.sha256()
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
                    digest.update(line)
                    if not any(key in line for key in (b'"session_meta"', b'"turn_context"', b'"token_count"')):
                        continue
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeError):
                        self.warning(con, path, start, 'Invalid complete JSON record skipped')
                        continue
                    try:
                        validate_record(event)
                    except (TypeError, ValueError, OverflowError) as exc:
                        self.warning(con, path, start, f'Invalid record skipped: {exc}')
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
                            (sid, sid, cwd, self.project_resolver.resolve(cwd), parent, source))
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
                        try:
                            if isinstance(used, bool) or isinstance(reset, bool):
                                raise ValueError('Boolean quota value')
                            used, reset = float(used), int(reset)
                            if not math.isfinite(used) or not 0 <= used <= 100 or not 0 < reset <= 253402300799:
                                raise ValueError('Quota value outside range')
                            stamp = epoch(event['timestamp'])
                            before = con.total_changes
                            con.execute('INSERT OR IGNORE INTO quota_samples VALUES (?,?,?,?,?,?,?)',
                                (str(path),start,stamp,rate.get('limit_id',rate.get('limitId')) or 'codex',
                                 reset,used,rate.get('plan_type',rate.get('planType')) or 'unknown'))
                            self._quota_dirty |= con.total_changes != before
                        except (TypeError, ValueError, KeyError, OverflowError):
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
                    before = con.total_changes
                    con.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (str(path), start, timestamp, sid, state.get('turn', 'unknown'), model,
                         state.get('effort', 'unknown'), 1, delta['input_tokens'],
                         delta['cached_input_tokens'], delta['input_tokens'] - delta['cached_input_tokens'],
                         delta['output_tokens'], delta['reasoning_output_tokens'], delta['total_tokens'], event_key))
                    self._quota_dirty |= con.total_changes != before
            state['_content_hash'] = digest.hexdigest()
            con.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)',
                (str(path), offset, stat.st_size, stat.st_mtime_ns, str(stat.st_ino), json.dumps(state)))

    def refresh_titles(self):
        paths = sorted(self.home.glob('state_*.sqlite'),
                       key=lambda p: int(re.search(r'state_(\d+)', p.name)[1]), reverse=True)
        for path in paths:
            try:
                external = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
                try:
                    columns = {r[1] for r in external.execute('PRAGMA table_info(threads)')}
                    display = "COALESCE(NULLIF(name,''),title)" if 'name' in columns else 'title'
                    rows = external.execute(f'SELECT id,{display},cwd,archived FROM threads').fetchall()
                finally:
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
            with self.connect() as con, path.open('rb') as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
                            raise ValueError('Invalid session index metadata')
                        for key in ('thread_name', 'title'):
                            if row.get(key) is not None and not isinstance(row[key], str):
                                raise ValueError('Invalid session index title')
                        con.execute('UPDATE threads SET title=? WHERE id=?',
                            (row.get('thread_name') or row.get('title') or row['id'], row['id']))
                    except (ValueError, KeyError, UnicodeError):
                        continue

    @synchronized
    def prepare_quota(self):
        if self.quota_cache is not None and not self._quota_dirty:
            return
        with self.connect() as con:
            samples=[dict(r) for r in con.execute('''SELECT timestamp,limit_id,reset_at,used_percent,plan
                FROM quota_samples GROUP BY timestamp,limit_id,reset_at,used_percent''')]
            events=[dict(r) for r in con.execute('SELECT * FROM events GROUP BY event_key')]
        quota=build_quota(samples,events,RATES)
        quota['events']=events
        self.quota_cache=quota
        self._quota_dirty = False

    @synchronized
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
                except (OSError, sqlite3.Error) as exc:
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
