"""Regression tests for readable EEG traces and dense session marker layouts.

Run from the repository root with:
    python -m unittest analysis.test_eeg_browser
The Agg backend exercises layout and callbacks without opening desktop windows.
"""
from types import SimpleNamespace
import unittest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

from analysis.eeg_browser import EEGBrowser


class EEGBrowserTest(unittest.TestCase):
    def make_raw(self, n_channels=3, n_samples=1250):
        """Include a large DC offset and substantially unequal amplitudes."""
        time = np.arange(n_samples) / 250
        patterns_uv = np.array([
            100_000 + 2 * np.sin(2 * np.pi * 5 * time),
            -15_000 + 800 * np.sin(2 * np.pi * 3 * time),
            300 + 25 * np.cos(2 * np.pi * 7 * time),
        ])
        signals_uv = np.asarray([patterns_uv[index % len(patterns_uv)]
                                 for index in range(n_channels)])
        names = [f"EEG {channel + 1}" for channel in range(n_channels)]
        return mne.io.RawArray(signals_uv * 1e-6,
                               mne.create_info(names, 250, "eeg"), verbose="ERROR")

    def browser(self, raw, **options):
        browser = EEGBrowser(raw, **options)
        self.addCleanup(plt.close, browser.figure)
        browser.figure.canvas.draw()
        return browser

    @staticmethod
    def annotations_snapshot(raw):
        return (raw.annotations.onset.copy(), raw.annotations.duration.copy(),
                raw.annotations.description.copy(), raw.annotations.orig_time)

    def test_auto_fit_separates_channels_and_contains_all_displayed_samples(self):
        raw = self.make_raw()
        browser = self.browser(raw, start=0, duration=2)
        self.assertEqual(len(browser.signal_axes), 3)
        self.assertEqual(len({id(axis) for axis in browser.signal_axes}), 3)
        self.assertEqual(len(browser.lines), 3)
        self.assertEqual(len(browser.offsets), 3)
        self.assertTrue(np.all(browser.clipped_counts == 0))
        # A channel with a huge DC offset still has a small, readable display range.
        self.assertGreater(browser.offsets[0], 99_000)
        self.assertLess(browser.offsets[1], -14_000)
        widths = []
        for axis, line in zip(browser.signal_axes, browser.lines):
            with self.subTest(channel=axis.get_ylabel()):
                self.assertIs(line.axes, axis)
                self.assertTrue(line.get_clip_on())
                values = np.asarray(line.get_ydata(), dtype=float)
                values = values[np.isfinite(values)]
                self.assertGreater(values.size, 0)
                lower, upper = axis.get_ylim()
                self.assertLessEqual(lower, values.min())
                self.assertGreaterEqual(upper, values.max())
                widths.append(upper - lower)
        self.assertGreater(widths[1], widths[0] * 100)
        # Separate axes and clipped artists prevent signal strokes entering another row.
        boxes = [axis.get_window_extent() for axis in browser.signal_axes]
        for first, second in zip(boxes, boxes[1:]):
            self.assertFalse(first.overlaps(second))

    def test_fixed_scale_is_shared_and_reports_clipped_samples(self):
        raw = self.make_raw()
        browser = self.browser(raw, duration=2, scale_uv=10)
        for axis in browser.signal_axes:
            np.testing.assert_allclose(axis.get_ylim(), (-10, 10))
        self.assertEqual(browser.clipped_counts[0], 0)
        self.assertGreater(browser.clipped_counts[1], 0)
        self.assertGreater(browser.clipped_counts[2], 0)
        for line, clipped in zip(browser.lines, browser.clipped_counts):
            values = np.asarray(line.get_ydata())
            self.assertEqual(int(clipped), int(np.count_nonzero(np.abs(values) > 10)))
        browser.auto_fit()
        self.assertTrue(np.all(browser.clipped_counts == 0))
        for axis, line in zip(browser.signal_axes, browser.lines):
            lower, upper = axis.get_ylim()
            self.assertLessEqual(lower, np.nanmin(line.get_ydata()))
            self.assertGreaterEqual(upper, np.nanmax(line.get_ydata()))

    def test_navigation_gain_and_event_selection_leave_raw_untouched(self):
        raw = self.make_raw()
        raw.set_annotations(mne.Annotations([0, 1, 1, 4], [0, 0, 0, 0],
                                            ["baseline", "task_onset | trial=1", "Husten", "end"]))
        original_data = raw.get_data().copy()
        original_annotations = self.annotations_snapshot(raw)
        browser = self.browser(raw, duration=2)
        browser.change_gain(2)
        browser.set_start(1)
        browser.set_duration(1)
        browser.select_event(2)
        browser.auto_fit()
        browser.figure.canvas.draw()
        np.testing.assert_array_equal(raw.get_data(), original_data)
        for original, current in zip(original_annotations, self.annotations_snapshot(raw)):
            if isinstance(original, np.ndarray):
                np.testing.assert_array_equal(current, original)
            else:
                self.assertEqual(current, original)

    def test_coincident_events_remain_individually_selectable_with_full_details(self):
        raw = self.make_raw(n_channels=1)
        descriptions = [
            "session_start | run=Baseline | condition=baseline | phase=baseline",
            "baseline_start | run=Baseline | condition=baseline | phase=baseline",
            'Husten, "leicht" | geprüft',
            "task_onset | run=Motorik | condition=arms | block=1 | trial=1 | attempt=2 | status=invalid",
        ]
        raw.set_annotations(mne.Annotations([0, 0, 0, 1], [0] * 4, descriptions))
        browser = self.browser(raw, duration=2)
        for index, description in enumerate(raw.annotations.description):
            with self.subTest(index=index):
                browser.select_event(index, jump=False)
                browser.figure.canvas.draw()
                self.assertEqual(browser.selected_event, index)
                # The stored source is exact. Details split structured fields onto lines.
                self.assertEqual(browser.descriptions[index], description)
                visible = " ".join(text.get_text() for text in browser.detail_axis.texts)
                normalized = "".join(visible.split())
                for part in description.split(" | "):
                    self.assertIn("".join(part.split()), normalized)
        self.assertEqual(len(raw.annotations), 4)

    def test_long_selected_event_remains_available_by_scrolling(self):
        raw = self.make_raw(n_channels=1)
        description = "Manual observation: " + " ".join(f"word{index:03d}" for index in range(100))
        raw.set_annotations(mne.Annotations([0], [0], [description]))
        browser = self.browser(raw, duration=2)
        browser.figure.set_size_inches(9, 6)
        browser._on_resize(SimpleNamespace(canvas=browser.figure.canvas))
        pages = [browser.detail_text.get_text()]
        for _ in range(100):
            previous_scroll = browser.detail_scroll
            browser._on_scroll(SimpleNamespace(inaxes=browser.detail_axis, button="down"))
            pages.append(browser.detail_text.get_text())
            if browser.detail_scroll == previous_scroll:
                break
        self.assertGreater(browser.detail_scroll, 0)
        self.assertEqual(browser.descriptions[0], description)
        all_text = " ".join(pages)
        for index in range(100):
            self.assertIn(f"word{index:03d}", all_text)

    def test_dense_marker_labels_do_not_overlap_after_resize(self):
        raw = self.make_raw(n_channels=8)
        onsets = np.concatenate((np.zeros(4), np.linspace(0.03, 1.97, 60)))
        descriptions = [f"task_onset | run=Motorik | condition=arms | trial={index + 1}"
                        for index in range(len(onsets))]
        descriptions[1] = 'Manual marker: a very long label with spaces, quotes "äöü", and | delimiters'
        raw.set_annotations(mne.Annotations(onsets, np.zeros(len(onsets)), descriptions))
        browser = self.browser(raw, duration=2)
        for width, height in ((14, 9), (9, 6)):
            with self.subTest(figsize=(width, height)):
                browser.figure.set_size_inches(width, height)
                browser._on_resize(SimpleNamespace(canvas=browser.figure.canvas))
                browser.figure.canvas.draw()
                renderer = browser.figure.canvas.get_renderer()
                boxes = [text.get_window_extent(renderer) for text in browser.marker_texts
                         if text.get_visible() and text.get_text()]
                self.assertGreater(len(boxes), 0)
                for index, first in enumerate(boxes):
                    for second in boxes[index + 1:]:
                        self.assertFalse(first.overlaps(second), "marker label bounding boxes overlap")
                for box in boxes:
                    for axis in browser.signal_axes:
                        self.assertFalse(box.overlaps(axis.get_window_extent(renderer)),
                                         "marker label invades an EEG channel")
                figure_box = browser.figure.bbox
                for box in boxes + [axis.yaxis.label.get_window_extent(renderer)
                                    for axis in browser.signal_axes]:
                    self.assertGreaterEqual(box.x0, figure_box.x0 - 1)
                    self.assertLessEqual(box.x1, figure_box.x1 + 1)
                    self.assertGreaterEqual(box.y0, figure_box.y0 - 1)
                    self.assertLessEqual(box.y1, figure_box.y1 + 1)
                header_boxes = [text.get_window_extent(renderer) for text in
                                (browser.heading, browser.subtitle, browser.event_note)]
                for index, first in enumerate(header_boxes):
                    for second in header_boxes[index + 1:]:
                        self.assertFalse(first.overlaps(second), "header text bounding boxes overlap")

    def test_long_window_preserves_narrow_positive_and_negative_artifacts(self):
        values_uv = np.zeros(20_000)
        # Both single-sample peaks sit in the same small rendering bucket.
        values_uv[10_001] = 400
        values_uv[10_002] = -900
        raw = mne.io.RawArray(values_uv[None, :] * 1e-6,
                               mne.create_info(["EEG 1"], 250, "eeg"), verbose="ERROR")
        browser = self.browser(raw, duration=80)
        displayed = browser.lines[0].get_ydata()
        self.assertAlmostEqual(np.max(displayed), 400)
        self.assertAlmostEqual(np.min(displayed), -900)
        lower, upper = browser.signal_axes[0].get_ylim()
        self.assertLessEqual(lower, -900)
        self.assertGreaterEqual(upper, 400)

    def test_navigation_clamps_to_recording_and_handles_long_window(self):
        raw = self.make_raw(n_channels=1)
        browser = self.browser(raw, duration=2)
        self.assertAlmostEqual(browser.total_duration, raw.n_times / raw.info["sfreq"])
        browser.set_start(-100)
        self.assertEqual(browser.start, 0)
        browser.set_start(1e6)
        self.assertAlmostEqual(browser.start, browser.total_duration - browser.duration)
        browser._on_key(SimpleNamespace(key="right"))
        self.assertAlmostEqual(browser.start, browser.total_duration - browser.duration)
        browser.set_duration(1000)
        self.assertEqual(browser.start, 0)
        self.assertGreater(browser.duration, 0)
        self.assertLessEqual(browser.duration, browser.total_duration)
        for line in browser.lines:
            self.assertGreater(len(line.get_xdata()), 0)
            self.assertTrue(np.isfinite(line.get_ydata()).all())

    def test_toolbar_navigation_cannot_bypass_the_browser_controller(self):
        browser = self.browser(self.make_raw(), duration=2)
        self.assertTrue(all(not axis.get_navigate() for axis in browser.figure.axes))
        # Disabling native pan/zoom must leave the synchronized controls operational.
        browser._on_key(SimpleNamespace(key="right"))
        self.assertEqual(browser.start, 1)
        np.testing.assert_allclose(browser.signal_axes[0].get_xlim(), (1, 3))
        self.assertEqual(browser.slider.val, 1)
        browser._on_key(SimpleNamespace(key="home"))
        self.assertEqual(browser.start, 0)

    def test_single_sample_single_channel_without_markers(self):
        raw = self.make_raw(n_channels=1, n_samples=1)
        browser = self.browser(raw, duration=10)
        browser.set_start(100)
        browser.set_duration(20)
        browser.auto_fit()
        browser.change_gain(0.5)
        browser._on_key(SimpleNamespace(key="left"))
        browser.figure.canvas.draw()
        self.assertEqual(browser.start, 0)
        self.assertIsNone(browser.selected_event)
        self.assertEqual(len(browser.signal_axes), 1)
        self.assertEqual(len(browser.lines[0].get_ydata()), 1)
        lower, upper = browser.signal_axes[0].get_ylim()
        self.assertTrue(np.isfinite([lower, upper]).all())
        self.assertLess(lower, upper)


if __name__ == "__main__":
    unittest.main()
