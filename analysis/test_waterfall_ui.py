"""Optional real-browser regression checks (pip install playwright).

Uses an installed Chrome, or EEG_BROWSER_EXECUTABLE; no browser download and no
real participant recordings. Normal numerical/server tests need no browser.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import threading
import unittest

import mne
import numpy as np

from analysis.waterfall_browser import create_waterfall_server

_CHROME = os.environ.get('EEG_BROWSER_EXECUTABLE') or next((str(p) for p in (
    Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
    Path(shutil.which('google-chrome') or '/nonexistent'),
    Path(shutil.which('chromium') or '/nonexistent'),
) if p.is_file()), None)
_AVAILABLE = _CHROME and importlib.util.find_spec('playwright') and importlib.util.find_spec('plotly')


@unittest.skipUnless(_AVAILABLE, 'Optional UI checks require playwright, plotly and installed Chrome.')
class WaterfallUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        sfreq = 250
        times = np.arange(sfreq * 24) / sfreq
        values = np.array([i * 100 + 20 * np.sin(2 * np.pi * (10 if i % 2 == 0 else 20) * times)
                           for i in range(8)])
        cls.raw = mne.io.RawArray(values * 1e-6,
                mne.create_info([f'EEG {i + 1}' for i in range(8)], sfreq, 'eeg'), verbose='ERROR')
        cls.raw.set_annotations(mne.Annotations([2, 5, 15], [0, 0, 0],
                ['Baseline', 'task_onset | condition=arms | trial=1', 'Rest']))
        cls.server = create_waterfall_server(cls.raw, title='Unicorn · UI test')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=_CHROME, headless=True,
                args=['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader',
                      '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1500, 'height': 1000})
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(self.server.url)
        self.page.wait_for_function("() => document.getElementById('status').textContent.includes('3D-Wasserfall')")

    def test_display_controls_channel_selection_scales_and_data_navigation(self):
        page = self.page
        self.assertEqual(page.locator('#amplitude-plot').evaluate('(e) => e.data.filter(t=>t.meta?.channel).length'), 8)
        self.assertEqual(page.locator('#sensor-dots .active').count(), 8)
        page.get_by_role('button', name='Nur Cz anzeigen', exact=True).click()
        page.wait_for_function("() => document.getElementById('amplitude-plot').data.filter(t=>t.meta?.channel).length===1")
        self.assertEqual(page.locator('#sensor-dots .active').count(), 1)
        self.assertEqual(page.locator('#amplitude-plot').evaluate('(e) => e.data[0].name'), 'Cz')
        page.locator('#all-channels').click()
        page.wait_for_function("() => document.getElementById('amplitude-plot').data.filter(t=>t.meta?.channel).length===8")
        page.get_by_text('Amplitude & Skalierung', exact=True).click()
        page.locator('#amplitude-range').fill('5')
        page.locator('#amplitude-range').press('Tab')
        page.wait_for_function("() => document.getElementById('amplitude-foot').textContent.includes('außerhalb')")
        page.locator('#fit-amplitude').click()
        page.wait_for_function("() => !document.getElementById('amplitude-foot').textContent.includes('außerhalb')")
        fixed_range = page.locator('#amplitude-range').input_value()
        page.locator('#next').click()
        page.wait_for_function("() => document.getElementById('status').textContent.startsWith('8–18')")
        self.assertEqual(page.locator('#amplitude-range').input_value(), fixed_range)
        self.assertEqual(page.locator('#event option').count(), 2)  # default + Rest at 15 s
        page.locator('#event').select_option('0')
        self.assertIn('Rest', page.locator('#event-detail').inner_text())
        page.locator('#mode').select_option('2d')
        page.wait_for_function("() => document.getElementById('amplitude-plot').data[0].type==='scatter'")
        self.assertTrue(page.locator('#camera-front').is_disabled())
        page.locator('#spacing').evaluate("(e) => {e.value='0.6';e.dispatchEvent(new Event('input',{bubbles:true}));}")
        page.wait_for_timeout(100)
        tight = page.locator('#amplitude-plot').evaluate("(e) => Math.max(...e.data[0].y)-Math.min(...e.data[0].y)")
        tight_domain = page.locator('#amplitude-plot').evaluate("(e) => e.layout.yaxis.range[1]-e.layout.yaxis.range[0]")
        page.locator('#spacing').evaluate("(e) => {e.value='2.4';e.dispatchEvent(new Event('input',{bubbles:true}));}")
        page.wait_for_timeout(100)
        loose = page.locator('#amplitude-plot').evaluate("(e) => Math.max(...e.data[0].y)-Math.min(...e.data[0].y)")
        loose_domain = page.locator('#amplitude-plot').evaluate("(e) => e.layout.yaxis.range[1]-e.layout.yaxis.range[0]")
        self.assertGreater(tight/tight_domain, 3.5*loose/loose_domain)
        page.locator('#order').select_option('reverse')
        page.wait_for_function("() => document.getElementById('amplitude-plot').data[0].name==='PO8'")
        page.get_by_text('Bandpower & Frequenzband', exact=True).click()
        page.locator('#band').select_option('13,30')
        page.wait_for_function("() => document.getElementById('power-title').textContent.includes('Beta')")
        self.assertGreater(page.locator('#power-plot').evaluate('(e) => Math.max(...e.data.find(t=>t.name==="C3").customdata)'), 150)
        page.locator('#power-unit').select_option('db')
        page.wait_for_function("() => document.getElementById('power-foot').textContent.includes('dB')")
        page.locator('#focus').select_option('power')
        self.assertFalse(page.locator('#amplitude-panel').is_visible())
        self.assertGreater(page.locator('#power-plot').evaluate('(e) => e.clientWidth'), 1000)
        self.assertEqual(self.errors, [])

    def test_png_export_contains_real_image_with_scientific_context(self):
        import tempfile
        page = self.page
        with page.expect_download() as downloaded:
            page.locator('[data-export=power]').click()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'power.png'
            downloaded.value.save_as(destination)
            self.assertEqual(destination.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertGreater(destination.stat().st_size, 10_000)
        self.assertEqual(self.errors, [])

    def test_validation_responsive_layout_and_dark_appearance(self):
        page = self.page
        page.locator('#duration').fill('0')
        page.locator('#duration').press('Tab')
        page.wait_for_function("() => document.getElementById('status').classList.contains('error')")
        self.assertEqual(page.locator('#amplitude-plot').evaluate('(e) => e.data.filter(t=>t.meta?.channel).length'), 8)
        page.locator('#duration').fill('4')
        page.locator('#duration').press('Tab')
        page.wait_for_function("() => document.getElementById('status').textContent.startsWith('0–4')")
        for width in (1500, 1100, 760, 390, 320):
            with self.subTest(width=width):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.wait_for_timeout(150)
                self.assertFalse(page.evaluate('() => document.documentElement.scrollWidth>innerWidth'))
                for selector in ('#amplitude-panel', '#power-panel', '#head-map'):
                    box = page.locator(selector).bounding_box()
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], width + 1)
        page.emulate_media(color_scheme='dark')
        page.wait_for_timeout(200)
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
