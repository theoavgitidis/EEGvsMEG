"""Regression tests for unit conversion, prepared data and EDF-to-training import."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis import download_physionet as download
from analysis.movement_features import HISTORY, window_features
from analysis.physionet_dataset import FILES, IMPORT_CONFIG, convert_history, load_prepared, prepare


def synthetic_prepared(folder, participants=(1, 2, 3)):
    """Independent synthetic participants with recognizable lateralized bandpower."""
    folder = Path(folder)
    folder.mkdir()
    rows, histories, sources = [], [], []
    time = np.arange(HISTORY) / 250
    for person in participants:
        for run in download.RUNS:
            recording = f"S{person:03d}R{run:02d}"
            source_file = f"S{person:03d}/{recording}.edf"
            for trial, label, code in [(1, "me_hand_left", "T1"), (3, "me_hand_right", "T2")]:
                amplitudes = [2, 2, 2, 2, 12, 12, 12, 12]
                if label.endswith("right"):
                    amplitudes = amplitudes[::-1]
                history = np.sin(2 * np.pi * 10 * time[:, None] + person / 10) * amplitudes
                history += .2 * np.sin(2 * np.pi * 20 * time[:, None] + run)
                histories.append(history)
                rows.append({"participant_id": f"physionet:S{person:03d}", "session_id": recording,
                    "session_key": f"physionet:{recording}", "trial_key": f"physionet:{recording}:E{trial:03d}",
                    "run": run, "block": run, "trial": trial, "source_code": code, "label": label,
                    "source_file": source_file, "source_onset_s": float(trial), "source_duration_s": 4.0,
                    "source_start_sample": trial * 160, "source_stop_sample_exclusive": trial * 160 + 560,
                    "history_index": len(rows), "cue_rounding_error_s": 0.0,
                    "label_source": "SYNTHETIC"})
            sources.append({"file": source_file, "participant_id": f"physionet:S{person:03d}",
                "session_id": recording, "imported_trials": 2, "issues": [],
                "data_sha256": hashlib.sha256(recording.encode()).hexdigest(), "signal": "raw",
                "movement_version": "SYNTHETIC", "excluded_task_windows": 0})
    np.save(folder / FILES[0], histories, allow_pickle=False)
    np.save(folder / FILES[1], [window_features(history) for history in histories], allow_pickle=False)
    pd.DataFrame(rows).to_csv(folder / FILES[2], index=False)
    manifest = {"schema_version": 1, "input_domain": "physionet-executed-fists",
        "import_config": IMPORT_CONFIG, "checksum_manifest_sha256": download.CHECKSUM_SHA256,
        "sources": sources, "limitations": ["SYNTHETIC test data"],
        "summary": {"trials": len(rows)}, "files_sha256": {name: download.sha256(folder / name) for name in FILES}}
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return folder


class PreparedTests(unittest.TestCase):
    def test_voltage_and_time_conversion_preserve_channel_order_and_input(self):
        time = np.arange(560) / 160
        source = 20e-6 * np.sin(2 * np.pi * 10 * time[:, None]) * np.arange(1, 9)
        original = source.copy()
        converted = convert_history(source)
        self.assertEqual(converted.shape, (875, 8))
        expected = 20 * np.sin(2 * np.pi * 10 * np.arange(875) / 250)
        np.testing.assert_allclose(converted[100:-100, 0], expected[100:-100], atol=.04, rtol=0)
        np.testing.assert_allclose(converted, converted[:, :1] * np.arange(1, 9), atol=1e-10)
        np.testing.assert_array_equal(source, original)
        with self.assertRaises(ValueError):
            convert_history(source[:-1])
        source[0, 0] = np.nan
        with self.assertRaises(ValueError):
            convert_history(source)

    def test_load_and_detect_changed_or_reordered_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_prepared(Path(folder) / "dataset")
            rows, x, manifest = load_prepared(path)
            self.assertEqual(x.shape, (18, 16))
            self.assertEqual(rows.participant_id.nunique(), 3)
            data = pd.read_csv(path / "windows.csv").iloc[::-1]
            data.to_csv(path / "windows.csv", index=False)
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_prepared(path)
            manifest["files_sha256"]["windows.csv"] = download.sha256(path / "windows.csv")
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "alignment"):
                load_prepared(path)

    def test_wrong_config_person_identity_or_stale_features_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_prepared(Path(folder) / "dataset")
            original = (path / "manifest.json").read_text()
            manifest = json.loads(original)
            manifest["import_config"]["output_unit"] = "V"
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "contract"):
                load_prepared(path)
            (path / "manifest.json").write_text(original)
            data = pd.read_csv(path / "windows.csv")
            data.loc[0, "participant_id"] = "physionet:S002"
            data.to_csv(path / "windows.csv", index=False)
            manifest = json.loads(original)
            manifest["files_sha256"]["windows.csv"] = download.sha256(path / "windows.csv")
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "identity"):
                load_prepared(path)
        with tempfile.TemporaryDirectory() as folder:
            path = synthetic_prepared(Path(folder) / "dataset")
            features = np.load(path / "features.npy", allow_pickle=False)
            features[0, 0] += 10
            np.save(path / "features.npy", features, allow_pickle=False)
            manifest = json.loads((path / "manifest.json").read_text())
            manifest["files_sha256"]["features.npy"] = download.sha256(path / "features.npy")
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "features do not match"):
                load_prepared(path)


@unittest.skipUnless(importlib.util.find_spec("mne"), "EDF preparation tests require the existing MNE environment")
class EDFImportTests(unittest.TestCase):
    def make_sources(self, folder, fs=160):
        from analysis.test_physionet import synthetic_edf
        source = Path(folder) / "source"
        for run in download.RUNS:
            path = source / f"S001/S001R{run:02d}.edf"
            synthetic_edf(path, fs=fs)
            content = bytearray(path.read_bytes())
            content[88:168] = f"SYNTHETIC run {run}".encode().ljust(80)
            # Reverse named target positions and give each physical signal a different amplitude.
            original_labels = [content[256 + i * 16:256 + (i + 1) * 16] for i in range(8)]
            for i, label in enumerate(reversed(original_labels)):
                content[256 + i * 16:256 + (i + 1) * 16] = label
            header_size = int(content[184:192])
            record_size = (64 * fs + 128) * 2
            wave = (100 * np.sin(2 * np.pi * 10 * np.arange(11 * fs) / fs)).astype("<i2")
            for record in range(11):
                for channel in range(64):
                    begin = header_size + record * record_size + channel * fs * 2
                    content[begin:begin + fs * 2] = (wave[record * fs:(record + 1) * fs]
                        * (channel + 1)).astype("<i2").tobytes()
            path.write_bytes(content)
            Path(str(path) + ".event").write_bytes(b"SYNTHETIC event sidecar")
        checksums = {str(p.relative_to(source)): download.sha256(p) for p in source.rglob("*") if p.is_file()}
        checksum = source / "SHA256SUMS.txt"
        checksum.write_text("".join(f"{digest} {name}\n" for name, digest in checksums.items()))
        return source, checksums, download.sha256(checksum)

    def test_edf_end_to_end_import_provenance_and_unchanged_sources(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            source, checksums, digest = self.make_sources(folder)
            output = Path(folder) / "prepared"
            with patch.object(download, "CHECKSUM_SHA256", digest):
                manifest = prepare(folder, output, [1])
            rows, x, restored = load_prepared(output)
            self.assertEqual(manifest, restored)
            self.assertEqual(x.shape, (6, 16))
            self.assertEqual(manifest["summary"]["class_counts"], {"me_hand_left": 3, "me_hand_right": 3})
            self.assertEqual(set(rows.source_start_sample), {160, 960})
            self.assertEqual(set(rows.source_stop_sample_exclusive), {720, 1520})
            self.assertNotIn("rest", set(rows.label))
            source_wave = (100 * np.sin(2 * np.pi * 10 * np.arange(160, 720) / 160)).astype("int16")
            expected_digital = source_wave[:, None] * np.arange(8, 0, -1)
            expected_volts = ((expected_digital + 32768) * 2000 / 65535 - 1000) * 1e-6
            np.testing.assert_allclose(np.load(output / "histories_uv.npy")[0],
                                       convert_history(expected_volts), atol=1e-9)
            for name, expected in checksums.items():
                self.assertEqual(download.sha256(source / name), expected)
            with self.assertRaises(FileExistsError):
                prepare(folder, output, [1])
            with self.assertRaisesRegex(ValueError, "outside"):
                prepare(folder, source / "new-output", [1])

    def test_bad_sampling_or_missing_sidecar_cannot_produce_a_dataset(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            _, _, digest = self.make_sources(folder, fs=128)
            output = Path(folder) / "prepared"
            with patch.object(download, "CHECKSUM_SHA256", digest):
                with self.assertRaisesRegex(ValueError, "No eligible"):
                    prepare(folder, output, [1])
            self.assertFalse(output.exists())
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            source, _, digest = self.make_sources(folder)
            (source / "S001/S001R03.edf.event").unlink()
            with patch.object(download, "CHECKSUM_SHA256", digest):
                with self.assertRaisesRegex(ValueError, "Missing, corrupt"):
                    prepare(folder, Path(folder) / "prepared", [1])


if __name__ == "__main__":
    unittest.main()
