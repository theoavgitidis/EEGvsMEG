# Unicorn API terminal

**OSCAR-Stand 27.10.2026:** `start session` nimmt standardmäßig mit OSCAR über Python auf; `start session raw` wählt ausdrücklich Rohdaten. Beide Varianten bleiben getrennt gespeichert. Einrichtung, Geräteübergabe, Signalwahl und noch erforderliche Windows-/Headset-Abnahme: [OSCAR-Anleitung](../../acquisition/README.md). Beide Viewer bevorzugen für neue OSCAR-Sitzungen die bereinigten Daten; `--signal raw` wählt Rohdaten. FIF-Exporte enthalten die gewählte Variante vor zusätzlichen Anzeigefiltern.

**Implementierte Sitzung 2.0 (45:04 min, 168 Trials):** [SESSION_ANLEITUNG.md](SESSION_ANLEITUNG.md).
`start session` runs baselines, randomized unilateral motor/imagery trials and bilateral/cognitive comparison tasks, breaks, recording and markers.
Use `session pause`, `session resume`, and `stop` to intervene; `mark LABEL` logs observations without changing session cues.

**Wissenschaftliches Protokoll:** [Versuchsprotokoll](../../docs/experiment-protocol.md). Links-/Rechts-Aufgaben und mentale Vergleichsbedingungen sind hardwarefrei geprüft; Windows-/Headset-Abnahme bleibt erforderlich. Technischer Stand: [Sitzungsspezifikation](../../docs/session-automation-plan.md).

**Vollständige deutsche Bedienungsanleitung:** [VERWENDUNG.md](VERWENDUNG.md)

**CSV-Aufnahmen mit MNE ansehen:** [MNE_ANLEITUNG.md](MNE_ANLEITUNG.md).
Use `view_eeg.py` in the repository root to import EEG and event labels,
view recordings in separate EEG axes with a dedicated marker timeline and selected event details, and optionally export FIF or PNG files. Auto scaling is per channel and visible window; displayed µV ranges make the scale explicit. The CSV unit must
be supplied explicitly (for example `--unit uV`, after checking `config`).

The viewer runs separately from the Unicorn CLI on Windows or macOS and opens completed recordings. Copy the entire participant folder into `recordings/` next to the repository, then open the main EEG `.csv`; its matching `.csv.events.csv` loads automatically. The guide includes installation, exact launch commands, controls, filtering, exports, and the alternative spectrum viewer.

Click marker ticks for full details; `< Event` / `Event >` also select individual events with identical timestamps. Automatic ranges differ per channel. Use `--scale-uv 100` for a common ±100 µV display range and check any `CLIPPED` indicators. `--snapshot` saves the initial view, including explicit display filters; `--save-fif` saves unfiltered EEG and complete imported annotations. The source CSV files remain unchanged.

Manual participant display: `cue open` opens a Windows window. During a manual
background recording started with `record`, `mark hands_up`, `mark legs_up`, `mark substract 7 from 100` and
`mark rest` both update it and log the marker. For arbitrary instructions use
`cue trial_01 | Hebe deine Hände hoch`. See the German guide for timing limits.

Interactive hardware test utility covering every function in the supplied
`unicorn.h`. Requires 64-bit Windows, the supplied Unicorn DLL, a working
Bluetooth adapter and a compatible headset. This is a manual diagnostic tool,
not an automated hardware test. It also supports background CSV recording
with a separate event log and an automated pilot session. See the
[project overview](../../README.md) for the current workflow.

## Build on Windows

Install Visual Studio 2022 or its Build Tools with Desktop development with C++
(including the Windows SDK), and CMake.
From PowerShell in the repository folder:

```powershell
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build-vs -G "Visual Studio 17 2022" -A x64
cmake --build gtec_Clib/terminal/build-vs --config Release
& .\gtec_Clib\terminal\build-vs\Release\unicorn_terminal.exe
```

`-G "Visual Studio 17 2022"` explicitly selects the Visual Studio 2022 build
system; `-A x64` selects a 64-bit build. Without `-G`, CMake may choose NMake,
which does not support `-A` and reports that it does not support platform
specification. The `build-vs` folder avoids reusing an earlier NMake configuration
in `build`. If `build-vs` already uses another generator, choose a new folder
and update all three commands. Run `cmake --help` to list generators; if you use
another Visual Studio version, select its corresponding generator. If Visual
Studio or a C++ compiler cannot be found, install the C++ workload through the
Visual Studio Installer.

CMake copies Unicorn.dll beside the executable. If Windows reports a missing
runtime dependency, install the Microsoft Visual C++ x64 runtime required by
the vendor DLL. Pair the headset through Windows or Unicorn Suite first.

