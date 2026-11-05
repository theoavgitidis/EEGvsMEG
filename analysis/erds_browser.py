"""Local-only, read-only ERD/ERS browser; no external assets or write routes."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import csv
import io
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit
import webbrowser

from .erds_data import head_geometry, json_safe


def create_erds_server(result, *, title='Handbewegungen · ERD/ERS', port=0):
    from plotly.offline import get_plotlyjs
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError('Port muss zwischen 0 und 65535 liegen.')
    payload = json_safe(dict(result, title=title, geometry=head_geometry()))
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    javascript = get_plotlyjs().encode('utf-8')
    html = Path(__file__).with_name('erds_view.html').read_bytes()
    summary = io.StringIO(newline='')
    writer = csv.writer(summary)
    writer.writerow(['condition', 'channel', 'band', 'n', 'reference_uV2',
                     'task_uV2', 'task_percent', 'rebound_uV2', 'rebound_percent'])
    for condition, values in payload['conditions'].items():
        if values['n']:
            for ci, channel in enumerate(payload['channels']):
                for bi, band in enumerate(payload['bands']):
                    writer.writerow([condition, channel['site'], band['id'], values['n'],
                        values['reference'][ci][bi], values['task_power'][ci][bi], values['task_percent'][ci][bi],
                        values['rebound_power'][ci][bi], values['rebound_percent'][ci][bi]])
    prefix = '/' + secrets.token_urlsafe(24) + '/'
    resources = {'': (html, 'text/html; charset=utf-8'),
                 'plotly.min.js': (javascript, 'text/javascript; charset=utf-8'),
                 'data': (data, 'application/json; charset=utf-8'),
                 'report.json': (data, 'application/json; charset=utf-8'),
                 'summary.csv': (summary.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            url = urlsplit(self.path)
            key = url.path[len(prefix):] if url.path.startswith(prefix) else None
            content, kind = resources.get(key, (b'Not found', 'text/plain'))
            self.send_response(200 if key in resources else 404)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; "
                "worker-src blob:; frame-ancestors 'none'; base-uri 'none'")
            if key in ('report.json', 'summary.csv'):
                self.send_header('Content-Disposition', f'attachment; filename="erds-{key}"')
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.url = f'http://127.0.0.1:{server.server_port}{prefix}'
    return server


def serve_erds(result, *, title='Handbewegungen · ERD/ERS', open_browser=True):
    server = create_erds_server(result, title=title)
    print(f'ERD/ERS-Kopfansicht: {server.url}\nLokal und offline. Beenden mit Strg+C.', flush=True)
    try:
        if open_browser:
            webbrowser.open(server.url)
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
