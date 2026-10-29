"""Exclusive g.Pype recorder. stdout is a versioned protocol, never a log.

Invoked by the C++ session recorder; not a second session scheduler.
"""
import argparse
from collections import deque
from contextlib import redirect_stdout
import csv
import faulthandler
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

import numpy as np

NAMES = ([f"EEG {i}" for i in range(1, 9)]
         + [f"{sensor} {axis}" for sensor in ("Accelerometer", "Gyroscope") for axis in "XYZ"]
         + ["Battery Level", "Counter", "Validation Indicator"])
# g.Pype exposes the two count-like channels as dimensionless, while the
# Unicorn driver reports their physical device configuration in counts.
UNITS = ["uV"] * 8 + ["g"] * 3 + ["deg/s"] * 3 + ["%", "-", "-"]
DEVICE_UNITS = ["uV"] * 8 + ["g"] * 3 + ["deg/s"] * 3 + ["%", "n", "n"]
HEADER = ["sample_index", "nominal_time_s", "host_read_utc_s", *NAMES]
COUNTER = NAMES.index("Counter")


def write_json(path, value):
    temp = Path(str(path) + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


class DualWriter:
    """Bounded asynchronous writer; verifies the measured delay on every sample."""
    def __init__(self, path, capacity=32768, alignment_capacity=32768):
        self.path = Path(path)
        self.clean_path = Path(str(path) + ".oscar.csv")
        self.queue = queue.Queue(capacity)
        self.raw_count = self.clean_count = self.output_count = 0
        self.delay = None
        self.error = None
        self.last_update = time.monotonic()
        self.last_clean_update = self.last_update
        self.ready = threading.Event()
        self.ledger = deque()
        self.alignment_capacity = alignment_capacity
        self.previous_counter = None
        self.marked = False
        self.files = []
        try:
            for path in (self.path, self.clean_path):
                self.files.append(path.open("x", encoding="utf-8", newline=""))
            self.writers = [csv.writer(f) for f in self.files]
            for writer in self.writers:
                writer.writerow(HEADER)
        except Exception:
            for file in self.files:
                file.close()
            raise
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, kind, block, delay=None):
        if self.error:
            raise RuntimeError(self.error)
        try:
            self.queue.put_nowait((kind, np.array(block, dtype=float, copy=True), delay, time.time()))
        except queue.Full as error:
            self.error = "Recording disk queue overflow; no samples may be dropped."
            raise RuntimeError(self.error) from error

    def _consume(self, kind, block, delay, received):
        if block.ndim != 2 or block.shape[1] != 17 or not np.isfinite(block).all():
            raise ValueError("Expected finite blocks with all 17 configured channels.")
        if kind == "raw":
            for row in block:
                counter = row[COUNTER]
                if counter != int(counter):
                    raise ValueError("Non-integral device counter.")
                if self.previous_counter is not None and counter != self.previous_counter + 1:
                    raise ValueError("Device counter discontinuity; refusing uncertain OSCAR timing.")
                self.previous_counter = counter
                self.ledger.append((self.raw_count, row.copy(), received))
                self.writers[0].writerow([self.raw_count, self.raw_count / 250, received, *row])
                self.raw_count += 1
            # g.Pype may receive source frames while the OSCAR model is fitting.
            # Keep a bounded pre-roll so the first delayed clean frame still has
            # its exact raw counterpart.
            if len(self.ledger) > self.alignment_capacity:
                raise ValueError("OSCAR backlog exceeds the bounded alignment buffer.")
            self.last_update = time.monotonic()
        elif kind == "clean":
            if delay is None or int(delay) != delay or not 0 < delay < 8192:
                raise ValueError("OSCAR did not report a supported positive sample delay.")
            if self.delay is not None and self.delay != delay:
                raise ValueError("OSCAR delay changed during the recording.")
            self.delay = int(delay)
            for row in block:
                source_index = self.output_count - self.delay
                self.output_count += 1
                if source_index < 0:
                    continue  # model start-up, never presented as measured EEG
                if not self.ledger or self.ledger[0][0] != source_index:
                    raise ValueError("OSCAR output is missing, reordered or outside the raw timeline.")
                index, original, stamp = self.ledger.popleft()
                # The counter is an auxiliary channel delayed together with EEG.
                # Compare all auxiliary values as well: never silently shift a marker.
                if not np.array_equal(row[8:], original[8:]):
                    raise ValueError("OSCAR delay/auxiliary alignment does not match the raw samples.")
                self.writers[1].writerow([index, index / 250, stamp, *row])
                self.clean_count += 1
            self.last_clean_update = time.monotonic()
            if self.clean_count:
                for file in self.files:
                    file.flush()
                self.ready.set()
        else:
            raise ValueError("Unknown writer block type.")

    def _run(self):
        try:
            while True:
                item = self.queue.get()
                if item is None:
                    break
                self._consume(*item)
        except Exception as error:
            self.error = str(error)
        finally:
            for file in self.files:
                try:
                    file.flush()
                    file.close()
                except Exception as error:
                    self.error = self.error or str(error)

    def close(self):
        if self.thread.is_alive():
            try:
                self.queue.put(None, timeout=2)
            except queue.Full:
                self.error = self.error or "Disk writer could not stop."
            self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.error = self.error or "Disk writer shutdown timed out."
        if self.error:
            raise RuntimeError(self.error)


