"""Hardware-free integration test; needs a C++17 compiler named clang++."""
import csv
import os
from pathlib import Path
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    exe = work / "terminal"
    subprocess.run(["clang++", "-std=c++17", "-pthread", "-I", str(root.parent / "lib"),
                    str(root / "main.cpp"), str(root / "mock_api.cpp"), "-o", str(exe)], check=True)

    def session(commands, fail=False):
        env = os.environ.copy()
        if fail:
            env["UNICORN_MOCK_FAIL"] = "1"
        p = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for command, wait in commands:
            p.stdin.write(command + "\n")
            p.stdin.flush()
            time.sleep(wait)
        output, _ = p.communicate(timeout=5)
        assert p.returncode == 0, output
        return output

    output = session([("open MOCK", 0), ("record 0.3 timed.csv test", .15),
                      ('mark task "left"', 0), ("info", .8), ("status", 0), ("quit", 0)])
    with (work / "timed.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 75, len(rows)
    assert rows[-1]["sample_index"] == "74"
    with (work / "timed.csv.events.csv").open() as f:
        markers = list(csv.DictReader(f))
    assert markers[0]["label"] == 'task "left"'
    assert "Background recording active" in output
    assert "samples=75" in output and "counter_discontinuities=0" in output, output

    output = session([("open MOCK", 0), ("record 0 continuous.csv", .25),
                      ("stop", 0), ("record 1 continuous.csv", 0), ("quit", 0)])
    assert "files already exist" in output
    with (work / "continuous.csv").open() as f:
        assert len(list(csv.DictReader(f))) >= 25

    output = session([("open MOCK", 0), ("record 1 failure.csv", .5),
                      ("status", 0), ("close", 0), ("quit", 0)], fail=True)
    assert "API error 9" in output
    print("PASS: timed recording, markers, API exclusion, continuous stop, overwrite protection, connection failure")
