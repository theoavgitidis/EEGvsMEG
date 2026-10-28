"""Exploratory block-held-out task decoding; numpy/scipy/pandas only.

Usage: python analysis/ml_feasibility.py RECORDING.csv --output RESULT.json
No model selection: fixed standardized ridge classifier, penalty 10.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt, welch


def features(epoch, fs, bands=((1, 4), (4, 8), (8, 13), (13, 30), (30, 40))):
    # Filter each epoch independently: no filtering across held-out boundaries.
    filtered = sosfiltfilt(butter(4, [1, 40], fs=fs, btype="bandpass", output="sos"), epoch, axis=0)
    freq, psd = welch(filtered, fs=fs, nperseg=min(500, len(epoch)), axis=0)
    return np.concatenate([
        np.log(np.maximum(np.trapezoid(psd[(freq >= lo) & (freq <= hi)],
                                      freq[(freq >= lo) & (freq <= hi)], axis=0), 1e-20))
        for lo, hi in bands
    ])


def predict_cv(x, y, groups):
    classes = np.unique(y)
    if len(classes) < 2 or len(np.unique(groups)) < 2:
        raise ValueError("At least two classes and two independent blocks are required.")
    pred = np.empty(len(y), dtype=y.dtype)
    folds = []
    for group in np.unique(groups):
        test = groups == group
        train = ~test
        if set(y[train]) != set(classes) or set(y[test]) != set(classes):
            raise ValueError("Each held-out block and training partition must contain every class.")
        mu, sd = x[train].mean(0), x[train].std(0)
        sd[sd < 1e-12] = 1
        a = np.column_stack([np.ones(train.sum()), (x[train] - mu) / sd])
        b = np.column_stack([np.ones(test.sum()), (x[test] - mu) / sd])
        penalty = 10 * np.eye(a.shape[1])
        penalty[0, 0] = 0
        weights = np.linalg.solve(a.T @ a + penalty, a.T @ (y[train, None] == classes))
        pred[test] = classes[np.argmax(b @ weights, axis=1)]
        folds.append(float(np.mean([np.mean(pred[test & (y == c)] == c) for c in classes])))
    score = float(np.mean([np.mean(pred[y == c] == c) for c in classes]))
    return score, folds, [[int(np.sum((y == c) & (pred == p))) for p in classes] for c in classes]


def evaluate(rows, feature_key, permutations=199):
    x = np.array([r[feature_key] for r in rows])
    y = np.array([r["label"] for r in rows])
    groups = np.array([r["block"] for r in rows])
    score, folds, confusion = predict_cv(x, y, groups)
    rng = np.random.default_rng(20261022)
    null = []
    for _ in range(permutations):
        shuffled = y.copy()
        if rows[0]["run"] == "Kognitiv":
            # Task/recovery are paired and adjacent in rows; swap within trial.
            for i in range(0, len(y), 2):
                shuffled[i:i + 2] = rng.permutation(y[i:i + 2])
        else:
            for group in np.unique(groups):
                idx = np.flatnonzero(groups == group)
                shuffled[idx] = rng.permutation(y[idx])
        null.append(predict_cv(x, shuffled, groups)[0])
    return {"n": len(rows), "classes": np.unique(y).tolist(), "balanced_accuracy": score,
            "fold_balanced_accuracy": folds, "confusion_true_rows": confusion,
            "permutation_p_exploratory": (1 + sum(s >= score for s in null)) / (1 + permutations),
            "permutations": permutations}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--signal", choices=["auto", "raw", "oscar"], default="auto")
    parser.add_argument("recording", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new report path; recordings and prior results are never overwritten.")
    from analysis.recording_files import resolve_recording
    from analysis.ml_data import trial_windows
    from analysis.session_conditions import CURRENT, select_evaluations
    selected = resolve_recording(args.recording, args.signal)
    meta = json.loads(Path(str(selected.raw) + ".session.json").read_text(errors="replace"))
    fs = meta["sampling_rate_hz"]
    data = pd.read_csv(selected.data)
    selected.validate_length(len(data))
    events = pd.read_csv(selected.events).fillna("")
    eeg_cols = [f"EEG {i}" for i in range(1, 9)]
    imu_cols = [f"{sensor} {axis}" for sensor in ["Accelerometer", "Gyroscope"] for axis in "XYZ"]
    channels = {c["name"]: c for c in meta["device"]["channels"]}
    if any(not channels[c]["enabled"] or channels[c]["unit"] not in ("µV", "μV", "uV") for c in eeg_cols):
        raise ValueError("All eight EEG channels must be confirmed in microvolts.")
    if not np.array_equal(data.sample_index.to_numpy(), np.arange(len(data))):
        raise ValueError("Non-contiguous sample indices; event offsets cannot be trusted.")
    windows, exclusions = trial_windows(events, len(data), fs, meta.get("protocol_version"))
    protocol = windows.protocol_version.iloc[0]
    eeg, imu = data[eeg_cols].to_numpy(), data[imu_cols].to_numpy()
    invalid = set()
    for window in windows.to_dict("records"):
        a, b = window["start_sample"], window["stop_sample"]
        if (not np.isfinite(eeg[a:b]).all() or not np.isfinite(imu[a:b]).all()
                or not (data["Validation Indicator"].iloc[a:b] == 1).all()):
            invalid.add(window["trial_key"])
    for trial in sorted(invalid):
        exclusions.append({"key": trial, "reason": "invalid_samples_in_trial_pair"})
    windows = windows[~windows.trial_key.isin(invalid)].reset_index(drop=True)
    evaluations = select_evaluations(windows, protocol)
    bands = ((8, 13), (13, 30)) if protocol == CURRENT else ((1, 4), (4, 8), (8, 13), (13, 30), (30, 40))
    rows = []
    for window in windows.to_dict("records"):
        left, right = window["start_sample"], window["stop_sample"]
        movement = imu[left:right]
        rows.append({**window, "eeg": features(eeg[left:right], fs, bands),
                     "imu": np.concatenate([movement.std(0), np.ptp(movement, axis=0)]),
                     "time": np.array([left / fs])})
    durations = []
    for _, group in events[events.source == "automatic"].groupby(["run", "block", "trial", "attempt"]):
        cue, offset = group[group.label == "cue_onset"], group[group.label == "task_offset"]
        if len(cue) == len(offset) == 1:
            durations.append((int(offset.iloc[0].samples_received)-int(cue.iloc[0].samples_received))/fs)
    result = {"recording": str(args.recording.resolve()), "participant": meta["participant_id"],
              "signal": selected.signal, "signal_description": selected.label,
              "selected_recording": str(selected.data.resolve()), "processing": selected.metadata,
              "samples": len(data), "duration_seconds": len(data) / fs,
              "sample_index_contiguous": bool(np.all(np.diff(data.sample_index) == 1)),
              "nonfinite_eeg_values": int((~np.isfinite(eeg)).sum()),
              "validation_counts": data["Validation Indicator"].value_counts().to_dict(),
              "zero_fraction_by_eeg_channel": dict(zip(eeg_cols, (eeg == 0).mean(0).tolist())),
              "task_duration_range_s": [min(durations), max(durations)] if durations else None,
              "protocol_version": protocol, "eeg_bands_hz": bands, "exclusions": exclusions, "skipped": len(exclusions),
              "method": "Fixed ridge penalty=10, training-fold standardization; leave-one-block-out; 3s epochs; 199 label permutations within blocks (legacy task/rest: within trial pairs). Exploratory, no multiplicity correction.",
              "results": {}}
    for run, indices in evaluations:
        subset = [rows[i] for i in indices]
        result["results"][run] = {f: evaluate(subset, f) for f in ["eeg", "imu", "time"]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