## Experiment folders

Recordings now go to `EEG/recordings/<experiment>/`, beside the `EEGvsMEG`
repository. CMake fixes this absolute base path when configuring, so launching
from another working directory does not change it. Reconfigure and rebuild if
moving the repository or distributing the executable to another machine.

```text
NewExp "Pilot 01"
ListExp
Where
GoToExp "Pilot 01"
```

`NewExp` creates and activates a folder; if it already exists, use `GoToExp`.
`GoToExp` activates an existing folder. `ListExp` marks the active folder with
`*`; `Where` prints its full path. The prompt always shows the active experiment,
for example `[Pilot 01] >`. Each new terminal session starts without a selected
experiment. Select one before `record`, manual `start`, or `start session`.

Top-level command names are case-insensitive; `session`, `pause`, `resume`,
`order`, `real`, `test` and cue subcommands use the lowercase spelling shown.
Names support spaces and Unicode; quote names
containing spaces. Windows reserved names, invalid characters and path traversal
are rejected. `record` and `read` accept filenames only, never other directories.
EEG data and `.events.csv` labels stay together. Existing files are refused,
including manual `read` exports. Experiment changes are blocked during both
manual acquisition and background recording; `Where` and `ListExp` remain usable.
Earlier recordings are not moved automatically.

If the executable is still running, exit it with `quit` before rebuilding. An
active EXE cannot be replaced on Windows. A separate build folder can be used
while the existing terminal remains open.

## Example session

### Automatic pilot session

```text
NewExp "VP01"
scan paired
open YOUR_SERIAL
config
cue open
start session
```

Use `GoToExp "VP01"` for an existing folder. All eight EEG channels must be enabled.
Move the cue window to the participant monitor before starting. The session enters
fullscreen and records continuously, including breaks. The planned duration is
45:04; unplanned pauses and trial repeats extend it.

`session pause` freezes the schedule; `session resume` repeats an interrupted trial
or baseline. `stop` displays PAUSE before waiting for recorder cleanup.
During an automated session, `mark LABEL` logs an observation without changing
the display, and manual `cue` commands are blocked. Use `session order imagery
motorik` before starting to change run order. See
[SESSION_ANLEITUNG.md](SESSION_ANLEITUNG.md) for displays, files and recovery.

### Manual experiment and cue commands

| Command | Behavior |
|---|---|
| `NewExp "NAME"` | Creates and activates an experiment folder; acquisition must be stopped. |
| `GoToExp "NAME"` | Selects an existing experiment folder; acquisition must be stopped. |
| `ListExp` | Lists experiments and marks the active one with `*`. |
| `Where` | Prints the active folder, or the base folder if none is selected. |
| `cue open` | Opens the participant window with `+`; no headset connection, recording or marker. |
| `cue close` | Closes only the participant window; recording continues. |
| `cue rest` | Shows `+` in the open window without writing a marker. |
| `cue text TEXT` | Shows custom text in the open window without writing a marker. |
| `cue LABEL \| TEXT` | Shows text and logs the label; requires an open window and active background recording. |
| `mark LABEL` | With manual `record`, logs a label and updates an open cue window. During `start session`, logs an observation only. |

The cue commands in this table describe manual operation outside an automatic
session. During `start session`, the session controls the display.

`open SERIAL` connects the headset, whereas `cue open` opens the display.
`close` stops acquisition and disconnects the headset; it leaves the display open.
`cue close` only closes the display. `stop` leaves both the connection and the
display intact. Finish a session with `stop`, `cue close`, `close`, then `quit`.
Cue subcommands `open`, `close`, `rest`, and `text` must be lowercase.
Enter `cue trial_01 | Raise your hands` inside the Unicorn terminal; the `|`
separates the logged label from the display text. Extra quotation marks become
part of that label/text. Preview commands never log markers; use `mark rest`
or `cue rest_start | +` to log a rest phase.

```text
NewExp "Pilot 01"
Where
version
error
bluetooth
scan paired
open YOUR_SERIAL
info
config
channels
index EEG 1
enable 0 1
start test
read 250 "test.csv"
stop
start real
read 250 "measurement.csv"
stop
outputs
outputs 0
close
quit
```

`scan unpaired` searches for unpaired devices and may take a long time; it
does not pair them. `enable` uses configuration indices (0..16), whereas
`index` returns the position within the current acquired scan. Query `config`
for channel names, units, ranges and enabled flags.

