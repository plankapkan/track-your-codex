"""Local Codex usage monitor. Python standard library only; no model/API calls."""
import argparse
import json
import os
import threading
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from .common import MSK
from .indexer import Index
from .reports import csv_text
from .server import Handler, LocalHTTPServer

DEFAULT_DATA = Path(__file__).resolve().parents[1] / 'data'

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

def build_parser(open_browser=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home()/'.codex')
    parser.add_argument('--data', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--from', dest='start')
    parser.add_argument('--to', dest='end')
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument('--open-browser', dest='open_browser', action='store_true',
                         help='Open the dashboard in your default browser')
    browser.add_argument('--no-browser', dest='open_browser', action='store_false',
                         help='Do not open a browser')
    parser.set_defaults(open_browser=open_browser)
    return parser


def main(argv=None, *, open_browser=False):
    parser = build_parser(open_browser=open_browser)
    args = parser.parse_args(argv)
    if args.interval < 5:
        parser.error('--interval must be at least 5 seconds')
    try:
        lock = RunLock(args.data / 'run.lock')
    except OSError:
        parser.error('Monitor already running for this data directory')
    try:
        index = Index(args.home, args.data, lazy=True)
        stop_file = args.data / 'stop'
        stop_file.unlink(missing_ok=True)
        if args.once:
            index.scan()
            today = datetime.now(MSK).date()
            result = index.report(args.start or (today-timedelta(days=6)).isoformat(), args.end or today.isoformat())
            (args.data / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            (args.data / 'chats.csv').write_text(csv_text(result['chats']), encoding='utf-8')
            print(json.dumps(dict(summary=result['summary'], index=result['index'], diagnostics=result['diagnostics']), ensure_ascii=True))
            return
        try:
            server = LocalHTTPServer(('127.0.0.1', args.port), Handler)
        except OSError as exc:
            parser.error(f'Cannot start local server: {exc}')
        with server:
            port = server.server_address[1]
            url = f'http://127.0.0.1:{port}/'
            server.daemon_threads = True
            server.index = index
            server.allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            server.timeout = 1
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
            try:
                watcher.start()
                (args.data / 'running.json').write_text(json.dumps(dict(pid=os.getpid(), url=url)), encoding='utf-8')
                print(f'Usage monitor: {url}', flush=True)
                if args.open_browser:
                    try:
                        webbrowser.open(url)
                    except Exception as exc:
                        print(f'Could not open browser: {exc}. Open {url} manually.', file=sys.stderr)
                while not stop_file.exists():
                    server.handle_request()
            except KeyboardInterrupt:
                pass
            finally:
                stopping.set()
                if watcher.ident is not None:
                    watcher.join(timeout=5)
                (args.data / 'running.json').unlink(missing_ok=True)
    finally:
        lock.close()

if __name__ == '__main__':
    main()
