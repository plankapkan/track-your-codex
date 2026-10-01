"""On-demand history must preserve accounting and avoid opening old journals."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from token_tracker.indexer import Index
from tests.test_monitor import meta, context, usage, plus


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        (self.home / 'sessions').mkdir(parents=True)
        self.now = datetime.now(timezone.utc)
        self.index = Index(self.home, self.root / 'data', lazy=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, ages):
        dates = [self.now - timedelta(days=age) for age in ages]
        rows = [meta(name, dates[0].isoformat()), context()]
        total = None
        for date in dates:
            event = usage(date.isoformat(), 10, 20, 5, reasoning=2)
            last = event['payload']['info']['last_token_usage']
            total = plus(total, last) if total else last.copy()
            event['payload']['info']['total_token_usage'] = total.copy()
            rows.append(event)
        path = self.home / 'sessions' / (name + '.jsonl')
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        os.utime(path, (dates[-1].timestamp(), dates[-1].timestamp()))
        return path

    def report(self, days=7, **kwargs):
        today = self.now.date().isoformat()
        return self.index.report(today, today, hours=days*24, **kwargs)

    def test_old_archive_is_loaded_only_when_requested_and_reused(self):
        old = self.write('old', [25])
        recent = self.write('recent', [1])
        with patch.object(self.index, 'ingest', wraps=self.index.ingest) as ingest:
            self.index.scan()
            self.assertEqual([call.args[0] for call in ingest.call_args_list], [recent])
        self.assertEqual(self.report()['summary']['total'], 35)
        self.assertEqual(self.report(30)['summary']['total'], 70)
        with self.index.connect() as con:
            self.assertIsNotNone(con.execute('SELECT * FROM files WHERE path=?', (str(old),)).fetchone())
        with patch.object(self.index, 'scan', side_effect=AssertionError('Repeated history load')):
            self.assertEqual(self.report(30)['summary']['total'], 70)
            self.assertEqual(self.report()['summary']['total'], 35)

    def test_resumed_old_chat_keeps_counters_and_cached_reasoning(self):
        self.write('resumed', [40, 1])
        self.index.scan()
        data = self.report()
        self.assertEqual(data['summary']['total'], 35)
        self.assertEqual(data['summary']['cached'], 20)
        self.assertEqual(data['summary']['reasoning'], 2)
        self.assertEqual(data['index']['events'], 1)

    def test_restart_bounds_existing_database_without_deleting_history(self):
        self.write('old', [25])
        self.write('recent', [1])
        self.assertEqual(self.report(30)['index']['events'], 2)
        self.index = Index(self.home, self.root / 'data', lazy=True)
        self.index.scan()
        self.assertEqual(self.report()['index']['events'], 1)
        self.assertEqual(self.report(30)['summary']['total'], 70)

    def test_boundary_quota_matches_full_index_and_filters(self):
        reset = int((self.now + timedelta(days=1)).timestamp())
        for name in ('a', 'b'):
            path = self.write(name, [8, 7.1, 6.9, 1])
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for event, used in zip(rows[2:], (10, 11, 12, 15)):
                event['payload']['rate_limits'] = {'secondary': {
                    'window_minutes': 10080, 'resets_at': reset, 'used_percent': used}}
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        full = Index(self.home, self.root / 'full')
        full.scan()
        self.index.scan()
        today = self.now.date().isoformat()
        expected = full.report(today, today, hours=168)
        actual = self.report()
        self.assertEqual(actual['summary'], expected['summary'])
        self.assertEqual(actual['quota']['period'], expected['quota']['period'])
        self.assertEqual(self.report(model='gpt-6.1-sol')['summary'], actual['summary'])

    def test_curve_and_custom_range_load_older_history(self):
        self.write('old', [25])
        first = self.now - timedelta(days=30)
        curve = self.index.curve(first.timestamp(), self.now.timestamp())
        self.assertEqual(curve['tokens']['points'][-1]['total'], 35)
        self.index = Index(self.home, self.root / 'custom', lazy=True)
        data = self.report(start_time=first.isoformat(), end_time=self.now.isoformat())
        self.assertEqual(data['summary']['total'], 35)
