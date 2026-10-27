"""Numerical and integrity checks for waterfall payloads.

Run with ``python -m unittest analysis.test_waterfall_data``.
"""
import json
import unittest

import mne
import numpy as np
from scipy.signal import periodogram

from analysis.waterfall_data import UNICORN_POSITIONS, build_waterfall_data, channel_metadata


def recording(values_uv, sfreq=250, names=None, first_samp=0):
    values_uv = np.atleast_2d(values_uv)
    names = names or [f"EEG {index + 1}" for index in range(len(values_uv))]
    return mne.io.RawArray(values_uv * 1e-6, mne.create_info(names, sfreq, "eeg"),
                           first_samp=first_samp, verbose="ERROR")


class WaterfallDataTest(unittest.TestCase):
    def test_documented_mapping_preserves_original_names_without_guessing(self):
        names = [f"EEG {index + 1}" for index in range(8)]
        names += ["cz", "PO7", "EEG 01", "EEG1", "CH1", "EEG 9", "misc"]
        raw = recording(np.zeros((len(names), 100)), names=names)
        metadata = channel_metadata(raw)
        self.assertEqual(tuple(item["label"] for item in metadata[:8]), UNICORN_POSITIONS)
        self.assertTrue(all(item["mapped"] for item in metadata[:10]))
        self.assertFalse(any(item["mapped"] for item in metadata[10:]))
        self.assertEqual([item["name"] for item in metadata], names)
        self.assertEqual(metadata[8]["label"], "Cz")

    def test_known_sinusoid_energy_units_centering_and_no_mutation(self):
        times = np.arange(2500) / 250
        raw = recording(1234 + 10 * np.sin(2 * np.pi * 10 * times), first_samp=12500)
        before = raw.get_data().copy()
        result = build_waterfall_data(raw)
        channel = result["channels"][0]
        np.testing.assert_allclose(channel["bandpower"], 50, rtol=1e-11)
        self.assertAlmostEqual(channel["offset_uv"], 1234, places=10)
        self.assertAlmostEqual(max(channel["amplitude"]), 10 * np.sin(.48 * np.pi), places=10)
        self.assertEqual(channel["power_times"][0], 1)
        self.assertLessEqual(channel["power_times"][-1], 9)
        self.assertGreater(channel["power_times"][-1], 9 - result["hop_seconds"])
        self.assertEqual(result["frequency_resolution"], .5)
        self.assertEqual(result["total_duration"], 10)
        self.assertEqual(result["warnings"], [])
        np.testing.assert_array_equal(before, raw.get_data())
        uncentered = build_waterfall_data(raw, center=False)["channels"][0]
        self.assertEqual(uncentered["offset_uv"], 0)
        np.testing.assert_allclose(np.asarray(uncentered["amplitude"])
                                   - np.asarray(channel["amplitude"]), 1234)
        self.assertEqual(uncentered["bandpower"], channel["bandpower"])

    def test_partial_frequency_bin_overlap_and_nyquist_preserve_energy(self):
        sfreq = 250
        samples = np.arange(1000)
        values = 6 * np.sin(2 * np.pi * 10 * samples / sfreq)
        raw = recording(values)
        channel = build_waterfall_data(raw, band=(9.9, 10.1))["channels"][0]
        frequencies, density = periodogram(values[:500], fs=sfreq, window="hann")
        # The band covers 0.2 Hz of the central 0.5-Hz Fourier-bin cell.
        expected = density[frequencies == 10][0] * .2
        np.testing.assert_allclose(channel["bandpower"], expected, rtol=1e-10)
        full = build_waterfall_data(recording(7 * (-1.0) ** samples), band=(0, 125))
        np.testing.assert_allclose(full["channels"][0]["bandpower"], 49, rtol=1e-12)

    def test_odd_window_matches_scipy_bin_overlap_integral(self):
        sfreq = 7.5
        rng = np.random.default_rng(24)
        values = rng.normal(size=90)
        raw = recording(values, sfreq=sfreq)
        result = build_waterfall_data(raw, band=(.4, 3.7))
        actual = result["channels"][0]
        frequencies, density = periodogram(values[:15], fs=sfreq, window="hann")
        edges = np.r_[0, (frequencies[:-1] + frequencies[1:]) / 2, sfreq / 2]
        weights = .5 * np.maximum(0, np.minimum(edges[1:], 3.7)
                                 - np.maximum(edges[:-1], .4)) / np.diff(edges)
        self.assertAlmostEqual(actual["bandpower"][0], density @ weights, places=12)
        self.assertEqual(result["window_seconds"], 2)
        self.assertEqual(result["hop_seconds"], 2 / 7.5)

    def test_navigation_keeps_identical_windows_and_cropped_time_origin(self):
        rng = np.random.default_rng(93)
        raw = recording(rng.normal(size=(2, 4000)), first_samp=25000)
        raw.set_annotations(mne.Annotations([3.5, 5.0], [0, 0], ["Task", "Rest"]))
        whole = build_waterfall_data(raw, duration=16)
        part = build_waterfall_data(raw, start=3.11, duration=4.92, channels=[1, 0])
        self.assertEqual([ch["index"] for ch in part["channels"]], [1, 0])
        for channel in part["channels"]:
            original = whole["channels"][channel["index"]]
            indices = np.searchsorted(original["power_times"], channel["power_times"])
            np.testing.assert_array_equal(np.asarray(original["power_times"])[indices], channel["power_times"])
            np.testing.assert_array_equal(np.asarray(original["bandpower"])[indices], channel["bandpower"])
        self.assertEqual(part["events"], [{"onset": 3.5, "description": "Task"},
                                          {"onset": 5.0, "description": "Rest"}])
        self.assertGreaterEqual(part["channels"][0]["times"][0], part["start"])
        self.assertLess(part["channels"][0]["times"][-1], part["stop"])
        cropped = raw.copy().crop(tmin=2, tmax=10, include_tmax=False)
        result = build_waterfall_data(cropped, duration=8)
        self.assertEqual(result["events"][0]["onset"], 1.5)
        self.assertEqual(result["channels"][0]["times"][0], 0)

    def test_nonfinite_samples_and_bad_annotations_are_null_power_gaps(self):
        values = np.ones(2500)
        values[[800, 1500]] = [np.nan, np.inf]
        raw = recording(values, first_samp=5000)
        raw.set_annotations(mne.Annotations([5], [.4], ["BAD_motion"]))
        result = build_waterfall_data(raw, max_points=50)
        channel = result["channels"][0]
        centers = np.asarray(channel["power_times"])
        starts = np.rint((centers - 1) * 250).astype(int)
        nonfinite = np.any([(starts <= index) & (index < starts + 500)
                            for index in (800, 1500)], axis=0)
        bad = (starts / 250 < 5.4) & ((starts + 500) / 250 > 5)
        np.testing.assert_array_equal([value is None for value in channel["bandpower"]], nonfinite | bad)
        self.assertIn(None, channel["amplitude"])
        self.assertTrue(any("BAD-Markierungen" in warning for warning in result["warnings"]))
        # A strict JSON encoder must never encounter a NaN or infinity.
        json.dumps(result, allow_nan=False)

    def test_envelope_preserves_positive_negative_spikes_and_narrow_gaps(self):
        values = np.zeros(20000)
        values[[147, 10112]] = [110, -95]
        values[9350:9352] = np.nan
        raw = recording(values)
        channel = build_waterfall_data(raw, duration=80, max_points=80, center=False)["channels"][0]
        self.assertLessEqual(len(channel["amplitude"]), 80)
        finite = [value for value in channel["amplitude"] if value is not None]
        self.assertAlmostEqual(max(finite), 110)
        self.assertAlmostEqual(min(finite), -95)
        self.assertIn(None, channel["amplitude"])
        paired = list(zip(channel["times"], channel["amplitude"]))
        self.assertAlmostEqual(dict(paired)[147 / 250], 110)
        self.assertAlmostEqual(dict(paired)[10112 / 250], -95)
        # Every pair of rendered finite samples must have no missing samples
        # between them, even if a one-sample gap falls between envelope extrema.
        for (first, left), (last, right) in zip(paired[:-1], paired[1:]):
            if left is not None and right is not None:
                self.assertTrue(np.isfinite(values[round(first * 250):round(last * 250) + 1]).all())

    def test_short_data_edges_passband_and_narrow_bands_are_explicit(self):
        short = build_waterfall_data(recording(np.zeros(100)), duration=10)
        self.assertEqual(short["channels"][0]["bandpower"], [])
        self.assertTrue(any("kürzer" in warning for warning in short["warnings"]))
        raw = recording(np.zeros(2500))
        edge = build_waterfall_data(raw, duration=.25)
        self.assertEqual(edge["channels"][0]["power_times"], [])
        self.assertTrue(any("kein Mittelpunkt" in warning for warning in edge["warnings"]))
        with raw.info._unlock():
            raw.info["highpass"] = 2
            raw.info["lowpass"] = 30
        result = build_waterfall_data(raw, band=(.5, 1.0))
        self.assertTrue(any("Filterdurchlassbereich" in warning for warning in result["warnings"]))
        result = build_waterfall_data(raw, band=(8.1, 8.2))
        self.assertTrue(any("Frequenzauflösung" in warning for warning in result["warnings"]))
        # A wildly oversized window must produce a useful empty result, never
        # allocate an FFT array for data that do not exist.
        result = build_waterfall_data(raw, window=10_000_000)
        self.assertEqual(result["channels"][0]["bandpower"], [])

    def test_power_envelope_caps_points_without_changing_estimates_or_crossing_gaps(self):
        sfreq = 100
        times = np.arange(2400) / sfreq
        values = (2 + 10 * np.exp(-((times - 12) / .5) ** 2)) * np.sin(2 * np.pi * 10 * times)
        raw = recording(values, sfreq=sfreq)
        raw.set_annotations(mne.Annotations([3], [.1], ["BAD_movement"]))
        full = build_waterfall_data(raw, duration=24, hop=.05)["channels"][0]
        result = build_waterfall_data(raw, duration=24, hop=.05, max_points=32)
        reduced = result["channels"][0]
        self.assertLessEqual(len(reduced["power_times"]), 32)
        self.assertEqual(len(reduced["power_times"]), len(reduced["bandpower"]))
        self.assertIn(None, reduced["bandpower"])
        for summarize in (min, max):
            self.assertEqual(summarize(value for value in reduced["bandpower"] if value is not None),
                             summarize(value for value in full["bandpower"] if value is not None))
        reference = dict(zip(full["power_times"], full["bandpower"]))
        for time, value in zip(reduced["power_times"], reduced["bandpower"]):
            self.assertEqual(value, reference[time])
        for position in range(len(reduced["power_times"]) - 1):
            if None not in reduced["bandpower"][position:position + 2]:
                first, last = reduced["power_times"][position:position + 2]
                self.assertTrue(all(value is not None for time, value in reference.items()
                                    if first <= time <= last))
        self.assertTrue(any("alle vollständigen Analysefenster" in warning for warning in result["warnings"]))

    def test_all_invalid_samples_and_point_hard_cap_remain_json_safe(self):
        raw = recording(np.full(2500, np.nan))
        result = build_waterfall_data(raw, max_points=8)
        channel = result["channels"][0]
        self.assertEqual(channel["offset_uv"], 0)
        self.assertTrue(all(value is None for value in channel["amplitude"]))
        self.assertTrue(all(value is None for value in channel["bandpower"]))
        json.dumps(result, allow_nan=False)
        result = build_waterfall_data(recording(np.zeros(20000)), duration=80, max_points=30000)
        self.assertLessEqual(len(result["channels"][0]["amplitude"]), 12000)
        self.assertTrue(any("12000" in warning for warning in result["warnings"]))

    def test_invalid_requests_raise_value_error_before_reading_data(self):
        raw = recording(np.zeros((2, 2500)))
        invalid = [
            {"start": -1}, {"start": 10}, {"start": np.nan}, {"start": True},
            {"duration": 0}, {"duration": np.inf}, {"duration": 1e-8, "start": 9.999},
            {"window": 0}, {"window": .001}, {"window": 1e308},
            {"hop": 0}, {"hop": .001}, {"hop": 1e308},
            {"band": (8,)}, {"band": (13, 8)}, {"band": (-1, 5)},
            {"band": (8, 126)}, {"band": (8, np.nan)}, {"band": None},
            {"channels": []}, {"channels": [-1]}, {"channels": [2]},
            {"channels": [0.0]}, {"channels": [True]}, {"channels": [0, 0]},
            {"max_points": 7}, {"max_points": 10.5}, {"center": "true"},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_waterfall_data(raw, **kwargs)

    def test_only_selected_channel_and_real_local_windows_are_read(self):
        class ReadRecorder:
            def __init__(self):
                self.info = {"sfreq": 250}
                self.n_times = 250 * 10000
                self.ch_names = ["EEG 1", "EEG 2"]
                self.reads = []

            def get_data(self, *, picks, start, stop):
                self.reads.append((picks, start, stop))
                return np.zeros((len(picks), stop - start))

        raw = ReadRecorder()
        result = build_waterfall_data(raw, start=100, duration=2, channels=[1])
        self.assertEqual(len(result["channels"]), 1)
        for picks, first, last in raw.reads:
            self.assertEqual(picks, [1])
            self.assertGreaterEqual(first / 250, 99)
            self.assertLessEqual(last / 250, 103)
            self.assertLess(last - first, raw.n_times // 1000)
        sparse = build_waterfall_data(raw, start=100, duration=8, hop=3, channels=[1])
        self.assertEqual(sparse["channels"][0]["power_times"], [100, 103, 106])


if __name__ == "__main__":
    unittest.main()
