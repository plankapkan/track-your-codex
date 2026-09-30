"""Foreground launcher, browser policy and startup/shutdown regression tests."""
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from token_tracker.cli import main
from token_tracker.server import Handler, LocalHTTPServer
from tests.test_monitor import meta, context, usage
from tests.test_packaging import REPO_ROOT


class StartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='token tracker launcher ')
        self.root = Path(self.temp.name)
        self.home, self.data = self.root / 'home', self.root / 'data'
        sessions = self.home / 'sessions'
        sessions.mkdir(parents=True)
        (sessions / 'fixture.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in
            [meta('launcher'), context(), usage('2026-09-29T10:01:00Z', 10, 0, 5)]), encoding='utf-8')
        self.args = ['--home', str(self.home), '--data', str(self.data), '--port', '0']
        self.env = os.environ.copy()
        self.env.pop('PYTHONPATH', None)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *args):
        return [sys.executable, str(REPO_ROOT / 'start.py'), *self.args, *args]

    def test_absolute_start_from_spaced_cwd_without_pythonpath_serves_and_stops(self):
        process = subprocess.Popen(self.command('--no-browser', '--interval', '5'), cwd=self.root,
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 20
            running = None
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    running = json.loads((self.data / 'running.json').read_text(encoding='utf-8'))
                    break
                except (OSError, ValueError):
                    time.sleep(.02)
            self.assertIsNotNone(running, 'Server did not publish running.json')
            url = running['url']
            self.assertGreater(urlparse(url).port, 0)
            self.assertEqual(running['pid'], process.pid)
            with urllib.request.urlopen(url + 'api/health', timeout=10) as response:
                self.assertEqual(json.load(response)['service'], 'codex-usage-monitor')
            with urllib.request.urlopen(url + 'api/usage?from=2026-09-29&to=2026-09-29', timeout=10) as response:
                self.assertEqual(json.load(response)['summary']['total'], 15)
            request = urllib.request.Request(url + 'api/health',
                headers={'Host': f'localhost:{urlparse(url).port}'})
            with urllib.request.urlopen(request, timeout=10) as response:
                self.assertEqual(response.status, 200)
            request = urllib.request.Request(url + 'api/health', headers={'Host': '127.0.0.1:0'})
            with self.assertRaises(urllib.error.HTTPError) as blocked:
                urllib.request.urlopen(request, timeout=10)
            self.assertEqual(blocked.exception.code, 403)
            (self.data / 'stop').touch()
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn(url, stdout)
            self.assertFalse((self.data / 'running.json').exists())
        finally:
            if process.poll() is None:
                self.data.mkdir(exist_ok=True)
                (self.data / 'stop').touch()
                try:
                    process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)
            else:
                process.communicate()

    def test_start_once_from_spaced_cwd_without_pythonpath(self):
        result = subprocess.run(self.command('--once', '--from', '2026-09-29', '--to', '2026-09-29'),
                                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['summary']['total'], 15)
        self.assertTrue((self.data / 'report.json').is_file())
        self.assertFalse((self.data / 'running.json').exists())

    def test_numeric_loopback_bind_and_monitor_start_do_not_resolve_names(self):
        # A slow or unavailable DNS service must not delay local startup.
        with contextlib.ExitStack() as stack:
            for name in ('getfqdn', 'gethostbyaddr', 'gethostbyname', 'getaddrinfo'):
                stack.enter_context(patch(f'socket.{name}', side_effect=AssertionError(f'DNS called: {name}')))
            with LocalHTTPServer(('127.0.0.1', 0), Handler) as server:
                self.assertEqual(server.server_name, '127.0.0.1')
                self.assertEqual(server.server_port, server.server_address[1])
                self.assertGreater(server.server_port, 0)
            with patch('token_tracker.cli.LocalHTTPServer.handle_request', autospec=True,
                       side_effect=self.stop_request), contextlib.redirect_stdout(io.StringIO()):
                main(self.args + ['--no-browser'])
            self.assertFalse((self.data / 'running.json').exists())

    def stop_request(self, server):
        (self.data / 'stop').touch()

    def test_browser_defaults_flags_and_successful_bind_before_opening(self):
        def open_after_start(url):
            running = json.loads((self.data / 'running.json').read_text(encoding='utf-8'))
            self.assertEqual(running['url'], url)
            parsed = urlparse(url)
            self.assertGreater(parsed.port, 0)
            with socket.create_connection((parsed.hostname, parsed.port), timeout=5):
                pass
            (self.data / 'stop').touch()
            return True
        for launcher_default, flags, should_open in (
                (True, [], True), (True, ['--no-browser'], False),
                (False, [], False), (False, ['--open-browser'], True)):
            with self.subTest(default=launcher_default, flags=flags):
                with patch('token_tracker.cli.webbrowser.open', side_effect=open_after_start) as browser, \
                     patch('token_tracker.cli.LocalHTTPServer.handle_request', autospec=True,
                           side_effect=self.stop_request), contextlib.redirect_stdout(io.StringIO()):
                    main(self.args + flags, open_browser=launcher_default)
                self.assertEqual(browser.call_count, int(should_open))
                self.assertFalse((self.data / 'running.json').exists())

    def test_browser_failure_does_not_stop_server_and_ctrl_c_releases_lock(self):
        with patch('token_tracker.cli.webbrowser.open', side_effect=RuntimeError('browser unavailable')) as browser, \
             patch('token_tracker.cli.LocalHTTPServer.handle_request', side_effect=KeyboardInterrupt) as handle, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
            main(self.args, open_browser=True)
        browser.assert_called_once()
        handle.assert_called_once()
        self.assertIn('Open http://127.0.0.1:', stderr.getvalue())
        self.assertFalse((self.data / 'running.json').exists())
        # A new run must be able to acquire the same data lock after Ctrl+C.
        with patch('token_tracker.cli.webbrowser.open') as browser, contextlib.redirect_stdout(io.StringIO()):
            main(self.args + ['--once'], open_browser=True)
        browser.assert_not_called()

    def test_help_once_invalid_args_and_bind_failure_never_open_browser(self):
        with patch('token_tracker.cli.webbrowser.open') as browser, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as help_exit:
                main(['--help'], open_browser=True)
            self.assertEqual(help_exit.exception.code, 0)
            self.assertFalse(self.data.exists())
            with self.assertRaises(SystemExit):
                main(self.args + ['--interval', '0'], open_browser=True)
            main(self.args + ['--once'], open_browser=True)
            with patch('token_tracker.cli.LocalHTTPServer', side_effect=OSError('port in use')):
                with self.assertRaises(SystemExit) as bind_exit:
                    main(self.args, open_browser=True)
            self.assertEqual(bind_exit.exception.code, 2)
            self.assertFalse((self.data / 'running.json').exists())
            main(self.args + ['--once'], open_browser=True)
        browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
