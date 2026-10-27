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


def features(epoch, fs):
    # Filter each epoch independently: no filtering across held-out boundaries.
    filtered = sosfiltfilt(butter(4, [1, 40], fs=fs, btype="bandpass", output="sos"), epoch, axis=0)
    freq, psd = welch(filtered, fs=fs, nperseg=min(500, len(epoch)), axis=0)
    return np.concatenate([
        np.log(np.maximum(np.trapezoid(psd[(freq >= lo) & (freq <= hi)],
                                      freq[(freq >= lo) & (freq <= hi)], axis=0), 1e-20))
        for lo, hi in [(1, 4), (4, 8), (8, 13), (13, 30), (30, 40)]
    ])


def predict_cv(x, y, groups):
    classes = np.unique(y)
    pred = np.empty(len(y), dtype=y.dtype)
    folds = []
    for group in np.unique(groups):
        test = groups == group
        train = ~test
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
    from analysis.recording_files import resolve_recording
    selected = resolve_recording(args.recording, args.signal)
    meta = json.loads(Path(str(selected.raw) + ".session.json").read_text(errors="replace"))
    fs = meta["sampling_rate_hz"]
    data = pd.read_csv(selected.data)
    selected.validate_length(len(data))
    events = pd.read_csv(selected.events).fillna("")
    key = ["run", "block", "trial", "attempt"]
    invalid = {tuple(r[k] for k in key) for r in events.to_dict("records") if r["label"] == "trial_invalidated"}
    eeg_cols = [f"EEG {i}" for i in range(1, 9)]
    imu_cols = [f"{sensor} {axis}" for sensor in ["Accelerometer", "Gyroscope"] for axis in "XYZ"]
    eeg = data[eeg_cols].to_numpy()
    imu = data[imu_cols].to_numpy()
    rows = []
    durations = []
    skipped = 0
    for group_key, group in events[events.trial.astype(int) > 0].groupby(key):
        if group_key in invalid or "trial_end" not in set(group.label):
            continue
        cue = group[group.label == "cue_onset"]
        offset = group[group.label == "task_offset"]
        end = group[(group.label == "phase_end") & (group.phase == "rest")]
        if len(cue) != 1 or len(offset) != 1 or len(end) != 1:
            skipped += 1
            continue
        cue, offset, end = cue.iloc[0], offset.iloc[0], end.iloc[0]
        start, stop = int(cue.samples_received), int(offset.samples_received)
        durations.append((stop - start) / fs)
        # Same 3-second window for every task. Exclude first 0.5 s of cue.
        windows = [(start + int(.5 * fs), start + int(3.5 * fs), cue.condition)]
        if cue.run == "Kognitiv":
            # Late recovery, paired by trial; same held-out block as task.
            windows.append((int(end.samples_received) - int(3.5 * fs),
                            int(end.samples_received) - int(.5 * fs), "rest"))
        for left, right, label in windows:
            if left < 0 or right > len(data) or not np.isfinite(eeg[left:right]).all():
                skipped += 1
                continue
            movement = imu[left:right]
            rows.append({"run": cue.run, "block": int(cue.block), "label": label,
                         "eeg": features(eeg[left:right], fs),
                         "imu": np.concatenate([movement.std(0), np.ptp(movement, axis=0)]),
                         "time": np.array([left / fs])})
    result = {"recording": str(args.recording.resolve()), "participant": meta["participant_id"],
              "signal": selected.signal, "signal_description": selected.label,
              "selected_recording": str(selected.data.resolve()), "processing": selected.metadata,
              "samples": len(data), "duration_seconds": len(data) / fs,
              "sample_index_contiguous": bool(np.all(np.diff(data.sample_index) == 1)),
              "nonfinite_eeg_values": int((~np.isfinite(eeg)).sum()),
              "validation_counts": data["Validation Indicator"].value_counts().to_dict(),
              "zero_fraction_by_eeg_channel": dict(zip(eeg_cols, (eeg == 0).mean(0).tolist())),
              "task_duration_range_s": [min(durations), max(durations)], "skipped": skipped,
              "method": "Fixed ridge penalty=10, training-fold standardization; leave-one-block-out; 3s epochs; 199 label permutations within blocks (cognitive: within trial pairs). Exploratory, no multiplicity correction.",
              "results": {}}
    for run in ["Motorik", "Imagery", "Kognitiv"]:
        subset = [r for r in rows if r["run"] == run]
        result["results"][run] = {f: evaluate(subset, f) for f in ["eeg", "imu", "time"]}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
