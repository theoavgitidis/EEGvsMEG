"""Exercise headless viewer export through the real command-line entry point."""
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import mne
import numpy as np

from analysis.event_annotations import event_descriptions


class ViewerCLITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="EEG viewer test ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.project = Path(__file__).resolve().parents[1]
        self.csv_path = self.directory / "recording geprüft.csv"
        time = np.arange(2500) / 250
        self.samples_uv = np.column_stack((1000 + 20 * time + 15 * np.sin(2 * np.pi * 8 * time),
                                            -2000 + 10 * np.cos(2 * np.pi * 12 * time)))
        with self.csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["sample_index", "EEG 1", "EEG 2"])
            writer.writerows((index, *values) for index, values in enumerate(self.samples_uv))
        self.rows = [
            dict(label="session_start", samples_received=0, source="automatic", run="Baseline", trial=0),
            dict(label="task_onset", samples_received=250, source="automatic", run="Motorik", block=1,
                 trial=1, attempt=1, condition="arms", phase="task"),
            dict(label="trial_end", samples_received=750, source="automatic", run="Motorik", block=1,
                 trial=1, attempt=1, condition="arms", phase="rest"),
            dict(label='Husten, "leicht": geprüft', samples_received=1000, source="manual"),
        ]
        fields = list(dict.fromkeys(field for row in self.rows for field in row))
        with Path(str(self.csv_path) + ".events.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.rows)

    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["MPLBACKEND"] = "Agg"
        return subprocess.run([sys.executable, str(self.project / "view_eeg.py"), str(self.csv_path),
                               "--unit", "uV", "--no-show", *arguments],
                              cwd=self.project, env=environment, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)

    def test_filtered_snapshot_and_fif_export_keep_unfiltered_data_and_all_annotations(self):
        fif_path = self.directory / "unfiltered_raw.fif"
        png_path = self.directory / "filtered preview.png"
        original_csv = self.csv_path.read_bytes()
        event_path = Path(str(self.csv_path) + ".events.csv")
        original_events = event_path.read_bytes()
        result = self.run_cli("--highpass", "1", "--lowpass", "40", "--start", "2", "--duration", "2",
                              "--save-fif", str(fif_path), "--snapshot", str(png_path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(fif_path.is_file())
        self.assertTrue(png_path.is_file())
        self.assertEqual(png_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        restored = mne.io.read_raw_fif(fif_path, preload=True, verbose="ERROR")
        # FIF's default single-precision storage introduces only rounding error.
        np.testing.assert_allclose(restored.get_data(), self.samples_uv.T * 1e-6,
                                   rtol=1e-6, atol=1e-12)
        self.assertEqual(restored.annotations.description.tolist(), event_descriptions(self.rows))
        np.testing.assert_allclose(restored.annotations.onset, [0, 1, 3, 4], atol=1e-7)
        self.assertEqual(restored.ch_names, ["EEG 1", "EEG 2"])
        self.assertEqual(restored.info["sfreq"], 250)
        self.assertEqual(self.csv_path.read_bytes(), original_csv)
        self.assertEqual(event_path.read_bytes(), original_events)

    def test_invalid_display_parameters_fail_without_producing_outputs(self):
        cases = [
            ("--duration", "0"),
            ("--start", "nan"),
            ("--start", "1000"),
            ("--scale-uv", "inf"),
            ("--lowpass", "125"),
            ("--highpass", "40", "--lowpass", "1"),
        ]
        for number, arguments in enumerate(cases):
            with self.subTest(arguments=arguments):
                destination = self.directory / f"invalid_{number}.png"
                result = self.run_cli(*arguments, "--snapshot", str(destination))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(destination.exists())

    def test_spectrogram_options_export_a_real_snapshot(self):
        destination = self.directory / "selected channel linear spectrogram.png"
        result = self.run_cli("--spectrogram-channel", "EEG 2", "--frequency-scale", "linear",
                              "--spectrogram-max", "45", "--snapshot", str(destination))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(destination.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_invalid_spectrogram_parameters_fail_before_fif_or_snapshot_export(self):
        for number, arguments in enumerate([
            ("--spectrogram-channel", "Missing channel"),
            ("--spectrogram-max", "nan"),
            ("--spectrogram-max", "inf"),
            ("--spectrogram-max", "0.5"),
            ("--spectrogram-max", "-1"),
        ]):
            with self.subTest(arguments=arguments):
                png_path = self.directory / f"invalid_spectral_{number}.png"
                fif_path = self.directory / f"invalid_spectral_{number}_raw.fif"
                result = self.run_cli(*arguments, "--snapshot", str(png_path),
                                      "--save-fif", str(fif_path))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(png_path.exists())
                self.assertFalse(fif_path.exists())

    def test_analysis_viewer_opens_through_script_and_module_entry_points(self):
        environment = os.environ.copy()
        environment["MPLBACKEND"] = "Agg"
        for invocation in ([str(self.project / "analysis" / "view_eeg.py")],
                           ["-m", "analysis.view_eeg"]):
            with self.subTest(invocation=invocation):
                result = subprocess.run([sys.executable, *invocation, str(self.csv_path), "--unit", "uV",
                                         "--spectrogram-channel", "EEG 2", "--frequency-scale", "linear",
                                         "--spectrogram-max", "45"],
                                        cwd=self.project, env=environment, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("4 Marker importiert", result.stdout)


if __name__ == "__main__":
    unittest.main()
