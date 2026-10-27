"""Both viewer entry points must choose the same signal and original markers."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import view_eeg
from analysis import view_eeg as alternative
from acquisition.oscar_worker import HEADER


class SignalImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / "session.csv"
        self.clean = Path(str(self.raw) + ".oscar.csv")
        for path, count, amplitude in ((self.raw, 1083, 10), (self.clean, 1000, 3)):
            with path.open("w", newline="", encoding="utf-8") as file:
                out = csv.writer(file)
                out.writerow(HEADER)
                for index in range(count):
                    out.writerow([index, index / 250, 1700000000 + index / 250,
                                  *([amplitude] * 8), *([0] * 7), index, 1])
        Path(str(self.raw) + ".events.csv").write_text(
            "samples_received,label\n250,task\n500,rest\n", encoding="utf-8")
        self.processing = dict(schema_version=1, mode="oscar", state="complete", sampling_rate_hz=250,
                               raw_file=self.raw.name, oscar_file=self.clean.name,
                               oscar_samples=1000, oscar_delay_samples=83)
        Path(str(self.raw) + ".processing.json").write_text(json.dumps(self.processing))

    def test_both_loaders_prefer_oscar_without_shifting_markers(self):
        for loader in (view_eeg.load_recording, alternative.load_recording):
            with self.subTest(loader=loader.__module__):
                corrected = loader(self.raw, "uV")
                raw = loader(self.clean, "uV", "raw")
                self.assertEqual(corrected.n_times, 1000)
                self.assertEqual(raw.n_times, 1083)
                np.testing.assert_allclose(corrected.get_data(), 3e-6)
                np.testing.assert_allclose(raw.get_data(), 10e-6)
                np.testing.assert_equal(corrected.annotations.onset, [1, 2])
                np.testing.assert_equal(corrected.annotations.onset, raw.annotations.onset)
                self.assertIn("OSCAR", corrected.info["description"])
                self.assertEqual(raw.info["description"], "Rohdaten")

    def test_declared_units_and_complete_length_are_enforced(self):
        for loader in (view_eeg.load_recording, alternative.load_recording):
            with self.assertRaisesRegex(ValueError, "uV"):
                loader(self.raw, "V")
        self.processing["oscar_samples"] = 999
        Path(str(self.raw) + ".processing.json").write_text(json.dumps(self.processing))
        for loader in (view_eeg.load_recording, alternative.load_recording):
            with self.assertRaisesRegex(ValueError, "length"):
                loader(self.raw, "uV")

    def test_ml_loader_uses_shared_selection_and_provenance(self):
        # No model weights or torch needed to verify the data importer.
        if not importlib.util.find_spec("sklearn"):
            self.skipTest("scikit-learn is not installed in this environment")
        from analysis.ml_data import load_recording
        meta = dict(sampling_rate_hz=250, participant_id="SYNTHETIC", session_id="SYNTHETIC",
                    device={"channels": [dict(name=f"EEG {i}", enabled=True, unit="uV") for i in range(1, 9)]})
        Path(str(self.raw) + ".session.json").write_text(json.dumps(meta))
        with Path(str(self.raw) + ".events.csv").open("w", newline="") as file:
            out = csv.DictWriter(file, fieldnames=["source", "run", "block", "trial", "attempt", "condition", "phase", "samples_received", "label"])
            out.writeheader()
            for label, phase, index in (("cue_onset", "task", 0), ("task_offset", "task", 900),
                                        ("phase_end", "rest", 999), ("trial_end", "rest", 999)):
                out.writerow(dict(source="automatic", run="Motorik", block=1, trial=1, attempt=1,
                                  condition="arms", phase=phase, samples_received=index, label=label))
        rows, _, _, _, provenance = load_recording(self.raw)
        self.assertEqual(provenance["signal"], "oscar")
        self.assertEqual(rows.start_sample.tolist(), [125])
        self.assertIn(str(self.clean.resolve()), provenance["inputs"])
        self.assertIsNotNone(provenance["processing_metadata_sha256"])
        self.assertEqual(load_recording(self.raw, "raw")[-1]["signal"], "raw")
