"""CLI/child-process integration with a synthetic protocol peer, no vendor SDK."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
FAKE = r'''
import argparse,csv,json,os,sys,threading,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--serial');p.add_argument('--output',type=Path);a=p.parse_args()
if os.environ.get('PEER_MODE') == 'startup_error':
 print('ERROR synthetic licence unavailable',flush=True);sys.exit(1)
stop=threading.Event()
def read():
 for line in sys.stdin:
  if line.strip() == 'STOP':break
 stop.set()
threading.Thread(target=read,daemon=True).start()
raw=a.output.open('x',encoding='utf-8');clean=Path(str(a.output)+'.oscar.csv').open('x',encoding='utf-8')
raw.write('sample_index,EEG 1\n');clean.write('sample_index,EEG 1\n')
Path(str(a.output)+'.device.json').write_text(json.dumps(dict(serial='SYNTHETIC',channels=[])))
count=100
print('SAMPLES 100 17',flush=True);print('READY 1 83',flush=True)
started=time.monotonic()
while not stop.wait(.02):
 count+=4
 if os.environ.get('PEER_MODE') != 'stall':
  print(f'SAMPLES {count} {count-83}',flush=True)
 if os.environ.get('PEER_MODE') == 'runtime_error' and time.monotonic()-started > .15:
  print('ERROR synthetic OSCAR failure',flush=True);sys.exit(1)
 if os.environ.get('PEER_MODE') == 'eof' and time.monotonic()-started > .15:sys.exit(0)
raw.close();clean.close()
print(f'SAMPLES {count+84} {count+1}',flush=True)
Path(str(a.output)+'.processing.json').write_text(json.dumps(dict(state='complete')))
print('DONE',flush=True)
if os.environ.get('PEER_MODE') == 'bad_exit':sys.exit(1)
'''

with tempfile.TemporaryDirectory(prefix="OSCAR protocol geprüft ") as temp:
    work = Path(temp)
    exe = work / ("terminal.exe" if os.name == "nt" else "terminal")
    recordings = work / "recordings"
    define = f'-DRECORDINGS_ROOT="{recordings.as_posix()}"'
    sources = [str(ROOT / "main.cpp"), str(ROOT / "mock_api.cpp")]
    if shutil.which("cl"):
        command = ["cl", "/nologo", "/std:c++17", "/EHsc", "/utf-8", "/DUNICORN_API=", "/DUNICORN_SESSION_TEST",
                   define, "/I" + str(ROOT.parent / "lib"), *sources, "/Fe:" + str(exe),
                   "/link", "user32.lib", "gdi32.lib"]
    else:
        command = ["clang++", "-std=c++17", "-pthread", "-DUNICORN_API=", "-DUNICORN_SESSION_TEST", define,
                   "-I", str(ROOT.parent / "lib"), *sources, "-o", str(exe),
                   *(["-luser32", "-lgdi32"] if os.name == "nt" else [])]
    subprocess.run(command, cwd=work, check=True)
    peer = work / "worker geprüft.py"
    peer.write_text(FAKE, encoding="utf-8")
    for mode in ("normal", "startup_error", "runtime_error", "eof", "bad_exit", "stall"):
        env = dict(os.environ, EEG_OSCAR_PYTHON=sys.executable, EEG_OSCAR_WORKER=str(peer), PEER_MODE=mode)
        process = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        process.stdin.write(f'NewExp "{mode}"\nopen MOCK\nstart session\n')
        process.stdin.flush()
        folder = recordings / mode
        deadline = time.monotonic() + 10
        meta = None
        while time.monotonic() < deadline:
            files = list(folder.glob("*.session.json")) if folder.exists() else []
            if files:
                meta = json.loads(files[0].read_text(encoding="utf-8"))
                target = "running" if mode in ("normal", "bad_exit") else "failed"
                if meta["state"] == target:
                    break
            time.sleep(.02)
        else:
            process.kill()
            output = process.communicate()[0]
            raise AssertionError((mode, meta, output))
        process.stdin.write('status\nopen MOCK\nstop\nstatus\nquit\n')
        process.stdin.flush()
        output = process.communicate(timeout=12)[0]
        assert process.returncode == 0, output
        meta = json.loads(next(folder.glob("*.session.json")).read_text(encoding="utf-8"))
        assert meta["processing_mode"] == "oscar" and meta["default_signal"] == "oscar", meta
        assert "processing=OSCAR" in output, output
        if mode == "normal":
            assert meta["state"] == "aborted", meta
            assert meta["oscar_delay_samples"] == 83 and meta["oscar_samples"] > 0, meta
            assert "Background recording active" in output, output
        else:
            assert meta["state"] == "failed", (mode, meta, output)
        with next(folder.glob("*.events.csv")).open(encoding="utf-8") as file:
            events = list(__import__('csv').DictReader(file))
        if mode == "startup_error":
            assert not any(event["label"] == "session_start" for event in events), events
            assert "synthetic licence unavailable" in output, output
        assert not list(folder.glob("*.reserve"))
        print(f"PASS: OSCAR process protocol {mode}, metadata, finalization and exclusive device handoff")
