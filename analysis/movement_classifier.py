"""Executed-movement baseline: local sessions, prepared public data and causal replay.

Run with ``python -m analysis.movement_classifier --help``. No hardware control.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler

from analysis.ml_data import CHANNELS, sha256, trial_windows
from analysis.ml_feasibility import exclude_before_marker
from analysis.recording_files import resolve_recording
from analysis.session_conditions import CURRENT
from analysis.movement_features import CONFIG, FS, HISTORY, WARMUP, WINDOW, window_features

TASKS = {
    "hands": ["rest", "me_hand_left", "me_hand_right"],
    "five": ["rest", "me_hand_left", "me_hand_right", "me_foot_left", "me_foot_right"],
    "hand-side": ["me_hand_left", "me_hand_right"],
}


def read_signal(path, signal="raw"):
    """Validate physical units, timing and selection before interpreting sample markers."""
    selected = resolve_recording(path, signal)
    meta = json.loads(selected.session.read_text(encoding="utf-8"))
    if meta.get("sampling_rate_hz") != FS:
        raise ValueError("Movement decoding requires confirmed 250 Hz sampling.")
    if meta.get("protocol_version") != CURRENT:
        raise ValueError(f"Movement decoding requires {CURRENT}; legacy labels are not remapped.")
    if not all(isinstance(meta.get(key), str) and meta[key].strip()
               for key in ["participant_id", "session_id"]):
        raise ValueError("Participant and session IDs must be recorded explicitly.")
    channels = {c["name"]: c for c in meta["device"]["channels"]}
    if any(c not in channels or channels[c].get("enabled") is not True
           or channels[c].get("unit") not in ("uV", "µV", "μV") for c in CHANNELS):
        raise ValueError("All eight EEG channels must be enabled and confirmed in microvolts.")
    frame = pd.read_csv(selected.data)
    selected.validate_length(len(frame))
    if not len(frame) or not np.array_equal(frame.sample_index.to_numpy(), np.arange(len(frame))):
        raise ValueError("Non-contiguous sample indices or empty recording.")
    if "nominal_time_s" not in frame or not np.allclose(
            frame.nominal_time_s, np.arange(len(frame)) / FS, rtol=0, atol=1e-6):
        raise ValueError("Nominal time must match sample_index / 250 Hz.")
    # A contiguous file index does not imply contiguous device samples.
    counters = frame["Counter"].to_numpy(dtype=float)
    valid = frame["Validation Indicator"].eq(1).to_numpy(copy=True)
    valid &= np.isfinite(counters) & (counters == np.floor(counters))
    valid[1:] &= np.diff(counters) == 1
    eeg = frame[CHANNELS].to_numpy(dtype=float)
    valid &= np.isfinite(eeg).all(axis=1)
    provenance = {
        "participant_id": meta["participant_id"], "session_id": meta["session_id"],
        "session_state": meta.get("state", "unknown"), "protocol_version": CURRENT,
        "movement_version": meta.get("movement_version"), "session_seed": meta.get("seed"),
        "signal": selected.signal, "processing": selected.metadata,
        "inputs_sha256": {str(p.resolve()): sha256(p) for p in
            [selected.data, selected.events, selected.session,
             Path(str(selected.raw) + ".plan.csv"), selected.processing] if p.is_file()},
        "data_sha256": sha256(selected.data),
        "montage_status": "recorded channel order; physical placement not independently verified",
    }
    return selected, eeg, valid, provenance


def movement_windows(events, samples, task="hands"):
    """Pair each motor task with late recovery, preserving attempts and invalidations."""
    if task not in TASKS:
        raise ValueError("Unknown movement task.")
    # The shared parser converts markers to int; reject fractional/missing markers first.
    positions = pd.to_numeric(events.samples_received, errors="coerce").to_numpy()
    if not np.isfinite(positions).all() or np.any(positions != np.floor(positions)):
        raise ValueError("Event sample positions must be finite integers.")
    tasks, exclusions = trial_windows(events, samples, FS, CURRENT)
    tasks = tasks[(tasks.run == "Motorik") & tasks.label.isin(
        [label for label in TASKS[task] if label != "rest"])]
    rows = []
    for row in tasks.to_dict("records"):
        if "rest" not in TASKS[task]:
            rows.append({**row, "input_start_sample": row["start_sample"] - WARMUP,
                         "label_source": "instructed_execution; actual onset unmeasured"})
            continue
        group = events[(events.source == "automatic") & (events.run == row["run"])
                       & (events.block == row["block"]) & (events.trial == row["trial"])
                       & (events.attempt == row["attempt"])]
        end = int(group[(group.label == "phase_end") & (group.phase == "rest")].iloc[0].samples_received)
        off = int(group[group.label == "task_offset"].iloc[0].samples_received)
        rest_start, rest_stop = end - WINDOW - WARMUP, end - WARMUP
        if rest_start - WARMUP < off or end > samples:
            exclusions.append({"key": row["trial_key"], "reason": "recovery_too_short_for_pair"})
            continue
        rows.append({**row, "input_start_sample": row["start_sample"] - WARMUP,
                     "label_source": "instructed_execution; actual onset unmeasured"})
        rows.append({**row, "label": "rest", "start_sample": rest_start, "stop_sample": rest_stop,
                     "input_start_sample": rest_start - WARMUP,
                     "label_source": "derived_late_recovery; not an independent rest trial"})
    if not rows:
        raise ValueError("No complete executed-movement/recovery pairs for this task.")
    return pd.DataFrame(rows), exclusions


def load_dataset(paths, task="hands", signal="raw", marker=None, settle_seconds=0):
    rows, matrices, sources = [], [], []
    identities, hashes = set(), set()
    for path in paths:
        selected, eeg, valid, source = read_signal(path, signal)
        identity = (source["participant_id"], source["session_id"])
        if identity in identities or source["data_sha256"] in hashes:
            raise ValueError("Duplicate recording/session; copies must not become independent folds.")
        identities.add(identity)
        hashes.add(source["data_sha256"])
        events = pd.read_csv(selected.events).fillna("")
        windows, exclusions = movement_windows(events, len(eeg), task)
        windows, removed, quality_rule = exclude_before_marker(
            windows, events, FS, len(eeg), marker, settle_seconds)
        exclusions.extend(removed)
        bad = set()
        for row in windows.to_dict("records"):
            if not valid[row["input_start_sample"]:row["stop_sample"]].all():
                bad.add(row["trial_key"])
        exclusions.extend({"key": key, "reason": "invalid_samples_in_task_or_recovery_history"}
                          for key in sorted(bad))
        windows = windows[~windows.trial_key.isin(bad)].copy()
        if windows.empty:
            raise ValueError(f"No valid movement pairs after exclusions in {source['session_id']}.")
        session_key = json.dumps(identity, separators=(",", ":"))
        windows["session_key"] = session_key
        windows["trial_key"] = session_key + "/" + windows.trial_key
        windows["participant_id"] = source["participant_id"]
        windows["session_id"] = source["session_id"]
        matrices.extend(window_features(eeg[r["input_start_sample"]:r["stop_sample"]])
                        for r in windows.to_dict("records"))
        rows.append(windows)
        sources.append({**source, "quality_rule": quality_rule, "exclusions": exclusions})
    if len({s["participant_id"] for s in sources}) != 1:
        raise ValueError("This baseline is person-specific; do not pool participants.")
    if len({s["movement_version"] for s in sources}) != 1:
        raise ValueError("Do not pool different movement definitions.")
    return pd.concat(rows, ignore_index=True), np.asarray(matrices), sources


def partitions(rows, classes):
    """Whole people, otherwise sessions/blocks. All windows of a trial stay together."""
    if set(rows.label) != set(classes):
        raise ValueError(f"All required classes must remain after exclusions: {classes}")
    groups = (rows.participant_id if rows.participant_id.nunique() > 1 else
              rows.session_key if rows.session_key.nunique() > 1
              else rows.block.map(lambda b: f"block/{int(b)}")).to_numpy()
    if len(np.unique(groups)) < 2:
        raise ValueError("At least two independent complete blocks/sessions are required.")
    for group in sorted(np.unique(groups)):
        test = groups == group
        train = ~test
        if any(set(rows.loc[ix, "label"]) != set(classes) for ix in [train, test]):
            raise ValueError(f"Every training/test partition must contain every class; incomplete {group}.")
        if set(rows.loc[train, "trial_key"]) & set(rows.loc[test, "trial_key"]):
            raise ValueError("Task/recovery trial leakage.")
        yield str(group), train, test


def fit_model(x, y, task):
    if set(y) != set(TASKS[task]):
        raise ValueError("Training requires every configured class.")
    scaler = StandardScaler().fit(x)
    classifier = LogisticRegression(C=1, class_weight="balanced", max_iter=2000, random_state=0)
    classifier.fit(scaler.transform(x), y)
    if np.any(classifier.n_iter_ >= 2000):
        raise ValueError("Classifier failed to converge; no model exported.")
    return {"mean": scaler.mean_, "scale": scaler.scale_, "weights": classifier.coef_,
            "intercept": classifier.intercept_, "classes": np.asarray(classifier.classes_, dtype=str)}


def probabilities(model, x):
    """Uncalibrated model probabilities, not verified confidence or safety estimates."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[1] != 16 or not np.isfinite(x).all():
        raise ValueError("Expected finite 16-feature rows.")
    logits = ((x - model["mean"]) / model["scale"]) @ model["weights"].T + model["intercept"]
    if len(model["classes"]) == 2:
        logits = np.column_stack([np.zeros(len(x)), logits[:, 0]])
    return softmax(logits, axis=1)


