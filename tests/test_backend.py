"""Regression coverage for record isolation, caching, snapshots and settings."""
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from token_tracker.indexer import Index
from token_tracker.server import Handler
from token_tracker.projects import ProjectResolver, FolderPickerUnavailable, pick_folder
from tests.test_monitor import meta, context, usage, plus


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.sessions = self.home / 'sessions'
        self.sessions.mkdir(parents=True)
        self.index = Index(self.home, self.root / 'data')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rows, append=False, name='session.jsonl'):
        path = self.sessions / name
        with path.open('a' if append else 'w', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row) + '\n')
        return path

    def report(self):
        return self.index.report('2026-09-29', '2026-09-29')

    def event(self, number, used=10):
        event = usage(f'2026-09-29T10:{number:02d}:00Z', 10, 0, 5)
        event['payload']['info']['total_token_usage'] = {
            k: v * number for k, v in event['payload']['info']['last_token_usage'].items()}
        event['payload']['rate_limits'] = dict(secondary=dict(
            window_minutes=10080, used_percent=used, resets_at=1800000000))
        return event

    def test_bad_quota_does_not_rollback_valid_tokens_or_following_record(self):
        self.write([meta('test'), context(), self.event(1, 'broken'), self.event(2, 12)])
        self.index.scan()
        report = self.report()
        self.assertEqual(report['summary']['total'], 30)
        with self.index.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM quota_samples').fetchone()[0], 1)
        self.assertTrue(any('Invalid weekly quota snapshot' in d['message'] for d in report['diagnostics']))

    def test_invalid_shapes_time_and_metadata_are_isolated(self):
        bad = [dict(type='session_meta', payload=[]),
               dict(type='session_meta', payload=dict(id=[], timestamp=0)),
               dict(type='session_meta', payload=dict(id='bad', cwd=[], timestamp='broken')),
               dict(type='turn_context', payload=dict(collaboration_mode='broken')),
               dict(type='turn_context', payload=dict(model=[])),
               dict(type='turn_context', payload=dict(collaboration_mode={'settings': {'reasoning_effort': []}})),
               dict(type='event_msg', timestamp=[], payload=dict(type='token_count')),
               dict(type='event_msg', timestamp='broken', payload=dict(type='token_count')),
               dict(type='event_msg', timestamp='2026-09-29T10:00:00Z', payload=dict(type='token_count', info=[]))]
        invalid = self.event(1)
        invalid['payload']['info']['total_token_usage'] = {'total_tokens': []}
        bad.append(invalid)
        invalid = self.event(1)
        invalid['payload']['rate_limits']['secondary'] = 12
        bad.append(invalid)
        self.write([meta('test'), context(), *bad, self.event(1), self.event(2, 12)])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 30)
        self.assertIsNone(self.index.status['error'])
        with self.index.connect() as con:
            self.assertGreaterEqual(con.execute('SELECT COUNT(*) FROM diagnostics').fetchone()[0], 10)

    def test_programming_errors_are_not_silently_skipped(self):
        self.write([meta('test')])
        with patch('token_tracker.indexer.validate_record', side_effect=RuntimeError('programming bug')):
            with self.assertRaisesRegex(RuntimeError, 'programming bug'):
                self.index.scan()

    def test_quota_cache_unchanged_reopen_append_archive_rewrite_and_settings(self):
        self.write([meta('test'), context(), self.event(1)])
        self.index.scan()
        first_cache = self.index.quota_cache
        with patch('token_tracker.indexer.build_quota', side_effect=AssertionError('Unnecessary rebuild')):
            self.index.scan()
            self.report()
            self.index.set_settings(None)
            self.index.scan()
        self.assertIs(self.index.quota_cache, first_cache)
        # Existing DB needs one cache build in a new process, even with no append.
        self.index = Index(self.home, self.root / 'data')
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 15)
        self.write([self.event(2, 12)], append=True)
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 30)
        archived = self.home / 'archived_sessions'
        archived.mkdir()
        (archived / 'copy.jsonl').write_bytes((self.sessions / 'session.jsonl').read_bytes())
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 30)
        # Larger rewrite of same inode must also replace the old file events.
        (archived / 'copy.jsonl').unlink()
        self.write([meta('replacement-long-thread-name'), context(), self.event(1), self.event(2, 13), self.event(3, 14)])
        self.index.scan()
        # The copied archived events are retained as historical evidence.
        self.assertEqual(self.report()['summary']['total'], 75)
        self.write([meta('replacement-long-thread-name'), context(), self.event(1)])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 45)

    def test_report_waits_for_completed_scan_including_quota_cache(self):
        self.write([meta('test'), context(), self.event(1)])
        self.index.scan()
        self.write([self.event(2, 12)], append=True)
        ready, release, done = threading.Event(), threading.Event(), threading.Event()
        original = self.index.prepare_quota
        errors, result = [], []
        def prepare():
            if threading.current_thread() is scanner:
                ready.set()
                if not release.wait(5):
                    raise RuntimeError('Test gate timeout')
            original()
        def scan():
            try:
                self.index.scan()
            except Exception as exc:
                errors.append(exc)
        def read():
            try:
                result.append(self.report())
                result.append(self.index.token_curve(0, 253402300799))
                result.append(self.index.curve(0, 253402300799))
            finally:
                done.set()
        scanner = threading.Thread(target=scan)
        reader = threading.Thread(target=read)
        with patch.object(self.index, 'prepare_quota', side_effect=prepare):
            scanner.start()
            self.assertTrue(ready.wait(5))
            reader.start()
            try:
                self.assertFalse(done.wait(.1), 'Reader observed unfinished indexing pass')
            finally:
                release.set()
                scanner.join(5)
                reader.join(5)
        self.assertFalse(errors)
        self.assertFalse(scanner.is_alive())
        self.assertFalse(reader.is_alive())
        self.assertEqual(result[0]['summary']['total'], 30)
        self.assertEqual(result[0]['index']['events'], 2)
        self.assertEqual(result[1]['points'][-1]['total'], 30)
        self.assertEqual(result[2]['tokens']['points'][-1]['total'], 30)
        self.assertEqual(len(result[2]['curve']), 2)
        self.assertEqual(len(self.index.quota_cache['events']), 2)

    def test_growing_rewrite_after_large_identical_prefix(self):
        prefix = [meta('test'), context(), {'type': 'irrelevant', 'padding': 'x' * 9000}]
        self.write([*prefix, self.event(1)])
        self.index.scan()
        replacement = usage('2026-09-29T10:01:00Z', 30, 0, 15)
        self.write([*prefix, replacement, {'type': 'irrelevant', 'padding': 'y' * 500}])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'], 45)

    def test_project_root_persists_and_regroups_without_removing_history(self):
        root = self.root / 'projects'
        root.mkdir()
        nested = root / 'one' / 'src' / 'nested'
        row = meta('test')
        row['payload']['cwd'] = str(nested)
        self.write([row, context(), self.event(1)])
        self.index.scan()
        self.index.set_settings(str(root))
        self.assertEqual(self.report()['chats'][0]['project'], 'one')
        self.assertEqual(self.report()['summary']['total'], 15)
        self.index = Index(self.home, self.root / 'data')
        self.assertEqual(self.index.get_settings()['projects_root'], str(root.resolve()))
        self.assertEqual(self.report()['chats'][0]['project'], 'one')
        for invalid in ('relative', str(self.root / 'missing'), '', 123, []):
            with self.assertRaises(ValueError):
                self.index.set_settings(invalid)
        self.assertEqual(self.index.get_settings()['projects_root'], str(root.resolve()))
        self.index.set_settings(None)
        self.assertEqual(self.report()['chats'][0]['project'], 'nested')

    def test_git_ancestor_and_legacy_grouping_without_git_process(self):
        repo = self.root / 'repo'
        repo.mkdir()
        (repo / '.git').write_text('gitdir: elsewhere')
        resolver = ProjectResolver()
        with patch('subprocess.run', side_effect=AssertionError('Git must not run')):
            self.assertEqual(resolver.resolve(str(repo / 'src' / 'tests')), 'repo')
            self.assertEqual(resolver.resolve('C:\\old\\ai_projects\\legacy\\src'), 'legacy')
            self.assertEqual(resolver.resolve('C:\\other\\example'), 'example')
        windows = ProjectResolver('C:\\Users\\Test\\Projects')
        self.assertEqual(windows.resolve('c:\\users\\test\\projects\\First\\src'), 'First')
        self.assertEqual(windows.resolve('C:\\Users\\Test\\Projects2\\Other'), 'Без проекта')

    def test_project_root_matches_canonical_alias_with_missing_cwd_and_caches_it(self):
        root = self.root / 'canonical' / 'projects'
        root.mkdir(parents=True)
        canonical_root = root.resolve()
        alias = self.root / 'alias' / 'projects'
        cwd = alias / 'one' / 'src' / 'removed'
        self.assertFalse(cwd.exists())
        original_resolve = Path.resolve
        def resolve(path, strict=False):
            # Model /var -> /private/var or RUNNER~1 -> runneradmin without
            # depending on symlink permissions or 8.3-name creation in CI.
            try:
                suffix = path.relative_to(alias)
            except ValueError:
                return original_resolve(path, strict=strict)
            return canonical_root / suffix
        resolver = ProjectResolver(str(canonical_root))
        with patch('token_tracker.projects.Path.resolve', autospec=True, side_effect=resolve) as canonical:
            self.assertEqual(resolver.resolve(str(cwd)), 'one')
            self.assertEqual(resolver.resolve(str(cwd)), 'one')
            canonical.assert_called_once_with(cwd, strict=False)

    def test_project_root_preserves_foreign_and_historical_lexical_paths(self):
        historical = ProjectResolver(str(self.root / 'removed-projects'))
        with patch('token_tracker.projects.Path.resolve', side_effect=AssertionError('Lexical match needs no filesystem')):
            self.assertEqual(historical.resolve(str(self.root / 'removed-projects' / 'one' / 'src')), 'one')
        # A path from another OS must not be resolved against the current OS.
        foreign = 'C:\\foreign\\projects' if Path('/').is_absolute() else '/foreign/projects'
        with patch('token_tracker.projects.Path.resolve', side_effect=AssertionError('Foreign path accessed')):
            resolver = ProjectResolver(foreign)
            self.assertEqual(resolver.resolve(foreign + '/one/src'), 'one')
            self.assertEqual(resolver.resolve(foreign + '-other/two'), 'Без проекта')

    def test_project_root_matches_real_symlink_alias_with_missing_descendants(self):
        root = self.root / 'real-projects'
        root.mkdir()
        alias = self.root / 'alias-projects'
        try:
            alias.symlink_to(root, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f'Directory symlink creation unavailable: {exc}')
        try:
            resolver = ProjectResolver(str(root.resolve()))
            self.assertEqual(resolver.resolve(str(alias / 'one' / 'removed' / 'nested')), 'one')
        finally:
            alias.unlink()

    def test_existing_index_projects_migrate_once_without_reading_logs(self):
        row = meta('test')
        row['payload']['cwd'] = str(self.root / 'work' / 'my-app')
        self.write([row, context(), self.event(1)])
        self.index.scan()
        with self.index.connect() as con:
            con.execute("UPDATE threads SET project='Без проекта'")
            con.execute("DELETE FROM settings WHERE key='project_grouping_version'")
            offsets = [tuple(r) for r in con.execute('SELECT path,offset FROM files')]
        with patch('pathlib.Path.open', side_effect=AssertionError('Journal read during migration')):
            index = Index(self.home, self.root / 'data')
        self.assertEqual(index.report('2026-09-29', '2026-09-29')['chats'][0]['project'], 'my-app')
        with index.connect() as con:
            self.assertEqual([tuple(r) for r in con.execute('SELECT path,offset FROM files')], offsets)
        # The migration marker prevents regrouping on every startup.
        with patch('token_tracker.projects.ProjectResolver.resolve', side_effect=AssertionError('Repeated migration')):
            Index(self.home, self.root / 'data')

    def test_settings_and_picker_http_and_security(self):
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            server.index = self.index
            port = server.server_address[1]
            host = f'127.0.0.1:{port}'
            server.allowed_hosts = {host}
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def request(path, body=None, headers=None, method=None):
                data = None if body is None else json.dumps(body).encode()
                req = urllib.request.Request(f'http://{host}{path}', data=data,
                    headers=headers or {'Content-Type': 'application/json'}, method=method)
                try:
                    response = urllib.request.urlopen(req, timeout=5)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    return response.status, json.load(response)
            try:
                # Startup probes/assets must work while a scan owns the lock.
                with self.index.lock:
                    self.assertEqual(request('/api/health')[0], 200)
                    with urllib.request.urlopen(f'http://{host}/', timeout=5) as response:
                        self.assertEqual(response.status, 200)
                self.assertEqual(request('/api/settings'), (200, {'projects_root': None}))
                self.assertEqual(request('/api/settings', {'projects_root': str(self.root)})[0], 200)
                before = self.index.get_settings()
                with patch('token_tracker.server.pick_folder', return_value=None):
                    self.assertEqual(request('/api/projects/pick', {}), (200, dict(**before, cancelled=True)))
                with patch('token_tracker.server.pick_folder', return_value=str(self.home)):
                    self.assertEqual(request('/api/projects/pick', {}),
                                     (200, dict(projects_root=str(self.home.resolve()), cancelled=False)))
                with patch('token_tracker.server.pick_folder', side_effect=FolderPickerUnavailable('unavailable')):
                    code, body = request('/api/projects/pick', {})
                    self.assertEqual(code, 503)
                    self.assertEqual(body['code'], 'folder_picker_unavailable')
                self.assertEqual(request('/api/settings', {'projects_root': 'missing'})[0], 400)
                self.assertEqual(request('/api/settings', {'projects_root': None},
                    {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
                self.assertEqual(request('/api/settings', {'projects_root': None},
                    {'Content-Type': 'application/json', 'Host': 'evil.example'})[0], 403)
                self.assertEqual(request('/api/settings', {'projects_root': None},
                    {'Content-Type': 'text/plain'})[0], 415)
                self.assertEqual(request('/api/settings', {'projects_root': 'x' * 9000})[0], 413)
                self.assertEqual(request('/api/settings', {'projects_root': None},
                    {'Content-Type': 'application/json', 'Origin': f'http://{host}'})[0], 200)
            finally:
                server.shutdown()
                worker.join(5)

    def test_picker_timeout_and_bad_result_are_unavailable(self):
        import subprocess
        with patch('token_tracker.projects.subprocess.run', side_effect=subprocess.TimeoutExpired('picker', 120)):
            with self.assertRaises(FolderPickerUnavailable):
                pick_folder()
        with patch('token_tracker.projects.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'broken', '')):
            with self.assertRaises(FolderPickerUnavailable):
                pick_folder()


if __name__ == '__main__':
    unittest.main()