`start test` still requires a connected headset. `read` takes 1..2500 scans
(up to ten seconds at 250 Hz), prints the first five and optionally saves
a new CSV in the active experiment folder. Existing files are refused. CSV headers follow the acquired channel
indices. There are no added timestamps or experiment markers.

After starting, run `read` promptly. Acquisition continues while the terminal
waits for commands, so long pauses can overflow the vendor buffer. After an
overflow, stop and restart acquisition. For continuous recordings, use the
background `record` command described below.

`outputs VALUE` writes an eight-bit mask and reads it back. For example, 1
sets bit 0 high and 0 sets all bits low. These calls may be unsupported on
your headset; check the connected hardware before using outputs. The program
does not automatically reset output states on exit.

API errors show their code and the text from `UNICORN_GetLastErrorText`.
Quit or terminal input EOF attempts to stop acquisition and close the device.
Forcefully terminating the process cannot guarantee cleanup.

## Buffer length discrepancy

The vendor header describes the GetData buffer length in floats, but the
supplied example passes bytes. This utility follows the example and allocates
four times the required float storage so either interpretation fits the
allocated memory. Only the requested scans are exported. Actual behavior
must be checked with the supplied DLL on Windows.

## Validation

C++17 syntax checked with Clang on macOS. Hardware-free integration tests
cover timed recording, markers and CSV quoting, exclusive background API
access, manual stopping, overwrite protection and simulated connection failure:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python -m unittest analysis.test_event_annotations analysis.test_eeg_browser analysis.test_view_eeg_cli
```

Run with MSVC `cl` available in an x64 Developer Command Prompt, or with `clang++` on PATH. Test recordings use a temporary folder.

The test links `mock_api.cpp` instead of the vendor DLL; the normal CMake build
never includes this simulated implementation. Bluetooth communication and hardware behavior require a connected headset. Earlier experiment-folder work was documented as built with MSVC. The current
automatic-session changes were tested with Clang on macOS and simulated hardware;
a current Windows build, real cue window, terminal rendering and vendor-DLL run
remain to be validated. The session tests cover 250 seeds, six run orders, a full
accelerated session, pause/repeat, window loss, recorder errors, delayed transitions
and PAUSE display before a blocked stop. Viewer tests require mne, numpy, pandas and matplotlib. They cover dense markers
and resizing, separate signal axes, scales and clipping indicators, navigation,
unchanged data, a real headless PNG export and an unfiltered FIF round trip.

## Manual background recording and task markers

This section describes `record`. For automatic task timing use `start session`
as described above; manual markers then remain observations only.

```text
GoToExp "Pilot 01"
open YOUR_SERIAL
record 60 "participant01.csv" real
mark baseline_start
status
mark baseline_end
stop
close
```

`record SECONDS CSV_PATH [real|test]` starts a background worker. Positive
durations record ceil(seconds * 250) scans; `0` records until `stop`, `close`,
`quit` or input EOF. An API or file error ends recording and is shown by
`status`. Existing data or event files are refused. Select an experiment first.
The default mode is `real`. After a timed recording ends, use `status` to
inspect its result; completion does not print asynchronously over your prompt.

During background recording, only `mark`, all `cue` commands, `status`, `Where`, `ListExp`, `help`, `stop`, `close`
and `quit` are accepted. This prevents simultaneous access to the vendor DLL.
The worker reads blocks of 25 scans (nominally 100 ms) and flushes data once
per second and at completion. Stop waits for the current GetData call to return;
if the DLL blocks during a connection failure, stopping can also block.

The EEG CSV contains `sample_index`, `nominal_time_s` (sample index / 250),
`host_read_utc_s` (Unix seconds when a block was received), and enabled channel
values. All scans in a block share the same host receipt timestamp. Nominal
time does not account for lost samples and is not a hardware timestamp.

`mark LABEL` writes to `CSV_PATH.events.csv`: UTC host time, monotonic elapsed
time since acquisition was requested, number of samples received so far, and
the label. Labels may contain spaces, commas and quotes. Markers describe when
the terminal processed the command, not an exact EEG sample boundary; buffered
Bluetooth data and human reaction introduce uncertainty. These timestamps alone
do not establish precise synchronization with MEG or another computer.

`status` reports sample count, nominal duration, counter discontinuities, the
latest battery and validation values when those channels are enabled, and
recording errors. Counter discontinuities include resets/wraps and are not an
exact count of missing samples. Battery and validation are reported as supplied
by the device; this utility does not assume thresholds or validation semantics.

Use background `record` for extended acquisition. The older `start` / `read`
commands remain available for manual API testing and retain their buffer-overflow
limitation when you pause between reads.
