"""Try the dashboard with fictional data. Never reads your Codex directory."""
import argparse
import json
import tempfile
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .server import Handler, LocalHTTPServer
from .indexer import Index


def build_demo(root, now=None):
    """Create synthetic logs and an index entirely inside the supplied directory."""
    now = now or datetime.now(timezone.utc)
    home = root / 'home'
    sessions = home / 'sessions'
    sessions.mkdir(parents=True)
    start = now - timedelta(hours=22)
    reset = int((start + timedelta(days=7)).timestamp())
    chats = [
        ('website', 'Build a portfolio website', 'portfolio', 'gpt-6.1-sol', None, 12),
        ('review', 'Review the layout', 'portfolio', 'gpt-6-astra', 'website', 5),
        ('tests', 'Fix failing tests', 'task-board', 'gpt-6.1-sol', None, 8),
        ('docs', 'Update the install guide', 'task-board', 'gpt-6-luna', None, 3),
    ]
    names = []
    for number, (sid, title, project, model, parent, scale) in enumerate(chats):
        metadata = dict(id=sid, timestamp=start.isoformat(), cwd=f'/demo/ai_projects/{project}')
        if parent:
            metadata['parent_thread_id'] = parent
        events = [dict(type='session_meta', timestamp=start.isoformat(), payload=metadata)]
        totals = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0,
                      reasoning_output_tokens=0, total_tokens=0)
        for step in range(20):
            stamp = start + timedelta(hours=step, minutes=number * 7)
            fresh = scale * (1800 + step * 80)
            cached = scale * (8000 + step * 900)
            output = scale * (300 + step * 15)
            last = dict(input_tokens=fresh + cached, cached_input_tokens=cached,
                        output_tokens=output, reasoning_output_tokens=output // 2,
                        total_tokens=fresh + cached + output)
            totals = {key: totals[key] + last[key] for key in totals}
            events.append(dict(type='turn_context', payload=dict(
                model=model, effort='medium', turn_id=f'{sid}-{step}')))
            events.append(dict(type='event_msg', timestamp=stamp.isoformat(), payload=dict(
                type='token_count', info=dict(total_token_usage=totals.copy(), last_token_usage=last),
                rate_limits=dict(limit_id='codex', plan_type='demo', secondary=dict(
                    window_minutes=10080, used_percent=10 + step * 2 + number * .4,
                    resets_at=reset)))))
        (sessions / f'{sid}.jsonl').write_text(
            ''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
        names.append(dict(id=sid, thread_name=title))
    (home / 'session_index.jsonl').write_text(
        ''.join(json.dumps(name) + '\n' for name in names), encoding='utf-8')
    index = Index(home, root / 'data')
    index.scan()
    return index


class DemoHandler(Handler):
    def send(self, status, body, mime):
        if mime.startswith('text/html') and status == 200:
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            banner = ('<aside class="demo-banner">'
                      '<strong>DEMO / ДЕМО</strong> — Fictional data. Your Codex logs are not read.'
                      ' / Вымышленные данные. Ваши журналы не читаются.</aside>')
            body = body.replace('<body>', '<body>' + banner, 1)
        elif mime.startswith('text/css') and status == 200:
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            body += ('\n.demo-banner {padding:12px 20px;background:#fff0bf;color:#332600;'
                     'text-align:center;font:15px system-ui;}\n')
        super().send(status, body, mime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='track-your-codex-demo-') as directory:
        index = build_demo(Path(directory))
        with LocalHTTPServer(('127.0.0.1', args.port), DemoHandler) as server:
            port = server.server_address[1]
            server.index = index
            server.allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            url = f'http://127.0.0.1:{port}/'
            print(f'Demo: {url} (fictional data; Ctrl+C to stop)', flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
