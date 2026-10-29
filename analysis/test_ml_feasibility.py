"""Quality-marker exclusions, intact trial pairs and partially evaluable sessions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis.ml_data import trial_windows
from analysis.ml_feasibility import exclude_before_marker


class QualityMarkerTests(unittest.TestCase):
    def setUp(self):
        self.events = pd.DataFrame([
            dict(source="automatic", run="Kognitiv", block=1, trial=1, attempt=1,
                 condition="mental_arithmetic", label=label, phase=phase, samples_received=sample)
            for label, phase, sample in [("cue_onset", "task", 1000), ("task_offset", "task", 3500),
                                         ("phase_end", "rest", 7500), ("trial_end", "rest", 7500)]])
        self.windows, _ = trial_windows(self.events, 8000, 250)

    def marker(self, sample):
        return pd.concat([self.events, pd.DataFrame([
            dict(source="manual", label="ground placed", samples_received=sample)])], ignore_index=True)

    def test_cue_boundary_and_settling_preserve_or_exclude_entire_pair(self):
        events = self.marker(1000)
        original = events.copy(deep=True)
        kept, excluded, rule = exclude_before_marker(self.windows, events, 250, 8000, "ground placed")
        pd.testing.assert_frame_equal(kept, self.windows)
        self.assertFalse(excluded)
        self.assertEqual(rule["marker_time_s"], 4)
        kept, excluded, rule = exclude_before_marker(self.windows, events, 250, 8000, "ground placed", .001)
        self.assertTrue(kept.empty)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(rule["cutoff_sample"], 1001)
        pd.testing.assert_frame_equal(events, original)

    def test_marker_inside_task_rejects_later_rest_too(self):
        kept, excluded, _ = exclude_before_marker(self.windows, self.marker(1100), 250, 8000, "ground placed")
        self.assertTrue(kept.empty)
        self.assertEqual(excluded[0]["key"], "Kognitiv/1/1/1")

    def test_missing_ambiguous_invalid_marker_and_invalid_guard_fail(self):
        for events in [self.events, pd.concat([self.marker(1000), self.marker(2000)])]:
            with self.assertRaisesRegex(ValueError, "exactly one"):
                exclude_before_marker(self.windows, events, 250, 8000, "ground placed")
        for sample in [-1, 8000, 1000.5, float("nan")]:
            with self.assertRaisesRegex(ValueError, "integer within"):
                exclude_before_marker(self.windows, self.marker(sample), 250, 8000, "ground placed")
        for guard in [-1, float("inf"), float("nan")]:
            with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                exclude_before_marker(self.windows, self.marker(0), 250, 8000, "ground placed", guard)
        with self.assertRaisesRegex(ValueError, "requires"):
            exclude_before_marker(self.windows, self.events, 250, 8000, settle_seconds=1)

    def test_default_keeps_all_windows(self):
        kept, excluded, rule = exclude_before_marker(self.windows, self.events, 250, 8000)
        pd.testing.assert_frame_equal(kept, self.windows)
        self.assertEqual((excluded, rule), ([], None))

    def test_cli_reports_single_motor_block_but_evaluates_imagery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.csv"
            events, start = [], 0
            for run, labels in [("Motorik", ["arms", "legs", "blink"]),
                                ("Imagery", ["imagine_arms", "imagine_legs"])]:
                for block in [1, 2]:
                    for trial, condition in enumerate(labels, 1):
                        for label, phase, offset in [("cue_onset", "task", 0), ("task_offset", "task", 900),
                                                     ("phase_end", "rest", 999), ("trial_end", "rest", 999)]:
                            events.append(dict(source="automatic", run=run, block=block, trial=trial,
                                attempt=1, condition=condition, label=label, phase=phase,
                                samples_received=start + offset))
                        start += 1000
            events.append(dict(source="manual", label="ground placed", samples_received=3000,
                               run="Motorik", block=2, trial=0, attempt=1, condition="", phase="prepare"))
            pd.DataFrame(events).to_csv(str(path) + ".events.csv", index=False)
            rng = np.random.default_rng(4)
            frame = pd.DataFrame({"sample_index": np.arange(start), "Validation Indicator": 1})
            for name in [*[f"EEG {i}" for i in range(1, 9)],
                         *[f"{sensor} {axis}" for sensor in ["Accelerometer", "Gyroscope"] for axis in "XYZ"]]:
                frame[name] = rng.normal(size=start)
            frame.to_csv(path, index=False)
            Path(str(path) + ".session.json").write_text(json.dumps(dict(
                sampling_rate_hz=250, participant_id="SYNTHETIC", session_id="SYNTHETIC",
                device={"channels": [dict(name=f"EEG {i}", enabled=True, unit="uV") for i in range(1, 9)]})))
            report = Path(folder) / "result.json"
            command = [sys.executable, "-m", "analysis.ml_feasibility", str(path), "--after-marker",
                       "ground placed", "--output", str(report)]
            completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                       capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(report.read_text())
            self.assertEqual(set(result["results"]), {"Imagery"})
            self.assertEqual(result["results"]["Imagery"]["eeg"]["n"], 4)
            self.assertEqual(result["skipped_evaluations"]["Motorik"]["blocks"], [2])
            self.assertEqual(len(result["exclusions"]), 3)
            self.assertEqual(min(w["start_sample"] for w in result["retained_windows"]), 3125)
            self.assertIn(path.name, result["inputs_sha256"])


if __name__ == "__main__":
    unittest.main()
