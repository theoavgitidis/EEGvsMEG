"""Prepare project recordings for BCI2000Analysis, or inspect native .dat files.

Cross-platform and strictly offline. Run: python -m analysis.bci2000_offline --help
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import numpy as np
import pandas as pd

from analysis.bci2000 import read_dat, write_dat, to_mne, sha256
from analysis.event_annotations import event_descriptions
from analysis.ml_data import CHANNELS, trial_windows
from analysis.ml_feasibility import exclude_before_marker
from analysis.recording_files import resolve_recording, read_session_metadata, eeg_unit_scale
from analysis.session_conditions import CURRENT, CONTRASTS, LEGACY_RUNS, protocol_for_events


def _json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _publish(staging, destination):
    """Reserve a new destination atomically; never replace another result."""
    destination.mkdir()
    for child in staging.iterdir():
        child.rename(destination / child.name)


def _integers(values, name, maximum=2**32 - 1):
    values = np.asarray(values, dtype=float)
    if (not np.isfinite(values).all() or np.any(values < 0) or np.any(values > maximum)
            or np.any(values != np.floor(values))):
        raise ValueError(f"{name} must contain finite nonnegative integers <= {maximum}.")
    return values.astype(np.uint32)


def load_project(path, signal="raw", marker=None, settle_seconds=0):
    selected = resolve_recording(path, signal)
    meta = read_session_metadata(selected.session)
    if meta.get("sampling_rate_hz") != 250:
        raise ValueError("Project export requires confirmed 250 Hz; no implicit resampling.")
    if any(not isinstance(meta.get(key), str) or not meta[key].strip() for key in ("participant_id", "session_id")):
        raise ValueError("Explicit participant_id and session_id are required.")
    configuration = {row["name"]: row for row in meta["device"]["channels"]}
    if len(configuration) != len(meta["device"]["channels"]):
        raise ValueError("Duplicate names in recorded device configuration.")
    scales = []
    for name in CHANNELS:
        channel = configuration.get(name, {})
        scale = eeg_unit_scale(channel.get("unit"))
        if channel.get("enabled") is not True or scale is None:
            raise ValueError(f"Enabled EEG channel and confirmed physical unit required: {name}")
        scales.append(scale * 1e6)
    frame = pd.read_csv(selected.data)
    selected.validate_length(len(frame))
    if not {"sample_index", "nominal_time_s", *CHANNELS} <= set(frame):
        raise ValueError("Project CSV requires sample_index, nominal_time_s and all eight EEG columns.")
    if [name for name in frame if name in CHANNELS] != CHANNELS:
        raise ValueError("Recorded EEG channel order must be EEG 1 through EEG 8; reordering is not implicit.")
    if (not len(frame) or not np.array_equal(frame.sample_index, np.arange(len(frame)))
            or not np.allclose(frame.nominal_time_s, np.arange(len(frame)) / 250, rtol=0, atol=1e-6)):
        raise ValueError("Project sample_index/nominal_time_s must be contiguous at 250 Hz.")
    eeg = frame[CHANNELS].to_numpy(dtype=float) * scales
    if not np.isfinite(eeg).all():
        raise ValueError("Non-finite EEG cannot be exported for BCI2000 filtering; sources remain unchanged.")
    if "Validation Indicator" not in frame or "Counter" not in frame:
        raise ValueError("Counter and Validation Indicator are required; quality is not invented.")
    counter = frame.Counter.to_numpy(dtype=float)
    quality = frame["Validation Indicator"].eq(1).to_numpy(copy=True)
    quality &= np.isfinite(counter) & (counter >= 0) & (counter == np.floor(counter))
    quality[1:] &= np.diff(counter) == 1
    events = pd.read_csv(selected.events, keep_default_na=False)
    required = {"source", "run", "block", "trial", "attempt", "condition", "phase", "samples_received", "label"}
    if not required <= set(events):
        raise ValueError("Structured automatic session events required; manual labels are not reinterpreted.")
    events["samples_received"] = _integers(pd.to_numeric(events.samples_received), "Event positions", 2**32 - 1)
    automatic = events.source.eq("automatic")
    for name in ("block", "trial", "attempt"):
        numeric = np.zeros(len(events), dtype=np.int64)
        numeric[automatic.to_numpy()] = _integers(pd.to_numeric(events.loc[automatic, name]), name)
        events[name] = numeric
    protocol, _ = protocol_for_events(events.loc[automatic], meta.get("protocol_version"))
    windows, excluded = trial_windows(events, len(eeg), 250, protocol)
    windows, cutoff_exclusions, cutoff = exclude_before_marker(windows, events, 250, len(eeg), marker, settle_seconds)
    excluded.extend(cutoff_exclusions)
    invalid = {row.trial_key for row in windows.itertuples() if not quality[row.start_sample:row.stop_sample].all()}
    excluded.extend({"key": key, "reason": "invalid_samples_in_trial_pair"} for key in sorted(invalid))
    windows = windows[~windows.trial_key.isin(invalid)].reset_index(drop=True)
    if windows.empty:
        raise ValueError("No valid complete analysis windows after exclusions.")
    inputs = [selected.raw, selected.data, selected.events, selected.session, selected.processing,
              Path(str(selected.raw) + ".plan.csv"), Path(str(selected.raw) + ".device.json")]
    provenance = {"participant_id": meta["participant_id"], "session_id": meta["session_id"],
                  "session_state": meta.get("state", "unknown"), "protocol_version": protocol,
                  "signal": selected.signal, "signal_description": selected.label,
                  "processing": selected.metadata, "quality_cutoff": cutoff,
                  "inputs_sha256": {str(p.resolve()): sha256(p) for p in dict.fromkeys(inputs) if p.is_file()},
                  "selected_data_sha256": sha256(selected.data), "exclusions": excluded,
                  "eeg_values_sha256": hashlib.sha256(eeg.astype("<f8").tobytes()).hexdigest(),
                  "channel_names": CHANNELS, "recorded_units": [configuration[n]["unit"] for n in CHANNELS],
                  "export_unit": "uV", "montage": "recorded order; physical positions not inferred",
                  "sample_position_method": meta.get("event_position_method", "received sample count; approximate")}
    return dict(selected=selected, meta=meta, frame=frame, eeg=eeg, quality=quality,
                events=events, windows=windows, provenance=provenance, protocol=protocol)


def context_states(source):
    events, count = source["events"], len(source["eeg"])
    states = {name: np.zeros(count, dtype=np.uint32) for name in
              ("EvmRun", "EvmBlock", "EvmTrial", "EvmAttempt", "EvmCondition", "EvmPhase", "EvmStatus")}
    maps = {name: {label: index + 1 for index, label in enumerate(sorted(set(events.loc[
            events.source.eq("automatic"), name]) - {""}))} for name in ("run", "condition", "phase")}
    descriptions = event_descriptions(events.to_dict("records"))
    rows = [(int(row.samples_received), row, label) for row, label in zip(events.itertuples(), descriptions)
            if row.source == "automatic" and row.label not in ("trial_invalidated", "trial_repeat")]
    rows.sort(key=lambda item: item[0])  # stable order for simultaneous original events
    for index, (start, row, description) in enumerate(rows):
        stop = min(rows[index + 1][0] if index + 1 < len(rows) else count, count)
        if not 0 <= start < stop:
            continue
        for column, name in (("run", "EvmRun"), ("condition", "EvmCondition"), ("phase", "EvmPhase")):
            states[name][start:stop] = maps[column].get(getattr(row, column), 0)
        for column, name in (("block", "EvmBlock"), ("trial", "EvmTrial"), ("attempt", "EvmAttempt")):
            states[name][start:stop] = int(getattr(row, column))
        status = next((value for label, value in (("completed", 1), ("invalid", 2), ("incomplete", 3))
                       if description.endswith(f" | status={label}")), 0)
        states["EvmStatus"][start:stop] = status
    return states, maps


def _block_bounds(source, run, block):
    # Late invalidations must NOT extend a block into a held-out block.
    events = source["events"]
    group = events[(events.source == "automatic") & (events.run == run) & (events.block == block)
                   & events.label.isin(["block_start", "block_end", "trial_start", "trial_end", "phase_start",
                                        "phase_end", "cue_onset", "task_onset", "task_offset", "rest_end"])]
    if group.empty:
        raise ValueError("Missing block timing markers.")
    start, stop = int(group.samples_received.min()), min(int(group.samples_received.max()), len(source["eeg"]))
    if not 0 <= start < stop:
        raise ValueError("Invalid block bounds.")
    return start, stop


def _folds(files, classes, sessions):
    if sessions > 1:
        keys = sorted({row["session_index"] for row in files})
        group_name = "session_index"
    else:
        keys = sorted({row["block"] for row in files})
        group_name = "block"
    if len(keys) < 2:
        return [], "At least two complete blocks/sessions are required for held-out evaluation."
    folds = []
    for key in keys:
        test = [row for row in files if row[group_name] == key]
        train = [row for row in files if row[group_name] != key]
        for subset in (train, test):
            if set().union(*(set(row["counts"]) for row in subset)) != set(classes):
                return [], "Each train/test partition must contain every class."
        folds.append({"held_out": key, "train": [r["file"] for r in train], "test": [r["file"] for r in test]})
    return folds, None


def prepare(paths, output, signal="raw", runs=None, marker=None, settle_seconds=0):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Choose a new output directory; existing results are never overwritten.")
    sources = [load_project(path, signal, marker, settle_seconds) for path in paths]
    identities = [(s["meta"]["participant_id"], s["meta"]["session_id"]) for s in sources]
    hashes = [s["provenance"]["selected_data_sha256"] for s in sources]
    eeg_hashes = [s["provenance"]["eeg_values_sha256"] for s in sources]
    if (len(set(identities)) != len(identities) or len(set(hashes)) != len(hashes)
            or len(set(eeg_hashes)) != len(eeg_hashes)):
        raise ValueError("Duplicate session identity or EEG data; copies are not independent sessions.")
    if len({s["protocol"] for s in sources}) != 1 or len({s["selected"].signal for s in sources}) != 1:
        raise ValueError("Do not pool protocol versions or raw/OSCAR signal variants.")
    if len({s["meta"]["participant_id"] for s in sources}) != 1:
        raise ValueError("This session-transfer export accepts one participant; do not mix persons.")
    protocol = sources[0]["protocol"]
    available = CONTRASTS if protocol == CURRENT else {**LEGACY_RUNS, "Kognitiv": {"mental_arithmetic", "rest"}}
    names = list(available) if runs is None else list(dict.fromkeys(runs))
    if not names or not set(names) <= set(available):
        raise ValueError(f"Choose protocol-specific contrasts: {', '.join(available)}")
    report = {"schema_version": 1, "kind": "eegvsmeg-bci2000-offline", "protocol_version": protocol,
              "state": "complete", "sources": [s["provenance"] for s in sources],
              "window": "0.5–3.5 s after instructed cue; 3 s; original received-sample timeline",
              "split": "leave-one-session-out" if len(sources) > 1 else "leave-one-block-out",
              "contrasts": {}, "skipped_contrasts": {},
              "versions": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scipy")},
              "limitations": ["BCI2000 executable compatibility requires native validation",
                  "SourceTime/StimulusTime are synthetic nominal times, not measured acquisition/display onsets",
                  "float32 export is derived; original files remain authoritative",
                  "BCI2000 continuous spectral filtering differs from project per-epoch Welch features"]}
    with tempfile.TemporaryDirectory(prefix=".bci2000-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for index, source in enumerate(sources, 1):
            folder = staging / f"session{index:03d}"
            folder.mkdir()
            source["folder"] = folder
            selected = source["selected"]
            shutil.copyfile(selected.events, folder / "source.events.csv")
            shutil.copyfile(selected.session, folder / "source.session.json")
            for suffix in (".plan.csv", ".device.json"):
                original = Path(str(selected.raw) + suffix)
                if original.is_file():
                    shutil.copyfile(original, folder / ("source" + suffix))
            if selected.processing.exists():
                shutil.copyfile(selected.processing, folder / "source.processing.json")
            auxiliary = [name for name in source["frame"] if name not in CHANNELS]
            arrays = {f"column_{i:03d}": source["frame"][name].to_numpy(dtype=float) for i, name in enumerate(auxiliary)}
            np.savez_compressed(folder / "source.auxiliary.npz", **arrays)
            _json(folder / "source.auxiliary.json", {f"column_{i:03d}": name for i, name in enumerate(auxiliary)})
            source["context"], source["maps"] = context_states(source)
            source["windows"].to_csv(folder / "retained-windows.csv", index=False)
        for contrast in names:
            labels = sorted(available[contrast])
            selections = [s["windows"][s["windows"].label.isin(labels)].copy() for s in sources]
            if any(set(rows.label) != set(labels) for rows in selections):
                reason = "Every input session needs complete classes: " + ", ".join(labels)
                if runs is not None:
                    raise ValueError(f"{contrast}: {reason}")
                report["skipped_contrasts"][contrast] = reason
                continue
            files = []
            for index, (source, rows) in enumerate(zip(sources, selections), 1):
                bounds = {(run, int(block)): _block_bounds(source, run, block) for run, block in
                          source["windows"][["run", "block"]].drop_duplicates().itertuples(index=False, name=None)}
                ordered = sorted(bounds.values())
                if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
                    raise ValueError("Overlapping block ranges; cannot export independent held-out files.")
                for (run, block), group in rows.groupby(["run", "block"], sort=True):
                    start, stop = bounds[run, int(block)]
                    count = stop - start
                    if any(r.start_sample < start or r.stop_sample > stop for r in group.itertuples()):
                        raise ValueError("Analysis window outside its block.")
                    state_data = {name: (32, values[start:stop]) for name, values in source["context"].items()}
                    target, window, endpoint = [np.zeros(count, dtype=np.uint32) for _ in range(3)]
                    for row in group.itertuples():
                        left, right = row.start_sample - start, row.stop_sample - start
                        if window[left:right].any():
                            raise ValueError("Overlapping analysis windows.")
                        target[left:right] = labels.index(row.label) + 1
                        window[left:right] = 1
                        endpoint[right - 1] = 1
                    clock = (np.arange(start, stop, dtype=np.uint64) * 4 % 65536).astype(np.uint32)
                    state_data.update(Running=(1, np.ones(count, dtype=np.uint32)), SourceTime=(16, clock),
                                      StimulusTime=(16, clock), TargetCode=(16, target), Feedback=(1, window),
                                      EvmWindow=(1, window), EvmAnalysis=(1, endpoint),
                                      EvmQuality=(1, source["quality"][start:stop].astype(np.uint32)))
                    for column, name in (("Counter", "Counter"), ("Validation Indicator", "Validation")):
                        values = source["frame"][column].iloc[start:stop].to_numpy(dtype=float)
                        if np.isfinite(values).all() and np.all(values >= 0) and np.all(values <= 2**32-1) and np.all(values == np.floor(values)):
                            state_data[name] = (32, values.astype(np.uint32))
                    destination = source["folder"] / f"{contrast}-block{int(block):02d}.dat"
                    params = {"SubjectName": source["meta"]["participant_id"], "SubjectSession": source["meta"]["session_id"],
                              "EvmProtocol": protocol, "EvmContrast": contrast, "EvmSignal": source["selected"].signal,
                              "EvmClassMap": json.dumps({i+1: label for i, label in enumerate(labels)}, sort_keys=True),
                              "EvmContextMap": json.dumps(source["maps"], sort_keys=True), "EvmOriginSample": str(start),
                              "EvmTiming": "synthetic nominal clocks; software markers; no hardware-onset claim"}
                    rounding = write_dat(destination, source["eeg"][start:stop], 250, CHANNELS, state_data,
                                         parameters=params, block_size=1)
                    _json(Path(str(destination) + ".metadata.json"), dict(schema_version=1,
                          dat_sha256=sha256(destination), events_file="source.events.csv",
                          events_sha256=sha256(source["folder"] / "source.events.csv"), original_start_sample=start,
                          original_stop_sample=stop, signal_description=source["selected"].label))
                    files.append({"file": destination.relative_to(staging).as_posix(), "session_index": index,
                                  "run": run, "block": int(block), "original_start_sample": start,
                                  "original_stop_sample": stop, "max_float32_rounding_uV": rounding,
                                  "sha256": sha256(destination), "counts": {label: int((group.label == label).sum()) for label in labels if (group.label == label).any()}})
            folds, unavailable = _folds(files, labels, len(sources))
            report["contrasts"][contrast] = {"classes": {str(i+1): label for i, label in enumerate(labels)},
                "analysis_conditions": [f"EvmAnalysis == 1 && TargetCode == {i+1}" for i in range(len(labels))],
                "csp_conditions": [f"EvmWindow == 1 && TargetCode == {i+1}" for i in range(len(labels))],
                "files": files, "folds": folds, "evaluation_unavailable": unavailable,
                "gui_note": "BCI2000Analysis uses two analysis conditions; contrasts with >2 classes need explicit pairwise analyses."}
        if not report["contrasts"]:
            raise ValueError("No complete contrasts available for export.")
        # Starting configuration only; no classifier trained or feedback application started.
        (staging / "spectral.prm").write_text(
            "Filtering float WindowLength= 3s\nFiltering int Detrend= 1\n"
            "Filtering int ModelOrder= 16\nFiltering int OutputType= 1\n"
            "Filtering float FirstBinCenter= 8Hz\nFiltering float LastBinCenter= 30Hz\n"
            "Filtering float BinWidth= 1Hz\nFiltering int EvaluationsPerBin= 15\n", encoding="ascii")
        _json(staging / "manifest.json", report)
        _publish(staging, output)
    return report


def convert(path, output, channels=None, save_fif=True):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Choose a new output directory.")
    recording = read_dat(path)
    raw = to_mne(path, channels) if save_fif else None
    with tempfile.TemporaryDirectory(prefix=".bci2000-", dir=output.parent) as temporary:
        staging = Path(temporary)
        frame = pd.DataFrame(recording.signal_uv, columns=recording.channel_names)
        frame.insert(0, "bci_sample_index", np.arange(len(frame)))
        frame.to_csv(staging / "calibrated-signals-uV.csv", index=False)
        np.savez_compressed(staging / "states.npz", **{f"state_{i:03d}": data for i, data in enumerate(recording.states.values())})
        summary = recording.summary()
        summary.update(state_arrays={f"state_{i:03d}": name for i, name in enumerate(recording.states)},
                       parameters=recording.parameters, state_definitions=recording.state_definitions,
                       input_name=Path(path).name)
        _json(staging / "metadata.json", summary)
        if raw is not None:
            raw.save(staging / "recording_raw.fif", overwrite=False, fmt="double", verbose="ERROR")
        _publish(staging, output)
    return summary


def find_tool(directory, name):
    if not re.fullmatch(r"(?:bci_[a-zA-Z0-9_]+|BCI2000Analysis)", name):
        raise ValueError("Only BCI2000 offline analysis tools can be selected.")
    base = Path(directory)
    for folder in (base, base / "tools" / "cmdline", base / "Tools" / "cmdline", base / "prog"):
        for candidate in (folder / name, folder / (name + ".exe"),
                          folder / (name + ".app") / "Contents" / "MacOS" / name):
            if candidate.is_file():
                return candidate.resolve()
    raise FileNotFoundError(f"Offline tool not found: {name}; select the BCI2000 installation directory.")


def doctor(directory):
    found = {}
    for name in ("BCI2000Analysis", "bci_dat2stream", "bci_stream2table", "bci_spatialfilter", "bci_arfilter"):
        try:
            path = find_tool(directory, name)
            found[name] = {"path": str(path), "sha256": sha256(path),
                           "host_executable": os.name == "nt" or (path.suffix != ".exe" and os.access(path, os.X_OK))}
        except FileNotFoundError:
            found[name] = None
    return {"platform": os.name, "tools": found, "note": "Presence is not a successful native execution test."}


def run_chain(path, directory, output, filters=(), parameters=None, timeout=300):
    """Binary pipes in Python, avoiding PowerShell text conversion and shell quoting."""
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and positive.")
    read_dat(path)  # reject malformed/uncalibrated input before starting external tools
    output = Path(output)
    if output.exists():
        raise FileExistsError("Choose a new output directory.")
    commands = [[str(find_tool(directory, name))] for name in ("bci_dat2stream", *filters, "bci_stream2table")]
    if parameters:
        parameters = Path(parameters).resolve(strict=True)
        commands[0].append("-p" + str(parameters))
    output.mkdir()
    processes, logs = [], []
    result = {"schema_version": 1, "state": "failed", "input_sha256": sha256(path), "commands": commands,
              "parameters_sha256": sha256(parameters) if parameters else None,
              "tools_sha256": {command[0]: sha256(command[0]) for command in commands}}
    try:
        with Path(path).open("rb") as source, (output / "data.tsv.partial").open("xb") as target:
            previous = source
            for index, command in enumerate(commands):
                log = (output / f"tool-{index:02d}.stderr.log").open("xb")
                logs.append(log)
                process = subprocess.Popen(command, stdin=previous,
                    stdout=target if index == len(commands)-1 else subprocess.PIPE, stderr=log, shell=False)
                processes.append(process)
                if previous is not source:
                    previous.close()
                previous = process.stdout
            deadline = time.monotonic() + timeout
            while any(process.poll() is None for process in processes):
                if any(process.poll() not in (None, 0) for process in processes):
                    raise RuntimeError("BCI2000 tool failed; inspect tool-*.stderr.log.")
                if time.monotonic() >= deadline:
                    raise TimeoutError("BCI2000 offline chain exceeded its timeout.")
                time.sleep(.025)
            if any(process.returncode for process in processes):
                raise RuntimeError("BCI2000 tool failed; inspect tool-*.stderr.log.")
        if not (output / "data.tsv.partial").stat().st_size:
            raise RuntimeError("BCI2000 returned an empty table.")
        (output / "data.tsv.partial").rename(output / "data.tsv")
        result["state"] = "complete"
        return result
    except (OSError, RuntimeError, TimeoutError) as error:
        result["error"] = str(error)
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout:
                process.stdout.close()
        for log in logs:
            log.close()
        result["returncodes"] = [process.returncode for process in processes]
        _json(output / "run.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="Projekt-CSV mit gültigen Trials und Folds für BCI2000Analysis exportieren")
    prepare_parser.add_argument("recordings", nargs="+", type=Path)
    prepare_parser.add_argument("--output-dir", required=True, type=Path)
    prepare_parser.add_argument("--signal", choices=("raw", "auto", "oscar"), default="raw")
    prepare_parser.add_argument("--runs", nargs="+")
    prepare_parser.add_argument("--after-marker")
    prepare_parser.add_argument("--settle-seconds", type=float, default=0)
    inspect_parser = commands.add_parser("inspect", help="Kalibrierung, Kanäle, Samples und alle States prüfen")
    inspect_parser.add_argument("recording", type=Path)
    convert_parser = commands.add_parser("convert", help="Native .dat in kalibrierte CSV, vollständige States und FIF exportieren")
    convert_parser.add_argument("recording", type=Path)
    convert_parser.add_argument("--output-dir", required=True, type=Path)
    convert_parser.add_argument("--bci-channels", nargs="+")
    convert_parser.add_argument("--no-fif", action="store_true")
    doctor_parser = commands.add_parser("doctor", help="Installierte native Offline-Werkzeuge finden")
    doctor_parser.add_argument("bci2000_dir", type=Path)
    chain_parser = commands.add_parser("run-chain", help="Native BCI2000-Filter offline über binäre Pipes ausführen")
    chain_parser.add_argument("recording", type=Path)
    chain_parser.add_argument("--bci2000-dir", required=True, type=Path)
    chain_parser.add_argument("--output-dir", required=True, type=Path)
    chain_parser.add_argument("--filter", action="append", default=[])
    chain_parser.add_argument("--parameters", type=Path)
    chain_parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.recordings, args.output_dir, args.signal, args.runs, args.after_marker, args.settle_seconds)
            print(f"Offline-Export: {args.output_dir.resolve()}; Kontraste: {', '.join(result['contrasts'])}")
        elif args.command == "inspect":
            print(json.dumps(read_dat(args.recording).summary(), ensure_ascii=False, indent=2))
        elif args.command == "convert":
            convert(args.recording, args.output_dir, args.bci_channels, not args.no_fif)
            print(f"Kalibrierter Offline-Import: {args.output_dir.resolve()}")
        elif args.command == "doctor":
            print(json.dumps(doctor(args.bci2000_dir), ensure_ascii=False, indent=2))
        elif args.command == "run-chain":
            run_chain(args.recording, args.bci2000_dir, args.output_dir, args.filter, args.parameters, args.timeout)
            print(f"Native Offline-Verarbeitung abgeschlossen: {args.output_dir.resolve()}")
    except (ValueError, OSError, KeyError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
