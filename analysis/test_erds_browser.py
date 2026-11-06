"""HTTP, both real CLI entry points, and optional real Chrome ERD/ERS QA."""
import csv
import http.client
import importlib.util
import io
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

import numpy as np

from analysis.erds_browser import create_erds_server
from analysis.erds_data import compute_erds
from analysis.test_erds import synthetic_baseline_session, synthetic_session, write_session


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
        self.assertNotIn('_trial_data', payload)
        self.assertIn(b"function colorFor", self.request('erds_view.js')[2])
        status, headers, body = self.request('report.json')
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertIn(b'normalization', body)
        self.assertIn(b'reference_uV2', self.request('summary.csv')[2])
        self.assertEqual(self.request('../data')[0], 404)
        self.assertEqual(self.request('data', method='POST')[0], 501)

    def test_selective_trial_endpoints_validate_selection_and_keep_own_reference(self):
        status, _, body = self.request('trial?key=Motorik%2F2%2F2%2F1&channel=C3')
        self.assertEqual(status, 200)
        detail = json.loads(body, parse_constant=lambda x: self.fail(x))
        self.assertEqual(detail['key'], 'Motorik/2/2/1')
        self.assertEqual(detail['trials'][0]['ordinal'], 2)
        self.assertAlmostEqual(detail['task_percent'][1][0], -75)
        self.assertEqual(len(detail['spectral_percent']), 35)
        self.assertEqual(len(detail['waveform_uv']), 12 * 250)
        status, _, body = self.request('channel?channel=C3&band=mu')
        self.assertEqual(status, 200)
        rows = json.loads(body)['conditions']['me_hand_right']
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[1]['task_percent'], -75)
        for resource in ('trial?key=unknown&channel=C3', 'trial?key=Motorik/2/2/1&channel=unknown',
                         'trial?key=Motorik/2/2/1', 'trial?key=Motorik/2/2/1&channel=C3&channel=C4',
                         'channel?channel=C3&band=unknown', 'channel?channel=C3&band=mu&other=1'):
            self.assertEqual(self.request(resource)[0], 400, resource)

    def test_baseline_endpoint_explicit_reference_and_strict_selection(self):
        key = 'prepare/Motorik/1/1/1'
        status, _, body = self.request(f'baseline?key={key}&reference={key}&channel=C3')
        self.assertEqual(status, 200)
        detail = json.loads(body, parse_constant=lambda x: self.fail(x))
        self.assertEqual(detail['section']['kind'], 'prepare')
        self.assertEqual(detail['section']['n_valid_windows'], 11)
        self.assertAlmostEqual(detail['reference'][1][0], 50)
        self.assertAlmostEqual(detail['mean_percent'][1][0], 0)
        self.assertEqual(len(detail['waveform_uv']), 500)
        for resource in (f'baseline?key={key}&channel=C3', f'baseline?key={key}&reference=unknown&channel=C3',
                         f'baseline?key={key}&reference={key}&channel=C3&extra=1',
                         f'baseline?key={key}&reference={key}&channel=C3&channel=C4'):
            self.assertEqual(self.request(resource)[0], 400, resource)


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
        right = p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values')
        self.assertAlmostEqual(right[1], -75)
        self.assertAlmostEqual(right[3], 0, places=8)
        colors = p.locator('#head-right').evaluate('(e)=>e.data[1].marker.color')
        self.assertNotEqual(colors[1], colors[3])
        self.assertEqual(colors[3], 'rgb(247,247,247)')
        self.assertEqual(p.locator('#bars-right').evaluate('(e)=>e.data[0].marker.color'), colors)
        p.evaluate("() => { const g=document.getElementById('head-right');const t=g.data[1];g.emit('plotly_click',{points:[{data:t,customdata:t.customdata[3]}]});}")
        self.ready()
        self.assertEqual(p.locator('#channel').input_value(), '3')
        self.assertTrue(p.locator('#curve-title').inner_text().startswith('C3 ·'))
        self.assertTrue(p.locator('#curve-title-c4').inner_text().startswith('C4 ·'))
        self.assertIn('C4', p.locator('#tf-title').inner_text())
        p.locator('#values tr').nth(1).click(); self.ready()
        self.assertEqual(p.locator('#channel').input_value(), '1')
        self.assertIn('ERD/ERS', p.locator('#curves').evaluate('(e)=>e.layout.yaxis.title.text'))
        p.locator('#mode').select_option('rebound'); p.locator('#band').select_option('1'); self.ready()
        self.assertAlmostEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values[1]'), 300)
        self.assertIn('1 Werte außerhalb', p.locator('#clip-right').inner_text())
        p.locator('#scale-max').fill('400'); p.locator('#scale-max').press('Tab'); self.ready()
        p.locator('#mode').select_option('time'); self.ready()
        p.locator('#time').fill('65'); self.ready()
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[3].marker.cmax'), 400)
        p.locator('#family').select_option('mi'); self.ready()
        self.assertEqual(p.locator('#scale-max').input_value(), '400')
        p.locator('#metric').select_option('power'); self.ready()
        self.assertGreater(float(p.locator('#scale-max').input_value()), 0)
        self.assertIn('keine ERD/ERS-Farbkodierung', p.locator('#color-note').inner_text())
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.yaxis.range'),
                         p.locator('#curves-c4').evaluate('(e)=>e.layout.yaxis.range'))
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
            p.get_by_role('link', name='Gesamtergebnisse + Metadaten (JSON)', exact=True).click()
        report = json.loads(Path(downloaded.value.path()).read_text())
        self.assertEqual(report['metadata']['signal'], 'oscar')
        with p.expect_download() as downloaded:
            p.get_by_role('button', name='C3-Kurven als PNG', exact=True).click()
        self.assertEqual(Path(downloaded.value.path()).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertIn('-C3', downloaded.value.suggested_filename)
        p.locator('#channel').select_option('1'); self.ready()
        with p.expect_download() as downloaded:
            p.get_by_role('button', name='C4-Kurven als PNG', exact=True).click()
        self.assertEqual(Path(downloaded.value.path()).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertIn('-C4', downloaded.value.suggested_filename)
        p.screenshot(path='/private/tmp/erds-browser-qa.png', full_page=True)
        self.assertFalse(self.errors)
        p.set_viewport_size({'width': 600, 'height': 900})
        p.wait_for_function('() => document.documentElement.scrollWidth <= 600')
        p.screenshot(path='/private/tmp/erds-browser-mobile-qa.png', full_page=True)

    def test_single_trials_navigation_heatmap_sync_and_selection_export(self):
        p = self.page
        self.assertIn('Mittelwert aus 2 Trials', p.locator('#selection-summary').inner_text())
        original = p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values')
        p.locator('#scope').select_option('single'); self.ready()
        self.assertIn('Block 1 · Trial 2 · Attempt 1', p.locator('#title-right').inner_text())
        self.assertTrue(p.locator('#waveform-panel').is_visible())
        self.assertIn('eigene Vorbereitung', p.locator('#selection-summary').inner_text())
        self.assertEqual(p.locator('#values tr').nth(1).locator('td').nth(5).inner_text(), '1')
        p.locator('#next-right').click(); self.ready()
        self.assertEqual(p.locator('#trial-right').input_value(), 'Motorik/2/2/1')
        self.assertEqual(p.locator('#trial-left').input_value(), 'Motorik/1/1/1')
        self.assertIn('Block 2 · Trial 2', p.locator('#title-right').inner_text())
        self.assertTrue(p.locator('#next-right').is_disabled())
        # Head, table, curves and selected-channel TFR all use the same trial.
        np.testing.assert_allclose(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values'), original, atol=1e-9)
        self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.data[3].y[35]'), -75)
        self.assertAlmostEqual(p.locator('#tf-right').evaluate('(e)=>e.data[0].z[4][35]'), -75)
        self.assertEqual(p.locator('#waveform').evaluate('(e)=>e.data[1].y.length'), 3000)
        p.locator('#channel').select_option('3'); self.ready()
        self.assertAlmostEqual(p.locator('#tf-right').evaluate('(e)=>e.data[0].z[4][35]'), 0, places=8)
        self.assertGreaterEqual(p.locator('#curves').evaluate('(e)=>e.layout.yaxis.range[1]-e.layout.yaxis.range[0]'), 1)
        self.assertIn('C4', p.locator('#waveform-title').inner_text())
        # Clicking any trial row opens that side's trial; the other side is retained.
        p.evaluate("() => document.getElementById('overview-c4-left').emit('plotly_click', {points:[{customdata:'Motorik/2/1/1'}]})")
        self.ready()
        self.assertEqual(p.locator('#trial-left').input_value(), 'Motorik/2/1/1')
        self.assertEqual(p.locator('#trial-right').input_value(), 'Motorik/2/2/1')
        p.locator('#fit-scale').click(); self.ready()
        limits = [p.locator('#scale-min').input_value(), p.locator('#scale-max').input_value()]
        np.testing.assert_allclose(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values'), original, atol=1e-9)
        p.locator('#prev-right').click(); self.ready()
        self.assertEqual([p.locator('#scale-min').input_value(), p.locator('#scale-max').input_value()], limits)
        self.assertTrue(p.evaluate('() => colorFor(0, -20, 400) === "rgb(247,247,247)"'))
        with p.expect_download() as downloaded:
            p.locator('#selection-json').click()
        exported = json.loads(Path(downloaded.value.path()).read_text())
        self.assertEqual(exported['selection']['scope'], 'single')
        self.assertEqual(exported['selection']['trial_left'], 'Motorik/2/1/1')
        self.assertEqual(exported['selection']['trial_right'], 'Motorik/1/2/1')
        self.assertEqual(exported['selection']['channel'], 'C4')
        self.assertEqual(exported['selection']['motor_comparison_channels'], ['C3', 'C4'])
        self.assertEqual(exported['right']['n'], 1)
        self.assertEqual(len(exported['times']), len(exported['right']['power'][1][0]))
        self.assertEqual(len(exported['frequencies']), len(exported['right']['spectral_percent']))
        self.assertEqual(exported['selection']['signal'], 'oscar')
        with p.expect_download() as downloaded:
            p.locator('#table-csv').click()
        row = next(csv.DictReader(io.StringIO(Path(downloaded.value.path()).read_text(encoding='utf-8-sig'))))
        params = json.loads(row['selection_json'])
        self.assertEqual(params['trial_right'], 'Motorik/1/2/1')
        self.assertEqual(params['signal'], 'oscar')
        self.assertEqual(params['montage'], 'fsaverage_1005')
        self.assertEqual(row['n_right'], '1')
        p.screenshot(path='/private/tmp/erds-single-trial-qa.png', full_page=True)
        p.locator('#scope').select_option('mean'); self.ready()
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values'), original)
        self.assertFalse(p.locator('#waveform-panel').is_visible())
        p.locator('#individual-curves').check(); self.ready()
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.data.length'), 6)
        self.assertEqual(p.locator('#curves-c4').evaluate('(e)=>e.data.length'), 6)
        self.assertFalse(self.errors)

    def test_missing_electrode_is_gray_and_zero_is_neutral_on_asymmetric_scale(self):
        p = self.page
        p.evaluate("() => {state.data.conditions.me_hand_right.task_percent[7][0]=null; state.data.conditions.me_hand_right.task_power[7][0]=null; render();}")
        self.ready()
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[2].marker.color'), ['#888888'])
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[2].text'), ['PO8 ×'])
        self.assertEqual(p.locator('#values tr').nth(7).locator('td').nth(8).inner_text(), '—')
        p.locator('#scale-min').fill('-80'); p.locator('#scale-min').press('Tab')
        p.locator('#scale-max').fill('400'); p.locator('#scale-max').press('Tab'); self.ready()
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].marker.color[3]'), 'rgb(247,247,247)')
        self.assertFalse(self.errors)

    def test_individual_curve_checkboxes_sync_preserve_means_and_export_visibility(self):
        p = self.page
        original = p.evaluate("() => JSON.stringify(state.data.conditions)")
        head = p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values')
        p.locator('#individual-curves').check(); self.ready()
        self.assertTrue(p.locator('#curve-trial-selection').is_visible())
        self.assertEqual(p.locator('#curve-trial-list-left input').count(), 2)
        self.assertEqual(p.locator('#curve-trial-list-right input').count(), 2)
        hidden_key = 'Motorik/1/2/1'
        checkbox = p.locator(f'input[data-trial-key="{hidden_key}"]')
        checkbox.uncheck(); self.ready()
        for graph in ('curves', 'curves-c4'):
            keys = p.locator('#' + graph).evaluate('(e)=>e.data.filter(t=>t.meta?.role==="individual").map(t=>t.meta.trialKey)')
            self.assertEqual(len(keys), 3)
            self.assertNotIn(hidden_key, keys)
            self.assertEqual(p.locator('#' + graph).evaluate('(e)=>e.data.filter(t=>!t.meta).length'), 2)
        self.assertIn('1 von 2', p.locator('#curve-trial-count-right').inner_text())
        self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values'), head)
        self.assertEqual(p.evaluate("() => JSON.stringify(state.data.conditions)"), original)
        self.assertEqual(p.locator('#values tr').nth(1).locator('td').nth(5).inner_text(), '2')
        # Checkboxes remain in the DOM during rendering, so keyboard focus and
        # toggling via Space work after the plot has finished updating.
        checkbox.focus(); checkbox.press('Space'); self.ready()
        self.assertTrue(checkbox.is_checked())
        self.assertTrue(checkbox.evaluate('(e)=>document.activeElement===e'))
        checkbox.press('Space'); self.ready()
        self.assertFalse(checkbox.is_checked())
        p.locator('#band').select_option('1'); self.ready()
        p.locator('#channel').select_option('3'); self.ready()
        p.locator('#metric').select_option('power'); self.ready()
        self.assertFalse(checkbox.is_checked())
        self.assertEqual(p.locator('#curves-c4').evaluate('(e)=>e.data.length'), 5)
        p.locator('#family').select_option('mi'); self.ready()
        self.assertEqual(p.locator('#curve-trial-list-right input:checked').count(), 2)
        p.locator('input[data-trial-key="Imagery/1/4/1"]').uncheck(); self.ready()
        p.locator('#family').select_option('me'); self.ready()
        self.assertFalse(checkbox.is_checked())
        p.locator('#scope').select_option('single'); self.ready()
        self.assertTrue(p.locator('#individual-curves').is_disabled())
        self.assertFalse(p.locator('#curve-trial-selection').is_visible())
        p.locator('#scope').select_option('mean'); self.ready()
        self.assertFalse(checkbox.is_checked())
        p.locator('#curve-hide-left').click(); self.ready()
        self.assertEqual(p.locator('#curve-trial-list-left input:checked').count(), 0)
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.data.length'), 3)
        p.locator('#curve-show-left').click(); self.ready()
        self.assertEqual(p.locator('#curve-trial-list-left input:checked').count(), 2)
        p.locator('#individual-curves').uncheck(); self.ready()
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.data.length'), 2)
        p.locator('#individual-curves').check(); self.ready()
        self.assertFalse(checkbox.is_checked())
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.data.length'), 5)
        with p.expect_download() as downloaded:
            p.locator('#selection-json').click()
        exported = json.loads(Path(downloaded.value.path()).read_text())
        visibility = exported['selection']['curve_visibility']
        self.assertTrue(visibility['overlays_enabled'])
        self.assertEqual(visibility['disabled_trial_keys'], [hidden_key])
        self.assertEqual(len(visibility['visible_trial_keys']), 3)
        self.assertEqual(exported['right']['n'], 2)
        with p.expect_download() as downloaded:
            p.locator('#png-curve').click()
        self.assertEqual(Path(downloaded.value.path()).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        p.wait_for_function('() => $("curves").layout.margin.t===40')
        p.locator('#motor-curves').screenshot(path='/private/tmp/erds-curve-visibility-qa.png')
        p.set_viewport_size({'width': 600, 'height': 900})
        p.wait_for_function('() => document.documentElement.scrollWidth <= 600')
        p.locator('#motor-curves').screenshot(path='/private/tmp/erds-curve-visibility-mobile-qa.png')
        p.locator('#curve-show-right').click(); self.ready()
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.data.length'), 6)
        self.assertEqual(p.evaluate("() => JSON.stringify(state.data.conditions)"), original)
        self.assertFalse(self.errors)

    def test_fixed_c3_c4_comparisons_keep_both_hands_and_channel_specific_values(self):
        data, events = synthetic_session()
        # A second, independent effect: only left-hand C4 loses 36% Mu power.
        # This catches swapping either the electrode columns or hand conditions.
        for row in events.to_dict('records'):
            if row['label'] == 'cue_onset' and row['condition'].endswith('left'):
                cue = row['samples_received']
                times = np.arange(cue, cue + 1000) / 250
                data[3, cue:cue + 1000] -= 2 * np.sin(2 * np.pi * 10 * times)
        result = compute_erds(data, events)
        result['metadata'].update(signal='oscar', signal_description='OSCAR · synthetische Prüfung')
        server = create_erds_server(result)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            p = self.page; p.goto(server.url); self.ready()
            for site, ids, expected in (
                    ('C3', ('overview-left', 'overview-right'), (0, -75)),
                    ('C4', ('overview-c4-left', 'overview-c4-right'), (-36, 0))):
                curve = 'curves' if site == 'C3' else 'curves-c4'
                for i, graph in enumerate(ids):
                    self.assertAlmostEqual(p.locator('#' + graph).evaluate('(e)=>e.data[0].z[0][35]'), expected[i], places=7)
                    self.assertAlmostEqual(p.locator('#' + curve).evaluate(f'(e)=>e.data[{i}].y[35]'), expected[i], places=7)
                self.assertIn('Links', p.locator('#' + curve).evaluate('(e)=>e.data[0].name'))
                self.assertIn('Rechts', p.locator('#' + curve).evaluate('(e)=>e.data[1].name'))
            self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.yaxis.range'),
                             p.locator('#curves-c4').evaluate('(e)=>e.layout.yaxis.range'))
            limits = [p.locator('#' + graph).evaluate('(e)=>[e.data[0].zmin,e.data[0].zmax]')
                      for graph in ('overview-left', 'overview-right', 'overview-c4-left', 'overview-c4-right')]
            self.assertEqual(limits, [[-100, 100]] * 4)
            for left, right in (('#overview-title', '#overview-title-c4'), ('#curves', '#curves-c4')):
                a, b = p.locator(left).bounding_box(), p.locator(right).bounding_box()
                self.assertLess(a['x'], b['x'])
                self.assertAlmostEqual(a['y'], b['y'], delta=2)
            p.locator('#channel').select_option('7'); self.ready()
            self.assertTrue(p.locator('#curve-title').inner_text().startswith('C3 ·'))
            self.assertTrue(p.locator('#curve-title-c4').inner_text().startswith('C4 ·'))
            self.assertIn('PO8', p.locator('#tf-title').inner_text())
            p.locator('#family').select_option('mi'); self.ready()
            self.assertAlmostEqual(p.locator('#curves-c4').evaluate('(e)=>e.data[0].y[35]'), -36)
            p.locator('#band').select_option('1'); self.ready()
            self.assertIn('Beta · 13–30 Hz', p.locator('#curve-title-c4').inner_text())
            self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.data[1].y[70]'), 300)
            self.assertAlmostEqual(p.locator('#curves-c4').evaluate('(e)=>e.data[1].y[70]'), 0, places=7)
            p.locator('#band').select_option('0'); self.ready()
            p.evaluate("() => $('overview-c4-left').emit('plotly_click', {points:[{customdata:'Imagery/1/3/1'}]})")
            self.ready()
            self.assertEqual(p.locator('#scope').input_value(), 'single')
            self.assertEqual(p.locator('#channel').input_value(), '3')
            self.assertAlmostEqual(p.locator('#curves-c4').evaluate('(e)=>e.data[1].y[35]'), -36)
            self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.data[3].y[35]'), -75)
            p.locator('#motor-overviews').screenshot(path='/private/tmp/erds-c3-c4-overviews-qa.png')
            p.locator('#motor-curves').screenshot(path='/private/tmp/erds-c3-c4-curves-qa.png')
            p.set_viewport_size({'width': 600, 'height': 900})
            p.wait_for_function('() => document.documentElement.scrollWidth <= 600')
            self.assertLess(p.locator('#curve-title').bounding_box()['y'],
                            p.locator('#curve-title-c4').bounding_box()['y'])
            self.assertFalse(self.errors)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)

    def test_resting_and_preparation_baseline_selection_reference_slider_exports_and_return(self):
        data, events = synthetic_baseline_session()
        valid = np.ones(data.shape[1], bool); valid[-1000] = False
        result = compute_erds(data, events, valid, qc={'bad_channels': ['PO8']})
        result['metadata'].update(signal='oscar', source_unit='uV', signal_description='OSCAR · synthetische Prüfung')
        server = create_erds_server(result)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            p = self.page; p.goto(server.url); self.ready()
            p.locator('#scope').select_option('baseline'); self.ready()
            self.assertTrue(p.locator('#baseline-view').is_visible())
            self.assertTrue(p.locator('#family').is_disabled())
            self.assertFalse(p.locator('#motor-curves').is_visible())
            self.assertEqual(p.locator('#baseline-section option').count(), 2)
            rest = [s for s in result['baselines'] if s['kind'] == 'rest']
            p.locator('#baseline-section').select_option(rest[1]['key']); self.ready()
            self.assertAlmostEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[1].meta.values[1]'), 0)
            p.locator('#baseline-reference').select_option(rest[0]['key']); self.ready()
            self.assertAlmostEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[1].meta.values[1]'), 300)
            self.assertEqual(p.locator('#baseline-values tr').nth(1).locator('td').nth(1).inner_text(), '50.00')
            self.assertEqual(p.locator('#baseline-values tr').nth(1).locator('td').nth(2).inner_text(), '200.00')
            self.assertEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[2].text'), ['PO8 ×'])
            self.assertEqual(p.locator('#baseline-c3').evaluate('(e)=>e.data.length'), 2)
            self.assertEqual(p.locator('#baseline-c3').evaluate('(e)=>e.layout.yaxis.range'),
                             p.locator('#baseline-c4').evaluate('(e)=>e.layout.yaxis.range'))
            p.locator('#baseline-time').fill('100'); self.ready()
            self.assertEqual(p.locator('#baseline-mode').input_value(), 'time')
            self.assertIn('10.5 s', p.locator('#baseline-time-label').inner_text())
            self.assertAlmostEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[1].meta.values[3]'), -75)
            for graph in ('baseline-c3', 'baseline-c4', 'baseline-waveform', 'baseline-tf'):
                self.assertEqual(p.locator('#' + graph).evaluate('(e)=>e.layout.shapes.find(s=>s.name==="baseline-cursor").x0'), 10.5)
            p.locator('#channel').select_option('3'); self.ready()
            self.assertEqual(p.locator('#baseline-time').input_value(), '100')
            self.assertIn('C4', p.locator('#baseline-tf-title').inner_text())
            self.assertAlmostEqual(p.locator('#baseline-tf').evaluate('(e)=>e.data[0].z[4][100]'), -75)
            p.locator('#baseline-play').click()
            p.wait_for_function('() => +$("baseline-time").value > 100')
            p.locator('#baseline-play').click(); self.ready()
            self.assertEqual(p.locator('#baseline-play').inner_text(), 'Abspielen')
            p.locator('#baseline-time').fill('551'); self.ready()  # overlaps invalid sample at 56 s
            self.assertEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[2].text.length'), 8)
            self.assertEqual(p.locator('#baseline-values tr').nth(1).locator('td').nth(2).inner_text(), '—')
            p.locator('#baseline-time').fill('100'); self.ready()
            with p.expect_download() as downloaded:
                p.locator('#baseline-json').click()
            exported = json.loads(Path(downloaded.value.path()).read_text())
            self.assertEqual(exported['selection']['reference_key'], rest[0]['key'])
            self.assertEqual(exported['selection']['signal'], 'oscar')
            self.assertEqual(exported['selection']['window_center_s'], 10.5)
            self.assertEqual(exported['detail']['section']['n_missing_windows'], 10)
            with p.expect_download() as downloaded:
                p.locator('#baseline-csv').click()
            row = next(csv.DictReader(io.StringIO(Path(downloaded.value.path()).read_text(encoding='utf-8-sig'))))
            self.assertEqual(json.loads(row['selection_json'])['reference_key'], rest[0]['key'])
            with p.expect_download() as downloaded:
                p.locator('[data-baseline-png="baseline-c3"]').click()
            self.assertEqual(Path(downloaded.value.path()).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            p.locator('#baseline-view').screenshot(path='/private/tmp/erds-resting-baseline-qa.png')
            p.locator('#baseline-kind').select_option('prepare'); self.ready()
            p.locator('#baseline-reference').select_option('self'); self.ready()
            self.assertEqual(p.locator('#baseline-section option').count(), 8)
            self.assertIn('Trial 1', p.locator('#baseline-description').inner_text())
            self.assertEqual(p.locator('#baseline-time').get_attribute('max'), '10')
            self.assertEqual(p.locator('#baseline-waveform').evaluate('(e)=>e.data[0].y.length'), 500)
            p.locator('#metric').select_option('power'); self.ready()
            self.assertAlmostEqual(p.locator('#baseline-head').evaluate('(e)=>e.data[1].meta.values[1]'), 50)
            p.locator('#baseline-view').screenshot(path='/private/tmp/erds-preparation-baseline-qa.png')
            p.set_viewport_size({'width': 600, 'height': 900})
            p.wait_for_function('() => document.documentElement.scrollWidth <= 600')
            p.screenshot(path='/private/tmp/erds-baseline-mobile-qa.png', full_page=True)
            p.locator('#scope').select_option('mean'); self.ready()
            p.locator('#metric').select_option('percent'); self.ready()
            self.assertFalse(p.locator('#baseline-view').is_visible())
            self.assertTrue(p.locator('#family').is_enabled())
            self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.data[1].y[35]'), -75)
            self.assertFalse(self.errors)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)

    def test_missing_resting_baseline_is_explicit_and_preparations_remain_available(self):
        p = self.page
        p.locator('#scope').select_option('baseline'); self.ready()
        self.assertTrue(p.locator('#baseline-empty').is_visible())
        self.assertEqual(p.locator('#baseline-section option').count(), 0)
        self.assertFalse(p.locator('#baseline-content').is_visible())
        p.locator('#baseline-kind').select_option('prepare'); self.ready()
        self.assertTrue(p.locator('#baseline-content').is_visible())
        self.assertEqual(p.locator('#baseline-section option').count(), 8)
        self.assertFalse(self.errors)

    def test_rendered_head_has_c3_blue_and_no_extra_colorbar_sensor(self):
        from PIL import Image
        graph = self.page.locator('#head-right')
        # Test the WebGL output too: Plotly treats size=0 inconsistently in 3D;
        # a colorbar-only trace must be explicitly transparent.
        self.assertEqual(graph.evaluate('(e)=>e.data[3].marker.opacity'), 0)
        image = Image.open(io.BytesIO(graph.screenshot())).convert('RGB')
        pixels = np.asarray(image.crop((0, 0, int(image.width * .7), image.height)), dtype=int).reshape(-1, 3)
        r, g, b = pixels.T
        red = np.count_nonzero((r > 110) & (g < 75) & (b < 110))
        blue = np.count_nonzero((r < 130) & (g > 60) & (g < 170) & (b > 135) & (b - r > 40))
        self.assertEqual(red, 0, 'No ERS was generated: a red point would be a rendering artifact.')
        self.assertGreater(blue, 30, 'The C3 ERD must be visibly blue in the rendered image.')
        self.assertEqual(self.page.locator('#bars-left').evaluate('(e)=>e.layout.xaxis.range'),
                         self.page.locator('#bars-right').evaluate('(e)=>e.layout.xaxis.range'))
        self.assertGreater(self.page.locator('#bars-left').evaluate('(e)=>e.layout.xaxis.range[1]-e.layout.xaxis.range[0]'), 1)
        self.assertFalse(self.errors)

    def test_empty_condition_and_excluded_sensor_remain_missing_in_single_view(self):
        data, events = synthetic_session()
        result = compute_erds(data, events, qc=dict(bad_channels=['PO8'],
                              bad_trials=['Motorik/1/1/1', 'Motorik/2/1/1']))
        result['metadata'].update(signal='oscar', signal_description='OSCAR · synthetische Prüfung')
        server = create_erds_server(result)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            p = self.page; p.goto(server.url); self.ready()
            p.locator('#scope').select_option('single'); self.ready()
            self.assertTrue(p.locator('#trial-left').is_disabled())
            self.assertIn('Kein gültiger Trial', p.locator('#title-left').inner_text())
            self.assertEqual(p.locator('#head-left').evaluate('(e)=>e.data[2].text.length'), 8)
            self.assertEqual(p.locator('#head-right').evaluate('(e)=>e.data[2].text'), ['PO8 ×'])
            self.assertEqual(p.locator('#waveform').evaluate('(e)=>e.data[0].y'), [])
            self.assertEqual(p.locator('#overview-left').evaluate('(e)=>e.data[0].z'), [])
            self.assertEqual(p.locator('#values tr').nth(7).locator('td').nth(8).inner_text(), '—')
            self.assertFalse(self.errors)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)

    def test_slider_keyboard_and_drag_enter_time_view_and_sync_values(self):
        p = self.page
        slider = p.locator('#time')
        self.assertTrue(slider.is_enabled(), 'Time navigation must be usable from the default task average.')
        p.evaluate("() => {window.originalTF=document.getElementById('tf-right').data[0].z; window.originalCurve=document.getElementById('curves').data[1].y;}")
        p.evaluate("() => Plotly.relayout(document.getElementById('curves'), {'xaxis.range':[-.5,4.5], 'yaxis.range':[-90,30]})")
        slider.focus(); slider.press('Home'); self.ready()
        self.assertEqual(p.locator('#mode').input_value(), 'time')
        self.assertIn('-1.5 s', p.locator('#time-label').inner_text())
        self.assertAlmostEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values[1]'), 0, places=8)
        box = slider.bounding_box()
        p.mouse.move(box['x'] + 8, box['y'] + box['height'] / 2)
        p.mouse.down()
        p.mouse.move(box['x'] + box['width'] * .34, box['y'] + box['height'] / 2, steps=14)
        p.mouse.up(); self.ready()
        index = int(slider.input_value())
        self.assertGreater(index, 25); self.assertLess(index, 46)
        self.assertAlmostEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values[1]'), -75)
        self.assertEqual(p.locator('#values tr').nth(1).locator('td').nth(8).inner_text(), '-75.00')
        time = p.evaluate('() => state.data.times[+$("time").value]')
        for graph in ('curves', 'curves-c4', 'tf-left', 'tf-right', 'overview-left', 'overview-right', 'overview-c4-left', 'overview-c4-right'):
            self.assertEqual(p.locator('#' + graph).evaluate('(e)=>e.layout.shapes.filter(s=>s.line.dash==="solid").map(s=>s.x0)'), [time])
        self.assertTrue(p.locator('#tf-right').evaluate('(e)=>e.data[0].z===window.originalTF'))
        self.assertTrue(p.locator('#curves').evaluate('(e)=>e.data[1].y===window.originalCurve'))
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.xaxis.range'), [-.5,4.5])
        self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.yaxis.range'), [-90,30])
        p.locator('#scope').select_option('single'); self.ready()
        p.locator('#mode').select_option('rebound'); self.ready()
        slider.focus(); slider.press('End'); self.ready()
        self.assertEqual(p.locator('#mode').input_value(), 'time')
        self.assertIn('9.5 s', p.locator('#time-label').inner_text())
        self.assertEqual(p.locator('#waveform').evaluate('(e)=>e.layout.shapes.filter(s=>s.line.dash==="solid").map(s=>s.x0)'), [9.5])
        self.assertFalse(self.errors)

    def test_playback_can_start_in_summary_pause_and_restart_at_end(self):
        p = self.page
        self.assertTrue(p.locator('#play').is_enabled())
        p.locator('#play').click()
        p.wait_for_function('() => +$("time").value > 30')
        p.locator('#play').click(); self.ready()
        self.assertEqual(p.locator('#mode').input_value(), 'time')
        self.assertEqual(p.locator('#play').inner_text(), 'Abspielen')
        p.evaluate('() => new Promise(resolve => setTimeout(resolve, 500))')
        self.assertIsNone(p.evaluate('() => state.timer'))
        p.locator('#time').fill('109'); self.ready()
        p.locator('#play').click()
        p.wait_for_function('() => +$("time").value===110 && state.timer===null')
        self.ready()
        p.locator('#play').click()
        p.wait_for_function('() => +$("time").value<5 && state.timer!==null')
        p.locator('#time').focus(); p.locator('#time').press('Home'); self.ready()
        self.assertIsNone(p.evaluate('() => state.timer'))
        self.assertEqual(p.locator('#time').input_value(), '0')
        self.assertFalse(self.errors)

    def test_visible_baseline_levels_actual_windows_and_single_trial_reference(self):
        data, events = synthetic_session()
        cue = 72 * 250
        time = np.arange(cue - 500, cue + 1000) / 250
        data[1, cue - 500:cue + 1000] += 10 * np.sin(2 * np.pi * 10 * time)
        result = compute_erds(data, events, qc=dict(bad_channels=['PO8']))
        result['metadata'].update(signal='oscar', signal_description='OSCAR · synthetische Prüfung')
        server = create_erds_server(result)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            p = self.page; p.goto(server.url); self.ready()
            self.assertIn('Referenz: 125.00 µV²', p.locator('#reference-right').inner_text())
            self.assertIn('Aufgabe: 62.50 µV² (-50.00 %)', p.locator('#reference-right').inner_text())
            self.assertIn('PSD-Fenstermitten -1.50 bis -0.50 s', p.locator('#reference-window-right').inner_text())
            self.assertIn('11 überlappende', p.locator('#reference-window-right').inner_text())
            shapes = p.locator('#curves').evaluate('(e)=>e.layout.shapes')
            source = [s for s in shapes if s.get('name') == 'baseline-source']
            self.assertEqual([(s['x0'],s['x1']) for s in source], [(-2,0)])
            self.assertEqual([s['y0'] for s in shapes if s.get('name') == 'baseline-zero'], [0])
            # Heatmap values keep their quantitative colors; only the baseline
            # outline is drawn on top, without tinting cells inside it.
            source = p.locator('#tf-right').evaluate('(e)=>e.layout.shapes.find(s=>s.name==="baseline-source")')
            self.assertEqual(source['fillcolor'].replace(' ', ''), 'rgba(0,0,0,0)')
            p.evaluate("() => Plotly.relayout(document.getElementById('curves'), {'xaxis.range':[1,4]})")
            p.locator('#reference-range').click(); self.ready()
            self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.xaxis.range'), [-2,10])
            p.locator('#reference-power').click(); self.ready()
            self.assertEqual(p.locator('#metric').input_value(), 'power')
            levels = p.locator('#curves').evaluate('(e)=>e.layout.shapes.filter(s=>s.name?.startsWith("baseline-level-")).map(s=>s.y0)')
            np.testing.assert_allclose(levels, [50,125])
            c4_levels = p.locator('#curves-c4').evaluate('(e)=>e.layout.shapes.filter(s=>s.name?.startsWith("baseline-level-")).map(s=>s.y0)')
            np.testing.assert_allclose(c4_levels, [50,50])
            p.locator('#scope').select_option('single'); self.ready()
            p.locator('#next-right').click(); self.ready()
            self.assertIn('Referenz: 200.00 µV²', p.locator('#reference-right').inner_text())
            self.assertIn('Aufgabe: 112.50 µV² (-43.75 %)', p.locator('#reference-right').inner_text())
            self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.layout.shapes.find(s=>s.name==="baseline-level-right").y0'), 200)
            p.locator('#time').focus(); p.locator('#time').press('Home'); self.ready()
            self.assertAlmostEqual(p.locator('#head-right').evaluate('(e)=>e.data[1].meta.values[1]'), 200)
            self.assertAlmostEqual(p.locator('#curves').evaluate('(e)=>e.layout.shapes.find(s=>s.name==="baseline-level-right").y0'), 200)
            with p.expect_download() as downloaded:
                p.locator('#selection-json').click()
            exported = json.loads(Path(downloaded.value.path()).read_text())
            self.assertIn('trial_preparation', exported['selection']['reference_type'])
            self.assertEqual(exported['selection']['reference_windows']['right'][0]['n_windows'], 11)
            p.locator('#curves').screenshot(path='/private/tmp/erds-baseline-curves-qa.png')
            p.locator('section[aria-label="Baseline und Referenzleistung"]').screenshot(path='/private/tmp/erds-baseline-panel-qa.png')
            p.screenshot(path='/private/tmp/erds-baseline-qa.png', full_page=True)
            p.locator('#channel').select_option('7'); self.ready()
            self.assertIn('nicht verfügbar', p.locator('#reference-right').inner_text())
            # The selected PO8 reference is missing; fixed C3/C4 comparisons
            # keep their own valid reference levels rather than following PO8.
            self.assertEqual(p.locator('#curves').evaluate('(e)=>e.layout.shapes.filter(s=>s.name?.startsWith("baseline-level-")).length'), 2)
            self.assertEqual(p.locator('#curves-c4').evaluate('(e)=>e.layout.shapes.filter(s=>s.name?.startsWith("baseline-level-")).length'), 2)
            self.assertFalse(self.errors)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)


if __name__ == '__main__':
    unittest.main()
