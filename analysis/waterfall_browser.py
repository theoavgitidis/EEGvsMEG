"""Local, read-only Plotly waterfall viewer backed by an MNE Raw recording.

Only requested time intervals are serialized. Plotly is served from the installed
Python package: no recording data, fonts or scripts are sent to external hosts.
The tokenized server binds exclusively to IPv4 loopback and has no write routes.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit
import webbrowser

if __package__:
    from .waterfall_data import build_waterfall_data, channel_metadata
else:
    from waterfall_data import build_waterfall_data, channel_metadata


class WaterfallServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_waterfall_server(raw, *, start=0, duration=10, scale_uv=None,
                            title=None, filter_label="Unfiltered", port=0):
    """Return a bound server; callers run ``serve_forever`` and ``server_close``.

    ``server.url`` is the only viewer address. Constructing a server never opens
    a browser or modifies Raw. Port zero chooses a free local port.
    """
    if not raw.n_times or not raw.ch_names:
        raise ValueError("Die Wasserfallansicht benötigt EEG-Samples und Kanäle.")
    if (not math.isfinite(start) or start < 0 or start >= raw.n_times / raw.info['sfreq']
            or not math.isfinite(duration) or duration <= 0):
        raise ValueError("Start muss in der Aufnahme liegen; Dauer muss positiv sein.")
    if scale_uv is not None and (not math.isfinite(scale_uv) or scale_uv <= 0):
        raise ValueError("scale-uv muss endlich und positiv sein.")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port muss zwischen 0 und 65535 liegen.")
    try:
        from plotly.offline import get_plotlyjs
    except ImportError as exc:
        raise ValueError("Für die Wasserfallansicht fehlt Plotly. Installieren mit: "
                         "python -m pip install 'plotly>=6,<7'") from exc
    plotly_js = get_plotlyjs().encode('utf-8')
    html = Path(__file__).with_name('waterfall_view.html').read_bytes()
    prefix = '/' + secrets.token_urlsafe(24) + '/'
    metadata = dict(title=title or "EEG-Aufnahme", channels=channel_metadata(raw),
                    sfreq=float(raw.info['sfreq']), total_duration=raw.n_times / raw.info['sfreq'],
                    start=float(start), duration=min(float(duration), raw.n_times / raw.info['sfreq']),
                    scale_uv=scale_uv, filter_label=filter_label,
                    highpass=float(raw.info['highpass']), lowpass=float(raw.info['lowpass']))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, content, content_type):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                             "connect-src 'self'; font-src 'self' data:; worker-src blob:; "
                             "frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def json_response(self, value, code=200):
            self.respond(code, json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'),
                         'application/json; charset=utf-8')

        def do_GET(self):
            url = urlsplit(self.path)
            if len(self.path) > 8192:
                return self.json_response({'error': 'Anfrage zu lang.'}, 400)
            if not url.path.startswith(prefix):
                return self.json_response({'error': 'Nicht gefunden.'}, 404)
            resource = url.path[len(prefix):]
            if resource == '':
                return self.respond(200, html, 'text/html; charset=utf-8')
            if resource == 'plotly.min.js':
                return self.respond(200, plotly_js, 'text/javascript; charset=utf-8')
            if resource == 'meta':
                return self.json_response(metadata)
            if resource != 'data':
                return self.json_response({'error': 'Nicht gefunden.'}, 404)
            try:
                q = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
                allowed = {'start', 'duration', 'channels', 'low', 'high', 'window', 'hop', 'center'}
                if set(q) - allowed or any(len(v) != 1 for v in q.values()):
                    raise ValueError('Unbekannter oder mehrfacher Anzeigeparameter.')
                def number(name, default):
                    value = float(q.get(name, [default])[0])
                    if not math.isfinite(value):
                        raise ValueError(f'{name} muss endlich sein.')
                    return value
                channels = [int(v) for v in q['channels'][0].split(',')] if 'channels' in q else None
                center = q.get('center', ['1'])[0]
                if center not in ('0', '1'):
                    raise ValueError('center muss 0 oder 1 sein.')
                window, hop = number('window', 2), number('hop', .25)
                if not .25 <= window <= 30 or not .05 <= hop <= 30 or hop > window:
                    raise ValueError('Analysefenster: 0,25–30 s; Schritt: 0,05 s bis Fensterlänge.')
                data = build_waterfall_data(raw, start=number('start', start),
                    duration=number('duration', duration), channels=channels,
                    band=(number('low', 8), number('high', 13)), window=window, hop=hop,
                    center=center == '1', max_points=1600)
                return self.json_response(data)
            except (ValueError, TypeError, OverflowError) as exc:
                return self.json_response({'error': str(exc)}, 400)
            except Exception:
                # Report the failure without leaking local paths or recording data.
                return self.json_response({'error': 'Die Ansicht konnte nicht berechnet werden.'}, 500)

    server = WaterfallServer(('127.0.0.1', port), Handler)
    server.url = f'http://127.0.0.1:{server.server_port}{prefix}'
    server.metadata = metadata
    return server


def serve_waterfall(raw, *, start=0, duration=10, scale_uv=None, title=None,
                    filter_label="Unfiltered", open_browser=True, port=0):
    """Run the local viewer until Ctrl+C; all source files remain unchanged."""
    server = create_waterfall_server(raw, start=start, duration=duration, scale_uv=scale_uv,
                                     title=title, filter_label=filter_label, port=port)
    print(f'Wasserfallansicht: {server.url}\nLokal und offline. Beenden mit Strg+C.', flush=True)
    try:
        if open_browser:
            webbrowser.open(server.url)
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
