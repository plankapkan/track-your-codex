"""Loopback HTTP dashboard and settings endpoints."""
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from common import MSK
from reports import csv_text
from projects import pick_folder, FolderPickerUnavailable

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, content_type):
        encoded = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or self.headers.get('Host') not in self.server.allowed_hosts:
            self.send(403, 'Local access only', 'text/plain; charset=utf-8')
            return
        url = urlparse(self.path)
        assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/theme.js': ('theme.js', 'text/javascript'), '/style.css': ('style.css', 'text/css'), '/i18n.js': ('i18n.js', 'text/javascript'), '/charts.js': ('charts.js', 'text/javascript')}
        if url.path in assets:
            name, mime = assets[url.path]
            self.send(200, (Path(__file__).parent / name).read_bytes(), mime + '; charset=utf-8')
            return
        if url.path == '/api/health':
            self.send(200, json.dumps(dict(service='codex-usage-monitor', index=self.server.index.status)), 'application/json; charset=utf-8')
            return
        if url.path == '/api/settings':
            self.send(200, json.dumps(self.server.index.get_settings()), 'application/json; charset=utf-8')
            return
        if url.path == '/api/curve':
            args = parse_qs(url.query)
            try:
                hours = int(args.get('hours', ['24'])[0])
                if hours not in (1, 5, 24, 168, 720):
                    raise ValueError('Unsupported chart interval')
                final = datetime.now(MSK).timestamp()
                first = final - hours * 3600
                if 'first_time' in args or 'final_time' in args:
                    if 'first_time' not in args or 'final_time' not in args:
                        raise ValueError('Both chart boundaries are required')
                    first = float(args['first_time'][0])
                    final = float(args['final_time'][0])
                    if not (0 <= first < final <= 253402300799):
                        raise ValueError('Invalid chart boundaries')
                data = self.server.index.curve(first, final)
                self.send(200, json.dumps(data), 'application/json; charset=utf-8')
            except ValueError as exc:
                self.send(400, json.dumps(dict(error=str(exc))), 'application/json; charset=utf-8')
            return
        if url.path not in ('/api/usage', '/api/export'):
            self.send(404, 'Not found', 'text/plain')
            return
        args = {k: v[0] for k, v in parse_qs(url.query).items()}
        today = datetime.now(MSK).date()
        try:
            data = self.server.index.report(args.get('from', (today-timedelta(days=6)).isoformat()),
                args.get('to', today.isoformat()), args.get('project', ''), args.get('model', ''),
                args.get('grouped', '1') != '0',args.get('cycle','0')=='1', hours=args.get('hours'),
                start_time=args.get('start_time'), end_time=args.get('end_time'))
            if url.path == '/api/export':
                self.send(200, csv_text(data['models'] if args.get('table') == 'models' else data['chats']), 'text/csv; charset=utf-8')
            else:
                self.send(200, json.dumps(data, ensure_ascii=False), 'application/json; charset=utf-8')
        except ValueError as exc:
            self.send(400, json.dumps(dict(error=str(exc)), ensure_ascii=False), 'application/json; charset=utf-8')
        except Exception as exc:
            self.send(500, json.dumps(dict(error=f'{type(exc).__name__}: {exc}')), 'application/json; charset=utf-8')

    def do_POST(self):
        mime = 'application/json; charset=utf-8'
        def error(status, message, **extra):
            self.send(status, json.dumps(dict(error=message, **extra), ensure_ascii=False), mime)
        host = self.headers.get('Host')
        origin = self.headers.get('Origin')
        if (host not in self.server.allowed_hosts or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                or (origin is not None and origin != f'http://{host}')):
            error(403, 'Local access only')
            return
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
            error(415, 'Content-Type must be application/json')
            return
        if self.headers.get('Transfer-Encoding'):
            error(400, 'Transfer-Encoding is not supported')
            return
        try:
            length = int(self.headers.get('Content-Length', ''))
            if not 0 <= length <= 8192:
                error(413, 'Request body is too large')
                return
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('JSON body must be an object')
        except (ValueError, UnicodeError) as exc:
            error(400, str(exc))
            return
        except TimeoutError:
            error(408, 'Request body timed out')
            return
        path = urlparse(self.path).path
        try:
            if path == '/api/settings':
                if set(body) != {'projects_root'}:
                    raise ValueError('Expected projects_root')
                result = self.server.index.set_settings(body['projects_root'])
            elif path == '/api/projects/pick':
                if body:
                    raise ValueError('Expected an empty JSON object')
                selected = pick_folder()
                result = (self.server.index.set_settings(selected) if selected is not None
                          else self.server.index.get_settings())
                result['cancelled'] = selected is None
            else:
                error(404, 'Not found')
                return
            self.send(200, json.dumps(result, ensure_ascii=False), mime)
        except FolderPickerUnavailable as exc:
            error(503, str(exc), code='folder_picker_unavailable')
        except (ValueError, OSError) as exc:
            error(400, str(exc))
