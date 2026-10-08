# Unicorn API terminal

**Vollständige deutsche Bedienungsanleitung:** [VERWENDUNG.md](VERWENDUNG.md)

Interactive hardware test utility covering every function in the supplied
`unicorn.h`. Requires 64-bit Windows, the supplied Unicorn DLL, a working
Bluetooth adapter and a compatible headset. This is a manual diagnostic tool,
not an automated hardware test. It also supports background CSV recording
with a separate event log.

## Build on Windows

Install Visual Studio C++ build tools (Desktop development with C++) and CMake.
From PowerShell in the repository folder:

```powershell
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build -A x64
cmake --build gtec_Clib/terminal/build --config Release
& .\gtec_Clib\terminal\build\Release\unicorn_terminal.exe
```

CMake copies Unicorn.dll beside the executable. If Windows reports a missing
runtime dependency, install the Microsoft Visual C++ x64 runtime required by
the vendor DLL. Pair the headset through Windows or Unicorn Suite first.

## Example session

```text
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
(up to ten seconds at 250 Hz), prints the first five and optionally overwrites
a CSV in the current working directory. CSV headers follow the acquired channel
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
python3 gtec_Clib/terminal/test_recorder.py
```

The test links `mock_api.cpp` instead of the vendor DLL; the normal CMake build
never includes this simulated implementation. Windows linking, DLL loading,
Bluetooth communication and hardware behavior have not been tested here.

## Background recording and task markers

```text
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
`status`. Existing data or event files are refused. Parent folders must exist.
The default mode is `real`. After a timed recording ends, use `status` to
inspect its result; completion does not print asynchronously over your prompt.

During background recording, only `mark`, `status`, `help`, `stop`, `close`
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
