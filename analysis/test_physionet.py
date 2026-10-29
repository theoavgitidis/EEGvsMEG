"""Synthetic/offline regression tests for the public-data download and label audit."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analysis import audit_physionet as audit
from analysis import download_physionet as download


def synthetic_edf(path, fs=160, unit="uV", right_duration=4, flat=False):
    """Small EDF+C fixture with synthetic signals and four embedded annotations."""
    labels = ["Fz..", "C3..", "Cz..", "C4..", "Pz..", "Po7.", "Oz..", "Po8."]
    labels += [f"X{i:02d}." for i in range(56)] + ["EDF Annotations"]
    count, records = len(labels), 11
    def field(value, width):
        return str(value).encode("ascii").ljust(width)
    header = b"".join(field(v, w) for v, w in [
        (0, 8), ("SYNTHETIC", 80), ("SYNTHETIC", 80), ("01.01.00", 8), ("00.00.00", 8),
        (256 * (count + 1), 8), ("EDF+C", 44), (records, 8), (1, 8), (count, 4)])
    for width, values in [(16, labels), (80, [""] * count), (8, [unit] * 64 + [""]),
            (8, [-1000] * count), (8, [1000] * count), (8, [-32768] * count),
            (8, [32767] * count), (80, [""] * count), (8, [fs] * 64 + [128]), (32, [""] * count)]:
        header += b"".join(field(v, width) for v in values)
    tal = b"+0\x14\x14\x00"
    for onset, duration, code in [(0, 1, "T0"), (1, 4, "T1"), (5, 1, "T0"), (6, right_duration, "T2")]:
        tal += f"+{onset}\x15{duration}\x14{code}\x14\x00".encode("ascii")
    wave = (1000 * np.sin(2 * np.pi * 10 * np.arange(records * fs) / fs)).astype("<i2")
    if flat:
        wave[:] = 0
    data = b""
    for record in range(records):
        data += wave[record * fs:(record + 1) * fs].tobytes() * 64
        data += (tal if record == 0 else f"+{record}\x14\x14\x00".encode("ascii")).ljust(256, b"\x00")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + data)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_selection_contains_only_executed_unilateral_runs_and_sidecars(self):
        paths = download.selected_files([2, 1, 1])
        self.assertEqual(len(paths), 12)
        self.assertEqual(paths[:2], ["S001/S001R03.edf", "S001/S001R03.edf.event"])
        self.assertFalse(any(f"R{r:02d}" in p for r in (4, 5, 8, 12) for p in paths))
        for invalid in ([], [0], [110]):
            with self.assertRaises(ValueError):
                download.selected_files(invalid)

    def test_atomic_download_checks_hash_and_reuses_existing_file_offline(self):
        content = b"SYNTHETIC"
        expected = hashlib.sha256(content).hexdigest()
        with patch.object(download, "urlopen", return_value=io.BytesIO(content)):
            result = download.fetch_file(self.root, "S001/test.edf", expected)
        self.assertEqual(result["bytes"], len(content))
        with patch.object(download, "urlopen", side_effect=AssertionError("No network allowed")):
            self.assertEqual(download.fetch_file(self.root, "S001/test.edf", expected, True), result)
        self.assertFalse(list(self.root.rglob("*.part")))

    def test_bad_download_is_never_published(self):
        with patch.object(download, "urlopen", side_effect=lambda *a, **k: io.BytesIO(b"bad")), \
                patch.object(download.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                download.fetch_file(self.root, "test.edf", "0" * 64)
        self.assertFalse((self.root / "test.edf").exists())
        self.assertFalse(list(self.root.glob("*.part")))

    def test_existing_corrupt_original_is_preserved(self):
        path = self.root / "test.edf"
        path.write_bytes(b"unchanged")
        with patch.object(download, "urlopen", side_effect=AssertionError("No network allowed")):
            with self.assertRaisesRegex(ValueError, "left unchanged"):
                download.fetch_file(self.root, path.name, "0" * 64)
            with self.assertRaises(FileNotFoundError):
                download.fetch_file(self.root, "missing.edf", "0" * 64, True)
        self.assertEqual(path.read_bytes(), b"unchanged")

    def test_checksum_manifest_is_pinned(self):
        path = self.root / "SHA256SUMS.txt"
        path.write_text("0" * 64 + " S001/test.edf\n")
        with self.assertRaisesRegex(ValueError, "pinned version"):
            download.read_checksums(path)


class LabelAuditTests(unittest.TestCase):
    def test_same_event_code_cannot_be_reused_for_imagery_or_bilateral_runs(self):
        self.assertEqual(audit.map_label(3, "T1"), "me_hand_left")
        self.assertEqual(audit.map_label(11, "T2"), "me_hand_right")
        for run in (1, 4, 5, 6, 8, 12, 13, 14):
            with self.assertRaises(ValueError):
                audit.map_label(run, "T1")
        with self.assertRaises(ValueError):
            audit.map_label(3, "T3")

    def test_short_tasks_are_excluded_and_rest_is_not_a_selected_window(self):
        rows, issues = audit.annotation_rows(1, 3, [0, 1, 5, 6], [1, 4, 1, 3],
            ["T0", "T1", "T0", "T2"], 11, 160)
        self.assertFalse(issues)
        self.assertEqual([r["label"] for r in rows if r["eligible_task_window"]], ["me_hand_left"])
        self.assertEqual(rows[-1]["exclusion_reasons"], ["task_shorter_than_3.5s"])
        self.assertEqual(rows[1]["candidate_window_start_s"], 1.5)
        self.assertEqual(rows[1]["candidate_window_stop_s"], 4.5)
        self.assertTrue(all(r["subject_id"] == "physionet:S001" for r in rows))

    def test_bad_annotation_boundaries_and_missing_classes(self):
        _, issues = audit.annotation_rows(1, 3, [0, 1], [2, 4], ["T0", "T1"], 4, 160)
        self.assertEqual(set(issues), {"annotation_gap_or_overlap", "annotation_outside_recording", "missing_class"})
        for onset, duration in [(float("nan"), 4), (1, float("inf")), (-1, 4), (0, 0)]:
            with self.assertRaises(ValueError):
                audit.annotation_rows(1, 3, [onset], [duration], ["T1"], 11, 160)

    def test_complete_offline_audit_keeps_original_samples_and_label_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            for run in download.RUNS:
                path = source / f"S001/S001R{run:02d}.edf"
                synthetic_edf(path)
                Path(str(path) + ".event").write_bytes(b"SYNTHETIC sidecar")
            entries = {str(p.relative_to(source)): download.sha256(p) for p in source.rglob("*") if p.is_file()}
            checksum = source / "SHA256SUMS.txt"
            checksum.write_text("".join(f"{digest} {name}\n" for name, digest in entries.items()))
            with patch.object(download, "CHECKSUM_SHA256", download.sha256(checksum)), redirect_stdout(io.StringIO()):
                report = audit.audit(root, [1], root / "audit")
                with self.assertRaisesRegex(ValueError, "outside"):
                    audit.audit(root, [1], source / "audit")
            self.assertEqual(report["summary"]["recordings_without_structural_issues"], 3)
            self.assertEqual(report["summary"]["eligible_task_window_counts"], {"me_hand_left": 3, "me_hand_right": 3})
            self.assertEqual(report["summary"]["subjects_with_three_structurally_usable_runs"], [1])
            self.assertEqual(report["recordings"][0]["target_channel_indices_zero_based"], list(range(8)))
            self.assertEqual(report["recordings"][0]["unannotated_tail_s"], 1)
            self.assertEqual(entries, {name: download.sha256(source / name) for name in entries})
            self.assertEqual(json.loads((root / "audit/audit.json").read_text())["runs"], [3, 7, 11])
            self.assertIn("me_hand_left", (root / "audit/annotations.csv").read_text())

    def test_unexpected_units_rate_flat_signal_and_corruption_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            path = source / "S001/S001R03.edf"
            sidecar = Path(str(path) + ".event")
            for settings, expected in [({"unit": "mV"}, "unexpected_physical_units"),
                    ({"fs": 128}, "unexpected_sampling_rate"), ({"flat": True}, "flat_channel")]:
                synthetic_edf(path, **settings)
                sidecar.write_bytes(b"SYNTHETIC")
                checksums = {str(p.relative_to(source)): download.sha256(p) for p in (path, sidecar)}
                result = audit.audit_recording(source, 1, 3, checksums)
                self.assertIn(expected, result["issues"])
                self.assertFalse(any(row["eligible_task_window"] for row in result["rows"]))
            sidecar.write_bytes(b"CORRUPTED")
            result = audit.audit_recording(source, 1, 3, checksums)
            self.assertIn("Checksum mismatch", result["issues"][0])

    def test_edf_truncation_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.edf"
            synthetic_edf(path)
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaisesRegex(ValueError, "size"):
                audit.edf_header(path)


if __name__ == "__main__":
    unittest.main()
