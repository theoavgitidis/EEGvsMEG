"""One explicit signal-selection contract for both viewers and ML importers."""
from dataclasses import dataclass
import json
from pathlib import Path


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
    session_meta = json.loads(session.read_text(encoding="utf-8")) if session.exists() else {}
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
