"""Local Codex usage monitor. Python standard library only; no model/API calls."""
import argparse
import json
import os
import threading
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from .common import MSK
from .indexer import Index
from .reports import csv_text
from .server import Handler

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

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home()/'.codex')
    parser.add_argument('--data', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--from', dest='start')
    parser.add_argument('--to', dest='end')
    return parser


def main():
    parser = build_parser()
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