def build_pipeline(gp, writer, serial):
    """Adapt public source.step and Sink hooks, leaving g.Pype authentication intact."""
    class RecordingHybridBlack(gp.HybridBlack):
        def step(self, data):
            result = super().step(data)
            if result and result.get("out") is not None:
                block = result["out"]
                if block.ndim != 2 or block.shape[1] != 18:
                    raise ValueError("Unicorn source layout changed (17 channels plus arrival timestamp required).")
                writer.submit("raw", block[:, :17])
            return result

    class RecordingSink(gp.Sink):
        def __init__(self, source):
            super().__init__()
            self.source = source

        def attach_entitlement(self, verdict):
            super().attach_entitlement(verdict)
            writer.marked = bool(self._marked)

        def setup(self, data, contexts):
            context = contexts["in"]
            if context.get("sampling_rate") != 250 or context.get("channel_count") != 17:
                raise ValueError("OSCAR output must preserve 250 Hz and 17 channels.")
            if context.get("channel_units") != UNITS:
                raise ValueError("OSCAR physical channel units do not match the recording contract.")
            return super().setup(data, contexts)

        def step(self, data):
            block = data.get("in")
            if block is not None:
                writer.submit("clean", block, self.source.oscar_delay_samples)
            return {}

    source = RecordingHybridBlack(serial=serial, channel_count=8, frame_size=4,
                                  include_accel=True, include_gyro=True, include_aux=True,
                                  enable_oscar=True)
    pipeline = gp.Pipeline()
    pipeline.connect(source, RecordingSink(source))
    return pipeline, source


def record(args, emit):
    started = time.monotonic()
    def diagnostic(event, **details):
        # stderr is the existing session log; stdout remains protocol-only.
        entry = dict(pid=os.getpid(), elapsed_s=round(time.monotonic() - started, 6), event=event)
        entry.update(details)
        print("OSCAR_STARTUP " + json.dumps(entry, ensure_ascii=True), file=sys.stderr, flush=True)
    output = args.output.resolve()
    diagnostic("worker_start", python_path=sys.executable, output_path=str(output), ready_path=str(output) + ".ready")
    try:
        _record(args, emit, diagnostic)
    except BaseException as error:
        diagnostic("failed", error_type=type(error).__name__, error=str(error))
        raise


