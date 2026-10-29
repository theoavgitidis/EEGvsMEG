"""CLI/child-process integration with a synthetic protocol peer, no vendor SDK."""
import csv
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
mode=os.environ['PEER_MODE']
if mode == 'startup_error':
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
ready=Path(str(a.output)+'.ready')
def confirmation(text='READY 1 83\n'):
 temporary=Path(str(ready)+'.tmp');temporary.write_bytes(text.encode('ascii'));temporary.replace(ready)
def consumed():
 deadline=time.monotonic()+2
 while ready.exists() and not stop.is_set() and time.monotonic()<deadline:time.sleep(.01)
invalid=dict(file_empty='',file_partial='READY 1',file_version='READY 2 83\n',
 file_zero='READY 1 0\n',file_negative='READY 1 -1\n',file_extra='READY 1 83 extra\n',
 file_multiline='READY 1 83\nGARBAGE\n',file_split_line='READY\n1 83\n',
 file_no_newline='READY 1 83',file_oversize='READY 1 83'+' '*256+'\n')
if mode == 'eof_before_ready':sys.exit(0)
if mode == 'unterminated_ready':
 sys.stdout.write('READY 1 83');sys.stdout.flush();sys.exit(0)
if mode == 'done_before_ready':
 print('DONE',flush=True);time.sleep(.15);confirmation()
elif mode == 'file_delayed_no_status':
 time.sleep(6.3);confirmation();consumed();time.sleep(.25)
else:
 print('SAMPLES 100 17',flush=True)
 if mode in invalid:confirmation(invalid[mode])
 elif mode in ('file_only','file_crlf','file_then_stdout','file_then_conflict'):
  time.sleep(.1);confirmation('READY 1 83\r\n' if mode == 'file_crlf' else 'READY 1 83\n');consumed()
  if mode not in ('file_only','file_crlf'):print('READY 1 '+('84' if mode == 'file_then_conflict' else '83'),flush=True)
 elif mode != 'missing_ready':
  print('READY 1 83',flush=True)
  if mode in ('stdout_then_file','stdout_then_conflict'):
   time.sleep(.25);confirmation('READY 1 '+('84' if mode == 'stdout_then_conflict' else '83')+'\n')
  if mode == 'duplicate_stdout':print('READY 1 83',flush=True)
Path(str(a.output)+'.peer-stage').write_text('ready sequence finished')
started=time.monotonic()
while not stop.wait(.02):
 count+=4
 if mode != 'stall':
  print(f'SAMPLES {count} {count-83}',flush=True)
 if mode == 'runtime_error' and time.monotonic()-started > .15:
  print('ERROR synthetic OSCAR failure',flush=True);sys.exit(1)
 if mode == 'eof' and time.monotonic()-started > .15:sys.exit(0)
