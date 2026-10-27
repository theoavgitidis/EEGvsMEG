"""Numerical and sample-access checks for the browser's time–frequency view.

Run with ``python -m unittest analysis.test_time_frequency``.
"""
import unittest

import mne
import numpy as np
from scipy.signal import spectrogram as scipy_spectrogram

from analysis.time_frequency import compute_spectrogram


class Recording:
    """Raw-shaped source recording exactly which data the estimator reads."""

    def __init__(self, data, sfreq):
        self.data = np.asarray(data)
        self.n_times = self.data.shape[1]
        self.ch_names = [f"EEG {index + 1}" for index in range(self.data.shape[0])]
        self.info = {"sfreq": sfreq}
        self.reads = []

    def get_data(self, picks, start, stop):
        self.reads.append((picks, start, stop))
        return self.data[picks, start:stop]


class TimeFrequencyTest(unittest.TestCase):
    def test_known_sinusoid_has_correct_peak_integrated_power_and_units(self):
        sfreq = 250
        times = np.arange(2500) / sfreq
        amplitude_uv = 10
        # A large channel offset must not leak into the frequency estimate.
        values = (12345 + amplitude_uv * np.sin(2 * np.pi * 10 * times)) * 1e-6
        raw = Recording(values[None, :], sfreq)
        result = compute_spectrogram(raw, 0, 0, 10)
        peaks = result.frequencies[np.argmax(result.power, axis=0)]
        np.testing.assert_array_equal(peaks, np.full(len(result.times), 10))
        np.testing.assert_allclose(result.power.sum(axis=0) * result.frequency_resolution,
                                   amplitude_uv ** 2 / 2, rtol=1e-10)
        peak_density = result.power[result.frequencies == 10][0]
        np.testing.assert_allclose(peak_density, 200 / 3, rtol=1e-10)
        np.testing.assert_allclose(result.power_db[result.frequencies == 10][0],
                                   10 * np.log10(200 / 3), rtol=1e-10)
        self.assertEqual(result.window_seconds, 2)
        self.assertAlmostEqual(result.frequency_resolution, 0.5)

    def test_density_matches_scipy_for_even_and_odd_windows(self):
        rng = np.random.default_rng(819)
        for sfreq in (250, 7.5):
            with self.subTest(sfreq=sfreq):
                values_uv = rng.normal(size=int(sfreq * 12))
                raw = Recording(values_uv[None, :] * 1e-6, sfreq)
                result = compute_spectrogram(raw, 0, 0, 12, max_frequency=sfreq / 2)
                samples = int(np.ceil(2 * sfreq))
                hop = max(1, int(round(0.25 * sfreq)))
                frequencies, times, expected = scipy_spectrogram(
                    values_uv, fs=sfreq, window="hann", nperseg=samples,
                    noverlap=samples - hop, detrend="constant", return_onesided=True,
                    scaling="density", mode="psd")
                np.testing.assert_allclose(result.frequencies, frequencies)
                np.testing.assert_allclose(result.times, times)
                np.testing.assert_allclose(result.power, expected, rtol=1e-12, atol=1e-12)

    def test_navigation_preserves_identical_estimates_and_recording_time_origin(self):
        sfreq = 250
        rng = np.random.default_rng(148)
        raw = mne.io.RawArray(rng.normal(size=(1, 2500)) * 1e-6,
                              mne.create_info(["C3"], sfreq, "eeg"),
                              first_samp=12_500, verbose="ERROR")
        before = raw.get_data().copy()
        whole = compute_spectrogram(raw, "C3", 0, 10)
        part = compute_spectrogram(raw, "C3", 3.11, 4.89)
        indices = np.searchsorted(whole.times, part.times)
        np.testing.assert_array_equal(whole.times[indices], part.times)
        np.testing.assert_array_equal(whole.power[:, indices], part.power)
        self.assertEqual(whole.times[0], 1)
        self.assertLessEqual(whole.times[-1], 9)
        self.assertGreater(whole.times[-1], 9 - whole.hop_seconds)
        self.assertEqual(whole.time_edges[0], 1 - whole.hop_seconds / 2)
        self.assertEqual(len(part.time_edges), len(part.times) + 1)
        self.assertEqual(len(part.frequency_edges), len(part.frequencies) + 1)
        np.testing.assert_array_equal(raw.get_data(), before)

    def test_only_requested_channel_and_local_context_are_read(self):
        raw = Recording(np.zeros((8, 250 * 500)), 250)
        result = compute_spectrogram(raw, "EEG 4", 100, 102)
        self.assertTrue(result.available)
        self.assertEqual(len(raw.reads), 1)
        picks, first, last = raw.reads[0]
        self.assertEqual(picks, [3])
        self.assertGreaterEqual(first / 250, 98.75)
        self.assertLessEqual(last / 250, 103.25)
        self.assertLess(last - first, raw.n_times // 100)
        self.assertTrue(np.isfinite(result.power_db).all())
        np.testing.assert_array_equal(result.power_db, np.full_like(result.power_db, -300))

    def test_nonfinite_samples_produce_full_window_gaps_without_interpolation(self):
        sfreq = 250
        data = np.ones((1, 2500)) * 1e-6
        bad_samples = [1000, 1500]
        data[0, bad_samples] = [np.nan, np.inf]
        raw = Recording(data, sfreq)
        result = compute_spectrogram(raw, 0, 0, 10)
        starts = np.rint((result.times - 1) * sfreq).astype(int)
        expected_bad = np.any([(starts <= bad) & (bad < starts + 500)
                               for bad in bad_samples], axis=0)
        np.testing.assert_array_equal(np.all(np.isnan(result.power), axis=0), expected_bad)
        np.testing.assert_array_equal(np.all(np.isnan(result.power_db), axis=0), expected_bad)
        self.assertEqual(result.invalid_window_count, int(expected_bad.sum()))
        self.assertTrue(np.isfinite(result.power[:, ~expected_bad]).all())
        self.assertTrue(result.available)

    def test_short_recordings_and_unestimated_edges_are_explicitly_unavailable(self):
        for n_samples in (0, 1, 499):
            with self.subTest(n_samples=n_samples):
                raw = Recording(np.zeros((1, n_samples)), 250)
                result = compute_spectrogram(raw, 0, 0, 2)
                self.assertFalse(result.available)
                self.assertIn("At least 2 s", result.unavailable_reason)
                self.assertEqual(result.power.shape[1], 0)
                self.assertEqual(raw.reads, [])
        raw = Recording(np.zeros((1, 2500)), 250)
        for start, stop in ((0, 0.5), (9.5, 10), (100, 101)):
            with self.subTest(interval=(start, stop)):
                result = compute_spectrogram(raw, 0, start, stop)
                self.assertFalse(result.available)
                self.assertIn("No full 2 s", result.unavailable_reason)
        self.assertEqual(raw.reads, [])

    def test_exactly_one_full_window_and_low_sample_rates_keep_honest_metadata(self):
        for sfreq in (1, 10, 250):
            with self.subTest(sfreq=sfreq):
                raw = Recording(np.zeros((1, int(sfreq * 2))), sfreq)
                result = compute_spectrogram(raw, 0, 0, 2)
                self.assertTrue(result.available)
                np.testing.assert_array_equal(result.times, [1])
                self.assertLessEqual(result.frequencies[-1], sfreq / 2)
                self.assertLessEqual(result.frequency_edges[-1], sfreq / 2)
                self.assertEqual(result.nyquist, sfreq / 2)
                self.assertEqual(result.frequency_resolution, 0.5)
        raw = Recording(np.zeros((1, 40)), 7.6)
        result = compute_spectrogram(raw, 0, 0, 5)
        self.assertGreaterEqual(result.window_seconds, 2)
        self.assertEqual(result.window_seconds, 16 / 7.6)
        self.assertEqual(result.frequency_resolution, 7.6 / 16)

    def test_invalid_requests_fail_before_reading_data(self):
        raw = Recording(np.zeros((1, 1000)), 250)
        for start, stop in ((-1, 1), (1, 1), (2, 1), (np.nan, 1), (0, np.inf)):
            with self.subTest(interval=(start, stop)):
                with self.assertRaises(ValueError):
                    compute_spectrogram(raw, 0, start, stop)
        for channel in (-1, 1, "missing", 0.5):
            with self.subTest(channel=channel):
                with self.assertRaises(ValueError):
                    compute_spectrogram(raw, channel, 0, 2)
        self.assertEqual(raw.reads, [])


if __name__ == "__main__":
    unittest.main()
