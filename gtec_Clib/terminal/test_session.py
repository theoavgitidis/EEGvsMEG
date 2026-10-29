"""Hardware-free session tests. Accelerated clock and fake cues exist only in test builds."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent


def build(work, sources, target, definitions=()):
    if shutil.which("cl"):
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/utf-8", "/DUNICORN_API=",
                   *definitions, "/I" + str(ROOT.parent / "lib"),
                   *map(str, sources), "/Fe:" + str(target), "/link", "user32.lib", "gdi32.lib"]
    else:
        command = ["clang++", "-std=c++17", "-pthread", "-Wall", "-Wextra", "-DUNICORN_API=",
                   *definitions, "-I", str(ROOT.parent / "lib"), *map(str, sources), "-o", str(target),
                   *(["-luser32", "-lgdi32"] if os.name == "nt" else [])]
    subprocess.run(command, cwd=work, check=True)


with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    unit = work / ("unit.exe" if os.name == "nt" else "unit")
    build(work, [ROOT / "test_session.cpp"], unit)
    subprocess.run([str(unit)], check=True)
    exe = work / ("terminal.exe" if os.name == "nt" else "terminal")
    recordings = work / "recordings"
    build(work, [ROOT / "main.cpp", ROOT / "mock_api.cpp"], exe,
          ["-DUNICORN_SESSION_TEST", f'-DRECORDINGS_ROOT="{recordings.as_posix()}"'])

    runtime = work / ("runtime.exe" if os.name == "nt" else "runtime")
    build(work, [ROOT / "test_session_runtime.cpp", ROOT / "mock_api.cpp"], runtime,
          ["-DUNICORN_SESSION_TEST", f'-DRECORDINGS_ROOT="{(work / "runtime-recordings").as_posix()}"'])
    runtime_env = os.environ.copy()
    runtime_env.pop("UNICORN_SESSION_SPEED", None)
    subprocess.run([str(runtime)], env=runtime_env, timeout=20, check=True)

    def launch(name, speed=100, **environment):
        env = dict(os.environ, UNICORN_SESSION_SPEED=str(speed), UNICORN_SESSION_SEED="42", **environment)
        p = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        send(p, f'NewExp "{name}"', "open MOCK", "start session raw")
        return p, recordings / name

    def send(p, *commands):
        p.stdin.write("\n".join(commands) + "\n")
        p.stdin.flush()

    def read_meta(folder):
        files = list(folder.glob("*.session.json"))
        if not files:
            return None
        try:
            return json.loads(files[-1].read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def wait_for(predicate, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.01)
        raise AssertionError("Timed out waiting for session state")

    def state_is(folder, state):
        value = read_meta(folder)
        return value if value and value["state"] == state else None

    def finish(p, *commands):
        send(p, *commands, "quit")
        output, _ = p.communicate(timeout=8)
        assert p.returncode == 0, output
        return output

    def events(folder):
        with next(folder.glob("*.events.csv")).open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    # Entire session with real recorder, accelerated schedule, no 45-minute wait.
    p, folder = launch("Complete ü")
    meta = wait_for(lambda: state_is(folder, "completed"), timeout=35)
    output = finish(p, "status")
    assert meta["completed_trials"] == 168 and meta["repetitions"] == 0, meta
    assert meta["planned_seconds"] == 2704 and meta["samples"] > 0
    assert meta["completed_trials_by_run"] == {"Motorik": 64, "Imagery": 104}
    assert len(meta["device"]["channels"]) == 17
    assert meta["protocol_version"] == "eeg-session-2.0" and meta["schema_version"] == 2
    assert meta["planned_trials"] == 168 and meta["task_language"] == "de"
    assert len(meta["local_timezone"]) == 5 and meta["local_timezone"][0] in "+-" and meta["local_timezone"][1:].isdigit()
    assert "45:04" in output and "REST 0:00" in output, output
    es = events(folder)
    assert sum(e["label"] == "trial_end" for e in es) == 168
    assert sum(e["label"] == "block_start" for e in es) == 8
    assert es[-1]["label"] == "session_end"
    assert float(es[-1]["planned_elapsed_s"]) == 2704
    assert all(float(e["actual_session_elapsed_s"]) >= 0 for e in es)
    assert not list(folder.glob("*.reserve"))
    assert all(e["source"] == "automatic" for e in es)
    assert [int(e["samples_received"]) for e in es] == sorted(int(e["samples_received"]) for e in es)
    plan = list(csv.DictReader(next(folder.glob("*.plan.csv")).open(encoding="utf-8")))
    assert sum(float(e["duration_s"]) for e in plan) == 2704
    tasks = [row for row in plan if row["phase"] == "task"]
    assert len({row["condition"] for row in tasks}) == 12
    for row in tasks:
        emitted = [e for e in es if e["label"] == "cue_onset" and e["run"] == row["run"] and e["trial"] == row["trial"]]
        assert len(emitted) == 1
        for key in ["condition", "mode", "body_part", "side", "movement_version", "language", "word_letter", "protocol_version"]:
            assert emitted[0][key] == row[key], (key, emitted[0], row)
        if row["condition"] == "mental_subtraction_single":
            assert int(emitted[0]["subtract"]) == int(row["subtract"]) and int(row["subtract"]) != 7
    assert all(e["protocol_version"] == "eeg-session-2.0" for e in es)
    print("PASS: complete 168-trial CLI session, files, metadata, automatic events, recorder")

    # Pause a trial, preserve manual observations without changing schedule, reject interfering commands.
    p, folder = launch("Paused", speed=20)
    wait_for(lambda: any(e["label"] == "trial_start" for e in events(folder)) if list(folder.glob("*.events.csv")) else False)
    send(p, "session pause")
    wait_for(lambda: state_is(folder, "paused"))
    send(p, 'mark Baseline', 'mark Husten, "leicht"', "cue rest", 'NewExp "Blocked"', "start session raw", "session pause")
    time.sleep(.05)
    send(p, "session resume")
    wait_for(lambda: state_is(folder, "running"))
    output = finish(p, "stop", "status")
    meta = read_meta(folder)
    assert meta["state"] == "aborted" and meta["repetitions"] == 1 and meta["invalid_attempts"] == 2, meta
    assert "controls the participant window" in output and "already active" in output, output
    assert "Stop acquisition before changing experiments" in output
    assert not (recordings / "Blocked").exists()
    es = events(folder)
    manual = [e for e in es if e["source"] == "manual"]
    assert [e["label"] for e in manual] == ["Baseline", 'Husten, "leicht"']
    assert all(e["trial"] == "1" for e in manual)
    assert any(e["label"] == "trial_repeat" and e["attempt"] == "2" for e in es)
    print("PASS: trial pause/repeat, observations, command guards, abort")

    # Window loss pauses automatically, resume recreates display and restarts baseline.
    p, folder = launch("Window", speed=1)
    wait_for(lambda: state_is(folder, "running"))
    send(p, "test-close-window")
    meta = wait_for(lambda: state_is(folder, "paused"))
    assert meta["reason"] == "participant_window_closed"
    send(p, "session resume")
    wait_for(lambda: state_is(folder, "running"))
    finish(p, "close", "status")
    assert read_meta(folder)["state"] == "aborted"
    assert sum(e["label"] == "baseline_start" for e in events(folder)) == 2
    print("PASS: window loss, recreation, baseline repeat, close")

    p, folder = launch("Failure", UNICORN_MOCK_FAIL="1")
    meta = wait_for(lambda: state_is(folder, "failed"))
    output = finish(p, "session resume", "status")
    assert "API error 9" in meta["reason"] and "not paused" in output
    assert meta["completed_trials"] == 0
    assert events(folder)[-1]["label"] == "session_error"
    print("PASS: recorder failure ends session and prevents resume")

    p, folder = launch("Missing", UNICORN_MOCK_MISSING_CHANNEL="1")
    output = finish(p, "status")
    assert "requires enabled channel EEG 1" in output, output
    assert not list(folder.glob("*.csv"))
    print("PASS: missing required channel refuses start before file creation")

    # Repeated sessions in one experiment never reuse or overwrite prior files.
    p, folder = launch("Repeated", speed=1)
    wait_for(lambda: state_is(folder, "running"))
    send(p, "stop", "session order imagery motorik kognitiv", "session order imagery imagery", "session order imagery motorik", "start session raw")
    wait_for(lambda: len(list(folder.glob("*.session.json"))) == 2)
    finish(p, "stop")
    metas = [json.loads(path.read_text()) for path in folder.glob("*.session.json")]
    assert len({m["session_id"] for m in metas}) == 2 and all(m["state"] == "aborted" for m in metas)
    assert len(list(folder.glob("*.csv"))) == 6
    assert any(m["order"] == ["Imagery", "Motorik"] for m in metas)
    print("PASS: unique filenames and session restart")

    p, folder = launch("Lateness", speed=1)
    wait_for(lambda: state_is(folder, "running"))
    send(p, "test-jump 100")
    meta = wait_for(lambda: state_is(folder, "paused"))
    assert meta["reason"] == "timing_deviation_over_250ms"
    assert any(e["label"] == "timing_deviation" for e in events(folder))
    finish(p, "stop")
    print("PASS: excessive lateness pauses rather than skipping phases")

    p, folder = launch("MetadataFailure", speed=1)
    wait_for(lambda: state_is(folder, "running"))
    metadata = next(folder.glob("*.session.json"))
    Path(str(metadata) + ".tmp").mkdir()
    output = finish(p, "session pause", "status")
    assert "Cannot write session metadata" in output and "failed" in output and "Recording: 0" in output, output
    print("PASS: metadata write failure stops recording and is reported")

    p, folder = launch("EOF", speed=1)
    wait_for(lambda: state_is(folder, "running"))
    p.stdin.close()
    p.stdin = None
    output, _ = p.communicate(timeout=8)
    assert p.returncode == 0 and read_meta(folder)["state"] == "aborted", output
    assert read_meta(folder)["reason"] == "input EOF"
    print("PASS: input EOF finalizes session")
