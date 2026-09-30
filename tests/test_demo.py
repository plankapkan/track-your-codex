import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from token_tracker.demo import DemoHandler, build_demo
from token_tracker.server import LocalHTTPServer


class DemoTests(unittest.TestCase):
    def test_demo_uses_only_fixture_home_and_groups_subagents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('pathlib.Path.home', side_effect=AssertionError('Real home accessed')):
                index = build_demo(root)
            self.assertEqual(index.home, root / 'home')
            report = index.report('2000-01-01', '2100-01-01', grouped=False)
            grouped = index.report('2000-01-01', '2100-01-01', grouped=True)
            self.assertEqual(report['summary']['calls'], 80)
            self.assertEqual(report['summary'], grouped['summary'])
            self.assertEqual({row['thread'] for row in report['chats']},
                             {'website', 'review', 'tests', 'docs'})
            self.assertNotIn('review', {row['thread'] for row in grouped['chats']})
            self.assertFalse(report['diagnostics'])
            with index.connect() as con:
                paths = [row[0] for row in con.execute('SELECT path FROM files')]
            self.assertTrue(all(Path(path).is_relative_to(root) for path in paths))

    def test_demo_page_labels_fictional_data_and_keeps_host_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            index = build_demo(Path(directory))
            with LocalHTTPServer(('127.0.0.1', 0), DemoHandler) as server:
                port = server.server_address[1]
                server.index = index
                server.allowed_hosts = {f'127.0.0.1:{port}'}
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = f'http://127.0.0.1:{port}'
                    with urllib.request.urlopen(base) as response:
                        self.assertIn('DEMO / ДЕМО', response.read().decode())
                    with urllib.request.urlopen(base + '/api/usage?hours=24') as response:
                        self.assertEqual(json.load(response)['summary']['calls'], 80)
                    request = urllib.request.Request(base, headers={'Host': 'example.com'})
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request)
                    self.assertEqual(caught.exception.code, 403)
                finally:
                    server.shutdown()
                    thread.join()


if __name__ == '__main__':
    unittest.main()
