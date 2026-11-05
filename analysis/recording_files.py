"""One explicit signal-selection contract for both viewers and ML importers."""
from dataclasses import dataclass
import json
from pathlib import Path
import warnings


def read_session_metadata(path):
    """Read UTF-8/BOM or legacy Windows-1252 JSON without replacing characters.

    Older Windows C++ recordings wrote device descriptions/units in the local
    code page. Fall back only on a Unicode decoding error, never on JSON errors.
    Source bytes and scientific metadata values remain unchanged.
    """
    path = Path(path)
    data = path.read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252')
        warnings.warn(f'{path.name}: ältere Windows-1252-Sitzungsmetadaten gelesen; '
                      'Originaldatei bleibt unverändert.', UnicodeWarning)
    return json.loads(text)


def eeg_unit_scale(unit):
    """Volts per recorded unit; recognize one evidenced legacy mojibake form.

    Some Windows JSON mixes ANSI descriptions with a UTF-8 micro sign. Reading
    the whole document as CP1252 yields exactly 'ÂµV'. Interpret only this known
    spelling with a warning; unknown/missing units remain unknown.
    """
    if unit == 'ÂµV':
        warnings.warn("Metadateneinheit 'ÂµV' als µV gelesen (bekannter Windows-Kodierungsfehler); "
                      'Originalmetadaten bleiben unverändert.', UnicodeWarning)
        return 1e-6
    return {'uV': 1e-6, 'µV': 1e-6, 'μV': 1e-6, 'mV': 1e-3, 'V': 1.}.get(unit)


@dataclass(frozen=True)
class RecordingFiles:
    raw: Path
    data: Path
    events: Path
    session: Path
    processing: Path
    signal: str
    label: str
    metadata: dict

    def validate_length(self, samples):
        if self.signal == "oscar" and samples != self.metadata["oscar_samples"]:
            raise ValueError("OSCAR file length differs from confirmed processing metadata.")


def resolve_recording(path, signal="auto"):
    if signal not in ("auto", "raw", "oscar"):
        raise ValueError("signal must be auto, raw or oscar.")
    path = Path(path)
    explicit_oscar = path.name.endswith(".oscar.csv")
    raw = Path(str(path)[:-len(".oscar.csv")]) if explicit_oscar else path
    events = Path(str(raw) + ".events.csv")
    session = Path(str(raw) + ".session.json")
    processing = Path(str(raw) + ".processing.json")
    session_meta = read_session_metadata(session) if session.exists() else {}
    meta = json.loads(processing.read_text(encoding="utf-8")) if processing.exists() else {}
    if signal == "auto":
        signal = "oscar" if (explicit_oscar or session_meta.get("processing_mode") == "oscar"
                               or meta.get("mode") == "oscar") else "raw"
    if signal == "raw":
        return RecordingFiles(raw, raw, events, session, processing, signal, "Rohdaten", {})
    clean = Path(str(raw) + ".oscar.csv")
    if (meta.get("schema_version") != 1 or meta.get("mode") != "oscar"
            or meta.get("state") != "complete" or meta.get("sampling_rate_hz") != 250
            or meta.get("raw_file") != raw.name or meta.get("oscar_file") != clean.name
            or not isinstance(meta.get("oscar_samples"), int) or meta["oscar_samples"] <= 0
            or not isinstance(meta.get("oscar_delay_samples"), int) or meta["oscar_delay_samples"] <= 0):
        raise ValueError("No complete, confirmed OSCAR output. Use --signal raw explicitly to inspect raw data.")
    if not clean.is_file() or not raw.is_file():
        raise ValueError("OSCAR session is missing raw or processed samples.")
    delay = meta["oscar_delay_samples"]
    label = f"OSCAR; {delay} Samples Verzögerung; auf Rohsample-Zeitachse ausgerichtet"
    if meta.get("noncommercial_mark"):
        label += "; g.Pype non-commercial use"
    return RecordingFiles(raw, clean, events, session, processing, signal, label, meta)