raw.close();clean.close()
if mode == 'file_on_stop':confirmation()
print(f'SAMPLES {count+84} {count+1}',flush=True)
Path(str(a.output)+'.processing.json').write_text(json.dumps(dict(state='complete',stop_received=True)))
print('DONE',flush=True)
if mode == 'bad_exit':sys.exit(1)
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
    # Exercise stale-artifact refusal directly, before a worker can overwrite it.
    harness = work / "stale.cpp"
    harness.write_text('#define main cli_main\n#include "' + (ROOT / "main.cpp").as_posix() + '"\n#undef main\n' + r'''
int main() {
    Recorder recorder;
    try { recorder.startOscar("MOCK",std::filesystem::current_path()/"stale.csv"); }
    catch (const std::exception& e) { return std::string(e.what()).find("files already exist") == std::string::npos ? 2 : 0; }
    return 1;
}
''', encoding="utf-8")
    stale_exe = work / ("stale.exe" if os.name == "nt" else "stale")
    stale_command = [str(harness) if arg == sources[0] else
                     str(stale_exe) if arg == str(exe) else
                     "/Fe:" + str(stale_exe) if arg == "/Fe:" + str(exe) else arg for arg in command]
    subprocess.run(stale_command, cwd=work, check=True)
    for suffix in (".ready", ".ready.tmp", ".startup.log"):
        artifact = work / ("stale.csv" + suffix)
        artifact.write_text("preserve stale evidence", encoding="utf-8")
        subprocess.run([str(stale_exe)], cwd=work, check=True)
        assert artifact.read_text(encoding="utf-8") == "preserve stale evidence"
        assert not (work / "stale.csv.events.csv").exists()
        artifact.unlink()
    print("PASS: stale readiness/startup artifacts refused without overwrite")
    peer = work / "worker geprüft.py"
    peer.write_text(FAKE, encoding="utf-8")
    success = {"normal", "file_only", "file_crlf", "file_then_stdout", "stdout_then_file", "duplicate_stdout", "file_delayed_no_status", "file_on_stop"}
    startup_failures = {"startup_error", "eof_before_ready", "done_before_ready", "missing_ready", "unterminated_ready",
                        "file_empty", "file_partial", "file_version", "file_zero", "file_negative", "file_extra", "file_multiline",
                        "file_no_newline", "file_oversize", "file_split_line"}
    modes = ["normal", "file_only", "file_crlf", "file_then_stdout", "stdout_then_file", "duplicate_stdout", "file_delayed_no_status", "file_on_stop",
             *sorted(startup_failures), "file_then_conflict", "stdout_then_conflict", "runtime_error", "eof", "bad_exit", "stall"]
    for mode in os.environ.get("OSCAR_TEST_MODES", ",".join(modes)).split(","):
        env = dict(os.environ, EEG_OSCAR_PYTHON=sys.executable, EEG_OSCAR_WORKER=str(peer), PEER_MODE=mode,
                   UNICORN_OSCAR_STARTUP_TIMEOUT_MS="450" if mode == "missing_ready" else "10000")
        process = subprocess.Popen([str(exe)], cwd=work, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        process.stdin.write(f'NewExp "{mode}"\nopen MOCK\nstart session\n')
        process.stdin.flush()
        folder = recordings / mode
        deadline = time.monotonic() + 15
        meta = None
        while time.monotonic() < deadline:
            files = list(folder.glob("*.session.json")) if folder.exists() else []
            if files:
                try:
                    meta = json.loads(files[0].read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):  # Windows may briefly deny reads during metadata replacement.
                    time.sleep(.02)
                    continue
                target = "running" if mode in success or mode == "bad_exit" else "failed"
                # Let both channels finish before stopping an ordering test.
                sequenced = list(folder.glob("*.peer-stage"))
                removed = not list(folder.glob("*.ready"))
                if meta["state"] == target and (target == "failed" or (sequenced and removed)):
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
        if mode in success:
            assert meta["state"] == "aborted", meta
            assert meta["oscar_delay_samples"] == 83 and meta["oscar_samples"] > 0, meta
            assert "Background recording active" in output, output
        else:
            assert meta["state"] == "failed", (mode, meta, output)
        with next(folder.glob("*.events.csv")).open(encoding="utf-8") as file:
            events = list(csv.DictReader(file))
        if mode in startup_failures:
            assert not any(event["label"] == "session_start" for event in events), events
            assert meta["completed_trials"] == 0, meta
            assert meta["reason"], meta
        log = next(folder.glob("*.startup.log")).read_text(encoding="utf-8")
        assert "controller=oscar-startup-v2" in log and "worker_pid=" in log, log
        assert "python=" + sys.executable in log and "worker=" + str(peer) in log, log
        ready_path = str(next(folder.glob("*.session.json"))).removesuffix(".session.json") + ".ready"
        assert "ready_path=" + ready_path in log, log
        assert log.count("readiness_accepted") == (0 if mode in startup_failures else 1), log
        if os.name == "nt":
            assert "executable=" + str(exe) in log, log
        if mode in {"file_then_stdout", "stdout_then_file", "file_on_stop"}:
            assert "source=file delay=83" in log and "source=stdout delay=83" in log, log
        if mode in {"file_then_conflict", "stdout_then_conflict"}:
            assert "Conflicting OSCAR readiness" in meta["reason"], meta
        if mode.startswith("file_") and mode in startup_failures:
            assert "Invalid OSCAR readiness" in meta["reason"], meta
            assert list(folder.glob("*.ready")), "Retain invalid confirmation as evidence"
        if mode == "missing_ready":
            assert "timed out without an accepted readiness" in meta["reason"], meta
            assert "startup_rejected ready=0 raw=" in log, log
        if mode == "unterminated_ready":
            assert "unterminated protocol line" in meta["reason"], meta
        if mode == "startup_error":
            assert "synthetic licence unavailable" in output, output
        assert not list(folder.glob("*.reserve"))
        if mode in success:
            assert not list(folder.glob("*.ready")), mode
        if mode not in {"startup_error", "runtime_error", "eof", "eof_before_ready", "bad_exit", "unterminated_ready"}:
            processing = json.loads(next(folder.glob("*.processing.json")).read_text(encoding="utf-8"))
            assert processing == dict(state="complete", stop_received=True), (mode, processing)
        print(f"PASS: OSCAR process protocol {mode}, metadata, finalization and exclusive device handoff")
