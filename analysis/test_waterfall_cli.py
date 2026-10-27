"""Check waterfall CLI dispatch without starting a browser or a local server."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import mne
import numpy as np

import view_eeg as primary_viewer
from analysis import view_eeg as analysis_viewer


class WaterfallCLITest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="waterfall cli ")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "recording.csv"
        times = np.arange(1000) / 250
        self.raw = mne.io.RawArray(
            np.array([20 * np.sin(2 * np.pi * 10 * times),
                      15 * np.cos(2 * np.pi * 20 * times)]) * 1e-6,
            mne.create_info(["EEG 1", "EEG 2"], 250, "eeg"), verbose="ERROR")
        self.waterfall = types.ModuleType("analysis.waterfall_browser")
        self.waterfall.serve_waterfall = mock.Mock()

    def invoke(self, module, *arguments, waterfall_module=True):
        output, errors = io.StringIO(), io.StringIO()
        server_module = self.waterfall if waterfall_module else None
        with mock.patch.object(module, "load_recording", return_value=self.raw) as load, \
             mock.patch.object(sys, "argv", ["view_eeg.py", str(self.path), "--unit", "uV", *arguments]), \
             mock.patch.dict(sys.modules, {"analysis.waterfall_browser": server_module}), \
             redirect_stdout(output), redirect_stderr(errors):
            try:
                module.main()
            except SystemExit as error:
                code = error.code
            else:
                code = 0
        return code, output.getvalue(), errors.getvalue(), load

    def test_primary_dispatches_requested_window_scale_and_display_filter(self):
        display = mock.Mock()
        display.filter.return_value = display
        original = self.raw.get_data().copy()
        with mock.patch.object(self.raw, "copy", return_value=display):
            code, _, errors, _ = self.invoke(primary_viewer, "--view", "waterfall",
                                             "--start", "1", "--duration", "2", "--scale-uv", "75",
                                             "--highpass", "1", "--lowpass", "40")
        self.assertEqual(code, 0, errors)
        display.filter.assert_called_once_with(1, 40)
        self.waterfall.serve_waterfall.assert_called_once_with(
            display, start=1, duration=2, scale_uv=75, title="recording.csv",
            filter_label="high-pass 1 Hz, low-pass 40 Hz")
        np.testing.assert_array_equal(self.raw.get_data(), original)

    def test_primary_snapshot_rejected_before_loading_or_any_export(self):
        png = Path(self.directory.name) / "preview.png"
        fif = Path(self.directory.name) / "recording_raw.fif"
        code, _, errors, load = self.invoke(primary_viewer, "--view", "waterfall",
                                             "--no-show", "--snapshot", str(png), "--save-fif", str(fif))
        self.assertNotEqual(code, 0)
        self.assertIn("PNG buttons", errors)
        load.assert_not_called()
        self.waterfall.serve_waterfall.assert_not_called()
        self.assertFalse(png.exists())
        self.assertFalse(fif.exists())

    def test_no_show_does_not_import_plotly_viewer_or_start_server(self):
        for module in (primary_viewer, analysis_viewer):
            with self.subTest(module=module.__name__):
                code, _, errors, load = self.invoke(module, "--view", "waterfall", "--no-show",
                                                     waterfall_module=False)
                self.assertEqual(code, 0, errors)
                load.assert_called_once_with(self.path, "uV", "auto")

    def test_primary_headless_waterfall_can_export_unfiltered_fif(self):
        fif = Path(self.directory.name) / "imported_raw.fif"
        code, _, errors, _ = self.invoke(primary_viewer, "--view", "waterfall", "--no-show",
                                         "--save-fif", str(fif), waterfall_module=False)
        self.assertEqual(code, 0, errors)
        restored = mne.io.read_raw_fif(fif, preload=True, verbose="ERROR")
        np.testing.assert_allclose(restored.get_data(), self.raw.get_data(), rtol=1e-6, atol=1e-12)

    def test_analysis_dispatches_filtered_copy_and_common_options(self):
        display = mock.Mock()
        display.notch_filter.return_value = display
        display.filter.return_value = display
        with mock.patch.object(self.raw, "copy", return_value=display):
            code, _, errors, _ = self.invoke(analysis_viewer, "--view", "waterfall", "--filtered",
                                             "--start", "0.5", "--duration", "1.5", "--scale-uv", "50")
        self.assertEqual(code, 0, errors)
        display.notch_filter.assert_called_once_with(50)
        display.filter.assert_called_once_with(.5, 30)
        self.waterfall.serve_waterfall.assert_called_once_with(
            display, start=.5, duration=1.5, scale_uv=50, title="recording.csv",
            filter_label="50 Hz notch + 0.5–30 Hz band-pass")

    def test_analysis_psd_is_incompatible_before_loading(self):
        code, _, errors, load = self.invoke(analysis_viewer, "--view", "waterfall", "--psd")
        self.assertNotEqual(code, 0)
        self.assertIn("--psd", errors)
        self.assertIn("--view waterfall", errors)
        load.assert_not_called()
        self.waterfall.serve_waterfall.assert_not_called()

    def test_both_entry_points_reject_invalid_waterfall_display_parameters(self):
        for module in (primary_viewer, analysis_viewer):
            for arguments in (("--duration", "0"), ("--duration", "nan"),
                              ("--start", "inf"), ("--start", "4"),
                              ("--scale-uv", "-1")):
                with self.subTest(module=module.__name__, arguments=arguments):
                    code, _, errors, _ = self.invoke(module, "--view", "waterfall", *arguments)
                    self.assertNotEqual(code, 0)
                    self.assertIn("Error:", errors)
                    self.assertNotIn("Traceback", errors)
        self.waterfall.serve_waterfall.assert_not_called()


if __name__ == "__main__":
    unittest.main()
