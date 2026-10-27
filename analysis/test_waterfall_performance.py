"""Optional browser regressions for timeline reuse and responsive 3D controls."""
import threading
import unittest

import mne
import numpy as np

from analysis.test_waterfall_ui import _AVAILABLE, _CHROME
from analysis.waterfall_browser import create_waterfall_server


@unittest.skipUnless(_AVAILABLE, 'Optional UI checks require playwright, plotly and installed Chrome.')
class WaterfallPerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        times = np.arange(6000) / 250
        raw = mne.io.RawArray(
            np.array([20e-6 * np.sin(2 * np.pi * frequency * times)
                      for frequency in (10, 11)]),
            mne.create_info(['Cz', 'Pz'], 250, 'eeg'), verbose='ERROR')
        raw.set_annotations(mne.Annotations(
            np.linspace(.1, 23.9, 1424), np.zeros(1424),
            [f'Marker {i}' for i in range(1424)]))
        cls.server = create_waterfall_server(raw, title='Dense marker performance test')
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=_CHROME, headless=True,
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
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.server.url)
        self.page.wait_for_function(
            "() => document.getElementById('status').textContent.includes('3D-Wasserfall')")

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def test_dense_timeline_geometry_is_reused_and_resize_invalidates_it(self):
        page = self.page
        self.assertEqual(page.locator('#recording-overview [data-event-id]').count(), 1424)
        page.evaluate("""() => {
            window.timelineNodes = {
                overview: document.querySelector('#recording-overview [data-event-id]'),
                detail: document.querySelector('#event-timeline [data-event-id]'),
                label: document.querySelector('#timeline-labels button'),
                viewport: document.querySelector('#recording-overview [data-viewport]'),
            };
        }""")
        page.locator('#event').select_option('0')
        page.wait_for_function("() => document.querySelector('#recording-overview [data-event-id="
                               "\"0\"]').classList.contains('selected-tick')")
        self.assertTrue(page.evaluate("""() =>
            timelineNodes.overview === document.querySelector('#recording-overview [data-event-id]') &&
            timelineNodes.detail === document.querySelector('#event-timeline [data-event-id]') &&
            timelineNodes.label === document.querySelector('#timeline-labels button')
        """))
        old_viewport_x = page.locator('#recording-overview [data-viewport]').get_attribute('x')
        page.locator('#next').click()
        page.wait_for_function(
            "() => document.getElementById('status').textContent.startsWith('8–18')")
        self.assertTrue(page.evaluate("""() =>
            timelineNodes.overview === document.querySelector('#recording-overview [data-event-id]') &&
            timelineNodes.viewport === document.querySelector('#recording-overview [data-viewport]')
        """))
        self.assertNotEqual(page.locator('#recording-overview [data-viewport]').get_attribute('x'),
                            old_viewport_x)
        self.assertEqual(page.locator('#recording-overview [data-event-id]').count(), 1424)
        page.set_viewport_size({'width': 1100, 'height': 1000})
        page.wait_for_function("""() => timelineNodes.overview !==
            document.querySelector('#recording-overview [data-event-id]')""")
        self.assertEqual(page.locator('#recording-overview [data-event-id]').count(), 1424)

    def test_slider_burst_coalesces_plot_updates(self):
        page = self.page
        page.evaluate("""() => {
            const original = Plotly.react;
            window.plotMetrics = {calls: 0, active: 0, maxActive: 0};
            Plotly.react = function(...args) {
                const m = window.plotMetrics;
                m.calls++; m.active++; m.maxActive = Math.max(m.maxActive, m.active);
                return Promise.resolve(original.apply(this, args)).finally(() => { m.active--; });
            };
            const spacing = document.getElementById('spacing');
            for (let i = 0; i < 10; i++) {
                spacing.value = String(.6 + i * .1);
                spacing.dispatchEvent(new Event('input', {bubbles: true}));
            }
        }""")
        page.wait_for_function('() => plotMetrics.calls >= 2 && plotMetrics.active === 0')
        page.wait_for_timeout(200)  # Detect a second, unnecessarily queued redraw batch.
        metrics = page.evaluate('() => plotMetrics')
        self.assertLessEqual(metrics['calls'], 4, metrics)
        self.assertLessEqual(metrics['maxActive'], 2, metrics)

    def test_wheel_over_3d_plot_scrolls_page_without_changing_camera(self):
        page = self.page
        page.evaluate('() => window.scrollTo(0, 0)')
        plot = page.locator('#amplitude-plot')
        box = plot.bounding_box()
        self.assertLess(box['y'], 950)
        camera = plot.evaluate('(el) => JSON.stringify(el.layout.scene.camera)')
        page.mouse.move(box['x'] + box['width'] / 2, min(930, box['y'] + 70))
        page.mouse.wheel(0, 220)
        page.wait_for_function('() => window.scrollY > 0')
        self.assertEqual(plot.evaluate('(el) => JSON.stringify(el.layout.scene.camera)'), camera)

    def test_camera_zoom_buttons_change_distance_and_disable_in_2d(self):
        page = self.page
        original = page.locator('#amplitude-plot').evaluate(
            'el => Math.hypot(...Object.values(el.layout.scene.camera.eye))')
        page.locator('#camera-zoom-in').click()
        page.wait_for_function("""distance => ['amplitude-plot', 'power-plot'].every(id =>
            Math.hypot(...Object.values(document.getElementById(id).layout.scene.camera.eye)) < distance)
        """, arg=original)
        page.locator('#camera-zoom-out').click()
        page.wait_for_function("""distance => ['amplitude-plot', 'power-plot'].every(id =>
            Math.abs(Math.hypot(...Object.values(document.getElementById(id).layout.scene.camera.eye))
                     - distance) < 1e-6)
        """, arg=original)
        page.locator('#mode').select_option('2d')
        page.wait_for_function("() => document.getElementById('camera-zoom-in').disabled && "
                               "document.getElementById('camera-zoom-out').disabled")


if __name__ == '__main__':
    unittest.main()
