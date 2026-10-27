"""Browser contracts for synchronized, quantitatively comparable EEG power."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

from analysis.eeg_browser import EEGBrowser
from analysis.time_frequency import compute_spectrogram


class SpectrogramBrowserTest(unittest.TestCase):
    def make_raw(self, samples=4000, sfreq=250):
        times = np.arange(samples) / sfreq
        rng = np.random.default_rng(8312)
        values_uv = np.array([
            1500 + 12 * np.sin(2 * np.pi * 10 * times),
            -2200 + 20 * np.sin(2 * np.pi * 20 * times),
            300 + 5 * np.sin(2 * np.pi * 6 * times),
        ]) + rng.normal(scale=0.5, size=(3, samples))
        raw = mne.io.RawArray(values_uv * 1e-6,
                              mne.create_info(["C3", "Cz", "C4"], sfreq, "eeg"),
                              verbose="ERROR")
        if samples / sfreq > 8:
            raw.set_annotations(mne.Annotations([1, 4, 8], [0, 0, 0],
                                                ["Baseline", "Task", "Rest"]))
        return raw

    def browser(self, raw=None, **kwargs):
        browser = EEGBrowser(raw if raw is not None else self.make_raw(), **kwargs)
        self.addCleanup(plt.close, browser.figure)
        browser.figure.canvas.draw()
        return browser

    def test_trace_controls_reuse_power_and_navigation_preserves_absolute_grid(self):
        with patch("analysis.eeg_browser.compute_spectrogram", wraps=compute_spectrogram) as compute:
            browser = self.browser(duration=4, start=2)
            original = browser.spectral_result
            self.assertEqual(compute.call_count, 1)
            for action in (lambda: browser.change_gain(2), browser.auto_fit,
                           lambda: browser.select_event(1, jump=False),
                           browser.toggle_frequency_scale, browser.fit_spectral_colors,
                           browser.reset_spectral_colors):
                action()
                self.assertIs(browser.spectral_result, original)
                self.assertEqual(compute.call_count, 1)
            browser.set_start(3)
            self.assertEqual(compute.call_count, 2)
            moved = browser.spectral_result
            common = np.intersect1d(original.times, moved.times)
            self.assertGreater(common.size, 0)
            np.testing.assert_allclose(
                original.power[:, np.searchsorted(original.times, common)],
                moved.power[:, np.searchsorted(moved.times, common)], rtol=1e-12, atol=1e-12)

    def test_named_and_clicked_channels_display_their_actual_frequency_peaks(self):
        browser = self.browser(spectrogram_channel="Cz", duration=4)
        self.assertEqual(browser.spectrogram_channel, 1)
        result = browser.spectral_result
        self.assertAlmostEqual(result.frequencies[np.argmax(result.power.mean(axis=1))], 20)
        browser.select_channel("C4")
        self.assertEqual(browser.spectrogram_channel, 2)
        self.assertIn("C4", browser.channel_heading.get_text())
        browser._on_click(SimpleNamespace(button=1, xdata=2, inaxes=browser.signal_axes[0]))
        self.assertEqual(browser.spectrogram_channel, 0)
        result = browser.spectral_result
        self.assertAlmostEqual(result.frequencies[np.argmax(result.power.mean(axis=1))], 10)
        browser.step_channel(-1)
        self.assertEqual(browser.spectrogram_channel, 2)
        with self.assertRaises(ValueError):
            browser.select_channel("Unknown")

    def test_color_limits_stay_fixed_until_explicit_fit_or_reset(self):
        browser = self.browser(duration=4)
        default = browser.spectral_norm.vmin, browser.spectral_norm.vmax
        self.assertEqual(default, (-20, 40))
        for action in (lambda: browser.change_gain(2), browser.auto_fit,
                       lambda: browser.set_start(2), lambda: browser.select_channel("Cz"),
                       browser.toggle_frequency_scale):
            action()
            self.assertEqual((browser.spectral_norm.vmin, browser.spectral_norm.vmax), default)
            self.assertIs(browser.spectral_mesh.norm, browser.spectral_norm)
        browser.fit_spectral_colors()
        fitted = browser.spectral_norm.vmin, browser.spectral_norm.vmax
        self.assertNotEqual(fitted, default)
        self.assertTrue(np.isfinite(fitted).all())
        self.assertGreaterEqual(fitted[1] - fitted[0], 10)
        browser.set_start(3)
        browser.select_channel("C3")
        self.assertEqual((browser.spectral_norm.vmin, browser.spectral_norm.vmax), fitted)
        browser.reset_spectral_colors()
        self.assertEqual((browser.spectral_norm.vmin, browser.spectral_norm.vmax), default)

    def test_frequency_scales_bounds_bands_and_filter_exclusions_are_visible(self):
        raw = self.make_raw().filter(1, 40, verbose="ERROR")
        browser = self.browser(raw, duration=4, spectrogram_max=90)
        self.assertEqual(browser.spectrogram_axis.get_yscale(), "log")
        np.testing.assert_allclose(browser.spectrogram_axis.get_ylim(), (.5, 90))
        names = [artist.get_text() for artist in browser.band_artists if hasattr(artist, "get_text")]
        self.assertTrue({"Delta", "Theta", "Alpha", "Beta", "Gamma"}.issubset(names))
        hatches = [artist for artist in browser.band_artists
                   if hasattr(artist, "get_hatch") and artist.get_hatch()]
        self.assertEqual(len(hatches), 2)
        self.assertIn("outside filter passband", browser.spectral_info.get_text())
        browser.toggle_frequency_scale()
        self.assertEqual(browser.spectrogram_axis.get_yscale(), "linear")
        np.testing.assert_allclose(browser.spectrogram_axis.get_ylim(), (.5, 90))
        low_rate = self.browser(self.make_raw(sfreq=100), spectrogram_max=100)
        self.assertEqual(low_rate.spectrogram_max, 50)
        self.assertLessEqual(low_rate.spectral_result.frequencies[-1], 50)
        self.assertLessEqual(low_rate.spectrogram_axis.get_ylim()[1], 50)

    def test_shared_time_and_selected_event_are_pixel_aligned_after_resize(self):
        browser = self.browser(duration=4)
        browser.select_event(2)
        onset = browser.onsets[browser.selected_event]
        for width, height in ((15, 10.5), (9, 6)):
            with self.subTest(size=(width, height)):
                browser.figure.set_size_inches(width, height)
                browser._on_resize(SimpleNamespace(canvas=browser.figure.canvas))
                browser.figure.canvas.draw()
                axes = [browser.marker_axis, *browser.signal_axes, browser.spectrogram_axis]
                expected = browser.marker_axis.transData.transform((onset, 0))[0]
                for axis in axes:
                    np.testing.assert_allclose(axis.get_xlim(), (browser.start, browser.start + browser.duration))
                    self.assertAlmostEqual(axis.transData.transform((onset, 0))[0], expected, places=6)
                for line in [browser.marker_selected, *browser.selected_lines]:
                    self.assertTrue(line.get_visible())
                    np.testing.assert_array_equal(line.get_xdata(), [onset, onset])

    def test_band_labels_remain_separate_on_both_frequency_scales(self):
        browser = self.browser(duration=4)
        for width, height in ((15, 10.5), (9, 6)):
            browser.figure.set_size_inches(width, height)
            for scale in ("log", "linear"):
                with self.subTest(size=(width, height), scale=scale):
                    browser.frequency_scale = scale
                    browser._on_resize(None)
                    browser.figure.canvas.draw()
                    renderer = browser.figure.canvas.get_renderer()
                    labels = [artist for artist in browser.band_artists
                              if hasattr(artist, "get_text") and artist.get_text() != "50 Hz"]
                    self.assertEqual(len(labels), 5)
                    boxes = [artist.get_window_extent(renderer) for artist in labels]
                    for index, box in enumerate(boxes):
                        self.assertFalse(box.overlaps(browser.spectral_title.get_window_extent(renderer)))
                        for other in boxes[index + 1:]:
                            self.assertFalse(box.overlaps(other))

    def test_spectrogram_sidebar_text_does_not_overlap_controls_or_colorbar(self):
        browser = self.browser(self.make_raw().filter(1, 40, verbose="ERROR"), duration=4)
        for dpi, width, height in ((100, 14.7, 9), (200, 14.7, 9),
                                   (100, 15, 10.5), (100, 12, 7.8),
                                   (100, 9, 9), (100, 9, 6)):
            with self.subTest(dpi=dpi, size=(width, height)):
                browser.figure.set_dpi(dpi)
                browser.figure.set_size_inches(width, height)
                browser._on_resize(None)
                browser.fit_spectral_colors()
                browser.figure.canvas.draw()
                renderer = browser.figure.canvas.get_renderer()
                texts = [text for text in (browser.channel_heading, browser.spectral_info,
                                          browser.color_label, browser.keyboard_help)
                         if text.get_visible()]
                controls = [browser.channel_previous, browser.channel_next, browser.color_fit_button,
                            browser.color_reset_button, browser.frequency_button]
                boxes = [(text.get_text(), text.get_window_extent(renderer)) for text in texts]
                boxes += [(button.label.get_text(), button.ax.get_window_extent(renderer))
                          for button in controls]
                boxes.append(("Colorbar", browser.color_axis.get_window_extent(renderer)))
                for index, (name, box) in enumerate(boxes):
                    for other_name, other in boxes[index + 1:]:
                        self.assertFalse(box.overlaps(other), f"{name!r} overlaps {other_name!r}")
                    self.assertGreaterEqual(box.x0, 0)
                    self.assertLessEqual(box.x1, browser.figure.bbox.width)
                    self.assertGreaterEqual(box.y0, 0)
                    self.assertLessEqual(box.y1, browser.figure.bbox.height)

    def test_controls_preserve_raw_samples_and_annotations(self):
        raw = self.make_raw()
        original = raw.get_data().copy()
        annotations = (raw.annotations.onset.copy(), raw.annotations.duration.copy(),
                       raw.annotations.description.copy())
        browser = self.browser(raw, duration=4)
        browser.select_channel("Cz")
        browser.change_gain(1.5)
        browser.fit_spectral_colors()
        browser.set_start(4)
        browser.select_event(2)
        browser.set_duration(3)
        browser.toggle_frequency_scale()
        browser.reset_spectral_colors()
        np.testing.assert_array_equal(raw.get_data(), original)
        for before, after in zip(annotations, (raw.annotations.onset, raw.annotations.duration,
                                               raw.annotations.description)):
            np.testing.assert_array_equal(before, after)

    def test_short_recording_keeps_trace_and_explains_absent_power(self):
        browser = self.browser(self.make_raw(samples=250))
        self.assertFalse(browser.spectral_result.available)
        self.assertIsNone(browser.spectral_mesh)
        self.assertTrue(browser.spectral_message.get_visible())
        self.assertIn("At least 2 s", browser.spectral_message.get_text())
        self.assertEqual(len(browser.lines[0].get_ydata()), 250)
        browser.fit_spectral_colors()
        browser.reset_spectral_colors()
        browser.toggle_frequency_scale()
        self.assertIsNone(browser.spectral_mesh)


if __name__ == "__main__":
    unittest.main()
