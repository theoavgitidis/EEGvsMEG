"""Validated trial windows shared by the CBraMod benchmark and its tests."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, resample_poly, sosfiltfilt, welch

from analysis.ml_feasibility import features

CHANNELS = [f"EEG {i}" for i in range(1, 9)]
POSITIONS = ["Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"]
RUNS = {"Motorik": {"arms", "legs", "blink"},
        "Imagery": {"imagine_arms", "imagine_legs"}, "Kognitiv": {"mental_arithmetic"}}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def trial_windows(events, samples, fs):
    """Reject invalid/incomplete attempts and retain task/rest pairs atomically."""
    if fs != 250:
        raise ValueError("This benchmark's input contract requires 250 Hz.")
    events = events.fillna("")
    events = events[(events.source == "automatic") & (events.trial.astype(int) > 0)]
    rows, exclusions = [], []
    for key, group in events.groupby(["run", "block", "trial", "attempt"], sort=True):
        run, block, trial, attempt = key
        reason = None
        labels = set(group.label)
        if "trial_invalidated" in labels:
            reason = "invalidated"
        elif "trial_end" not in labels:
            reason = "incomplete"
        cue = group[group.label == "cue_onset"]
        offset = group[group.label == "task_offset"]
        rest_end = group[(group.label == "phase_end") & (group.phase == "rest")]
        if not reason and (len(cue) != 1 or len(offset) != 1 or len(rest_end) != 1):
            reason = "missing_or_duplicate_markers"
        if reason:
            exclusions.append({"key": list(key), "reason": reason})
            continue
        cue, offset, rest_end = cue.iloc[0], offset.iloc[0], rest_end.iloc[0]
        if run not in RUNS or cue.condition not in RUNS[run]:
            raise ValueError(f"Unknown condition: {run}/{cue.condition}")
        if len(set(group.condition) - {cue.condition, ""}) > 0:
            raise ValueError(f"Inconsistent condition in {key}")
        onset, off, end = map(int, [cue.samples_received, offset.samples_received, rest_end.samples_received])
        bounds = [(onset + 125, onset + 875, cue.condition, onset, off)]
        if run == "Kognitiv":
            bounds.append((end - 875, end - 125, "rest", off, end))
        if any(not (0 <= phase_start <= left < right <= phase_end <= samples)
               for left, right, _, phase_start, phase_end in bounds):
            exclusions.append({"key": list(key), "reason": "window_outside_phase_or_recording"})
            continue
        for left, right, label, _, _ in bounds:
            rows.append({"run": run, "block": int(block), "trial": int(trial),
                         "attempt": int(attempt), "label": label,
                         "trial_key": f"{run}/{block}/{trial}/{attempt}",
                         "start_sample": left, "stop_sample": right})
    if not rows:
        raise ValueError("No complete valid trials.")
    return pd.DataFrame(rows), exclusions


def model_signal(epoch_uv):
    """Offline, per-epoch CAR and bandpass; preserves physical three-second length."""
    referenced = epoch_uv - epoch_uv.mean(axis=1, keepdims=True)
    filtered = sosfiltfilt(butter(5, [.3, 40], btype="bandpass", fs=250, output="sos"),
                         referenced, axis=0)
    return resample_poly(filtered, 4, 5, axis=0).T  # channels x 600, still uV


def bandpower_processed(signal_uv):
    freq, psd = welch(signal_uv, fs=200, nperseg=400, axis=-1)
    return np.concatenate([np.log(np.maximum(np.trapezoid(
        psd[:, (freq >= lo) & (freq <= hi)], freq[(freq >= lo) & (freq <= hi)], axis=-1), 1e-20))
        for lo, hi in [(1, 4), (4, 8), (8, 13), (13, 30), (30, 40)]])


def load_recording(path):
    path = Path(path)
    meta_path, event_path = Path(str(path) + ".session.json"), Path(str(path) + ".events.csv")
    meta = json.loads(meta_path.read_text(errors="replace"))
    eeg_channels = {c["name"]: c for c in meta["device"]["channels"]}
    if any(not eeg_channels[c]["enabled"] or eeg_channels[c]["unit"] not in ("µV", "μV", "uV") for c in CHANNELS):
        raise ValueError("All eight enabled EEG channels must be confirmed in microvolts.")
    frame = pd.read_csv(path)
    if not np.array_equal(frame.sample_index.to_numpy(), np.arange(len(frame))):
        raise ValueError("Non-contiguous sample indices; event offsets cannot be trusted.")
    rows, exclusions = trial_windows(pd.read_csv(event_path), len(frame), meta["sampling_rate_hz"])
    eeg = frame[CHANNELS].to_numpy()
    x, original, matched, invalid_pairs = [], [], [], set()
    for row in rows.to_dict("records"):
        a, b = row["start_sample"], row["stop_sample"]
        if not np.isfinite(eeg[a:b]).all() or not (frame["Validation Indicator"].iloc[a:b] == 1).all():
            invalid_pairs.add(row["trial_key"])
    for key in sorted(invalid_pairs):
        exclusions.append({"key": key, "reason": "invalid_samples_in_trial_pair"})
    rows = rows[~rows.trial_key.isin(invalid_pairs)].reset_index(drop=True)
    for row in rows.to_dict("records"):
        epoch = eeg[row["start_sample"]:row["stop_sample"]]
        processed = model_signal(epoch)
        x.append((processed / 100).reshape(8, 3, 200))
        original.append(features(epoch, 250))
        matched.append(bandpower_processed(processed))
    x = np.asarray(x, dtype=np.float32)
    if not np.isfinite(x).all():
        raise ValueError("Non-finite model input.")
    provenance = {"participant_id": meta["participant_id"], "session_id": meta["session_id"],
                  "inputs": {str(p.resolve()): sha256(p) for p in [path, event_path, meta_path]},
                  "channel_order": CHANNELS, "assumed_positions": POSITIONS,
                  "montage_status": "standard project mapping; physical placement not independently verified",
                  "input_shape": list(x.shape), "exclusions": exclusions,
                  "preprocessing": "3s; CAR over 8 channels; independent epoch 5th-order 0.3-40Hz Butterworth sosfiltfilt; polyphase 250->200Hz; uV/100; no rejection by amplitude; offline",
                  "signal_absolute_quantiles_uV": dict(zip(["p50", "p95", "p99", "max"],
                      np.quantile(np.abs(x.astype(float) * 100), [.5, .95, .99, 1]).tolist()))}
    return rows, x, np.asarray(original), np.asarray(matched), provenance


def splits(rows):
    """Outer leave-one-block-out; one cyclic inner validation block, no test selection."""
    blocks = sorted(rows.block.unique())
    if len(blocks) < 3:
        raise ValueError("At least three blocks needed for train/validation/test.")
    for i, test_block in enumerate(blocks):
        val_block = blocks[(i + 1) % len(blocks)]
        train = np.flatnonzero(~rows.block.isin([test_block, val_block]).to_numpy())
        val = np.flatnonzero((rows.block == val_block).to_numpy())
        test = np.flatnonzero((rows.block == test_block).to_numpy())
        outer_train = np.flatnonzero((rows.block != test_block).to_numpy())
        partitions = [set(rows.iloc[ix].trial_key) for ix in [train, val, test]]
        if any(partitions[a] & partitions[b] for a, b in [(0, 1), (0, 2), (1, 2)]):
            raise AssertionError("Trial leakage between partitions.")
        if any(set(rows.iloc[ix].label) != set(rows.label) for ix in [train, val, test]):
            raise ValueError("Every partition must contain every class.")
        yield int(test_block), int(val_block), train, val, test, outer_train
