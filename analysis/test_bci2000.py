"""Independent byte fixtures, calibration, context-preserving exports and offline pipes."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import mne
import numpy as np
import pandas as pd

import view_eeg
from analysis import view_eeg as other_viewer
from analysis.bci2000 import read_dat, write_dat, to_mne, parse_parameters, sha256
from analysis.bci2000_offline import prepare, convert, load_project, run_chain, doctor


def fixture(path, data_format="int16", *, missing_gain=False, extra_state=None, names="Fz C3"):
    """Manual struct fixture: independent of the production writer and bit encoder."""
    header_length = 1024
    lines = [f"BCI2000V= 1.1 HeaderLen= {header_length} SourceCh= 2 StatevectorLen= 6 DataFormat= {data_format}",
             "[ State Vector Definition ]", "Running 1 1 0 0", "TargetCode 3 0 0 7", "EvmAttempt 32 0 2 0"]
    if extra_state:
        lines.append(extra_state)
    lines += ["[ Parameter Definition ]", "Source float SamplingRate= 200Hz",
              f"Source list ChannelNames= 2 {names}", "Source list SourceChOffset= 2 3 -2"]
    if not missing_gain:
        lines.append("Source list SourceChGain= 2 2muV 0.001mV")
    header = "\r\n".join(lines).encode("ascii")
    header += b" " * (header_length - len(header) - 4) + b"\r\n\r\n"
    payload = bytearray()
    symbol = {"int16": "h", "int32": "i", "float32": "f"}[data_format]
    for index, (first, second) in enumerate(((10, -2), (11, -1), (12, 0))):
        state = (1 | ((index + 1) << 7)).to_bytes(2, "little") + (2**31 + index).to_bytes(4, "little")
        payload += struct.pack("<" + 2 * symbol, first, second) + state
    path.write_bytes(header + payload)
    return path


def project(folder, session="session-one", seed=3, blocks=2, invalid=False,
            conditions=("me_hand_left", "me_hand_right")):
    path = Path(folder) / (session + ".csv")
    rows, start = [], 0
    for block in range(1, blocks + 1):
        for trial, condition in enumerate(conditions, 1):
            attempts = (1, 2) if invalid and block == trial == 1 else (1,)
            for attempt in attempts:
                for label, phase, offset in (("trial_start", "prepare", 0), ("phase_start", "prepare", 0),
                    ("cue_onset", "task", 500), ("task_offset", "task", 1500),
                    ("phase_end", "rest", 3250), ("trial_end", "rest", 3250)):
                    rows.append(dict(source="automatic", run="Motorik", condition=condition, block=block,
                        trial=trial, attempt=attempt, phase=phase, samples_received=start+offset,
                        label=label, protocol_version="eeg-session-2.0"))
                start += 3250
    if invalid:
        row = rows[0].copy()
        row.update(label="trial_invalidated", samples_received=start+100, reason="synthetic late invalidation")
        rows.append(row)
    pd.DataFrame(rows).to_csv(str(path) + ".events.csv", index=False)
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({"sample_index": np.arange(start), "nominal_time_s": np.arange(start)/250,
                          "host_read_utc_s": 1700000000+np.arange(start)/250})
    for index in range(8):
        frame[f"EEG {index+1}"] = rng.normal(size=start) * 10
    frame["Counter"] = np.arange(start)
    frame["Validation Indicator"] = 1
    frame["Accelerometer X"] = -.125
    frame.to_csv(path, index=False)
    meta = dict(sampling_rate_hz=250, participant_id="DEV-BCI2000", session_id=session,
                protocol_version="eeg-session-2.0", state="completed",
                device={"channels": [dict(name=f"EEG {i+1}", unit="uV", enabled=True) for i in range(8)]})
    Path(str(path)+".session.json").write_text(json.dumps(meta), encoding="utf-8")
    return path


class NativeReaderTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_independent_fixtures_calibrate_all_formats_and_bit_boundaries(self):
        for data_format in ("int16", "int32", "float32"):
            path = fixture(self.folder / (data_format+".dat"), data_format)
            source_hash = sha256(path)
            recording = read_dat(path)
            np.testing.assert_array_equal(recording.signal_uv, [[14, 0], [16, 1], [18, 2]])
            np.testing.assert_array_equal(recording.states["TargetCode"], [1, 2, 3])
            np.testing.assert_array_equal(recording.states["EvmAttempt"], 2**31 + np.arange(3))
            self.assertEqual(recording.channel_names, ["Fz", "C3"])
            self.assertEqual(recording.sampling_rate, 200)
            raw = to_mne(path)
            np.testing.assert_allclose(raw.get_data(picks="eeg"), np.array([[14, 16, 18], [0, 1, 2]]) * 1e-6)
            np.testing.assert_array_equal(raw.get_data(picks=["BCI::EvmAttempt"])[0], 2**31+np.arange(3))
            self.assertEqual(sha256(path), source_hash)

    def test_mne_fif_retains_high_integer_states_and_calibration(self):
        path = fixture(self.folder/"input.dat")
        convert(path, self.folder/"converted")
        raw = mne.io.read_raw_fif(self.folder/"converted/recording_raw.fif", preload=True, verbose="ERROR")
        np.testing.assert_array_equal(raw.get_data(picks=["BCI::EvmAttempt"])[0], 2**31+np.arange(3))
        self.assertEqual(raw.info["sfreq"], 200)
        with np.load(self.folder/"converted/states.npz", allow_pickle=False) as states:
            np.testing.assert_array_equal(states["state_002"], 2**31+np.arange(3))
        with self.assertRaises(FileExistsError):
            convert(path, self.folder/"converted")

    def test_missing_calibration_and_corrupt_layout_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "calibration"):
            read_dat(fixture(self.folder/"missing.dat", missing_gain=True))
        for extra in ("Duplicate 1 0 0 0", "Outside 8 0 6 0", "Negative 8 0 -1 0", "TargetCode 2 0 1 2"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                read_dat(fixture(self.folder/"bad.dat", extra_state=extra))
        path = fixture(self.folder/"short.dat")
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "truncated"):
            read_dat(path)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            read_dat(fixture(self.folder/"names.dat", names="Fz Fz"))

    def test_parameter_labels_percent_encoding_empty_names_and_negative_gain(self):
        params = parse_parameters(["Source list ChannelNames= { first second } Fz EEG%202 // comment",
                                   "X matrix Weights= 1 { A B } 1 2", "X string Text= Gr%C3%BC%C3%9Fe%20%25"])
        self.assertEqual(params["ChannelNames"]["values"], ["Fz", "EEG 2"])
        self.assertEqual(params["Weights"]["values"], ["1", "2"])
        self.assertEqual(params["Text"]["values"], ["Grüße %"])
        path = fixture(self.folder/"generic.dat")
        blob = path.read_bytes().replace(b"ChannelNames= 2 Fz C3", b"ChannelNames= 0      ")
        self.assertEqual(len(blob), path.stat().st_size)
        path.write_bytes(blob.replace(b"2muV", b"-2uV"))
        recording = read_dat(path)
        self.assertEqual(recording.channel_names, ["EEG 1", "EEG 2"])
        self.assertEqual(recording.signal_uv[0, 0], -14)

    def test_writer_rounding_complete_states_and_overwrite_protection(self):
        path = self.folder/"derived.dat"
        data = np.array([[1.123456789, -2], [3.5, 4]])
        values = np.array([0, 2**32-1], dtype=np.uint32)
        rounding = write_dat(path, data, 250, ["EEG 1", "C3"], {"Wide": (32, values)})
        result = read_dat(path)
        np.testing.assert_array_equal(result.states["Wide"], values)
        np.testing.assert_array_equal(result.signal_uv, data.astype(np.float32).astype(float))
        self.assertAlmostEqual(rounding, float(np.max(np.abs(result.signal_uv-data))))
        with self.assertRaises(FileExistsError):
            write_dat(path, data, 250, ["EEG 1", "C3"], {})
        for state in ((1, np.array([0, 2])), (32, np.array([-1, 0])), (1, np.array([0., 1.]))):
            with self.assertRaises(ValueError):
                write_dat(self.folder/"invalid.dat", data, 250, ["EEG 1", "C3"], {"Bad": state})
        self.assertFalse((self.folder/"invalid.dat").exists())

    def test_unknown_channel_type_needs_explicit_choice(self):
        path = fixture(self.folder/"unknown.dat", names="CustomA CustomB")
        with self.assertRaisesRegex(ValueError, "explicitly"):
            to_mne(path)
        self.assertEqual(to_mne(path, ["CustomB"]).get_channel_types(), ["eeg", "misc", "misc", "misc"])

    def test_64_bit_states_are_exact_in_npz_and_not_silently_rounded_for_fif(self):
        path = self.folder/"wide.dat"
        lines = ["BCI2000V= 1.1 HeaderLen= 1024 SourceCh= 1 StatevectorLen= 8 DataFormat= float32",
                 "[ State Vector Definition ]", "Wide 64 0 0 0", "[ Parameter Definition ]",
                 "Source float SamplingRate= 250Hz", "Source list ChannelNames= 1 EEG%201",
                 "Source list SourceChGain= 1 1muV", "Source list SourceChOffset= 1 0"]
        header = "\r\n".join(lines).encode("ascii")
        header += b" "*(1024-len(header)-4)+b"\r\n\r\n"
        path.write_bytes(header+struct.pack("<fQ",1.25,2**63+1))
        self.assertEqual(int(read_dat(path).states["Wide"][0]),2**63+1)
        with self.assertRaisesRegex(ValueError,"precision"):
            to_mne(path)
        convert(path,self.folder/"wide-export",save_fif=False)
        with np.load(self.folder/"wide-export/states.npz",allow_pickle=False) as data:
            self.assertEqual(int(data["state_000"][0]),2**63+1)


class ProjectExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = project(self.folder, invalid=True)

    def test_valid_windows_folds_context_and_originals(self):
        original = {p: sha256(p) for p in self.folder.iterdir()}
        report = prepare([self.path], self.folder/"export", runs=["ME_HandSide"])
        contrast = report["contrasts"]["ME_HandSide"]
        self.assertEqual(len(contrast["files"]), 2)
        self.assertEqual(len(contrast["folds"]), 2)
        self.assertEqual({e["reason"] for e in report["sources"][0]["exclusions"]}, {"invalidated"})
        for fold in contrast["folds"]:
            self.assertFalse(set(fold["train"]) & set(fold["test"]))
        full = pd.read_csv(self.path)
        for entry in contrast["files"]:
            dat = self.folder/"export"/entry["file"]
            result = read_dat(dat)
            a, b = entry["original_start_sample"], entry["original_stop_sample"]
            np.testing.assert_allclose(result.signal_uv, full[[f"EEG {i+1}" for i in range(8)]].to_numpy()[a:b], rtol=1e-7)
            self.assertEqual(int(result.states["EvmAnalysis"].sum()), 2)
            self.assertEqual(int(result.states["EvmWindow"].sum()), 1500)
            self.assertEqual(result.parameters["SampleBlockSize"]["values"], ["1"])
            if entry["block"] == 1:
                self.assertTrue(np.all(result.states["EvmStatus"][:3250] == 2))
                self.assertFalse(result.states["TargetCode"][:3250].any())
                self.assertEqual(result.states["EvmAttempt"][3250], 2)
            raws = [loader(dat) for loader in (view_eeg.load_recording, other_viewer.load_recording)]
            np.testing.assert_array_equal(raws[0].get_data(), raws[1].get_data())
            self.assertEqual(list(raws[0].annotations.description), list(raws[1].annotations.description))
            if entry["block"] == 1:
                self.assertTrue(any("status=invalid" in label for label in raws[0].annotations.description))
                fif = self.folder/"all_states_raw.fif"
                raws[0].save(fif,fmt="double",verbose="ERROR")
                restored = mne.io.read_raw_fif(fif,preload=True,verbose="ERROR")
                self.assertEqual(restored.ch_names,raws[0].ch_names)
                np.testing.assert_array_equal(restored.get_data(),raws[0].get_data())
        for path, checksum in original.items():
            self.assertEqual(sha256(path), checksum)
        with self.assertRaises(FileExistsError):
            prepare([self.path], self.folder/"export")

    def test_sidecar_mismatch_and_missing_quality_are_not_silently_accepted(self):
        report = prepare([self.path], self.folder/"export", runs=["ME_HandSide"])
        dat = self.folder/"export"/report["contrasts"]["ME_HandSide"]["files"][0]["file"]
        events = dat.parent/"source.events.csv"
        events.write_bytes(events.read_bytes()+b"\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            to_mne(dat)
        frame = pd.read_csv(self.path).drop(columns="Validation Indicator")
        frame.to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, "required"):
            load_project(self.path)

    def test_quality_marker_and_invalid_samples_exclude_whole_attempts(self):
        frame = pd.read_csv(self.path)
        frame.loc[3250+630, "Validation Indicator"] = 0
        frame.to_csv(self.path, index=False)
        loaded = load_project(self.path)
        self.assertFalse(((loaded["windows"].block == 1) & (loaded["windows"].trial == 1)).any())
        report = prepare([self.path], self.folder/"quality", runs=["ME_HandSide"])
        self.assertIsNotNone(report["contrasts"]["ME_HandSide"]["evaluation_unavailable"])
        events = pd.read_csv(str(self.path)+".events.csv")
        events = pd.concat([events, pd.DataFrame([dict(source="manual", label="ground placed", samples_received=10000)])])
        events.to_csv(str(self.path)+".events.csv", index=False)
        loaded = load_project(self.path, marker="ground placed", settle_seconds=.001)
        self.assertTrue((loaded["windows"].block == 2).all())

    def test_separate_sessions_duplicate_detection_and_no_invented_identity(self):
        second = project(self.folder, session="session-two", seed=4)
        report = prepare([self.path, second], self.folder/"two", runs=["ME_HandSide"])
        self.assertEqual(report["split"], "leave-one-session-out")
        self.assertEqual(len(report["contrasts"]["ME_HandSide"]["folds"]), 2)
        for fold in report["contrasts"]["ME_HandSide"]["folds"]:
            self.assertEqual(len({Path(name).parts[0] for name in fold["test"]}), 1)
            self.assertFalse({Path(n).parts[0] for n in fold["train"]} & {Path(n).parts[0] for n in fold["test"]})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare([self.path, self.path], self.folder/"duplicate")
        copied = self.folder/"copy.csv"
        copied.write_bytes(self.path.read_bytes().replace(b"1700000000", b"1700000100"))
        shutil.copyfile(str(self.path)+".events.csv",str(copied)+".events.csv")
        copy_meta = json.loads(Path(str(self.path)+".session.json").read_text())
        copy_meta["session_id"] = "renamed-copy"
        Path(str(copied)+".session.json").write_text(json.dumps(copy_meta))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare([self.path,copied],self.folder/"duplicate-values")
        meta_path = Path(str(second)+".session.json")
        meta = json.loads(meta_path.read_text())
        meta["participant_id"] = "DEV-OTHER"
        meta_path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, "one participant"):
            prepare([self.path, second], self.folder/"mixed")

    def test_explicit_oscar_selection_and_units_are_validated(self):
        with self.assertRaisesRegex(ValueError, "OSCAR"):
            prepare([self.path], self.folder/"oscar", signal="oscar")
        meta_path = Path(str(self.path)+".session.json")
        meta = json.loads(meta_path.read_text())
        meta["device"]["channels"][0]["unit"] = "unknown"
        meta_path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, "unit"):
            load_project(self.path)
        self.assertFalse((self.folder/"oscar").exists())

    def test_confirmed_oscar_preserves_source_sample_positions(self):
        frame = pd.read_csv(self.path)
        count = len(frame)
        clean = frame.copy()
        eeg_names = [f"EEG {i+1}" for i in range(8)]
        clean[eeg_names] *= .25
        clean_path = Path(str(self.path)+".oscar.csv")
        clean.to_csv(clean_path, index=False)
        tail = frame.iloc[-83:].copy()
        tail["sample_index"] = np.arange(count, count+83)
        tail["nominal_time_s"] = tail.sample_index/250
        tail["Counter"] = tail.sample_index
        pd.concat([frame, tail]).to_csv(self.path, index=False)
        Path(str(self.path)+".processing.json").write_text(json.dumps(dict(schema_version=1, mode="oscar",
            state="complete", sampling_rate_hz=250, raw_file=self.path.name, oscar_file=clean_path.name,
            oscar_samples=count, oscar_delay_samples=83)))
        output = self.folder/"clean"
        report = prepare([self.path], output, signal="auto", runs=["ME_HandSide"])
        self.assertEqual(report["sources"][0]["signal"], "oscar")
        entry = report["contrasts"]["ME_HandSide"]["files"][0]
        recording = read_dat(output/entry["file"])
        a,b = entry["original_start_sample"],entry["original_stop_sample"]
        np.testing.assert_allclose(recording.signal_uv, clean[eeg_names].iloc[a:b], rtol=1e-7)
        self.assertEqual(np.flatnonzero(recording.states["EvmAnalysis"])[0], 3250+1375-1)

    def test_fractional_markers_counter_gaps_and_channel_reordering(self):
        frame = pd.read_csv(self.path)
        frame.loc[3250+700:, "Counter"] += 1
        frame.to_csv(self.path, index=False)
        loaded = load_project(self.path)
        self.assertFalse(((loaded["windows"].block == 1) & (loaded["windows"].trial == 1)).any())
        fields = frame.columns.tolist()
        first,second = fields.index("EEG 1"), fields.index("EEG 2")
        fields[first],fields[second] = fields[second],fields[first]
        frame[fields].to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, "channel order"):
            load_project(self.path)
        frame.to_csv(self.path, index=False)
        events_path = Path(str(self.path)+".events.csv")
        events = pd.read_csv(events_path)
        events["samples_received"] = events.samples_received.astype(float)
        events.loc[0,"samples_received"] = .5
        events.to_csv(events_path, index=False)
        with self.assertRaisesRegex(ValueError, "integers"):
            load_project(self.path)

    def test_legacy_export_keeps_original_labels(self):
        events_path = Path(str(self.path)+".events.csv")
        events = pd.read_csv(events_path)
        events["condition"] = events.condition.replace({"me_hand_left":"arms", "me_hand_right":"legs"})
        events["protocol_version"] = "eeg-session-1.0"
        events.to_csv(events_path,index=False)
        meta_path=Path(str(self.path)+".session.json")
        meta=json.loads(meta_path.read_text())
        meta["protocol_version"]="eeg-session-1.0"
        meta_path.write_text(json.dumps(meta))
        # The legacy Motorik contrast has a third blink class; missing it must not be relabeled.
        with self.assertRaisesRegex(ValueError,"complete classes"):
            prepare([self.path],self.folder/"old",runs=["Motorik"])
        with self.assertRaisesRegex(ValueError,"protocol-specific"):
            prepare([self.path],self.folder/"wrong-contrast",runs=["ME_HandSide"])
        complete = project(self.folder, session="legacy", conditions=("arms", "legs", "blink"))
        event_path = Path(str(complete)+".events.csv")
        events = pd.read_csv(event_path)
        events["protocol_version"] = "eeg-session-1.0"
        events.to_csv(event_path, index=False)
        meta_path = Path(str(complete)+".session.json")
        meta = json.loads(meta_path.read_text())
        meta["protocol_version"] = "eeg-session-1.0"
        meta_path.write_text(json.dumps(meta))
        report = prepare([complete], self.folder/"legacy-complete", runs=["Motorik"])
        self.assertEqual(set(report["contrasts"]["Motorik"]["classes"].values()), {"arms", "legs", "blink"})
        self.assertEqual(len(report["contrasts"]["Motorik"]["folds"]), 2)

    def test_failed_exports_publish_no_partial_directory(self):
        with self.assertRaisesRegex(ValueError,"complete classes"):
            prepare([self.path],self.folder/"missing",runs=["MI_Bilateral"])
        self.assertFalse((self.folder/"missing").exists())
        self.assertFalse(list(self.folder.glob('.bci2000-*')))

    def test_both_cli_entry_points_use_native_rate_and_preserve_states_in_fif(self):
        path = fixture(self.folder/"input.dat")
        destination = self.folder/"native_raw.fif"
        root = Path(__file__).resolve().parents[1]
        commands = [[str(root/"view_eeg.py"), str(path), "--no-show", "--save-fif", str(destination)],
                    [str(root/"analysis/view_eeg.py"), str(path), "--no-show"],
                    ["-m", "analysis.view_eeg", str(path), "--no-show"]]
        for command in commands:
            result = subprocess.run([sys.executable, *command], cwd=root, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        raw = mne.io.read_raw_fif(destination, preload=True, verbose="ERROR")
        self.assertEqual(raw.info["sfreq"], 200)
        np.testing.assert_array_equal(raw.get_data(picks=["BCI::EvmAttempt"])[0], 2**31+np.arange(3))


class OfflineChainTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = fixture(self.folder/"input with spaces.dat")
        self.tools = self.folder/"BCI tools with spaces"
        self.tools.mkdir()
        for name, body in (("bci_dat2stream", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"),
                           ("bci_stream2table", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"),
                           ("bci_fail", "import sys; sys.exit(7)"),
                           ("bci_sleep", "import time; time.sleep(5)")):
            (self.tools/name).write_text(body)
        real_popen = subprocess.Popen
        self.popen = patch("analysis.bci2000_offline.subprocess.Popen",
                           side_effect=lambda command, **kwargs: real_popen([sys.executable, *command], **kwargs))

    def test_binary_transport_and_diagnostics_with_synthetic_processes(self):
        with self.popen:
            result = run_chain(self.path, self.tools, self.folder/"result")
        self.assertEqual(result["state"], "complete")
        self.assertEqual((self.folder/"result/data.tsv").read_bytes(), self.path.read_bytes())
        self.assertEqual(result["returncodes"], [0, 0])
        self.assertIsNotNone(doctor(self.tools)["tools"]["bci_dat2stream"])
        with self.assertRaises(ValueError):
            run_chain(self.path, self.tools, self.folder/"unsafe", filters=["Operator"])
        self.assertFalse((self.folder/"unsafe").exists())

    def test_native_failures_and_timeouts_never_publish_a_complete_table(self):
        for name, timeout in (("bci_fail", 10), ("bci_sleep", .1)):
            output = self.folder/name
            with self.popen, self.assertRaises((RuntimeError, TimeoutError)):
                run_chain(self.path, self.tools, output, filters=[name], timeout=timeout)
            self.assertFalse((output/"data.tsv").exists())
            self.assertEqual(json.loads((output/"run.json").read_text())["state"], "failed")


if __name__ == "__main__":
    unittest.main()
