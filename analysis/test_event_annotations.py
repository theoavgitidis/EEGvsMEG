"""Regression tests: session context survives both viewers and a real FIF round trip.

Run from the repository root: python -m unittest analysis.test_event_annotations
Requires the viewers' dependencies: mne, numpy, pandas.
"""
import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
import warnings

import mne

import view_eeg as root_viewer
from analysis import view_eeg as analysis_viewer
from analysis.event_annotations import event_descriptions


class EventAnnotationsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "recording.csv"
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["sample_index", "EEG 1"])
            writer.writerows((sample, 1.5) for sample in range(1000))

    def write_events(self, rows):
        fields = list(dict.fromkeys(field for row in rows for field in row))
        with Path(str(self.path) + ".events.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def auto(label, sample, trial=1, attempt=1, condition="arms", **extra):
        return dict(label=label, samples_received=sample, source="automatic", run="Motorik",
                    block=1, trial=trial, attempt=attempt, condition=condition, phase="task", **extra)

    def load(self, viewer):
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # intentionally out-of-range invalidation marker
            return viewer.load_recording(self.path, "uV")

    def assert_fif_round_trip(self, raw, name):
        destination = Path(self.temp.name) / (name + "_raw.fif")
        raw.save(destination, overwrite=False, verbose="ERROR")
        restored = mne.io.read_raw_fif(destination, preload=False, verbose="ERROR")
        self.assertEqual(raw.annotations.description.tolist(), restored.annotations.description.tolist())

    def test_structured_trials_and_invalid_attempts_survive_import_and_fif(self):
        rows = [
            self.auto("task_onset", 25),
            self.auto("trial_invalidated", 100),
            self.auto("task_onset", 150, attempt=2),
            self.auto("trial_end", 250, attempt=2),
            self.auto("task_onset", 300, trial=2, condition="legs"),
            self.auto("trial_end", 400, trial=2, condition="legs"),
            dict(self.auto("task_onset", 500, condition="mental_arithmetic", start_number=347, subtract=7), run="Kognitiv"),
            dict(self.auto("trial_end", 600, condition="mental_arithmetic", start_number=347, subtract=7), run="Kognitiv"),
            self.auto("task_onset", 700, trial=3),
            self.auto("trial_end", 750, trial=3),
            # Must still invalidate the attempt although this marker itself is outside raw.times.
            self.auto("trial_invalidated", 1000, trial=3),
            dict(label='Husten, "leicht": geprüft', samples_received=800, source="manual"),
        ]
        self.write_events(rows)
        first = None
        for viewer in (root_viewer, analysis_viewer):
            with self.subTest(viewer=viewer.__name__):
                raw = self.load(viewer)
                labels = raw.annotations.description.tolist()
                if first is None:
                    first = labels
                else:
                    self.assertEqual(first, labels)
                tasks = [label for label in labels if label.startswith("task_onset |")]
                self.assertEqual(len(tasks), 5)
                self.assertIn("condition=arms", tasks[0])
                self.assertIn("trial=1 | attempt=1", tasks[0])
                self.assertIn("status=invalid", tasks[0])
                self.assertIn("trial=1 | attempt=2", tasks[1])
                self.assertIn("status=completed", tasks[1])
                self.assertIn("condition=legs", tasks[2])
                self.assertIn("run=Kognitiv", tasks[3])
                self.assertIn("start_number=347 | subtract=7", tasks[3])
                self.assertIn("status=invalid", tasks[4])
                self.assertIn('Husten, "leicht": geprüft', labels)
                self.assert_fif_round_trip(raw, viewer.__name__.replace(".", "_"))

    def test_legacy_labels_are_unchanged(self):
        rows = [dict(host_utc_s=0, elapsed_s=0, samples_received=sample, label=label)
                for sample, label in [(0, "baseline"), (25, "hands_up"), (100, 'Husten, "leicht": geprüft')]]
        self.write_events(rows)
        for viewer in (root_viewer, analysis_viewer):
            with self.subTest(viewer=viewer.__name__):
                raw = self.load(viewer)
                self.assertEqual(raw.annotations.description.tolist(), [row["label"] for row in rows])
                self.assert_fif_round_trip(raw, viewer.__name__.replace(".", "_"))

    def test_incomplete_attempts_and_manual_labels(self):
        rows = [self.auto("task_onset", 25),
                dict(self.auto("trial_invalidated", 30), source="manual")]
        labels = event_descriptions(rows)
        self.assertIn("status=incomplete", labels[0])
        self.assertEqual(labels[1], "trial_invalidated")

    def test_invalidation_wins_even_after_trial_end(self):
        rows = [self.auto("task_onset", 1), self.auto("trial_end", 2), self.auto("trial_invalidated", 3)]
        self.assertTrue(all("status=invalid" in label for label in event_descriptions(rows)))


if __name__ == "__main__":
    unittest.main()
