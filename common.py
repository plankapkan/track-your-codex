"""Shared constants and accounting helpers."""
import sqlite3
import math
from functools import wraps
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'total_tokens')
METRICS = ('calls', 'input', 'cached', 'fresh', 'output', 'reasoning', 'total')
RATE_DATE = '2026-09-29'
RATES = {'gpt-6-astra': (250, 25, 1250), 'gpt-6.1-sol': (50, 2.5, 250),
         'gpt-6-sol': (50, 5, 250), 'gpt-6-luna': (2.5, .25, 12.5),
         'gpt-5.6-sol': (100, 10, 500), 'gpt-5.6-terra': (50, 5, 300),
         'gpt-5.6-luna': (5, .5, 30), 'gpt-5.5': (125, 12.5, 750)}

def epoch(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be a string')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timestamp must include a timezone')
    result = stamp.timestamp()
    if not math.isfinite(result):
        raise ValueError('Invalid timestamp')
    return result

def synchronized(method):
    """Serialize reads with completed indexing passes (reentrant for nested queries)."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call

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
