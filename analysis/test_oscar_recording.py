"""Timing and file integrity tests, including an optional real OSCAR model run."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from acquisition.oscar_worker import DualWriter, HEADER, UNITS, build_pipeline
from analysis.recording_files import resolve_recording


class OscarFilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic geprüft.csv"
        self.path.write_text(",".join(HEADER) + "\n", encoding="utf-8")
        Path(str(self.path) + ".oscar.csv").write_text(",".join(HEADER) + "\n", encoding="utf-8")
        self.metadata = dict(schema_version=1, mode="oscar", state="complete", sampling_rate_hz=250,
                             raw_file=self.path.name, oscar_file=self.path.name + ".oscar.csv",
                             oscar_samples=10, oscar_delay_samples=83)
        self.meta_path = Path(str(self.path) + ".processing.json")
        self.save_meta()

    def save_meta(self):
        self.meta_path.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_auto_and_explicit_raw_use_original_events(self):
        selected = resolve_recording(self.path)
        self.assertEqual(selected.signal, "oscar")
        self.assertEqual(selected.events, Path(str(self.path) + ".events.csv"))
        self.assertEqual(resolve_recording(selected.data, "raw").data, self.path)
        selected.validate_length(10)
        with self.assertRaisesRegex(ValueError, "length"):
            selected.validate_length(9)

    def test_incomplete_oscar_never_silently_falls_back(self):
        for state in ("preparing", "recording", "failed"):
            self.metadata["state"] = state
            self.save_meta()
            with self.assertRaisesRegex(ValueError, "confirmed"):
                resolve_recording(self.path)
            self.assertEqual(resolve_recording(self.path, "raw").data, self.path)

    def test_missing_or_unrelated_output_is_refused(self):
        self.metadata["oscar_file"] = "../another.csv"
        self.save_meta()
        with self.assertRaises(ValueError):
            resolve_recording(self.path)
        self.metadata["oscar_file"] = self.path.name + ".oscar.csv"
        self.save_meta()
        Path(str(self.path) + ".oscar.csv").unlink()
        with self.assertRaises(ValueError):
            resolve_recording(self.path)

    def test_legacy_session_keeps_raw_default(self):
        self.meta_path.unlink()
        self.assertEqual(resolve_recording(self.path).signal, "raw")
        with self.assertRaises(ValueError):
            resolve_recording(self.path, "oscar")


class DualWriterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.csv"

    def test_delay_removes_startup_without_shifting_markers(self):
        writer = DualWriter(self.path)
        raw = np.arange(340, dtype=float).reshape(20, 17)
        raw[:, 15] = np.arange(100, 120)
        clean = np.vstack((np.zeros((3, 17)), raw[:-3]))
        clean[3:, :8] *= .5
        writer.submit("raw", raw)
        writer.submit("clean", clean, 3)
        writer.close()
        self.assertEqual((writer.raw_count, writer.clean_count), (20, 17))
        self.assertTrue(writer.ready.is_set())
        with self.path.open() as f:
            original = list(csv.DictReader(f))
        with writer.clean_path.open() as f:
            corrected = list(csv.DictReader(f))
        for index, row in enumerate(corrected):
            self.assertEqual(int(row["sample_index"]), index)
            self.assertEqual(row["Counter"], original[index]["Counter"])
            self.assertEqual(row["host_read_utc_s"], original[index]["host_read_utc_s"])
            self.assertEqual(float(row["EEG 1"]), float(original[index]["EEG 1"]) * .5)

    def test_misaligned_auxiliary_channels_fail_closed(self):
        writer = DualWriter(self.path)
        raw = np.zeros((10, 17)); raw[:, 15] = np.arange(10)
        writer.submit("raw", raw)
        writer.submit("clean", raw, 3)  # deliberately undelayed Counter
        with self.assertRaisesRegex(RuntimeError, "alignment"):
            writer.close()

    def test_gaps_and_nonfinite_samples_are_not_hidden(self):
        for kind in ("gap", "nan"):
            with self.subTest(kind=kind):
                writer = DualWriter(self.path.with_name(kind + ".csv"))
                raw = np.zeros((10, 17)); raw[:, 15] = np.arange(10)
                if kind == "gap":
                    raw[5:, 15] += 1
                else:
                    raw[0, 0] = np.nan
                writer.submit("raw", raw)
                with self.assertRaises(RuntimeError):
                    writer.close()

    def test_no_overwrite(self):
        writer = DualWriter(self.path)
        writer.close()
        with self.assertRaises(FileExistsError):
            DualWriter(self.path)


@unittest.skipUnless(importlib.util.find_spec("gpype"), "Optional pinned vendor packages are not installed")
class VendorOscarTest(unittest.TestCase):
    def test_actual_model_preserves_counter_alignment_on_synthetic_source(self):
        import gpype as gp
        from gpype.common._private.channels import wrap_time, stamp_clock

        class SyntheticDevice:
            serial_number = "SYNTHETIC-TEST-ONLY"
            def start(self, **kwargs): pass
            def stop(self): pass
            def close(self): pass

        class SyntheticHybridBlack(gp.HybridBlack):
            def _connect(self):
                self._device = SyntheticDevice()

            def _acquisition_function(self):
                # Driver substitute only. Real g.Pype entitlement and OSCAR remain active.
                for index in range(125):
                    if not self._running:
                        break
                    frame = np.zeros((4, 18), dtype=np.float32)
                    frame[:, :8] = 10 * np.sin((index * 4 + np.arange(4))[:, None] / 10)
                    frame[:, 15] = 100 + index * 4 + np.arange(4)
                    frame[:, 16] = 1
                    frame[:, 17] = wrap_time(stamp_clock())
                    self._current_frame = frame
                    self.cycle()
                    time.sleep(.016)

        with tempfile.TemporaryDirectory() as temp:
            writer = DualWriter(Path(temp) / "vendor_synthetic.csv")
            with patch.object(gp, "HybridBlack", SyntheticHybridBlack):
                pipeline, source = build_pipeline(gp, writer, "SYNTHETIC-TEST-ONLY")
            try:
                pipeline.start()
                self.assertTrue(writer.ready.wait(15), writer.error)
                time.sleep(.2)
                measured_delay = source.oscar_delay_samples
            finally:
                pipeline.close()
                writer.close()
            self.assertIsNone(writer.error)
            self.assertGreater(writer.clean_count, 0)
            # close() may stop between the raw tap and the downstream sink;
            # this tail is retained as raw, never presented as cleaned EEG.
            self.assertGreaterEqual(writer.raw_count - writer.clean_count, writer.delay)
            self.assertEqual(writer.delay, measured_delay)

    def test_worker_ready_stop_drain_and_complete_metadata(self):
        import os
        from types import SimpleNamespace
        from collections import namedtuple
        import gpype as gp
        from gpype.common._private.channels import wrap_time, stamp_clock
        from acquisition.oscar_worker import NAMES, record

        Channel = namedtuple("Channel", "name unit enabled")
        class Device:
            serial_number = "SYNTHETIC-TEST-ONLY"
            def start(self, **kwargs): pass
            def close(self): pass
            def stop(self): pass
            def get_configuration(self):
                return [Channel(name, unit, True) for name, unit in zip(NAMES, UNITS)]
            def get_api_version(self): return "synthetic"

        class Source(gp.HybridBlack):
            def _connect(self): self._device = Device()
            def _acquisition_function(self):
                index = 0
                while self._running:
                    frame = np.zeros((4, 18), dtype=np.float32)
                    frame[:, :8] = np.sin((index + np.arange(4))[:, None] / 10) * 10
                    frame[:, 15] = index + np.arange(4) + 100
                    frame[:, 16] = 1
                    frame[:, 17] = wrap_time(stamp_clock())
                    self._current_frame = frame
                    self.cycle()
                    index += 4
                    time.sleep(.016)

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.csv"
            read_fd, write_fd = os.pipe()
            messages = []
            def emit(message):
                messages.append(message)
                if message.startswith("READY "):
                    os.write(write_fd, b"STOP\n")
            try:
                with os.fdopen(read_fd, "r") as commands:
                    with patch.object(gp, "HybridBlack", Source), patch("sys.stdin", commands):
                        record(SimpleNamespace(output=path, serial="SYNTHETIC-TEST-ONLY"), emit)
                meta = json.loads(Path(str(path) + ".processing.json").read_text())
                self.assertEqual(meta["state"], "complete")
                self.assertGreaterEqual(meta["oscar_samples"], meta["stop_target_raw_samples"])
                self.assertEqual(messages[-1], "DONE")
                self.assertEqual(resolve_recording(path).signal, "oscar")
            finally:
                os.close(write_fd)
