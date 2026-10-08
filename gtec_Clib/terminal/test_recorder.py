"""Hardware-free integration test; needs MSVC cl (Developer Command Prompt) or clang++."""
import csv
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    exe = work / ("terminal.exe" if os.name == "nt" else "terminal")
    recordings = work / "recordings"
    source = [str(root / "main.cpp"), str(root / "mock_api.cpp")]
    define = f'-DRECORDINGS_ROOT="{recordings.as_posix()}"'
    if shutil.which("cl"):
        subprocess.run(["cl", "/nologo", "/std:c++17", "/EHsc", "/utf-8", "/DUNICORN_API=",
                        define, "/I" + str(root.parent / "lib"), *source, "/Fe:" + str(exe),
                        "/link", "user32.lib", "gdi32.lib"], cwd=work, check=True)
    else:
        subprocess.run(["clang++", "-std=c++17", "-pthread", "-DUNICORN_API=", define,
                        "-I", str(root.parent / "lib"), *source, "-o", str(exe),
                        *(["-luser32", "-lgdi32"] if os.name == "nt" else [])], check=True)

    def session(commands, fail=False):
        env = os.environ.copy()
        if fail:
            env["UNICORN_MOCK_FAIL"] = "1"
        p = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        for command, wait in commands:
            p.stdin.write(command + "\n")
            p.stdin.flush()
            time.sleep(wait)
        output, _ = p.communicate(timeout=5)
        assert p.returncode == 0, output
        return output

    output = session([("open MOCK", 0), ("record 1 absent.csv", 0), ("start test", 0),
                      ('NewExp "../escape"', 0), ('NewExp "..\\escape"', 0), ('NewExp "CON"', 0), ('NewExp "bad."', 0),
                      ('GoToExp "missing"', 0), ('NewExp "Pilot ü 01"', 0),
                      ('NewExp "Pilot ü 01"', 0), ('NewExp "Other"', 0),
                      ('gOtOeXp "Pilot ü 01"', 0), ("Where", 0), ("ListExp", 0),
                      ('record 1 "../escape.csv"', 0), ("quit", 0)])
    assert "Select an experiment first" in output, output
    assert "Invalid Windows name" in output and "Reserved Windows name" in output, output
    assert "Experiment not found" in output and "Experiment already exists" in output, output
    assert "[Pilot ü 01] >" in output and "* Pilot ü 01" in output, output
    assert str(recordings.as_posix()) in output.replace("\\", "/"), output
    assert not (work / "absent.csv").exists() and not (work / "escape.csv").exists()
    assert sorted(p.name for p in recordings.iterdir()) == ["Other", "Pilot ü 01"]

    output = session([('GoToExp "Pilot ü 01"', 0), ("open MOCK", 0), ("record 0.3 timed.csv test", .15),
                      ('mark task "left"', 0), ('GoToExp "Other"', 0), ('NewExp "Blocked"', 0), ("Where", 0), ("ListExp", 0), ("info", .8), ("status", 0), ("quit", 0)])
    with (recordings / "Pilot ü 01" / "timed.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 75, len(rows)
    assert rows[-1]["sample_index"] == "74"
    with (recordings / "Pilot ü 01" / "timed.csv.events.csv").open() as f:
        markers = list(csv.DictReader(f))
    assert markers[0]["label"] == 'task "left"'
    assert "Stop acquisition before changing experiments" in output, output
    assert not (recordings / "Blocked").exists()
    assert "Background recording active" in output
    assert "samples=75" in output and "counter_discontinuities=0" in output, output

    output = session([('GoToExp "Pilot ü 01"', 0), ("open MOCK", 0), ("record 0 continuous.csv", .25),
                      ("stop", 0), ("record 1 continuous.csv", 0), ("quit", 0)])
    assert "files already exist" in output
    with (recordings / "Pilot ü 01" / "continuous.csv").open() as f:
        assert len(list(csv.DictReader(f))) >= 25

    output = session([('GoToExp "Pilot ü 01"', 0), ("open MOCK", 0), ("record 1 failure.csv", .5),
                      ("status", 0), ("close", 0), ("quit", 0)], fail=True)
    assert "API error 9" in output
    output = session([('GoToExp "Pilot ü 01"', 0), ("open MOCK", 0), ("start test", 0),
                      ('GoToExp "Other"', 0), ('read 25 "manual ü.csv"', 0),
                      ('read 25 "manual ü.csv"', 0), ('read 25 "../escape.csv"', 0),
                      ("stop", 0), ('GoToExp "Other"', 0), ("quit", 0)])
    assert "Stop acquisition before changing experiments" in output and "files already exist" in output, output
    assert "Invalid Windows name" in output, output
    with (recordings / "Pilot ü 01" / "manual ü.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 25
    assert not (recordings / "Other" / "manual ü.csv").exists()
    print("PASS: experiments, Unicode, prompts, switching guards, paths, overwrite protection, manual CSV, timed recording, markers, API exclusion, continuous stop, connection failure")
