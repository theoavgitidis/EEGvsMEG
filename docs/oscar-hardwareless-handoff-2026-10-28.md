# OSCAR Startup Failure: Hardwareless Handoff

Date: 2026-10-28. Audience: Astra or another engineer working without the Unicorn headset. This is an incident report and debugging brief, not a claim that OSCAR acquisition is validated.

## Executive Summary

The following incident evidence describes the pre-investigation build. See the [hardware-free investigation update](#hardware-free-investigation-update) for changes and remaining uncertainty. The Windows experiment is not yet accepted.

`start session` consistently fails after its 120-second preparation timeout on the Windows measurement computer. The failure is in the handoff between the Python OSCAR worker and the C++ session scheduler, not in basic device streaming or OSCAR output:

- The Python worker receives live data and writes both raw and OSCAR CSVs.
- It reaches `processing.json.state == "complete"` after the scheduler stops it.
- The latest failed run wrote 30,636 raw samples and 30,545 OSCAR samples at a measured delay of 83 samples.
- The C++ session remains in `failed`, starts zero trials, and reports `OSCAR startup failed or timed out.`
- A post-failure `status` reports `Recording: 0` but also the worker's real sample counters. This establishes that the recorder worker produced status data while the scheduler never accepted startup.

Do not use the failed sessions for analysis. They have zero completed trials and no task events. Do not treat a longer timeout, a bigger queue, or the presence of a completed OSCAR output as a fix for the scheduler startup problem.

## Scope and Safety

- Repository: `C:\EEG\EEGvsMEG`, branch `main`.
- This report deliberately names only the pseudonymous folder `EVM-P002`; no names, license keys, or participant-identifying information are included.
- Original recordings are outside Git under `C:\EEG\recordings\EVM-P002\`. Do not alter or delete them during software work.
- Failed session IDs to exclude from all analysis:
  - `session_20261028_192527`
  - `session_20261028_193115`
  - `session_20261028_193910`
- A current real-session workaround is `start session raw`, which preserves raw data and the session protocol but does not perform OSCAR. It is a separate acquisition mode, not an OSCAR fallback.

## Current Git State

Relevant commits, in order:

| Commit | Change | Outcome on real hardware |
|---|---|---|
| `04170ec` | Raised OSCAR startup wait from 35 to 90 seconds; enlarged initial writer/alignment buffers; corrected device units. | Did not solve scheduler startup. |
| `4a171c6` | Raised wait to 120 seconds; enlarged writer queue to 32,768 samples. | Did not solve scheduler startup. |
| `868151a` | Added a `.ready` file intended as an out-of-pipe readiness confirmation. | Did not solve scheduler startup. The `.ready` file remained after failure. |

The working tree was clean when this report was written. The release executable was built after `868151a`, but the new readiness path did not pass a complete real-hardware acceptance test.

## Observed Real-Hardware Evidence

### Device and package facts

- Headset serial: `UN-2024.08.40`; firmware `000.000.006`.
- All 17 channels were enabled: 8 EEG, accelerometer XYZ, gyroscope XYZ, battery, counter, validation indicator.
- Sampling rate: 250 Hz.
- Python environment: `gpype 4.1.0`, `gtec-oscar 1.3.2`, `gtec-unicorn 1.0.0`, `gtec-licensing 2.4.0`.
- `gtec_licensing.api.check_license("Unicorn Python Hybrid Black")` returned `SUCCESS`.
- g.Pype sets `noncommercial_mark: true` and logs a missing g.Pype Runtime licence. This may require a vendor licensing clarification, but it did not prevent streaming or OSCAR output in the incident runs.

### Latest incident: `session_20261028_193910`

The user selected `EVM-P002`, opened the headset, verified all channels, and executed `start session`. After 2:08 the CLI printed:

```text
OSCAR startup failed or timed out.
SITZUNG session_20261028_193910 | failed | ... | VERSTRICHEN 2:08
```

The subsequent `status` output was:

```text
Recording: 0 samples=30636 nominal_seconds=122.544 counter_discontinuities=0 \
processing=OSCAR oscar_samples=30545 oscar_delay_samples=83
```

Corresponding external artifacts:

| Artifact | Relevant value |
|---|---|
| `session_20261028_193910.csv.processing.json` | `state: "complete"` |
| Same processing JSON | `raw_samples: 30636`, `oscar_samples: 30545`, `oscar_delay_samples: 83` |
| `session_20261028_193910.csv.session.json` | `state: "failed"`, `completed_trials: 0`, reason contains the startup timeout |
| `session_20261028_193910.csv.events.csv` | header only; no task events |
| `session_20261028_193910.csv.ready` | exists after failure, despite the C++ code intending to consume and remove it |
| `session_20261028_193910.csv.worker.log` | g.Pype warning: "Falling behind the amplifier: a whole frame has been waiting after every read for 1 s." |

The worker log warning is important but separate. Sample counts over approximately 122.5 seconds are consistent with 250 Hz, so it does not alone explain why the scheduler rejected readiness. It must nevertheless be investigated before a 45-minute production run.

## Architecture and Expected Startup Contract

### Components

| File | Responsibility |
|---|---|
| `gtec_Clib/terminal/main.cpp` | CLI commands and session start request |
| `gtec_Clib/terminal/session.h` | Session state machine and protocol start after recorder readiness |
| `gtec_Clib/terminal/recorder.h` | Starts/stops worker, consumes status, exposes `running`, counters and errors |
| `gtec_Clib/terminal/worker_process.h` | Windows child process, stdin/stdout pipes, worker stderr log |
| `acquisition/oscar_worker.py` | Exclusive g.Pype/Unicorn access, raw+OSCAR writing, protocol emission |

### Worker lifecycle

1. C++ closes its Unicorn C API handle before starting Python.
2. `WorkerProcess::start()` launches Python unbuffered: `python -u oscar_worker.py --serial ... --output ...`.
3. The worker creates `DualWriter`, starts g.Pype `HybridBlack(enable_oscar=True)`, and taps both raw and OSCAR output.
4. On first aligned cleaned output, the worker validates actual device layout/units, writes `.device.json`, and atomically writes `.processing.json` with `state: "recording"`.
5. The worker then writes `<output>.ready` containing `READY 1 <delay>`, emits `SAMPLES ...`, emits `READY 1 <delay>` on stdout, and enters its normal status loop.
6. C++ must accept readiness before `session.start()` starts the initial baseline and trial scheduler.
7. On stop, worker drains OSCAR output to the raw stop position, writes `state: "complete"`, emits final `SAMPLES` and `DONE`.

### C++ readiness paths as currently implemented

`Recorder::startOscar()` starts two concurrent paths:

- A reader thread blocks in `child.line(line)` and processes stdout protocol messages:
  - `READY 1 <delay>` sets `ready=true`, `delaySamples`, and `running=true`.
  - `SAMPLES <raw> <clean>` updates counters.
  - `ERROR ...` sets failure.
- The starter thread polls `<output>.ready` every approximately 100 ms for up to 120 seconds. A valid line should likewise set `ready=true`, `delaySamples`, and `running=true`, then remove the file.

The latest real incident proves neither path caused `startOscar()` to return successfully, even though the worker wrote large valid outputs. The leftover `.ready` artifact is especially important: either the starter never observed the file, the test ran a different executable/source than assumed, or the current state/locking/control flow prevents the polling branch from accepting it. Do not assume which without a deterministic test.

## Why Earlier Theories Are Not Sufficient

### Not simply slow OSCAR initialization

The timeout was raised from 35 to 90 and then 120 seconds. The worker was already producing more than 30,000 cleaned samples before the 120-second timeout. Increasing the limit again merely creates longer failed sessions.

### Not a missing OSCAR model or basic Python license

The worker produced aligned OSCAR output with delay 83 and recorded all expected metadata. The Unicorn Python license check returned `SUCCESS`.

### Not only disk-queue capacity

One earlier run reported `Recording disk queue overflow; no samples may be dropped.` Increasing the bounded queue removed that particular terminal failure, but later runs still timed out while producing complete raw/OSCAR files. Queue behavior and startup signaling are separate concerns.

### Not an acceptable successful recording

The session JSON is authoritative for the session state. All incident session JSONs are `failed` with zero completed trials. A worker processing JSON of `complete` means the worker finalized its own files after being stopped; it does not make the protocol session valid.

## Existing Hardware-Free Coverage and Its Gap

### Existing tests

- `gtec_Clib/terminal/test_oscar_session.py` compiles a C++ CLI against `mock_api.cpp` and starts a synthetic Python peer.
- `analysis/test_oscar_recording.py` tests `DualWriter`, alignment, optional real OSCAR model operation with a synthetic source, and worker stop/drain metadata.
- `gtec_Clib/terminal/test_recorder.py` and `test_session.py` cover the normal recorder/session behavior.

### Missing regression case

`test_oscar_session.py` only tests a peer that prints stdout `SAMPLES`, then stdout `READY`. It does **not** test:

1. Worker writes a valid readiness file but never writes stdout `READY`.
2. Worker sends `SAMPLES` before readiness while the `READY` line is delayed or absent.
3. C++ consumes `.ready`, removes it, transitions the session to running, and later accepts a matching stdout `READY` without treating it as duplicate/conflicting.
4. Invalid, partial, stale, or conflicting `.ready` contents fail closed and are cleaned or retained intentionally.
5. A readiness confirmation is durable enough for a process restart/error diagnostic and does not get confused with files from a prior session.

This gap explains why commit `868151a` could build and still fail on the measurement computer.

## Recommended Hardware-Free Investigation Plan

Do this before another hardware session. Keep changes small and demonstrate the failing condition with the existing synthetic peer.

1. Reproduce the intended file-only readiness path.
   - Extend `FAKE` in `gtec_Clib/terminal/test_oscar_session.py` with a mode such as `ready_file_only`.
   - In that mode, write `<output>.ready` atomically with exactly `READY 1 83\n`, write a valid `.device.json`, and emit monotonically increasing `SAMPLES` lines, but never stdout `READY`.
   - Expect session metadata to reach `running`; then issue `stop`; expect `aborted`, positive OSCAR counters, and no remaining `.ready` file.
   - This test should fail on the implementation that only depends on stdout. It should pass only once the file path is genuinely functional.

2. Test both orderings.
   - `ready_file_then_stdout_ready`: file first, matching stdout `READY` later.
   - `stdout_ready_then_file`: stdout first, file later or left behind.
   - Expected behavior: exactly one readiness transition, same delay accepted, no false error. Define whether the later file is removed by the controller or worker cleanup.

3. Test invalid/conflicting input.
   - Malformed file, unsupported version, nonpositive delay, extra token, and a delay that conflicts with stdout.
   - Expected behavior: fail before baseline, explicit error in session JSON, no task events, worker gets a controlled stop.

4. Instrument before redesigning.
   - Add temporary or permanent concise diagnostics to the worker log or a dedicated startup log: worker PID, exact readiness-file path, successful replace timestamp, and emitted protocol timestamp.
   - Add C++ diagnostics: selected worker path/Python path, readiness-file polling attempts or first observation, parsed readiness value, and cause of timeout. Avoid printing credentials or personal data.
   - Do not use stdout for diagnostics because stdout is the strict protocol channel.

5. Inspect the synchronization design with sanitizers/static reasoning.
   - `ready`, `failure`, `samples`, `cleanedSamples`, and `delaySamples` are mutex-protected in the shown paths; `running` is atomic.
   - Verify every access in `recorder.h`, including predicates, happens under the same mutex where required.
   - Verify the reader thread cannot starve the startup polling loop by repeatedly taking the mutex for high-rate `SAMPLES` messages.
   - Verify startup exits only after it has actually observed `ready` or `failure`, not a stale local `signaled` value.

6. Only then reconsider the design.
   - Prefer one explicit state contract as the source of truth, not several partially authoritative signals.
   - A reasonable candidate is a small atomically replaced startup-state JSON containing schema version, state, delay, raw/clean counts, PID, and error. C++ would poll it during startup and stdout would remain for live counters/error transport.
   - Do not implement this redesign until a synthetic test demonstrates why the current file path fails. The simpler defect may be polling/control-flow rather than architecture.

## Acceptance Criteria for a Future Fix

Without hardware, all of these must pass:

- `python gtec_Clib/terminal/test_oscar_session.py`, including the new file-only and ordering cases.
- `python gtec_Clib/terminal/test_recorder.py`.
- `python gtec_Clib/terminal/test_session.py`.
- `python -m unittest analysis.test_oscar_recording` in the intended Python environment; optional vendor tests may be skipped only if dependencies/licensing are unavailable, and that limitation must be stated.
- A clean MSVC Release build:

```powershell
& cmd.exe /c 'call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64 && cmake --build gtec_Clib\terminal\build-vs --config Release'
```

On hardware later, the minimum acceptance sequence is:

```text
GoToExp "DEV-OSCAR-CHECK"
open UN-2024.08.40
cue open
start session
status
mark hardware_check
session pause
session resume
status
stop
quit
```

The start must leave preparation and begin baseline. During recording raw and OSCAR counters must grow. The test session must be intentionally stopped and have session state `aborted`, worker processing state `complete`, and `oscar_samples >= stop_target_raw_samples`. Only after this passes should a full 45:04 OSCAR session be attempted.

## Separate Performance and Licensing Follow-Ups

These do not block the hardwareless handshake fix, but must be retained as explicit open risks:

- g.Pype warning: "Falling behind the amplifier ... after every read for 1 s." Measure CPU, disk latency, queue depth, and actual counter continuity during a long run. Do not raise `frame_size` or relax no-drop behavior without validating timing/alignment consequences.
- g.Pype applies `noncommercial_mark: true` while the Unicorn Python product check is `SUCCESS`. Clarify whether the intended study usage requires a separate g.Pype Runtime entitlement. Do not put activation keys or emails in Git.
- The current worker accesses vendor internals such as `source._device`; retain package-version pinning and fail closed if the expected layout changes.

## Relevant Paths

```text
acquisition/oscar_worker.py
acquisition/README.md
gtec_Clib/terminal/recorder.h
gtec_Clib/terminal/worker_process.h
gtec_Clib/terminal/test_oscar_session.py
analysis/test_oscar_recording.py
docs/oscar-integration.md
C:\EEG\recordings\EVM-P002\session_20261028_193910.csv.*   (external evidence; do not modify)
```

## Constraints for Astra

- No hardware is available. Do not claim real-headset success.
- Preserve raw recordings and never overwrite source CSVs.
- Keep OSCAR and raw modes separate; no silent fallback from failed OSCAR to raw.
- Do not weaken counter/alignment checks or turn queue overflow into sample dropping.
- Do not remove failed session metadata. It is the evidence that no task trials started.
- Do not expose or commit licenses, emails, names, or raw participant data.

## Hardware-free investigation update

28 October 2026, macOS host with Clang and a synthetic Python peer. **Windows/MSVC and headset verification remain outstanding.** The incident recordings were not accessed or modified. The 120-second production limit, OSCAR model, queue size, no-drop/alignment rules and 45:04 task protocol are unchanged.

### What was reproduced

The old implementation already passed a new **file-only READY** case under macOS: the session reached `running` without stdout `READY`. This does not reproduce the reported Windows timeout. The next case, stdout `READY` followed by a delayed `.ready`, failed deterministically: the session ran but the file remained unconsumed. The old starter stopped polling as soon as stdout won.

Independent code review found that the old deletion also ran while the input stream was open, an avoidable Windows sharing issue. Other defects were acceptance of trailing file lines, ignoring empty files until timeout, stale status time after a delayed file-only startup, and accepting `DONE` before readiness. These defects have been addressed. Neither mutex inspection nor the synthetic file-only test demonstrates a deadlock or a stale `signaled` variable. A leftover `.ready` therefore does **not** prove that readiness was never observed. The exact cause of the original Windows 120-second failure remains unproven.

### Implemented contract and diagnostics

- One shared, mutex-protected readiness transition handles both transports. Either can start recording; matching confirmations cause only one transition. An independent file monitor continues after stdout wins, while the pipe reader may block normally.
- A file is read completely with a small size limit and closed before deletion. Unsupported versions, nonpositive delays, partial/empty payloads and additional tokens fail closed. A malformed/conflicting file is retained as evidence. A valid file is removed; deletion errors are recorded explicitly.
- Readiness after worker finalization cannot restore `running`. `DONE` before readiness or before requested stop is an error. Unterminated stdout messages and pipe read errors have explicit causes. A file confirmation starts a fresh six-second status window.
- A conflict observed before startup prevents baseline and task events. A conflict arriving **after** an accepted confirmation is a runtime failure; existing events are preserved. It is impossible to reject a future delayed conflict before baseline while allowing either transport alone to start.
- Existing `.ready`, `.ready.tmp` and `.startup.log` files at the selected stem prevent overwrite. Failed-session evidence is preserved.
- `<output>.startup.log` records controller handshake/build identity (`oscar-startup-v2` plus compile time), actual EXE path on Windows, configured Python, absolute worker/ready paths, child PID, elapsed monotonic times, first counters, observed READY source/delay, deletion and rejection cause. `<output>.worker.log` adds `OSCAR_STARTUP` JSON entries for actual Python/PID/paths, pipeline start, successful atomic replace and before/after the first protocol emissions. No diagnostics are written to stdout.

### Verification and next Windows action

The expanded synthetic peer covers file-only operation, both orderings, duplicates, file readiness after more than six seconds without prior stdout status, malformed/partial/empty/version/delay/token cases, conflicting transports, early `DONE`/EOF, missing readiness, controlled stop, runtime error, bad exit and stalled status. A direct Recorder harness checks stale artifact refusal without modification. All files and binaries are synthetic and temporary.

Executed with `/Users/theoa/.venvs/eeg-mne/bin/python` and Clang on macOS:

| Check | Result |
|---|---|
| `gtec_Clib/terminal/test_oscar_session.py` | 29 synthetic peer scenarios plus 3 stale-artifact cases passed, including explicit CRLF file input and a matching file published during stop. |
| `gtec_Clib/terminal/test_recorder.py` | Passed. |
| `gtec_Clib/terminal/test_session.py` | Passed, including 250 plan seeds, timing/error cases and the accelerated complete 168-trial session. |
| `-m unittest analysis.test_oscar_recording` | 11 tests: 9 passed, 2 optional vendor tests skipped because pinned vendor packages are not installed in this environment. No new real-model result is claimed. |
| MSVC Release / Windows UI / real headset | Not run: this host has no Windows/MSVC/headset environment. |

Run the tests above in an **x64 Visual Studio 2022 Developer PowerShell/Command Prompt**, with `cl` available and the intended Python interpreter. Then rebuild the production Release EXE with the command above and launch that exact path. The `.startup.log` must identify the new controller and expected EXE/worker/Python paths. Absence of this log or a different identity is evidence to check the executable selection before repeating a long wait.

Perform the short `DEV-OSCAR-CHECK` sequence above before any full study session. If it still fails, preserve `.startup.log`, `.worker.log`, `.session.json` and `.processing.json` together. The last successful worker stage and controller observation distinguish initialization, file visibility/parsing, stdout transport, early exit and executable/path mismatches. Completed worker CSVs alone still do not validate a failed session. The performance warning and licensing follow-ups above remain open.
