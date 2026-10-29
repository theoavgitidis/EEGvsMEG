"""Regression tests with synthetic EEG only; no headset or downloaded models."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from analysis.movement_classifier import (
    CHANNELS, CONFIG, FS, HISTORY, TASKS, DecisionGate, check_sources, cross_validate,
    fit_model, load_dataset, load_model, main, movement_windows, partitions,
    probabilities, read_signal, replay_rows, save_model, window_features,
)
from analysis.ml_feasibility import exclude_before_marker
from analysis.session_conditions import CURRENT


def synthetic_recording(folder, session="SYNTHETIC-1", blocks=3, five=False):
    path = Path(folder) / f"{session}.csv"
    rng = np.random.default_rng(42 + sum(map(ord, session)))
    labels = TASKS["five" if five else "hands"][1:]
    length = blocks * len(labels) * 3250
    time = np.arange(length) / FS
    eeg = 7 * np.sin(2 * np.pi * 10 * time[:, None] + np.arange(8))
    eeg += rng.normal(0, .3, eeg.shape)
    events, start, trial = [], 0, 0
    for block in range(1, blocks + 1):
        for condition in labels:
            trial += 1
            cue = start + 500
            patterns = [[2, 2, 2, 2, 12, 12, 12, 12], [12, 12, 12, 12, 2, 2, 2, 2],
                        [2, 12, 2, 12, 2, 12, 2, 12], [12, 2, 12, 2, 12, 2, 12, 2]]
            eeg[cue:cue + 1000] *= np.asarray(patterns[labels.index(condition)]) / 7
            for label, phase, offset in [("cue_onset", "task", 500),
                                         ("task_offset", "task", 1500),
                                         ("phase_end", "rest", 3250),
                                         ("trial_end", "rest", 3250)]:
                events.append(dict(source="automatic", run="Motorik", block=block,
                    trial=trial, attempt=1, condition=condition, phase=phase,
                    label=label, samples_received=start + offset, protocol_version=CURRENT))
            start += 3250
    frame = pd.DataFrame(eeg, columns=CHANNELS)
    frame.insert(0, "sample_index", np.arange(length))
    frame["nominal_time_s"] = time
    frame["Counter"] = np.arange(length) + 1
    frame["Validation Indicator"] = 1
    frame.to_csv(path, index=False)
    pd.DataFrame(events).to_csv(str(path) + ".events.csv", index=False)
    Path(str(path) + ".session.json").write_text(json.dumps({
        "participant_id": "SYNTHETIC", "session_id": session, "state": "completed",
        "sampling_rate_hz": FS, "protocol_version": CURRENT,
        "movement_version": "synthetic-fist-v1", "device": {"channels": [
            {"name": c, "enabled": True, "unit": "uV"} for c in CHANNELS]}}))
    return path


class MovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = synthetic_recording(cls.temp.name)
        cls.events = pd.read_csv(str(cls.path) + ".events.csv").fillna("")
        cls.rows, cls.x, cls.sources = load_dataset([cls.path])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_rest_pairs_and_causal_history_bounds(self):
        rows, exclusions = movement_windows(self.events, 19500)
        self.assertFalse(exclusions)
        self.assertEqual(rows.label.value_counts().to_dict(),
                         {"rest": 6, "me_hand_left": 3, "me_hand_right": 3})
        for _, pair in rows.groupby("trial_key"):
            self.assertEqual(len(pair), 2)
            self.assertIn("rest", set(pair.label))
            self.assertTrue(((pair.stop_sample - pair.input_start_sample) == HISTORY).all())
        first = rows.iloc[0]
        self.assertEqual((first.input_start_sample, first.start_sample, first.stop_sample), (500, 625, 1375))
        rest = rows.iloc[1]
        self.assertEqual((rest.input_start_sample, rest.stop_sample), (2250, 3125))

    def test_invalidated_and_incomplete_attempts_never_become_rest(self):
        events = self.events.copy()
        invalid = events.iloc[0].copy()
        invalid["label"] = "trial_invalidated"
        events = pd.concat([events, invalid.to_frame().T], ignore_index=True)
        events = events[~((events.trial == 2) & (events.label == "trial_end"))]
        rows, exclusions = movement_windows(events, 19500)
        self.assertFalse(rows.trial.isin([1, 2]).any())
        self.assertEqual({e["reason"] for e in exclusions}, {"invalidated", "incomplete"})

    def test_fractional_markers_and_short_recovery_rejected(self):
        events = self.events.copy()
        events["samples_received"] = events.samples_received.astype(float)
        events.loc[0, "samples_received"] += .5
        with self.assertRaisesRegex(ValueError, "finite integers"):
            movement_windows(events, 19500)
        events = self.events.copy()
        events.loc[(events.trial == 1) & (events.phase == "rest"), "samples_received"] = 2000
        rows, exclusions = movement_windows(events, 19500)
        self.assertFalse((rows.trial == 1).any())
        self.assertIn("recovery_too_short_for_pair", [e["reason"] for e in exclusions])

    def test_quality_marker_excludes_complete_task_rest_pair(self):
        events = pd.concat([self.events, pd.DataFrame([{
            "source": "manual", "label": "ground placed", "samples_received": 501}])], ignore_index=True)
        kept, excluded, _ = exclude_before_marker(self.rows, events, FS, 19500, "ground placed")
        self.assertFalse((kept.trial == 1).any())
        self.assertEqual(len(excluded), 1)

    def test_invalid_warmup_or_rest_rejects_entire_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_recording(folder)
            frame = pd.read_csv(path)
            frame.loc[510, "Validation Indicator"] = 0  # Warmup only, outside feature interval.
            frame.loc[6000:, "Counter"] += 1  # Gap in trial 2's late recovery.
            frame.to_csv(path, index=False)
            rows, _, sources = load_dataset([path])
            self.assertFalse(rows.trial.isin([1, 2]).any())
            self.assertEqual(len(sources[0]["exclusions"]), 2)

    def test_units_sampling_and_nominal_time_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_recording(folder)
            meta_path = Path(str(path) + ".session.json")
            original = json.loads(meta_path.read_text())
            for key, value in [("sampling_rate_hz", 200), ("protocol_version", "eeg-session-1.0")]:
                meta_path.write_text(json.dumps({**original, key: value}))
                with self.assertRaises(ValueError):
                    read_signal(path)
            original["device"]["channels"][0]["unit"] = "V"
            meta_path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "microvolts"):
                read_signal(path)
            original["device"]["channels"][0]["unit"] = "uV"
            meta_path.write_text(json.dumps(original))
            frame = pd.read_csv(path)
            frame.loc[100, "nominal_time_s"] += .01
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Nominal time"):
                read_signal(path)

    def test_partition_completeness_pairs_and_test_once(self):
        seen = np.zeros(len(self.rows), dtype=int)
        for _, train, test in partitions(self.rows, TASKS["hands"]):
            self.assertFalse(set(self.rows.loc[train, "trial_key"]) & set(self.rows.loc[test, "trial_key"]))
            seen[test] += 1
        np.testing.assert_array_equal(seen, 1)
        with self.assertRaisesRegex(ValueError, "At least two"):
            list(partitions(self.rows[self.rows.block == 1], TASKS["hands"]))
        with self.assertRaisesRegex(ValueError, "Every training/test"):
            list(partitions(self.rows[~((self.rows.block == 1) & (self.rows.label == "me_hand_left"))], TASKS["hands"]))

    def test_whole_sessions_and_duplicate_identity_rejection(self):
        other = self.rows.copy()
        other["session_key"] = "OTHER"
        other["trial_key"] = "OTHER/" + other.trial_key
        rows = pd.concat([self.rows, other], ignore_index=True)
        for _, train, test in partitions(rows, TASKS["hands"]):
            self.assertEqual(rows.loc[test, "session_key"].nunique(), 1)
            self.assertFalse(set(rows.loc[train, "session_key"]) & set(rows.loc[test, "session_key"]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_dataset([self.path, self.path])

    def test_export_matches_sklearn_and_contains_no_pickle(self):
        model = fit_model(self.x, self.rows.label.to_numpy(), "hands")
        scaler = StandardScaler().fit(self.x)
        classifier = LogisticRegression(C=1, class_weight="balanced", max_iter=2000, random_state=0)
        classifier.fit(scaler.transform(self.x), self.rows.label)
        np.testing.assert_allclose(probabilities(model, self.x), classifier.predict_proba(scaler.transform(self.x)))
        manifest = {"schema_version": 1, "config": CONFIG, "task": "hands", "training_sources": self.sources}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "movement-model.npz"
            save_model(path, model, manifest)
            restored, meta = load_model(path)
            self.assertEqual(meta, manifest)
            np.testing.assert_array_equal(probabilities(model, self.x), probabilities(restored, self.x))
            with self.assertRaises(FileExistsError):
                save_model(path, model, manifest)

    def test_corrupt_model_config_or_parameters_are_rejected(self):
        model = fit_model(self.x, self.rows.label.to_numpy(), "hands")
        with tempfile.TemporaryDirectory() as folder:
            for name, parameters, config in [
                ("scale", {**model, "scale": np.zeros(16)}, CONFIG),
                ("filter", model, {**CONFIG, "history_samples": 10}),
                ("weights", {**model, "weights": np.zeros((1, 16))}, CONFIG),
            ]:
                path = Path(folder) / name
                save_model(path, parameters, {"schema_version": 1, "task": "hands", "config": config})
                with self.assertRaises(ValueError):
                    load_model(path)

    def test_held_out_features_do_not_affect_training_scaling_or_weights(self):
        _, train, test = next(partitions(self.rows, TASKS["hands"]))
        first = fit_model(self.x[train], self.rows.label.to_numpy()[train], "hands")
        changed = self.x.copy()
        changed[test] += 10000
        second = fit_model(changed[train], self.rows.label.to_numpy()[train], "hands")
        for key in first:
            np.testing.assert_array_equal(first[key], second[key])
        np.testing.assert_allclose(first["mean"], self.x[train].mean(axis=0))

    def test_synthetic_decoding_and_five_class_support(self):
        result, predictions = cross_validate(self.rows, self.x, "hands")
        self.assertGreater(result["balanced_accuracy"], .95)
        self.assertEqual(len(predictions), len(self.rows))
        self.assertEqual(sum(map(sum, result["confusion_true_rows"])), len(self.rows))
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_recording(folder, five=True)
            rows, x, _ = load_dataset([path], task="five")
            result, _ = cross_validate(rows, x, "five")
            self.assertGreater(result["balanced_accuracy"], .95)

    def test_new_session_evaluation_rejects_seen_or_incompatible_data(self):
        manifest = {"training_sources": self.sources}
        with self.assertRaisesRegex(ValueError, "new session"):
            check_sources(manifest, self.sources, independent=True)
        other = {**self.sources[0], "session_id": "OTHER", "data_sha256": "new"}
        check_sources(manifest, [other], independent=True)
        for key, value in [("participant_id", "OTHER"), ("signal", "oscar"), ("movement_version", "other")]:
            with self.assertRaisesRegex(ValueError, "same participant"):
                check_sources(manifest, [{**other, key: value}])

    def test_replay_uses_only_past_and_abstains_for_full_invalid_history(self):
        model = fit_model(self.x, self.rows.label.to_numpy(), "hands")
        _, eeg, valid, _ = read_signal(self.path)
        eeg, valid = eeg[:1400].copy(), valid[:1400].copy()
        baseline = list(replay_rows(eeg, valid, model))
        changed = eeg.copy()
        changed[1100:] = 1e6
        prefix = list(replay_rows(changed, valid, model))
        self.assertEqual([r for r in baseline if r["stop_sample_exclusive"] <= 1100],
                         [r for r in prefix if r["stop_sample_exclusive"] <= 1100])
        valid[900] = False
        bad = list(replay_rows(eeg, valid, model))
        self.assertEqual(bad[0]["prediction"], baseline[0]["prediction"])
        self.assertTrue(all(r["prediction"] == "unknown" and not r["event"]
                            for r in bad if r["input_start_sample"] <= 900 < r["stop_sample_exclusive"]))

    def test_command_line_train_evaluate_replay_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            output = Path(folder) / "trained"
            main(["train", str(self.path), "--output-dir", str(output)])
            model_path = output / "movement-model.npz"
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["evaluation"]["split"], "leave-one-block-out")
            with self.assertRaises(SystemExit):
                main(["train", str(self.path), "--output-dir", str(output)])
            other = synthetic_recording(folder, session="SYNTHETIC-2")
            evaluated = Path(folder) / "evaluated"
            main(["evaluate", str(model_path), str(other), "--output-dir", str(evaluated)])
            self.assertEqual(json.loads((evaluated / "report.json").read_text())["evaluation"]["split"],
                             "independent-session; no fitting")
            with self.assertRaisesRegex(ValueError, "new session"):
                main(["evaluate", str(model_path), str(self.path), "--output-dir", str(Path(folder) / "invalid")])
            replay = Path(folder) / "replay.csv"
            main(["replay", str(model_path), str(other), "--output", str(replay), "--step-samples", "1000"])
            self.assertTrue(replay.is_file())
            self.assertTrue(pd.read_csv(replay).seen_in_training.eq(False).all())
            self.assertEqual(self.sources[0]["data_sha256"], read_signal(self.path)[3]["data_sha256"])


class GateTests(unittest.TestCase):
    def test_requires_rest_then_confirms_only_one_event_until_new_rest(self):
        gate = DecisionGate(confirmations=2)
        self.assertEqual([gate.update("me_hand_left", .95)[1] for _ in range(4)], [""] * 4)
        for _ in range(2):
            gate.update("rest", .95)
        self.assertEqual([gate.update("me_hand_left", .95)[1] for _ in range(4)],
                         ["", "me_hand_left", "", ""])
        self.assertEqual(gate.update("me_hand_right", .95)[1], "")
        self.assertEqual(gate.update("me_hand_right", .95)[1], "")
        for _ in range(2):
            gate.update("rest", .95)
        self.assertEqual(gate.update("me_hand_right", .95)[1], "")
        self.assertEqual(gate.update("me_hand_right", .95)[1], "me_hand_right")

    def test_low_score_invalidity_and_alternation_do_not_emit_events(self):
        gate = DecisionGate(confirmations=2)
        for _ in range(2):
            gate.update("rest", .95)
        gate.update("unknown", float("nan"))
        self.assertFalse(gate.armed)
        for label in ["me_hand_left", "me_hand_right"] * 4:
            self.assertEqual(gate.update(label, .95), ("unknown", ""))
        self.assertEqual(gate.update("rest", .1), ("unknown", ""))
        for threshold in [-1, 0, 2, float("nan")]:
            with self.assertRaises(ValueError):
                DecisionGate(threshold)
        with self.assertRaises(ValueError):
            DecisionGate(confirmations=0)


if __name__ == "__main__":
    unittest.main()
