"""Audit downloaded executed-fist EEG and export label provenance, without processing EEG."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import warnings

import mne
import numpy as np

from analysis.download_physionet import (
    CHECKSUM_SHA256, DATASET_URL, DEFAULT_ROOT, RUNS, read_checksums, selected_files, sha256,
)

POSITIONS = ("Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8")
LABELS = {"T0": "rest", "T1": "me_hand_left", "T2": "me_hand_right"}
WINDOW_START_S = 0.5
WINDOW_STOP_S = 3.5


def map_label(run, code):
    if run not in RUNS:
        raise ValueError("Only executed unilateral fist runs 3, 7, 11 are supported.")
    if code not in LABELS:
        raise ValueError(f"Unknown annotation code: {code}")
    return LABELS[code]


def edf_header(path):
    """Read technical header fields only; do not export EDF participant/date fields."""
    with Path(path).open("rb") as handle:
        fixed = handle.read(256)
        if len(fixed) != 256 or fixed[:8].strip() != b"0":
            raise ValueError("Invalid/truncated EDF header.")
        count, size = int(fixed[252:256]), int(fixed[184:192])
        records, seconds = int(fixed[236:244]), float(fixed[244:252])
        if (not 1 <= count <= 256 or size != 256 * (count + 1) or records <= 0
                or not math.isfinite(seconds) or seconds <= 0):
            raise ValueError("Invalid EDF dimensions.")
        channel_header = handle.read(size - 256)
    if len(channel_header) != size - 256:
        raise ValueError("Truncated channel header.")
    fields, offset = {}, 0
    for name, width in [("label", 16), ("transducer", 80), ("unit", 8),
                        ("physical_min", 8), ("physical_max", 8), ("digital_min", 8),
                        ("digital_max", 8), ("prefilter", 80), ("samples_per_record", 8),
                        ("reserved", 32)]:
        fields[name] = [channel_header[offset + i * width:offset + (i + 1) * width]
                        .decode("ascii").strip() for i in range(count)]
        offset += width * count
    samples = [int(v) for v in fields["samples_per_record"]]
    if any(n <= 0 for n in samples) or Path(path).stat().st_size != size + records * sum(samples) * 2:
        raise ValueError("EDF size does not match its sample dimensions.")
    eeg = [i for i, label in enumerate(fields["label"]) if label != "EDF Annotations"]
    calibration = [[float(fields[k][i]) for k in
        ("physical_min", "physical_max", "digital_min", "digital_max")] for i in eeg]
    if not np.isfinite(calibration).all():
        raise ValueError("Non-finite EDF calibration.")
    return {"channel_labels": [fields["label"][i] for i in eeg],
        "physical_units": [fields["unit"][i] for i in eeg],
        "sampling_rates_hz": [samples[i] / seconds for i in eeg],
        "physical_ranges": [[float(fields[k][i]) for k in ("physical_min", "physical_max")] for i in eeg],
        "digital_ranges": [[float(fields[k][i]) for k in ("digital_min", "digital_max")] for i in eeg],
        "prefilters": sorted(set(fields["prefilter"][i] for i in eeg)),
        "duration_s": records * seconds}


def annotation_rows(subject, run, onsets, durations, codes, recording_duration, sfreq):
    """Preserve every source annotation; flag invalid boundaries and short task windows."""
    rows, issues = [], []
    previous_end = 0.0
    if not (len(onsets) == len(durations) == len(codes)):
        raise ValueError("Annotation arrays must have equal lengths.")
    for index, (onset, duration, code) in enumerate(zip(onsets, durations, codes)):
        onset, duration = float(onset), float(duration)
        label = map_label(run, str(code))
        reasons = []
        if not np.isfinite([onset, duration]).all() or onset < 0 or duration <= 0:
            raise ValueError("Invalid annotation time.")
        else:
            if onset + duration > recording_duration + 1 / sfreq:
                issues.append("annotation_outside_recording")
                reasons.append("annotation_outside_recording")
            if abs(onset - previous_end) > 1 / sfreq:
                issues.append("annotation_gap_or_overlap")
            previous_end = onset + duration
        task = code != "T0"
        if task and duration < WINDOW_STOP_S:
            reasons.append("task_shorter_than_3.5s")
        rows.append({"subject_id": f"physionet:S{subject:03d}",
            "recording_id": f"S{subject:03d}R{run:02d}", "run": run,
            "annotation_id": index, "trial_id": f"S{subject:03d}R{run:02d}:E{index:03d}",
            "source_code": str(code), "label": label,
            "onset_s": onset, "duration_s": duration,
            "candidate_window_start_s": onset + WINDOW_START_S if task else None,
            "candidate_window_stop_s": onset + WINDOW_STOP_S if task else None,
            "exclusion_reasons": reasons,
            "eligible_task_window": task and not reasons})
    if not rows:
        issues.append("missing_annotations")
    counts = Counter(row["label"] for row in rows)
    if any(not counts[label] for label in LABELS.values()):
        issues.append("missing_class")
    return rows, sorted(set(issues))


def audit_recording(source, subject, run, checksums):
    relative = f"S{subject:03d}/S{subject:03d}R{run:02d}.edf"
    record = {"subject_id": f"physionet:S{subject:03d}", "run": run,
              "file": relative, "issues": [], "rows": []}
    try:
        for name in (relative, relative + ".event"):
            if sha256(source / name) != checksums[name]:
                raise ValueError(f"Checksum mismatch: {name}")
        record["sha256"] = checksums[relative]
        record["event_sidecar_sha256"] = checksums[relative + ".event"]
        header = edf_header(source / relative)
        record["header"] = header
        normalized = [name.replace(".", "").upper() for name in header["channel_labels"]]
        if len(normalized) != 64 or len(set(normalized)) != 64:
            record["issues"].append("expected_64_unique_eeg_channels")
        if any(name.upper() not in normalized for name in POSITIONS):
            record["issues"].append("missing_target_channel")
        else:
            record["target_channel_indices_zero_based"] = [normalized.index(name.upper()) for name in POSITIONS]
        if set(header["physical_units"]) != {"uV"}:
            record["issues"].append("unexpected_physical_units")
        if set(header["sampling_rates_hz"]) != {160.0}:
            record["issues"].append("unexpected_sampling_rate")
        ranges = header["physical_ranges"] + header["digital_ranges"]
        if any(not np.isfinite(pair).all() or pair[0] >= pair[1] for pair in ranges):
            record["issues"].append("invalid_calibration_range")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            raw = mne.io.read_raw_edf(source / relative, preload=True, verbose="ERROR")
        record["reader_warnings"] = [str(w.message) for w in caught]
        if caught:
            record["issues"].append("edf_reader_warning")
        data = raw.get_data()
        record["sampling_rate_hz"] = float(raw.info["sfreq"])
        record["samples"] = int(raw.n_times)
        record["duration_s"] = raw.n_times / raw.info["sfreq"]
        if record["duration_s"] != header["duration_s"]:
            record["issues"].append("header_reader_duration_mismatch")
        if data.shape[0] != 64 or not np.isfinite(data).all():
            record["issues"].append("invalid_signal_array")
        record["flat_channels"] = [name for name, span in zip(raw.ch_names, np.ptp(data, axis=1)) if span == 0]
        if record["flat_channels"]:
            record["issues"].append("flat_channel")
        # MNE converts EDF physical uV to volts. This is a reported diagnostic only.
        maximum = float(np.max(np.abs(data)) * 1e6)
        record["max_abs_amplitude_uv"] = maximum if np.isfinite(maximum) else None
        record["rows"], annotation_issues = annotation_rows(subject, run, raw.annotations.onset,
            raw.annotations.duration, raw.annotations.description, record["duration_s"], raw.info["sfreq"])
        record["issues"].extend(annotation_issues)
        record["annotation_counts"] = dict(Counter(row["label"] for row in record["rows"]))
        record["unannotated_tail_s"] = max(0.0, record["duration_s"] - max(
            (row["onset_s"] + row["duration_s"] for row in record["rows"]), default=0))
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        record["issues"].append(f"read_or_integrity_error: {exc}")
    record["issues"] = sorted(set(record["issues"]))
    for row in record["rows"]:
        row["exclusion_reasons"] = sorted(set(row["exclusion_reasons"] + record["issues"]))
        row["eligible_task_window"] = row["label"] != "rest" and not row["exclusion_reasons"]
    return record


def audit(root, subjects, output):
    subjects = sorted(set(subjects))
    selected_files(subjects)  # Validate selection before reading/writing.
    source = Path(root) / "source"
    checksums = read_checksums(source / "SHA256SUMS.txt")
    output = Path(output).resolve()
    if output == source.resolve() or source.resolve() in output.parents:
        raise ValueError("Audit output must be outside the original source directory.")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for subject in subjects:
        for run in RUNS:
            records.append(audit_recording(source, subject, run, checksums))
        if len(records) % 30 == 0 or subject == subjects[-1]:
            print(f"Audited {len(records)}/{len(subjects) * len(RUNS)} EDF files", flush=True)
    rows = [row for record in records for row in record["rows"]]
    selected = [row for row in rows if row["eligible_task_window"]]
    complete_subjects = [subject for subject in subjects if all(
        not record["issues"] and all(any(row["eligible_task_window"] and row["label"] == label
            for row in record["rows"]) for label in ("me_hand_left", "me_hand_right"))
        for record in records if record["subject_id"] == f"physionet:S{subject:03d}")]
    summary = {"recordings": len(records), "subjects": len(subjects),
        "recordings_without_structural_issues": sum(not r["issues"] for r in records),
        "subjects_with_three_structurally_usable_runs": complete_subjects,
        "duration_hours": sum(r.get("duration_s", 0) for r in records) / 3600,
        "sampling_rate_counts": dict(Counter(str(r.get("sampling_rate_hz", "unreadable")) for r in records)),
        "annotation_counts": dict(Counter(row["label"] for row in rows)),
        "eligible_task_window_counts": dict(Counter(row["label"] for row in selected)),
        "excluded_task_windows": sum(row["label"] != "rest" and not row["eligible_task_window"] for row in rows),
        "recording_issue_counts": dict(Counter(issue for r in records for issue in r["issues"]))}
    report = {"dataset_url": DATASET_URL, "version": "1.0.0", "license": "ODC-By-1.0",
        "checksum_manifest_sha256": CHECKSUM_SHA256,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "software": {"mne": mne.__version__, "numpy": np.__version__},
        "subjects": subjects, "runs": list(RUNS), "label_mapping": LABELS,
        "target_positions": POSITIONS, "candidate_task_window_relative_s": [WINDOW_START_S, WINDOW_STOP_S],
        "processing": "None: no filtering, resampling, rereferencing, artifact rejection or training. MNE reads values in V.",
        "limitations": ["Structural eligibility is not signal-quality or physiological validation.",
            "Labels describe cues; actual compliance and left/right correctness cannot be proven from EDF alone.",
            "Original WFDB .event sidecars are checksum-verified; annotation rows are read from EDF+ only.",
            "T0 is inter-task rest, not an independently randomized neutral class; no rest windows are selected.",
            "Public subjects keep a dataset namespace; no local EVM participant IDs are assigned.",
            "No train/test split or montage transfer is validated; future cross-subject tests must hold out whole people."],
        "summary": summary, "recordings": records}
    (output / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    compact = {key: value for key, value in report.items() if key != "recordings"}
    compact["flagged_recordings"] = [{key: record.get(key) for key in
        ("file", "subject_id", "run", "issues", "sampling_rate_hz", "annotation_counts")}
        | {"excluded_task_windows": sum(row["label"] != "rest" and not row["eligible_task_window"]
            for row in record["rows"])} for record in records if record["issues"] or any(
                row["label"] != "rest" and not row["eligible_task_window"] for row in record["rows"])]
    (output / "summary.json").write_text(json.dumps(compact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "annotations.csv").open("w", newline="", encoding="utf-8") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "exclusion_reasons": ";".join(row["exclusion_reasons"])})
    print(json.dumps(summary, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 110)))
    parser.add_argument("--output", type=Path, help="Default: ROOT/audit")
    args = parser.parse_args(argv)
    root = args.root.expanduser()
    audit(root, args.subjects, args.output.expanduser() if args.output else root / "audit")


if __name__ == "__main__":
    main()
