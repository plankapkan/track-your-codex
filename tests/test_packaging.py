"""Checks for package entrypoints and paths after moving out of the root."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import token_tracker
from token_tracker.indexer import Index
from token_tracker.server import Handler, LocalHTTPServer
from token_tracker.projects import pick_folder
from tests.test_monitor import meta, context, usage


REPO_ROOT = Path(token_tracker.__file__).resolve().parent.parent


class PackagingTests(unittest.TestCase):
    def run_python(self, args, cwd):
        env = os.environ.copy()
        env['PYTHONPATH'] = str(REPO_ROOT) + os.pathsep + env.get('PYTHONPATH', '')
        result = subprocess.run([sys.executable, *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_entrypoints_and_default_data_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            for module in ('token_tracker', 'token_tracker.demo'):
                with self.subTest(module=module):
                    output = self.run_python(['-m', module, '--help'], directory)
                    self.assertIn('--port', output)
            output = self.run_python(['-c',
                'from token_tracker.cli import build_parser; print(build_parser().parse_args([]).data)'], directory)
            self.assertEqual(Path(output.strip()), REPO_ROOT / 'data')
            output = self.run_python(['-m', 'scripts.benchmark_backend',
                                     '--events', '20', '--files', '2', '--repeats', '1'], directory)
            self.assertEqual(json.loads(output)['events'], 20)

    def test_once_entrypoint_writes_only_selected_data_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, data = root / 'home', root / 'data'
            sessions = home / 'sessions'
            sessions.mkdir(parents=True)
            (sessions / 'fixture.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in
                [meta('package'), context(), usage('2026-09-29T10:01:00Z', 10, 0, 5)]), encoding='utf-8')
            output = self.run_python(['-m', 'token_tracker', '--once', '--home', str(home),
                                      '--data', str(data), '--from', '2026-09-29', '--to', '2026-09-29'], root)
            self.assertEqual(json.loads(output)['summary']['total'], 15)
            self.assertEqual(json.loads((data / 'report.json').read_text(encoding='utf-8'))['summary']['total'], 15)
            self.assertTrue((data / 'usage.sqlite').is_file())
            self.assertTrue((data / 'chats.csv').is_file())

    def test_every_static_url_serves_packaged_file_from_other_cwd(self):
        assets = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
                  '/app.js': ('app.js', 'text/javascript'), '/theme.js': ('theme.js', 'text/javascript'),
                  '/i18n.js': ('i18n.js', 'text/javascript'), '/charts.js': ('charts.js', 'text/javascript')}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = Index(root / 'home', root / 'data')
            with LocalHTTPServer(('127.0.0.1', 0), Handler) as server:
                port = server.server_address[1]
                server.index = index
                server.allowed_hosts = {f'127.0.0.1:{port}'}
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                previous = Path.cwd()
                try:
                    os.chdir(root)
                    worker.start()
                    for url, (name, mime) in assets.items():
                        with self.subTest(url=url):
                            expected = (REPO_ROOT / 'token_tracker' / 'web' / name).read_bytes()
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}{url}', timeout=5) as response:
                                self.assertEqual(response.headers.get_content_type(), mime)
                                self.assertEqual(response.read(), expected)
                finally:
                    os.chdir(previous)
                    server.shutdown()
                    worker.join(5)

    def test_picker_subprocess_keeps_absolute_packaged_script_path(self):
        with patch('token_tracker.projects.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 0, 'null', '')) as run:
            self.assertIsNone(pick_folder())
        argv = run.call_args.args[0]
        self.assertEqual(argv, [sys.executable, str(REPO_ROOT / 'token_tracker' / 'projects.py'), '--pick'])
        self.assertTrue(Path(argv[1]).is_file())
        self.assertEqual(run.call_args.kwargs['timeout'], 120)


if __name__ == '__main__':
    unittest.main()
