"""HTTP, both real CLI entry points, and optional real Chrome ERD/ERS QA."""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

from analysis.erds_browser import create_erds_server
from analysis.erds_data import compute_erds
from analysis.test_erds import synthetic_session, write_session


class ERDSCLITest(unittest.TestCase):
    def test_both_scripts_and_module_use_oscar_and_export_same_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_session(directory)
            root = Path(__file__).resolve().parents[1]
            reports = []
            for i, invocation in enumerate([['view_eeg.py'], ['analysis/view_eeg.py'], ['-m', 'analysis.view_eeg']]):
                target = Path(directory) / f'export-{i}'
                command = [sys.executable, *invocation, str(path), '--unit', 'uV', '--view', 'erds',
                           '--no-show', '--erds-export', str(target)]
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                reports.append(json.loads((target / 'report.json').read_text()))
                self.assertIn('OSCAR', result.stdout)
            self.assertEqual(reports[0], reports[1]); self.assertEqual(reports[0], reports[2])

    def test_raw_requires_explicit_flag_and_filters_fail_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_session(directory, oscar=False)
            root = Path(__file__).resolve().parents[1]
            for entry in ('view_eeg.py', 'analysis/view_eeg.py'):
                command = [sys.executable, entry, str(path), '--unit', 'uV', '--view', 'erds', '--no-show']
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('confirmed OSCAR', result.stderr)
                result = subprocess.run(command + ['--signal', 'raw'], cwd=root, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Rohdaten', result.stdout)
                target = Path(directory) / 'must-not-exist'
                option = ['--highpass', '1'] if entry == 'view_eeg.py' else ['--filtered']
                result = subprocess.run(command + ['--signal', 'raw', '--erds-export', str(target), *option],
                                        cwd=root, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(target.exists())


class ERDSServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data, events = synthetic_session()
        cls.result = compute_erds(data, events)
        cls.result['metadata'].update(signal='oscar', signal_description='OSCAR · synthetische Prüfung')
        cls.server = create_erds_server(cls.result, title='<script>untrusted title</script>')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(3)

    def request(self, resource, method='GET'):
        address = urlsplit(self.server.url)
        connection = http.client.HTTPConnection(address.hostname, address.port, timeout=5)
        connection.request(method, address.path + resource)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, dict(response.getheaders()), data

    def test_local_assets_strict_json_exports_and_no_mutating_routes(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        status, headers, body = self.request('')
        self.assertEqual(status, 200)
        self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
        self.assertIn(b'src="plotly.min.js"', body)
        self.assertNotIn(b'https://', body)
        status, _, body = self.request('data')
        payload = json.loads(body, parse_constant=lambda x: self.fail('Nonstandard JSON: ' + x))
        self.assertAlmostEqual(payload['conditions']['me_hand_right']['task_percent'][1][0], -75)
        self.assertEqual(payload['title'], '<script>untrusted title</script>')
        self.assertEqual(len(payload['geometry']['sensors_mm']), 8)
        status, headers, body = self.request('report.json')
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertIn(b'normalization', body)
        self.assertIn(b'reference_uV2', self.request('summary.csv')[2])
        self.assertEqual(self.request('../data')[0], 404)
        self.assertEqual(self.request('data', method='POST')[0], 501)


_CHROME = os.environ.get('EEG_BROWSER_EXECUTABLE') or next((str(p) for p in (
    Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
    Path(shutil.which('google-chrome') or '/nonexistent'),
    Path(shutil.which('chromium') or '/nonexistent'),
) if p.is_file()), None)
_AVAILABLE = _CHROME and importlib.util.find_spec('playwright')


@unittest.skipUnless(_AVAILABLE, 'Optional: playwright und installiertes Chrome erforderlich.')
class ERDSUITest(ERDSServerTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=_CHROME, headless=True,
            args=['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop(); super().tearDownClass()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1450, 'height': 1100})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(self.server.url)
        self.ready()

    def ready(self):
        self.page.wait_for_function("() => document.getElementById('status').textContent.startsWith('Bereit')")
        self.page.evaluate('() => state.rendering')

    def test_head_click_table_curve_sync_scales_and_missing_data(self):
        p = self.page
        p.evaluate("() => {window.originalHeadMesh=document.getElementById('head-left').data[0].x;}")
        self.assertEqual(p.locator('#head-left').evaluate('(e)=>e.data[1].text.length'), 8)
        self.assertIn('<script>', p.locator('#recording').inner_text())
        self.assertEqual(p.locator('#recording script').count(), 0)
        right = p.locator('#head-right').evaluate('(e)=>e.data[1].marker.color')
        self.assertAlmostEqual(right[1], -75)
        self.assertAlmostEqual(right[3], 0, places=8)
        p.evaluate("() => { const g=document.getElementById('head-right');const t=g.data[1];g.emit('plotly_click',{points:[{data:t,customdata:t.customdata[3]}]});}")
        self.ready()
        self.assertEqual(p.locator('#channel').input_value(), '3')
        self.assertIn('C4', p.locator('#curve-title').inner_text())
        p.locator('#values tr').nth(1).click(); self.ready()
        self.assertEqual(p.locator('#channel').input_value(), '1')
        self.assertIn('ERD/ERS', p.locator('#curves').evaluate('(e)=>e.layout.yaxis.title.text'))
        p.locator('#mode').select_option('rebound'); p.locator('#band').select_option('1'); self.ready()
        self.assertAlmostEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].marker.color[1]'), 300)
        self.assertIn('1 Werte außerhalb', p.locator('#clip-right').inner_text())
        p.locator('#scale-max').fill('400'); p.locator('#scale-max').press('Tab'); self.ready()
        p.locator('#mode').select_option('time'); self.ready()
        p.locator('#time').fill('65'); self.ready()
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].marker.cmax'), 400)
        p.locator('#family').select_option('mi'); self.ready()
        self.assertEqual(p.locator('#scale-max').input_value(), '400')
        p.locator('#metric').select_option('power'); self.ready()
        self.assertGreater(float(p.locator('#scale-max').input_value()), 0)
        p.locator('#metric').select_option('percent'); self.ready()
        self.assertEqual(p.locator('#scale-max').input_value(), '400')
        self.assertTrue(p.locator('#head-left').evaluate('(e)=>e.data[0].x===window.originalHeadMesh'))
        self.assertFalse(self.errors)

    def test_camera_rotation_export_and_visual_layout(self):
        p = self.page
        p.get_by_role('button', name='Linke Seite', exact=True).click()
        p.wait_for_function("() => document.getElementById('head-left').layout.scene.camera.eye.x < -2")
        p.locator('#mode').select_option('rebound'); self.ready()
        self.assertLess(p.locator('#head-left').evaluate('(e)=>e.layout.scene.camera.eye.x'), -2)
        p.get_by_role('button', name='Von oben', exact=True).click()
        box = p.locator('#head-left').bounding_box()
        p.mouse.move(box['x'] + box['width'] * .4, box['y'] + box['height'] * .5)
        p.mouse.down(); p.mouse.move(box['x'] + box['width'] * .6, box['y'] + box['height'] * .6, steps=8); p.mouse.up()
        p.wait_for_function("() => Math.abs(document.getElementById('head-left').layout.scene.camera.eye.x)>0.01")
        with p.expect_download() as downloaded:
            p.get_by_role('link', name='Ergebnisse + Metadaten (JSON)', exact=True).click()
        report = json.loads(Path(downloaded.value.path()).read_text())
        self.assertEqual(report['metadata']['signal'], 'oscar')
        with p.expect_download() as downloaded:
            p.get_by_role('button', name='Kurven als PNG', exact=True).click()
        self.assertEqual(Path(downloaded.value.path()).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        p.screenshot(path='/private/tmp/erds-browser-qa.png', full_page=True)
        self.assertFalse(self.errors)
        p.set_viewport_size({'width': 600, 'height': 900})
        p.wait_for_function('() => document.documentElement.scrollWidth <= 600')
        p.screenshot(path='/private/tmp/erds-browser-mobile-qa.png', full_page=True)


if __name__ == '__main__':
    unittest.main()
