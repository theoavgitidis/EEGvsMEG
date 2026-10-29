"""Prepare audited PhysioNet fist histories and load them into the movement pipeline.

Preparation needs the existing MNE environment; loading needs only NumPy/SciPy/pandas.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from scipy.signal import resample_poly

from analysis.download_physionet import CHECKSUM_SHA256, DEFAULT_ROOT, RUNS, read_checksums, selected_files, sha256
from analysis.ml_data import POSITIONS
from analysis.movement_features import CONFIG, FS, HISTORY, window_features

IMPORT_CONFIG = {
    "source_sampling_rate_hz": 160, "target_sampling_rate_hz": FS,
    "source_unit": "uV in EDF header; MNE returns V", "output_unit": "uV",
    "channel_positions": POSITIONS, "history_relative_to_cue_s": [0.0, 3.5],
    "feature_relative_to_cue_s": [0.5, 3.5],
    "resampling": "per-history scipy.signal.resample_poly(up=25, down=16, axis=0, window=('kaiser', 5.0), padtype='constant', cval=0)",
    "timing": "Cue rounded to nearest 160-Hz sample; exclusive stop after 560 source samples. No source samples outside this history.",
    "reference": "as recorded; no additional rereferencing",
    "feature_config": CONFIG,
}
FILES = ("histories_uv.npy", "features.npy", "windows.csv")
CLASSES = ("me_hand_left", "me_hand_right")


def convert_history(data_v):
    """Convert exactly 3.5 s x eight source channels from V/160 Hz to uV/250 Hz."""
    data_v = np.asarray(data_v, dtype=float)
    if data_v.shape != (560, 8) or not np.isfinite(data_v).all():
        raise ValueError("Expected 560 finite source samples x eight named channels in volts.")
    converted = resample_poly(data_v * 1e6, 25, 16, axis=0,
                              window=("kaiser", 5.0), padtype="constant", cval=0)
    if converted.shape != (HISTORY, 8) or not np.isfinite(converted).all():
        raise ValueError("Invalid converted history.")
    return converted


def prepare(root, output, subjects):
    # Lazy imports keep MNE out of the existing ML environment's loading path.
    import mne
    from analysis.audit_physionet import audit_recording

    subjects = sorted(set(subjects))
    selected_files(subjects)
    source = (Path(root).expanduser() / "source").resolve()
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError("Prepared output already exists; choose a new directory.")
    if output == source or source in output.parents:
        raise ValueError("Prepared data must be outside the original source directory.")
    checksums = read_checksums(source / "SHA256SUMS.txt")
    records = []
    for subject in subjects:
        for run in RUNS:
            record = audit_recording(source, subject, run, checksums)
            if any(issue.startswith("read_or_integrity_error") for issue in record["issues"]):
                raise ValueError(f"Missing, corrupt or unreadable input: {record['file']}: {record['issues']}")
            records.append(record)
        if len(records) % 30 == 0 or subject == subjects[-1]:
            print(f"Rechecked {len(records)}/{len(subjects) * len(RUNS)} source recordings", flush=True)
    count = sum(row["eligible_task_window"] for r in records for row in r["rows"])
    if count == 0:
        raise ValueError("No eligible hand trials after the fresh source audit.")
    accepted = [r for r in records if any(row["eligible_task_window"] for row in r["rows"])]
    if len({r["sha256"] for r in accepted}) != len(accepted):
        raise ValueError("Duplicate EDF content must not become independent recordings or people.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".physionet-prepare-", dir=output.parent) as temporary:
        folder = Path(temporary)
        histories = np.lib.format.open_memmap(folder / FILES[0], mode="w+", dtype="float64",
                                              shape=(count, HISTORY, 8))
        features = np.empty((count, 16), dtype=float)
        rows, sources = [], []
        for record in records:
            eligible = [row for row in record["rows"] if row["eligible_task_window"]]
            sources.append({"participant_id": record["subject_id"], "session_id": Path(record["file"]).stem,
                "protocol_version": "physionet-eegmmidb-1.0.0", "movement_version": "physionet-fist-opening-closing",
                "signal": "raw", "data_sha256": record["sha256"],
                "event_sidecar_sha256": record["event_sidecar_sha256"], "file": record["file"],
                "issues": record["issues"], "imported_trials": len(eligible),
                "excluded_task_windows": sum(row["label"] != "rest" and not row["eligible_task_window"]
                                              for row in record["rows"])})
            if not eligible:
                continue
            if sha256(source / record["file"]) != record["sha256"]:
                raise ValueError("Source changed after audit.")
            with mne.io.read_raw_edf(source / record["file"], preload=False, verbose="ERROR") as raw:
                names = [name.replace(".", "").upper() for name in raw.ch_names]
                picks = [names.index(name.upper()) for name in POSITIONS]
                for row in eligible:
                    start = round(row["onset_s"] * 160)
                    stop = start + 560
                    if (stop > raw.n_times or start < 0 or
                            stop / 160 > row["onset_s"] + row["duration_s"] + 1e-9):
                        raise ValueError("Imported history would extend outside its source task.")
                    history = convert_history(raw.get_data(picks=picks, start=start, stop=stop).T)
                    index = len(rows)
                    histories[index] = history
                    features[index] = window_features(history)
                    rows.append({"participant_id": row["subject_id"], "session_id": row["recording_id"],
                        "session_key": f"physionet:{row['recording_id']}", "trial_key": f"physionet:{row['trial_id']}",
                        "run": row["run"], "block": row["run"], "trial": row["annotation_id"],
                        "source_code": row["source_code"], "label": row["label"],
                        "source_file": record["file"], "source_onset_s": row["onset_s"],
                        "source_duration_s": row["duration_s"], "source_start_sample": start,
                        "source_stop_sample_exclusive": stop, "history_index": index,
                        "cue_rounding_error_s": start / 160 - row["onset_s"],
                        "label_source": "PhysioNet EDF+ instructed execution; actual movement onset unmeasured"})
        histories.flush()
        del histories
        np.save(folder / FILES[1], features, allow_pickle=False)
        pd.DataFrame(rows).to_csv(folder / FILES[2], index=False)
        manifest = {"schema_version": 1, "input_domain": "physionet-executed-fists",
            "checksum_manifest_sha256": CHECKSUM_SHA256, "import_config": IMPORT_CONFIG,
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "subjects_requested": subjects,
            "sources": sources, "software_versions": {name: importlib.metadata.version(name)
                for name in ("mne", "numpy", "scipy", "pandas")},
            "summary": {"trials": len(rows), "persons": len({row["participant_id"] for row in rows}),
                "class_counts": dict(Counter(row["label"] for row in rows)),
                "excluded_recordings": sum(bool(r["issues"]) for r in records),
                "excluded_task_windows": sum(s["excluded_task_windows"] for s in sources)},
            "files_sha256": {name: sha256(folder / name) for name in FILES},
            "limitations": ["Structural checks do not validate artifact-free EEG or correct cue compliance.",
                "Only left/right executed fists; no rest, foot or imagery class.",
                "Per-history centered FIR resampling is offline; not a validated streaming adapter.",
                "No additional reference or artifact correction; source/device differences remain.",
                "No split is learned here; later evaluation must hold out whole people.",
                "Generic local EEG 1..8 names still require independently verified physical placement."]}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        # Do not replace an existing result even if it appeared during preparation.
        output.mkdir(exist_ok=False)
        for path in folder.iterdir():
            path.rename(output / path.name)
    print(json.dumps(manifest["summary"], indent=2))
    return manifest


def load_prepared(folder):
    """Verify prepared data, including row alignment and features, without MNE or pickle."""
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("input_domain") != "physionet-executed-fists"
            or manifest.get("import_config") != IMPORT_CONFIG
            or manifest.get("checksum_manifest_sha256") != CHECKSUM_SHA256
            or set(manifest.get("files_sha256", {})) != set(FILES)):
        raise ValueError("Unsupported prepared PhysioNet contract.")
    for name in FILES:
        if sha256(folder / name) != manifest["files_sha256"][name]:
            raise ValueError(f"Prepared data checksum mismatch: {name}")
    rows = pd.read_csv(folder / "windows.csv")
    required = {"participant_id", "session_id", "session_key", "trial_key", "run", "block", "trial",
                "source_code", "label", "source_file", "source_onset_s", "source_duration_s",
                "source_start_sample", "source_stop_sample_exclusive", "history_index", "cue_rounding_error_s"}
    if not required.issubset(rows.columns) or rows[list(required)].isna().any().any():
        raise ValueError("Missing prepared trial metadata.")
    histories = np.load(folder / "histories_uv.npy", mmap_mode="r", allow_pickle=False)
    features = np.load(folder / "features.npy", allow_pickle=False)
    if (not len(rows) or histories.shape != (len(rows), HISTORY, 8) or features.shape != (len(rows), 16)
            or not np.isfinite(features).all() or not np.array_equal(rows.history_index, np.arange(len(rows)))
            or rows.trial_key.duplicated().any() or set(rows.label) != set(CLASSES)
            or not rows.participant_id.str.fullmatch(r"physionet:S\d{3}").all()
            or not rows.run.isin(RUNS).all()):
        raise ValueError("Invalid prepared histories, row alignment or classes.")
    sources = manifest.get("sources", [])
    by_file = {source["file"]: source for source in sources}
    if len(by_file) != len(sources) or manifest.get("summary", {}).get("trials") != len(rows):
        raise ValueError("Invalid prepared source identities or trial count.")
    counts = rows.source_file.value_counts().to_dict()
    if counts != {source["file"]: source["imported_trials"] for source in sources if source["imported_trials"]}:
        raise ValueError("Prepared rows do not match their source provenance.")
    for row in rows.to_dict("records"):
        source = by_file[row["source_file"]]
        recording = f"S{int(row['participant_id'][-3:]):03d}R{int(row['run']):02d}"
        if (source["issues"] or source["participant_id"] != row["participant_id"]
                or row["source_file"] != f"{recording[:4]}/{recording}.edf"
                or row["session_id"] != recording or row["session_key"] != f"physionet:{recording}"
                or row["trial"] != int(row["trial"]) or row["block"] != row["run"]
                or row["trial_key"] != f"physionet:{recording}:E{int(row['trial']):03d}"
                or row["source_code"] != {"me_hand_left": "T1", "me_hand_right": "T2"}[row["label"]]
                or not np.isfinite([row[k] for k in ("source_onset_s", "source_duration_s",
                    "source_start_sample", "source_stop_sample_exclusive", "cue_rounding_error_s")]).all()
                or row["source_start_sample"] != round(row["source_onset_s"] * 160)
                or row["source_stop_sample_exclusive"] != row["source_start_sample"] + 560
                or abs(row["cue_rounding_error_s"] - (row["source_start_sample"] / 160 - row["source_onset_s"])) > 1e-12
                or row["source_duration_s"] < 3.5 or row["source_onset_s"] < 0):
            raise ValueError("Inconsistent prepared trial, marker or participant identity.")
    # Detect stale/misaligned caches, rather than trusting a caller-supplied feature matrix.
    for index in range(len(rows)):
        if not np.allclose(features[index], window_features(histories[index]), rtol=1e-12, atol=1e-12):
            raise ValueError("Prepared features do not match their histories.")
    return rows, features, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 110)))
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory outside source/.")
    args = parser.parse_args(argv)
    prepare(args.root, args.output_dir, args.subjects)


if __name__ == "__main__":
    main()