def metrics(y, predicted, classes):
    precision, recall, f1, support = precision_recall_fscore_support(
        y, predicted, labels=classes, zero_division=0)
    return {"n_windows": len(y), "n_trials": len(y) // (2 if "rest" in classes else 1),
            "accuracy": float(accuracy_score(y, predicted)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
            "macro_f1": float(f1.mean()), "class_order": list(classes),
            "confusion_true_rows": confusion_matrix(y, predicted, labels=classes).tolist(),
            "per_class": {c: {"precision": float(precision[i]), "recall": float(recall[i]),
                "f1": float(f1[i]), "support": int(support[i])} for i, c in enumerate(classes)}}


def cross_validate(rows, x, task):
    y = rows.label.to_numpy()
    predicted = np.empty(len(rows), dtype=object)
    scores = np.empty(len(rows))
    folds, fold_names = [], np.empty(len(rows), dtype=object)
    for name, train, test in partitions(rows, TASKS[task]):
        model = fit_model(x[train], y[train], task)
        proba = probabilities(model, x[test])
        predicted[test] = model["classes"][proba.argmax(axis=1)]
        scores[test], fold_names[test] = proba.max(axis=1), name
        folds.append({"held_out": name, "train_windows": int(train.sum()),
                      **metrics(y[test], predicted[test], TASKS[task])})
    predictions = rows.copy()
    predictions["prediction"] = predicted
    predictions["uncalibrated_score"] = scores
    predictions["held_out"] = fold_names
    split = ("leave-one-participant-out" if rows.participant_id.nunique() > 1 else
             "leave-one-session-out" if rows.session_key.nunique() > 1 else "leave-one-block-out")
    return {"split": split,
            "folds": folds, **metrics(y, predicted, TASKS[task])}, predictions


def save_model(path, model, manifest):
    # Numeric arrays + JSON, never pickle or executable sklearn objects.
    with Path(path).open("xb") as handle:
        np.savez_compressed(handle, **model, manifest=np.array(json.dumps(manifest)))


def load_model(path):
    with np.load(path, allow_pickle=False) as archive:
        manifest = json.loads(str(archive["manifest"].item()))
        model = {key: archive[key].copy() for key in ["mean", "scale", "weights", "intercept", "classes"]}
    if (manifest.get("schema_version") != 1 or manifest.get("config") != CONFIG
            or manifest.get("task") not in TASKS):
        raise ValueError("Unsupported model or preprocessing configuration.")
    classes = model["classes"].tolist()
    if classes != sorted(TASKS[manifest["task"]]):
        raise ValueError("Model classes do not match task.")
    outputs = 1 if len(classes) == 2 else len(classes)
    for key, shape in [("mean", (16,)), ("scale", (16,)),
                       ("weights", (outputs, 16)), ("intercept", (outputs,))]:
        if model[key].shape != shape or not np.isfinite(model[key]).all():
            raise ValueError("Invalid model parameters.")
    if np.any(model["scale"] <= 0):
        raise ValueError("Invalid model scaling.")
    return model, manifest


def check_sources(manifest, sources, independent=False):
    if manifest.get("input_domain") == "physionet-executed-fists":
        raise ValueError("Public-data models are not validated for local Unicorn evaluation or replay.")
    training = manifest["training_sources"]
    for source in sources:
        if (source["participant_id"] != training[0]["participant_id"]
                or source["signal"] != training[0]["signal"]
                or source["movement_version"] != training[0]["movement_version"]):
            raise ValueError("Model requires the same participant, signal variant and movement definition.")
        if independent and any(
                source["session_id"] == old["session_id"] or source["data_sha256"] == old["data_sha256"]
                for old in training):
            raise ValueError("Evaluation requires a new session not used for training.")


class DecisionGate:
    """Diagnostic gesture events: confirm rest to arm; one event until rest returns."""
    def __init__(self, threshold=.8, confirmations=3):
        if not np.isfinite(threshold) or not 0 < threshold <= 1:
            raise ValueError("Threshold must be in (0, 1].")
        if isinstance(confirmations, bool) or not isinstance(confirmations, int) or confirmations < 1:
            raise ValueError("Confirmations must be a positive integer.")
        self.threshold, self.confirmations = threshold, confirmations
        self.reset()

    def reset(self):
        self.candidate, self.count, self.armed = "unknown", 0, False

    def update(self, label, score):
        if label == "unknown" or not np.isfinite(score) or score < self.threshold:
            self.reset()
            return "unknown", ""
        self.count = self.count + 1 if label == self.candidate else 1
        self.candidate = label
        if self.count < self.confirmations:
            return "unknown", ""
        if label == "rest":
            self.armed = True
        elif self.armed:
            self.armed = False
            return label, label
        return label, ""


def replay_rows(eeg, valid, model, step_samples=50, threshold=.8, confirmations=3):
    """Feed past windows only. Invalid samples require a complete fresh clean history."""
    if not isinstance(step_samples, int) or step_samples < 1:
        raise ValueError("Replay step must be a positive integer number of samples.")
    gate = DecisionGate(threshold, confirmations)
    for stop in range(HISTORY, len(eeg) + 1, step_samples):
        start = stop - HISTORY
        if not valid[start:stop].all():
            prediction, score = "unknown", float("nan")
        else:
            proba = probabilities(model, window_features(eeg[start:stop])[None, :])[0]
            prediction, score = str(model["classes"][proba.argmax()]), float(proba.max())
        state, event = gate.update(prediction, score)
        yield {"input_start_sample": start, "stop_sample_exclusive": stop,
               "data_available_time_s": stop / FS, "prediction": prediction,
               "uncalibrated_score": score, "confirmed_state": state, "event": event}


def base_report(sources):
    return {"schema_version": 1, "config": CONFIG, "sources": sources,
            "software_versions": {p: importlib.metadata.version(p)
                                  for p in ["numpy", "scipy", "pandas", "scikit-learn"]},
            "limitations": [
                "Exploratory person-specific executed-movement decoding, not validated neural origin.",
                "Rest labels are derived late recovery, not independent rest/no-command recordings.",
                "Instruction markers do not measure actual movement onset.",
                "Window metrics do not measure false events/minute or event detection latency.",
                "Model probabilities are uncalibrated; replay thresholds are unvalidated defaults.",
                "Causal window processing is available; hardware latency and motor control are not validated.",
            ]}


def write_results(folder, report, predictions):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    predictions.to_csv(folder / "predictions.csv", index=False)
    result = report["evaluation"]
    public = report.get("input_domain") == "physionet-executed-fists"
    lines = ["# Explorative Bewegungsklassifikation", "",
             f"Aufgabe: `{report['task']}`. Aufteilung: `{result['split']}`.", "",
             f"{result['n_trials']} Trials, {result['n_windows']} Auswertungsfenster. "
             f"Balanced Accuracy: {result['balanced_accuracy']:.1%}; "
             f"Accuracy: {result['accuracy']:.1%}; Macro-F1: {result['macro_f1']:.3f}.", "",
             "## Klassen", "", "| Klasse | Fenster | Precision | Recall | F1 |",
             "|---|---:|---:|---:|---:|"]
    for label, row in result["per_class"].items():
        lines.append(f"| {label} | {row['support']} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |")
    classes = result["class_order"]
    lines.extend(["", "## Konfusionsmatrix", "", "Zeilen: tatsächliches Label; Spalten: Vorhersage.", "",
                  "| Label | " + " | ".join(classes) + " |", "|---|" + "---:|" * len(classes)])
    for label, counts in zip(classes, result["confusion_true_rows"]):
        lines.append("| " + label + " | " + " | ".join(map(str, counts)) + " |")
    if "folds" in result:
        lines.extend(["", "## Zurückgehaltene Gruppen", "", "| Gruppe | Testfenster | Balanced Accuracy |",
                      "|---|---:|---:|"])
        for fold in result["folds"]:
            lines.append(f"| {fold['held_out']} | {fold['n_windows']} | {fold['balanced_accuracy']:.1%} |")
    scope = ("Öffentlicher PhysioNet-Offline-Benchmark mit vollständig zurückgehaltenen Personen; "
             "keine Validierung auf lokalen Unicorn-Aufnahmen. " if public else
             "Personenspezifischer Offline-Pilot; neuronale Herkunft und Echtzeitsteuerung sind nicht validiert. ")
    rest = ("Ruhe stammt aus später Erholung und wurde nicht als unabhängiger Ruhe-Trial erhoben. "
            if "rest" in TASKS[report["task"]] else
            "Zweiklassenvergleich links/rechts; keine Ruhe-, Unknown- oder Gestenerkennung. ")
    lines.extend(["", "## Grenzen", "", scope + rest +
                  "Marker beschreiben die Anweisung, nicht den gemessenen Bewegungsbeginn. "
                  "Fenstermetriken messen weder Fehlereignisse pro Minute noch die Erkennungslatenz. "
                  "Modellscores sind unkalibriert. Ausschlüsse, Eingabe-Hashes, Softwareversionen und "
                  "Verarbeitung stehen in report.json; alle Testvorhersagen in predictions.csv."])
    if "exported_model" in report:
        lines.extend(["", "Das exportierte Modell wurde nach der Kreuzvalidierung auf allen Eingabefenstern "
                      "neu trainiert. Die obigen Testwerte stammen aus den getrennten Folds."])
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def train_physionet(folder, output):
    """Train the existing binary baseline with whole-person folds on prepared public data."""
    from analysis.physionet_dataset import load_prepared

    rows, x, preparation = load_prepared(folder)
    if rows.participant_id.nunique() < 2:
        raise ValueError("Public-data evaluation requires at least two complete participants.")
    sources = [source for source in preparation["sources"] if source["imported_trials"]]
    report = {**base_report(sources), "task": "hand-side", "input_domain": preparation["input_domain"],
              "preparation": preparation, "preparation_manifest_sha256": sha256(Path(folder) / "manifest.json"),
              "limitations": preparation["limitations"] + [
                  "Public-data cross-person evaluation is not a local Unicorn transfer or streaming validation.",
                  "Model probabilities are uncalibrated; no event gating is defined without a rest class."]}
    result, predictions = cross_validate(rows, x, "hand-side")
    model = fit_model(x, rows.label.to_numpy(), "hand-side")
    manifest = {"schema_version": 1, "config": CONFIG, "task": "hand-side",
                "input_domain": preparation["input_domain"], "external_import_config": preparation["import_config"],
                "preparation_manifest_sha256": report["preparation_manifest_sha256"],
                "training_sources": sources, "software_versions": report["software_versions"]}
    report.update({"evaluation": result,
                   "exported_model": "movement-model.npz; refitted on all public task windows after held-out evaluation"})
    write_results(output, report, predictions)
    save_model(Path(output) / "movement-model.npz", model, manifest)
    print(f"{result['split']}: balanced accuracy={result['balanced_accuracy']:.3f}; {output}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["train", "evaluate"]:
        command = commands.add_parser(name)
        if name == "evaluate":
            command.add_argument("model", type=Path)
        command.add_argument("recordings", type=Path, nargs="+")
        command.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrite.")
        command.add_argument("--signal", choices=["raw", "oscar"], default="raw")
        command.add_argument("--after-marker", help="Unique manual quality marker; applied to each input session.")
        command.add_argument("--settle-seconds", type=float, default=0)
        if name == "train":
            command.add_argument("--task", choices=TASKS, default="hands")
    public = commands.add_parser("train-physionet", help="Prepared left/right fist data; hold out whole people.")
    public.add_argument("dataset", type=Path)
    public.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrite.")
    replay = commands.add_parser("replay", help="Diagnostic causal CSV replay; no hardware commands or performance claim.")
    replay.add_argument("model", type=Path)
    replay.add_argument("recording", type=Path)
    replay.add_argument("--output", type=Path, required=True, help="New prediction CSV.")
    replay.add_argument("--step-samples", type=int, default=50)
    replay.add_argument("--threshold", type=float, default=.8)
    replay.add_argument("--confirmations", type=int, default=3)
    args = parser.parse_args(argv)
    destination = args.output if args.command == "replay" else args.output_dir
    if destination.exists():
        parser.error("Output exists; choose a new path. Inputs and prior results are never overwritten.")
    if args.command == "train-physionet":
        train_physionet(args.dataset, args.output_dir)
        return
    if args.command == "replay":
        model, manifest = load_model(args.model)
        if "rest" not in TASKS[manifest["task"]]:
            raise ValueError("Gesture replay requires a trained rest class; hand-side is an offline contrast.")
        _, eeg, valid, source = read_signal(args.recording, manifest["training_sources"][0]["signal"])
        check_sources(manifest, [source])
        # Respect a training session's known quality cutoff during diagnostic replay.
        for old in manifest["training_sources"]:
            if source["session_id"] == old["session_id"] or source["data_sha256"] == old["data_sha256"]:
                if old.get("quality_rule"):
                    valid[:old["quality_rule"]["cutoff_sample"]] = False
        predictions = pd.DataFrame(replay_rows(eeg, valid, model, args.step_samples,
                                                args.threshold, args.confirmations))
        if predictions.empty:
            raise ValueError("Recording is shorter than required model history.")
        predictions["session_id"] = source["session_id"]
        predictions["model_sha256"] = sha256(args.model)
        predictions["recording_sha256"] = source["data_sha256"]
        predictions["threshold"] = args.threshold
        predictions["confirmations"] = args.confirmations
        predictions["seen_in_training"] = any(
            source["data_sha256"] == old["data_sha256"] or source["session_id"] == old["session_id"]
            for old in manifest["training_sources"])
        with args.output.open("x", encoding="utf-8", newline="") as handle:
            predictions.to_csv(handle, index=False)
        print(f"Diagnostic replay: {len(predictions)} windows; no event accuracy or hardware validation. {args.output}")
        return
    if args.command == "evaluate":
        model, manifest = load_model(args.model)
        task = manifest["task"]
    else:
        task = args.task
    rows, x, sources = load_dataset(args.recordings, task, args.signal,
                                   args.after_marker, args.settle_seconds)
    report = {**base_report(sources), "task": task}
    if "rest" not in TASKS[task]:
        report["limitations"][1] = "Two-class hand-side contrast; no rest, unknown or event detection."
    if args.command == "train":
        result, predictions = cross_validate(rows, x, task)
        model = fit_model(x, rows.label.to_numpy(), task)
        manifest = {"schema_version": 1, "config": CONFIG, "task": task,
                    "training_sources": sources, "software_versions": report["software_versions"]}
        report.update({"evaluation": result,
                       "exported_model": "movement-model.npz; refitted on all input windows after held-out evaluation"})
    else:
        check_sources(manifest, sources, independent=True)
        if set(rows.label) != set(TASKS[task]):
            raise ValueError("Evaluation requires every model class after exclusions.")
        proba = probabilities(model, x)
        predictions = rows.copy()
        predictions["prediction"] = model["classes"][proba.argmax(axis=1)]
        predictions["uncalibrated_score"] = proba.max(axis=1)
        report.update({"model_sha256": sha256(args.model), "evaluation": {
            "split": "independent-session; no fitting", **metrics(rows.label, predictions.prediction, TASKS[task])}})
    write_results(args.output_dir, report, predictions)
    if args.command == "train":
        save_model(args.output_dir / "movement-model.npz", model, manifest)
    print(f"{report['evaluation']['split']}: balanced accuracy={report['evaluation']['balanced_accuracy']:.3f}; {args.output_dir}")


if __name__ == "__main__":
    main()
