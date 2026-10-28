"""Protocol 2.0 import, legacy isolation and predefined evaluation contrasts."""
import unittest

import numpy as np
import pandas as pd

from analysis.ml_data import splits, trial_windows
from analysis.ml_feasibility import features, predict_cv
from analysis.session_conditions import (CURRENT, LEGACY, CURRENT_RUNS, CONTRASTS,
                                         protocol_for_events, select_evaluations, prediction_indices)


class SessionProtocolTest(unittest.TestCase):
    def test_mu_beta_features_and_complete_held_out_classes(self):
        time = np.arange(750)/250
        epoch = np.tile(np.sin(2*np.pi*10*time)[:, None], (1, 8))
        self.assertEqual(features(epoch, 250).shape, (40,))
        self.assertEqual(features(epoch, 250, ((8, 13), (13, 30))).shape, (16,))
        with self.assertRaisesRegex(ValueError, "every class"):
            predict_cv(np.zeros((4, 16)), np.array(["a", "a", "a", "b"]), np.array([1, 1, 2, 2]))

    def events(self):
        rows = []
        sample = 1000
        for block in range(1, 5):
            trial = 0
            for run, conditions in CURRENT_RUNS.items():
                for condition in sorted(conditions):
                    trial += 1
                    duration = 5 if condition in {"mi_hands_bilateral", "mi_feet_bilateral", "word_generation", "mental_subtraction_single"} else 4
                    for label, phase, at in [("cue_onset", "task", sample),
                            ("task_offset", "task", sample+duration*250),
                            ("phase_end", "rest", sample+(duration+7)*250),
                            ("trial_end", "rest", sample+(duration+7)*250)]:
                        rows.append(dict(run=run, condition=condition, block=block, trial=trial, attempt=1,
                                         source="automatic", label=label, phase=phase, samples_received=at,
                                         protocol_version=CURRENT))
                    sample += 4000
        return pd.DataFrame(rows), sample

    def test_current_conditions_use_same_three_seconds_without_synthetic_rest(self):
        events, count = self.events()
        windows, exclusions = trial_windows(events, count, 250, CURRENT)
        self.assertFalse(exclusions)
        self.assertEqual(len(windows), 48)
        self.assertEqual(set(windows.label), set.union(*CURRENT_RUNS.values()))
        self.assertEqual(set(windows.stop_sample-windows.start_sample), {750})
        self.assertEqual(set(windows.protocol_version), {CURRENT})
        evaluations = select_evaluations(windows, CURRENT)
        self.assertEqual({name for name, _ in evaluations}, set(CONTRASTS))
        for name, indices in evaluations:
            sub = windows.iloc[indices].reset_index(drop=True)
            self.assertEqual(set(sub.label), CONTRASTS[name])
            tested = []
            for _, _, train, val, test, _ in splits(sub):
                self.assertFalse(set(sub.iloc[train].trial_key) & set(sub.iloc[test].trial_key))
                self.assertFalse(set(sub.iloc[val].trial_key) & set(sub.iloc[test].trial_key))
                tested.extend(test)
            self.assertEqual(sorted(tested), list(range(len(sub))))

    def test_invalid_incomplete_and_duplicate_attempts_are_excluded(self):
        events, count = self.events()
        key = events.iloc[0]
        invalid = key.copy(); invalid["label"] = "trial_invalidated"; invalid["samples_received"] = count+10
        events = pd.concat([events, invalid.to_frame().T], ignore_index=True)
        second = events.iloc[4]
        mask = (events.run == second.run) & (events.block == second.block) & (events.trial == second.trial)
        events = events[~(mask & (events.label == "trial_end"))]
        windows, exclusions = trial_windows(events, count, 250)
        self.assertEqual(len(windows), 46)
        self.assertEqual({e["reason"] for e in exclusions}, {"invalidated", "incomplete"})

    def test_versions_cannot_mix_or_relabel_legacy_data(self):
        events, count = self.events()
        with self.assertRaisesRegex(ValueError, "conflicting"):
            trial_windows(events, count, 250, LEGACY)
        events.loc[0, "condition"] = "arms"
        with self.assertRaisesRegex(ValueError, "match protocol"):
            trial_windows(events, count, 250)
        with self.assertRaisesRegex(ValueError, "mixed"):
            protocol_for_events(events.drop(columns="protocol_version"))
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            protocol_for_events(events.drop(columns="protocol_version"), "future-version")

    def test_old_files_infer_legacy_and_preserve_task_rest_pair(self):
        events = pd.DataFrame([dict(source="automatic", run="Kognitiv", block=1, trial=1, attempt=1,
                  condition="mental_arithmetic", label=label, phase=phase, samples_received=sample)
                  for label, phase, sample in [("cue_onset", "task", 1000), ("task_offset", "task", 3500),
                          ("phase_end", "rest", 7500), ("trial_end", "rest", 7500)]])
        windows, _ = trial_windows(events, 8000, 250)
        self.assertEqual(windows.label.tolist(), ["mental_arithmetic", "rest"])
        self.assertEqual(select_evaluations(windows, LEGACY)[0][0], "Kognitiv")

    def test_no_mixed_mental_run_or_legacy_contrast_for_current_protocol(self):
        events, count = self.events()
        windows, _ = trial_windows(events, count, 250)
        for name in ["Imagery", "Motorik", "Kognitiv"]:
            with self.assertRaisesRegex(ValueError, "not defined"):
                select_evaluations(windows, CURRENT, [name])
        windows = windows[windows.label != "mi_feet_bilateral"]
        with self.assertRaisesRegex(ValueError, "complete classes"):
            select_evaluations(windows, CURRENT, ["MI_Bilateral"])

    def test_saved_models_are_protocol_and_contrast_specific(self):
        events, count = self.events()
        windows, _ = trial_windows(events, count, 250)
        state = dict(run="MI_Bilateral", classes=sorted(CONTRASTS["MI_Bilateral"]), protocol_version=CURRENT)
        selected = prediction_indices(windows, CURRENT, state)
        self.assertEqual(len(selected), 8)
        with self.assertRaisesRegex(ValueError, "different session protocols"):
            prediction_indices(windows, CURRENT, dict(run="Imagery", classes=["imagine_arms", "imagine_legs"]))
        with self.assertRaisesRegex(ValueError, "classes do not match"):
            prediction_indices(windows, CURRENT, {**state, "classes": ["mi_hand_left", "mi_hand_right"]})


if __name__ == "__main__":
    unittest.main()
