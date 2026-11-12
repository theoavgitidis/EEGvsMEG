"""BCI2000 1.0/1.1 files, calibrated EEG and complete integer state vectors.

No vendor library, MNE reader internals, device access or experiment control.
Specification: https://www.bci2000.org/mediawiki/index.php/Technical_Reference:BCI2000_File_Format
"""
from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote

import numpy as np

FORMATS = {"int16": "<i2", "int32": "<i4", "float32": "<f4"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode_token(value):
    return quote(str(value), safe="-_.") if str(value) else "%"


def decode_token(value):
    return "" if value == "%" else unquote(value, encoding="utf-8", errors="strict")


def _dimension(tokens, position):
    if position >= len(tokens):
        raise ValueError("Missing BCI2000 parameter dimension.")
    if tokens[position] == "{":
        try:
            end = tokens.index("}", position + 1)
        except ValueError as error:
            raise ValueError("Unclosed BCI2000 dimension labels.") from error
        return end - position - 1, end + 1
    try:
        count = int(tokens[position])
    except ValueError as error:
        raise ValueError("Invalid BCI2000 parameter dimension.") from error
    if count < 0:
        raise ValueError("Negative BCI2000 parameter dimension.")
    return count, position + 1


def parse_parameters(lines):
    """Decode values, retaining each original parameter line for provenance."""
    result = {}
    for line in lines:
        body = line.split("//", 1)[0].strip()
        if not body:
            continue
        match = re.fullmatch(r"\S+\s+(\S+)\s+(\S+?)\s*=\s*(.*)", body)
        if not match:
            raise ValueError("Malformed BCI2000 parameter line (section/type/name/value expected).")
        kind, name, value = match.groups()
        if name in result:
            raise ValueError(f"Duplicate BCI2000 parameter: {name}")
        tokens = re.findall(r"[{}]|[^\s{}]+", value)
        position, count = 0, 1
        if kind.endswith("list"):
            count, position = _dimension(tokens, 0)
        elif kind.endswith("matrix"):
            rows, position = _dimension(tokens, 0)
            cols, position = _dimension(tokens, position)
            count = rows * cols
        if len(tokens) < position + count:
            raise ValueError(f"Incomplete BCI2000 parameter: {name}")
        result[name] = {"type": kind, "values": [decode_token(v) for v in tokens[position:position + count]],
                        "line": line}
    return result


def _number(value, scales):
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([^\s]*)", value)
    if not match or match[2] not in scales:
        raise ValueError(f"Unsupported numeric value/unit: {value!r}")
    number = float(match[1]) * scales[match[2]]
    if not np.isfinite(number):
        raise ValueError("Non-finite BCI2000 calibration/rate.")
    return number


@dataclass
class Recording:
    path: Path
    sampling_rate: float
    channel_names: list
    signal_uv: np.ndarray  # samples x channels, no display or analysis filter
    states: dict
    parameters: dict
    state_definitions: dict
    data_format: str
    header_text: str

    def summary(self):
        return {"schema_version": 1, "format": "BCI2000", "sha256": sha256(self.path),
                "sampling_rate_hz": self.sampling_rate, "samples": len(self.signal_uv),
                "duration_s": len(self.signal_uv) / self.sampling_rate,
                "channel_names": self.channel_names, "calibrated_unit": "uV",
                "channel_names_from_header": bool(self.parameters.get("ChannelNames", {}).get("values")),
                "source_filter_parameters": {name: self.parameters[name]["values"] for name in
                    ("HighPassFilter", "LowPassFilter", "NotchFilter") if name in self.parameters},
                "data_format": self.data_format,
                "nonfinite_signal_values": int((~np.isfinite(self.signal_uv)).sum()),
                "states": {name: {"bits": self.state_definitions[name]["length"],
                                  "min": int(values.min()), "max": int(values.max()),
                                  "changes": int(np.count_nonzero(values[1:] != values[:-1]))}
                           for name, values in self.states.items()},
                "timing": "recorded sample order; state timestamps are not UTC or measured display onsets"}


def read_dat(path):
    path = Path(path)
    with path.open("rb") as stream:
        first = stream.readline(4096)
        if not first.endswith(b"\n"):
            raise ValueError("Missing/truncated BCI2000 first header line.")
        fields = {key.lower(): value for key, value in re.findall(rb"(\w+)\s*=\s*(\S+)", first)}
        fields = {key.decode("ascii"): value.decode("ascii") for key, value in fields.items()}
        try:
            header_length = int(fields["headerlen"])
            channels = int(fields["sourcech"])
            vector_length = int(fields.get("statevectorlen", fields.get("statevectorlength", "-1")))
        except (KeyError, ValueError) as error:
            raise ValueError("Missing/invalid BCI2000 header dimensions.") from error
        if fields.get("bci2000v", "1.0") not in ("1.0", "1.1"):
            raise ValueError("Unsupported BCI2000 file format version.")
        data_format = fields.get("dataformat", "int16")
        if data_format not in FORMATS:
            raise ValueError(f"Unsupported BCI2000 DataFormat: {data_format}")
        if not (len(first) <= header_length <= 64 * 1024 * 1024 and 1 <= channels <= 65536
                and 0 <= vector_length <= 65536):
            raise ValueError("Invalid BCI2000 header dimensions.")
        remaining = stream.read(header_length - len(first))
        if len(remaining) != header_length - len(first):
            raise ValueError("Truncated BCI2000 header.")
    try:
        header = (first + remaining).decode("utf-8")
    except UnicodeDecodeError:
        header = (first + remaining).decode("cp1252")
    sections, section = {"states": [], "parameters": []}, None
    for line in header.splitlines()[1:]:
        clean = line.strip()
        if clean == "[ State Vector Definition ]":
            section = "states"
        elif clean == "[ Parameter Definition ]":
            section = "parameters"
        elif clean:
            if section is None:
                raise ValueError("Unexpected content before BCI2000 header sections.")
            sections[section].append(clean)
    parameters = parse_parameters(sections["parameters"])
    definitions, occupied = {}, set()
    for line in sections["states"]:
        tokens = line.split()
        if len(tokens) != 5 or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", tokens[0]):
            raise ValueError("Malformed BCI2000 state definition.")
        name = tokens[0]
        try:
            length, default, byte, bit = map(int, tokens[1:])
        except ValueError as error:
            raise ValueError("Non-integer BCI2000 state layout.") from error
        if not (1 <= length <= 64 and byte >= 0 and 0 <= bit <= 7 and 0 <= default < 2**length):
            raise ValueError("Invalid BCI2000 state layout/default.")
        positions = set(range(byte * 8 + bit, byte * 8 + bit + length))
        if name in definitions or occupied & positions or max(positions) >= vector_length * 8:
            raise ValueError("Duplicate, overlapping or out-of-bounds BCI2000 state.")
        occupied |= positions
        definitions[name] = dict(length=length, default=default, byte=byte, bit=bit)
    dtype = np.dtype([("signal", FORMATS[data_format], (channels,)), ("state", "u1", (vector_length,))])
    size = path.stat().st_size - header_length
    if size <= 0 or size % dtype.itemsize:
        raise ValueError("Empty or truncated BCI2000 sample frames.")
    frames = np.fromfile(path, dtype=dtype, offset=header_length)
    if len(frames) * dtype.itemsize != size:
        raise ValueError("BCI2000 file changed during reading.")

    def values(name, count):
        if name not in parameters or len(parameters[name]["values"]) != count:
            raise ValueError(f"Missing/incorrect BCI2000 parameter: {name}; calibration is not guessed.")
        return parameters[name]["values"]

    rate = _number(values("SamplingRate", 1)[0], {"": 1, "Hz": 1, "kHz": 1000})
    if rate <= 0:
        raise ValueError("SamplingRate must be positive.")
    gain = np.array([_number(v, {"": 1, "uV": 1, "muV": 1, "µV": 1, "μV": 1, "mV": 1000, "V": 1e6})
                     for v in values("SourceChGain", channels)])
    if np.any(gain == 0):
        raise ValueError("SourceChGain must be nonzero.")
    offset = np.array([_number(v, {"": 1}) for v in values("SourceChOffset", channels)])
    names = (values("ChannelNames", channels) if parameters.get("ChannelNames", {}).get("values")
             else [f"EEG {i+1}" for i in range(channels)])
    if len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError("Empty or duplicate BCI2000 channel names.")
    if "SourceCh" in parameters and int(values("SourceCh", 1)[0]) != channels:
        raise ValueError("Conflicting SourceCh in BCI2000 header.")
    if "StateVectorLength" in parameters and int(values("StateVectorLength", 1)[0]) != vector_length:
        raise ValueError("Conflicting StateVectorLength in BCI2000 header.")
    states = {}
    for name, definition in definitions.items():
        output = np.zeros(len(frames), dtype=np.uint64)
        for bit in range(definition["length"]):
            position = definition["byte"] * 8 + definition["bit"] + bit
            output |= ((frames["state"][:, position // 8].astype(np.uint64) >> np.uint64(position % 8)) & np.uint64(1)) << np.uint64(bit)
        states[name] = output
    signal_uv = (frames["signal"].astype(np.float64) - offset) * gain
    return Recording(path, rate, names, signal_uv, states, parameters, definitions, data_format, header)


def write_dat(path, signal_uv, sampling_rate, channel_names, states, *, parameters=None, block_size=25):
    """Write a derived float32/uV file, refusing overwrites and reporting rounding."""
    signal_uv = np.asarray(signal_uv, dtype=np.float64)
    if (signal_uv.ndim != 2 or not len(signal_uv) or signal_uv.shape[1] != len(channel_names)
            or not np.isfinite(signal_uv).all() or len(set(channel_names)) != len(channel_names)
            or any(not isinstance(name, str) or not name for name in channel_names)
            or not np.isfinite(sampling_rate) or sampling_rate <= 0
            or not isinstance(block_size, int) or block_size <= 0):
        raise ValueError("Invalid EEG data, names, sampling rate or block size.")
    stored = signal_uv.astype("<f4")
    if not np.isfinite(stored).all():
        raise ValueError("EEG values exceed float32 storage range.")
    definitions, values, position = [], {}, 0
    for name, (width, data) in states.items():
        data = np.asarray(data)
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) or not isinstance(width, int) or not 1 <= width <= 32
                or data.shape != (len(stored),) or not np.issubdtype(data.dtype, np.integer)
                or np.any(data < 0) or np.any(data > 2**width - 1)):
            raise ValueError(f"Invalid state values/width: {name}")
        definitions.append(f"{name} {width} {int(data[0])} {position // 8} {position % 8}")
        values[name] = (position, width, data.astype(np.uint64))
        position += width
    vector_length = (position + 7) // 8
    count = len(channel_names)
    params = [f"Source int SourceCh= {count}", f"Source float SamplingRate= {sampling_rate:g}Hz",
              f"Source int SampleBlockSize= {block_size}",
              f"Source list ChannelNames= {count} " + " ".join(encode_token(n) for n in channel_names),
              f"Source floatlist SourceChGain= {count} " + " ".join(["1muV"] * count),
              f"Source floatlist SourceChOffset= {count} " + " ".join(["0"] * count),
              "Source int AlignChannels= 0", f"Source floatlist SourceChTimeOffset= {count} " + " ".join(["0"] * count),
              f"System int StateVectorLength= {vector_length}", "Storage string DataDirectory= .",
              "Storage int SubjectRun= 1", "Storage string ID_System= EEGvsMEG-offline-export",
              "Storage string ID_Amp= %", "Storage string ID_Montage= %"]
    # No online modules were run: retain the standard fields without inventing versions/addresses.
    for module in ("EEGsource", "SignalProcessing", "Application"):
        params.extend([f"System string {module}IP= %", f"System int {module}Port= 0",
                       f"System matrix {module}Version= 0 0"])
    params.append("System matrix OperatorVersion= 0 0")
    for name in ("SubjectName", "SubjectSession"):
        if name not in (parameters or {}):
            params.append(f"Storage string {name}= %")
    reserved = {name for line in params for name in [line.split("=", 1)[0].split()[-1]]}
    for name, value in (parameters or {}).items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) or name in reserved:
            raise ValueError(f"Invalid/reserved export parameter: {name}")
        params.append(f"EEGvsMEG string {name}= {encode_token(value)}")
    header_length = 1024
    while True:
        text = "\r\n".join([f"BCI2000V= 1.1 HeaderLen= {header_length} SourceCh= {count} StatevectorLen= {vector_length} DataFormat= float32",
                              "[ State Vector Definition ]", *definitions, "[ Parameter Definition ]", *params])
        encoded = text.encode("ascii")
        if len(encoded) + 4 <= header_length:
            break
        header_length *= 2
    # Padding precedes the final CRLF CRLF; HeaderLen is the exact data offset.
    header = encoded + b" " * (header_length - len(encoded) - 4) + b"\r\n\r\n"
    dtype = np.dtype([("signal", "<f4", (count,)), ("state", "u1", (vector_length,))])
    with Path(path).open("xb") as stream:
        stream.write(header)
        for start in range(0, len(stored), 65536):
            end = min(start + 65536, len(stored))
            frames = np.zeros(end - start, dtype=dtype)
            frames["signal"] = stored[start:end]
            for position, width, data in values.values():
                for bit in range(width):
                    at = position + bit
                    frames["state"][:, at // 8] |= (((data[start:end] >> np.uint64(bit)) & np.uint64(1)) << np.uint64(at % 8)).astype(np.uint8)
            stream.write(frames.tobytes())
    return float(np.max(np.abs(stored.astype(float) - signal_uv)))


def to_mne(path, channels=None):
    """Keep states as dimensionless misc channels; plots must pick EEG explicitly."""
    import mne
    try:
        from .event_annotations import event_descriptions
    except ImportError:
        from event_annotations import event_descriptions
    recording = read_dat(path)
    if recording.parameters.get("AlignChannels", {}).get("values", ["0"]) != ["0"]:
        raise ValueError("AlignChannels is enabled; channel time alignment is not implemented.")
    if channels is None:
        pattern = r"(?:EEG\s*\d+|(?:Fp|AF|F|FT|FC|T|C|TP|CP|P|PO|O|I)[pz\d]+)"
        channels = [name for name in recording.channel_names if re.fullmatch(pattern, name, re.I)]
    if not channels or len(set(channels)) != len(channels) or not set(channels) <= set(recording.channel_names):
        raise ValueError("Choose EEG channels explicitly with --bci-channels; channel types are not guessed.")
    indices = [recording.channel_names.index(name) for name in channels]
    data = recording.signal_uv[:, indices].T * 1e-6
    if not np.isfinite(data).all():
        raise ValueError("Non-finite EEG; inspect the recording before viewing/exporting.")
    state_names = [f"BCI::{name}" for name in recording.states]
    if set(channels) & set(state_names):
        raise ValueError("EEG/state channel name collision.")
    if any(np.any(values > 2**53) for values in recording.states.values()):
        raise ValueError("A state exceeds exact float64 integer precision; use NPZ state export.")
    if state_names:
        data = np.vstack([data, *[values.astype(float)[None, :] for values in recording.states.values()]])
    raw = mne.io.RawArray(data, mne.create_info([*channels, *state_names], recording.sampling_rate,
                                              ["eeg"] * len(channels) + ["misc"] * len(state_names)), verbose="ERROR")
    raw.info["description"] = "BCI2000; Headerkalibrierung nach V; States unverändert als misc; keine zusätzliche Filterung"
    source_filters = [f"{name}={','.join(recording.parameters[name]['values'])}" for name in
                      ("HighPassFilter", "LowPassFilter", "NotchFilter") if name in recording.parameters]
    if source_filters:
        raw.info["description"] += "; gespeicherte SourceFilter-Parameter: " + ", ".join(source_filters)
    sidecar = Path(str(path) + ".metadata.json")
    onsets, descriptions = [], []
    if sidecar.exists():
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if (not isinstance(metadata, dict) or metadata.get("schema_version") != 1
                or metadata.get("dat_sha256") != sha256(path)
                or not isinstance(metadata.get("events_file"), str)
                or not isinstance(metadata.get("events_sha256"), str)
                or not isinstance(metadata.get("original_start_sample"), int)
                or metadata["original_start_sample"] < 0
                or metadata.get("original_stop_sample") != metadata["original_start_sample"] + raw.n_times
                or recording.parameters.get("EvmOriginSample", {}).get("values") != [str(metadata["original_start_sample"])]
                or not isinstance(metadata.get("signal_description"), str)):
            raise ValueError("BCI2000 export sidecar does not match the data file.")
        name = metadata["events_file"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Unsafe event sidecar path.")
        event_path = sidecar.parent / name
        if sha256(event_path) != metadata["events_sha256"]:
            raise ValueError("BCI2000 event sidecar hash mismatch.")
        with event_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        # Resolve status on the ENTIRE log before slicing a block.
        labels = event_descriptions(rows)
        origin = metadata["original_start_sample"]
        for row, label in zip(rows, labels):
            sample = float(row["samples_received"]) - origin
            if np.isfinite(sample) and 0 <= sample < raw.n_times:
                onsets.append(sample / recording.sampling_rate)
                descriptions.append(label)
        raw.info["description"] += "; " + metadata["signal_description"]
    else:
        for name in ("StimulusCode", "TargetCode", "EvmClass"):
            if name not in recording.states:
                continue
            values = recording.states[name]
            changes = np.flatnonzero(np.r_[True, values[1:] != values[:-1]])
            for sample in changes:
                onsets.append(sample / recording.sampling_rate)
                context = [f"{key}={int(recording.states[key][sample])}" for key in
                           ("EvmRun", "EvmBlock", "EvmTrial", "EvmAttempt", "EvmStatus") if key in recording.states]
                descriptions.append(" | ".join([f"{name}={int(values[sample])}", *context]))
    raw.set_annotations(mne.Annotations(onsets, np.zeros(len(onsets)), descriptions))
    return raw
