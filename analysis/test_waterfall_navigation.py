"""Browser checks for persistent recording context and annotation navigation.

These exercise the viewer with synthetic EEG only; the browser dependency and
installed-Chrome detection are shared with the optional display checks.
"""
import threading
import unittest

import mne
import numpy as np

from analysis.test_waterfall_ui import _AVAILABLE, _CHROME
from analysis.waterfall_browser import create_waterfall_server


@unittest.skipUnless(_AVAILABLE, 'Optional UI checks require playwright, plotly and installed Chrome.')
class WaterfallNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        sfreq = 250
        times = np.arange(sfreq * 24) / sfreq
        values = np.array([20 * np.sin(2 * np.pi * (10 + i) * times)
                           for i in range(8)])
        raw = mne.io.RawArray(values * 1e-6,
                             mne.create_info([f'EEG {i + 1}' for i in range(8)],
                                             sfreq, 'eeg'), verbose='ERROR')
        raw.set_annotations(mne.Annotations([2, 5, 15], [0, 0, 0],
                            ['Baseline', 'task_onset | condition=arms | trial=1', 'Rest']))
        cls.server = create_waterfall_server(raw, title='Unicorn · Navigation test')
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

    def wait_for_selected(self, description, onset):
        self.page.wait_for_function(
            "([description, onset]) => {"
            " const detail = document.getElementById('event-detail').textContent;"
            " const cursor = document.getElementById('cursor-readout').textContent;"
            " return detail.includes(description) && cursor.includes(String(onset));"
            "}", arg=[description, onset])

    def test_all_markers_visible_without_selecting_in_both_plot_modes(self):
        page = self.page
        self.assertEqual(page.locator('#recording-overview [data-event-id]').count(), 3)
        self.assertEqual(page.locator('#event-timeline [data-event-id]').count(), 2)
        self.assertIn('Baseline', page.locator('#timeline-labels').inner_text())
        self.assertIn('task_onset | condition=arms | trial=1',
                      page.locator('#timeline-labels [data-event-id="1"]').get_attribute('aria-label'))
        self.assertEqual(page.locator('#event').input_value(), '')
        for plot in ('amplitude-plot', 'power-plot'):
            onsets = page.locator(f'#{plot}').evaluate(
                "el => el.data.filter(t => t.meta?.role === 'events')"
                ".flatMap(t => Array.from(t.x)).filter(x => x !== null)")
            self.assertTrue({2, 5}.issubset(set(onsets)), (plot, onsets))
        position = page.locator('#position-readout').inner_text()
        self.assertIn(':', position)
        self.assertIn('10', position)
        self.assertIn('s', position)

        page.locator('#mode').select_option('2d')
        page.wait_for_function(
            "() => document.getElementById('amplitude-plot').data[0].type === 'scatter'")
        for plot in ('amplitude-plot', 'power-plot'):
            onsets = page.locator(f'#{plot}').evaluate(
                "el => (el.layout.shapes || []).filter(s => s.type === 'line' && s.x0 === s.x1)"
                ".map(s => s.x0)")
            self.assertTrue({2, 5}.issubset(set(onsets)), (plot, onsets))

    def test_global_event_navigation_crosses_viewport_and_keeps_full_description(self):
        page = self.page
        for description, onset in [('Baseline', 2),
                                   ('task_onset | condition=arms | trial=1', 5),
                                   ('Rest', 15)]:
            page.locator('#next-event').click()
            self.wait_for_selected(description, onset)
            page.wait_for_function(
                "onset => { const start = +document.getElementById('start').value;"
                " return start <= onset && start + +document.getElementById('duration').value >= onset; }",
                arg=onset)
        self.assertGreater(float(page.locator('#start').input_value()), 0)
        page.locator('#previous-event').click()
        self.wait_for_selected('task_onset | condition=arms | trial=1', 5)
        page.wait_for_function(
            "() => +document.getElementById('start').value <= 5 && "
            "document.querySelector('#event option:checked').textContent.includes('trial=1')")

    def test_marker_click_selection_survives_data_reload_and_display_changes(self):
        page = self.page
        page.locator('#timeline-labels [data-event-id="1"]').click()
        self.wait_for_selected('task_onset | condition=arms | trial=1', 5)
        self.assertEqual(page.locator('#event').input_value(), '1')
        page.locator('#mode').select_option('2d')
        page.wait_for_function(
            "() => document.getElementById('amplitude-plot').data[0].type === 'scatter'")
        self.assertEqual(page.locator('#event').input_value(), '1')
        page.locator('#start').fill('1')
        page.locator('#start').press('Tab')
        page.wait_for_function(
            "() => document.getElementById('status').textContent.startsWith('1–11')")
        self.assertEqual(page.locator('#event').input_value(), '1')
        self.wait_for_selected('task_onset | condition=arms | trial=1', 5)

    def test_hover_leave_preserves_markers_selected_event_and_cursor(self):
        page = self.page
        description = 'task_onset | condition=arms | trial=1'
        page.locator('#timeline-labels [data-event-id="1"]').click()
        self.wait_for_selected(description, 5)

        def assert_selection_and_navigation_survive(order):
            # Redraw without fetching data: this exposes accidental clearing
            # of the recording-wide event list as well as cursor/selection.
            page.locator('#order').select_option(order)
            page.wait_for_function(
                "name => document.getElementById('amplitude-plot').data[0].name === name",
                arg='PO8' if order == 'reverse' else 'Fz')
            self.assertEqual(page.locator('#recording-overview [data-event-id]').count(), 3)
            self.assertEqual(page.locator('#event').input_value(), '1')
            self.wait_for_selected(description, 5)
            self.assertIn('00:05.000', page.locator('#cursor-readout').inner_text())
            self.assertFalse(page.locator('#next-event').is_disabled())
            self.assertFalse(page.locator('#previous-event').is_disabled())

        page.locator('#channels .channel').first.hover()
        page.locator('#position-readout').hover()
        assert_selection_and_navigation_survive('reverse')

        # Exercise Plotly's own unhover event independently of sidebar hover.
        page.locator('#amplitude-plot').evaluate(
            "el => el.emit('plotly_unhover', {points: []})")
        assert_selection_and_navigation_survive('forward')

        page.locator('#next-event').click()
        self.wait_for_selected('Rest', 15)
        page.wait_for_function(
            "() => +document.getElementById('start').value <= 15 && "
            "+document.getElementById('start').value + +document.getElementById('duration').value >= 15")

    def test_2d_pan_zoom_and_fit_keep_shared_time_and_channel_axes(self):
        page = self.page
        page.locator('#mode').select_option('2d')
        page.wait_for_function(
            "() => document.getElementById('amplitude-plot').data[0].type === 'scatter'")

        def wait_for_axes(start, stop):
            page.wait_for_function(
                "([start, stop]) => ['amplitude-plot', 'power-plot'].every(id => {"
                " const axes = document.getElementById(id)._fullLayout;"
                " return Math.abs(axes.xaxis.range[0] - start) < 1e-8 && "
                " Math.abs(axes.xaxis.range[1] - stop) < 1e-8 && "
                " Math.abs(axes.yaxis.range[0] + 0.7) < 1e-8 && "
                " Math.abs(axes.yaxis.range[1] - 7.7) < 1e-8 && "
                " axes.xaxis.autorange === false && axes.yaxis.autorange === false && "
                " axes.yaxis.fixedrange === true; })",
                arg=[start, stop])

        # Real pan/wheel zoom emits indexed bounds; both plots and the
        # recording controls must move together, including at record edges.
        for start, stop, expected in ((3, 7, (3, 7)), (-2, 2, (0, 4)),
                                      (22, 26, (20, 24))):
            page.locator('#amplitude-plot').evaluate(
                "(el, range) => Plotly.relayout(el, {"
                " 'xaxis.range[0]': range[0], 'xaxis.range[1]': range[1]})",
                [start, stop])
            wait_for_axes(*expected)
            self.assertEqual(float(page.locator('#start').input_value()), expected[0])
            self.assertEqual(float(page.locator('#duration').input_value()), expected[1] - expected[0])

        # Plotly also supports a range-array event, e.g. from integrations.
        page.locator('#power-plot').evaluate(
            "el => Plotly.relayout(el, {'xaxis.range': [8, 14]})")
        wait_for_axes(8, 14)
        self.assertEqual(float(page.locator('#start').input_value()), 8)
        self.assertEqual(float(page.locator('#duration').input_value()), 6)

        # A reset/autorange event must restore the selected recording window,
        # rather than fitting only one plot to its retained sample positions.
        page.locator('#power-plot').evaluate(
            "el => Plotly.relayout(el, {'xaxis.autorange': true, 'yaxis.autorange': true})")
        wait_for_axes(8, 14)

        # Explicit fit also restores the common channel extent after an
        # external axis change, without preserving a stale Plotly zoom.
        for plot, fit in (('amplitude-plot', 'fit-amplitude'),
                          ('power-plot', 'fit-power')):
            page.locator(f'#{plot}').evaluate(
                "el => Plotly.relayout(el, {'yaxis.range': [2, 4]})")
            page.locator(f'#{fit}').click()
            wait_for_axes(8, 14)

        page.locator('#mode').select_option('3d')
        page.wait_for_function(
            "() => ['amplitude-plot', 'power-plot'].every(id => {"
            " const plot = document.getElementById(id);"
            " return plot.data[0].type === 'scatter3d' && "
            " plot.layout.scene.xaxis.range[0] === 8 && "
            " plot.layout.scene.xaxis.range[1] === 14; })")

    def test_coincident_markers_remain_individually_accessible(self):
        raw = mne.io.RawArray(np.zeros((1, 6000)),
                             mne.create_info(['Cz'], 250, 'eeg'), verbose='ERROR')
        descriptions = ['Baseline', 'Cue', 'Response', 'Rest']
        raw.set_annotations(mne.Annotations([2, 2, 2, 5], [0, 0, 0, 0], descriptions))
        server = create_waterfall_server(raw, title='Coincident marker test')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            page = self.page
            page.goto(server.url)
            page.wait_for_function(
                "() => document.getElementById('status').textContent.includes('3D-Wasserfall')")
            self.assertEqual(page.locator('#event option').count(), 5)
            self.assertEqual(page.locator('#timeline-labels [data-event-id]').count(), 2)
            self.assertIn('+2', page.locator('#timeline-labels').inner_text())
            for description, onset in zip(descriptions, [2, 2, 2, 5]):
                page.locator('#next-event').click()
                self.wait_for_selected(description, onset)
            for description in reversed(descriptions[:-1]):
                page.locator('#previous-event').click()
                self.wait_for_selected(description, 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_fit_controls_stay_reachable_and_overview_keyboard_navigation(self):
        page = self.page
        for selector in ('#fit-amplitude', '#fit-power'):
            self.assertTrue(page.locator(selector).is_visible())
            self.assertFalse(page.locator(selector).evaluate("el => !!el.closest('details')"))
        page.evaluate('() => window.scrollTo(0, document.body.scrollHeight)')
        for selector in ('#fit-amplitude', '#fit-power'):
            box = page.locator(selector).bounding_box()
            self.assertGreaterEqual(box['y'], 0)
            self.assertLessEqual(box['y'] + box['height'], 1000)
        page.evaluate('() => window.scrollTo(0, 0)')

        overview = page.locator('#recording-overview')
        box = overview.bounding_box()
        overview.click(position={'x': box['width'] * .72, 'y': box['height'] * .85})
        page.wait_for_function("() => +document.getElementById('start').value > 0")
        page.wait_for_function(
            "() => document.getElementById('amplitude-plot').layout.scene.xaxis.range[0] > 0")
        self.assertIn(':', page.locator('#cursor-readout').inner_text())

        page.locator('#start').fill('0')
        page.locator('#start').press('Tab')
        page.wait_for_function(
            "() => document.getElementById('status').textContent.startsWith('0–10')")
        page.locator('body').click(position={'x': 2, 'y': 2})
        page.keyboard.press('ArrowRight')
        page.wait_for_function(
            "() => document.getElementById('status').textContent.startsWith('8–18')")
        page.locator('#start').focus()
        page.keyboard.press('ArrowRight')
        page.wait_for_timeout(250)  # Past the 160 ms data-loading debounce.
        self.assertEqual(float(page.locator('#start').input_value()), 8)


if __name__ == '__main__':
    unittest.main()