def _record(args, emit, diagnostic):
    # Fixed protocol and package contract: refuse changed vendor internals/layout.
    versions = {name: importlib.metadata.version(name)
                for name in ("gpype", "gtec-oscar", "gtec-unicorn", "gtec-licensing")}
    expected = {"gpype": "4.1.0", "gtec-oscar": "1.3.2", "gtec-unicorn": "1.0.0", "gtec-licensing": "2.4.0"}
    if versions != expected:
        raise RuntimeError(f"Unsupported acquisition versions; install acquisition/requirements.txt: {versions}")
    import gpype as gp
    ready_path = Path(str(args.output) + ".ready")
    for suffix in ("", ".oscar.csv", ".processing.json", ".device.json", ".ready"):
        if Path(str(args.output) + suffix).exists():
            raise FileExistsError(f"Recording artifact already exists: {args.output}{suffix}")
    stop = threading.Event()
    def commands():
        for line in sys.stdin:
            if line.strip() == "STOP":
                break
        stop.set()  # parent EOF is also a stop, not an orphaned recording
    threading.Thread(target=commands, daemon=True).start()
    writer = DualWriter(args.output)
    pipeline = None
    metadata = {"schema_version": 1, "mode": "oscar", "state": "preparing", "sampling_rate_hz": 250,
                "raw_file": args.output.name, "oscar_file": writer.clean_path.name,
                "default_signal": "oscar", "versions": versions,
                "channel_names": NAMES, "channel_units": DEVICE_UNITS,
                "alignment": "sample_index is the original raw sample index; verified by all auxiliary channels",
                "oscar_delay_samples": None, "raw_samples": 0, "oscar_samples": 0}
    meta_path = Path(str(args.output) + ".processing.json")
    def metadata_update(state, error=None):
        metadata.update(state=state, raw_samples=writer.raw_count, oscar_samples=writer.clean_count,
                        oscar_delay_samples=writer.delay, noncommercial_mark=writer.marked)
        if error:
            metadata["error"] = error
        write_json(meta_path, metadata)
    try:
        metadata_update("preparing")
        # g.Pype resolves OSCAR lazily on the first pipeline cycle. Load it
        # before opening the live stream so SciPy imports cannot delay it.
        diagnostic("oscar_import_starting")
        import gtec_oscar  # noqa: F401
        diagnostic("oscar_imported")
        pipeline, source = build_pipeline(gp, writer, args.serial)
        diagnostic("pipeline_starting")
        # Vendor startup can block while opening Bluetooth or obtaining an
        # entitlement. Preserve its Python stack in the existing worker log.
        faulthandler.dump_traceback_later(30, file=sys.stderr)
        try:
            pipeline.start()
        finally:
            faulthandler.cancel_dump_traceback_later()
        diagnostic("pipeline_started")
        deadline = time.monotonic() + 30
        ready = False
        stop_target = None
        last_report = 0
        while True:
            if writer.error:
                raise RuntimeError(writer.error)
            if pipeline.failure:
                raise RuntimeError(f"g.Pype processing failed: {pipeline.failure}")
            now = time.monotonic()
            if max(now - writer.last_update, now - writer.last_clean_update) > (5 if ready else 30):
                raise RuntimeError("Raw/OSCAR sample stream stalled.")
            if not ready and writer.ready.is_set():
                # Driver configuration is queried from the handle this source owns.
                channels = source._device.get_configuration()
                if [c.name for c in channels] != NAMES or not all(c.enabled for c in channels):
                    raise RuntimeError("Actual device channel layout differs from the recorded layout.")
                if [c.unit.replace("µ", "u").replace("μ", "u") for c in channels] != DEVICE_UNITS:
                    raise RuntimeError("Actual device units differ from the required units.")
                device = {"serial": source.device_serial(), "api_version": source._device.get_api_version(),
                          "channels": [{"name": c.name, "unit": c.unit, "enabled": c.enabled} for c in channels]}
                write_json(Path(str(args.output) + ".device.json"), device)
                metadata_update("recording")
                # The controller also polls this atomically replaced file.  It
                # prevents a Windows pipe read from delaying session start.
                ready_temp = Path(str(ready_path) + ".tmp")
                ready_temp.write_text(f"READY 1 {writer.delay}\n", encoding="ascii")
                ready_temp.replace(ready_path)
                diagnostic("ready_file_replaced", delay_samples=writer.delay)
                diagnostic("protocol_emit_begin", message_type="SAMPLES")
                emit(f"SAMPLES {writer.raw_count} {writer.clean_count}")
                diagnostic("protocol_emit_complete", message_type="SAMPLES")
                diagnostic("protocol_emit_begin", message_type="READY")
                emit(f"READY 1 {writer.delay}")
                diagnostic("protocol_emit_complete", message_type="READY")
                ready = True
            if not ready and now > deadline:
                raise RuntimeError("OSCAR startup timed out before the first aligned samples.")
            if ready and now - last_report >= .04:
                emit(f"SAMPLES {writer.raw_count} {writer.clean_count}")
                last_report = now
            if stop.is_set():
                if not ready:
                    raise RuntimeError("Recording stopped before OSCAR became ready.")
                if stop_target is None:
                    stop_target = writer.raw_count
                    deadline = now + 5
                if writer.clean_count >= stop_target:
                    metadata["stop_target_raw_samples"] = stop_target
                    break
                if now > deadline:
                    raise RuntimeError("OSCAR tail drain timed out.")
            time.sleep(.01)
        pipeline.close()
        pipeline = None
        writer.close()
        metadata_update("complete")
        emit(f"SAMPLES {writer.raw_count} {writer.clean_count}")
        emit("DONE")
    except BaseException as error:
        if pipeline is not None:
            pipeline.close()
        try:
            writer.close()
        finally:
            metadata_update("failed", str(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = sys.stdout
    lock = threading.Lock()
    def emit(message):
        with lock:
            print(message, file=protocol, flush=True)
    try:
        # Vendor messages must never be mistaken for status protocol frames.
        with redirect_stdout(sys.stderr):
            record(args, emit)
    except BaseException as error:
        emit("ERROR " + str(error).replace("\n", " ").replace("\r", " "))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
