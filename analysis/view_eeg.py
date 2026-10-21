"""Open Unicorn terminal CSV recordings in MNE without modifying them."""
import argparse
import csv
from pathlib import Path
import re
import warnings

import numpy as np
import mne
if __package__:
    from .event_annotations import event_descriptions
else:
    from event_annotations import event_descriptions


def load_recording(path, unit):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        names = [name for name in reader.fieldnames or [] if re.fullmatch(r"EEG [1-8]", name)]
        if not names:
            raise ValueError("Keine EEG-Spalten gefunden. Erwartet: EEG 1 bis EEG 8.")
        names.sort(key=lambda name: int(name.split()[1]))
        values, indices, counters = [], [], []
        for row in reader:
            values.append([float(row[name]) for name in names])
            if "sample_index" in row:
                indices.append(float(row["sample_index"]))
            if "Counter" in row:
                counters.append(float(row["Counter"]))
    if not values:
        raise ValueError("Die Aufnahme hat keine Datenzeilen.")
    data = np.asarray(values, dtype=float).T
    if not np.isfinite(data).all():
        raise ValueError("Die EEG-Daten enthalten NaN oder unendliche Werte.")
    if indices and not np.array_equal(indices, np.arange(len(values))):
        raise ValueError("sample_index ist nicht fortlaufend ab 0; Zeitachse muss geprüft werden.")
    if counters and np.any(np.diff(counters) != 1):
        warnings.warn("Zählerunterbrechungen vorhanden: Die nominale Zeitachse kann Sample-Lücken verbergen.")
    scale = {"uV": 1e-6, "mV": 1e-3, "V": 1}[unit]
    info = mne.create_info(names, sfreq=250, ch_types="eeg")
    raw = mne.io.RawArray(data * scale, info)
    events_path = Path(str(path) + ".events.csv")
    if events_path.exists():
        onsets, descriptions = [], []
        with events_path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            required = {"samples_received", "label"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Ereignisdatei enthält nicht samples_received und label.")
            rows = list(reader)
        for row, description in zip(rows, event_descriptions(rows)):
            onset = float(row["samples_received"]) / 250
            if not np.isfinite(onset) or not 0 <= onset <= raw.times[-1]:
                warnings.warn(f"Marker außerhalb der Aufnahme übersprungen: {row['label']}")
                continue
            onsets.append(onset)
            descriptions.append(description)
        raw.set_annotations(mne.Annotations(onsets, [0] * len(onsets), descriptions))
        print(f"{len(onsets)} Marker importiert (Positionen sind Näherungen aus samples_received / 250).")
    else:
        print("Keine separate Ereignisdatei gefunden; Anzeige ohne Marker.")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--unit", required=True, choices=["uV", "mV", "V"],
                        help="EEG-Einheit aus dem Recorder-Befehl config; nicht raten.")
    parser.add_argument("--filtered", action="store_true", help="Anzeigekopie: 50-Hz-Notch und 0.5–30-Hz-Bandpass")
    parser.add_argument("--psd", action="store_true", help="Frequenzspektrum statt Zeitkurven anzeigen")
    args = parser.parse_args()
    raw = load_recording(args.csv, args.unit)
    print(f"Kanäle: {raw.ch_names}; Samples: {raw.n_times}; nominale Dauer: {raw.n_times / 250:.3f} s")
    if args.filtered:
        raw = raw.copy().notch_filter(50).filter(0.5, 30)
        print("Gefilterte Anzeigekopie; die CSV bleibt unverändert. Kein OSCAR/keine Bewegungskorrektur.")
    if args.psd:
        import matplotlib.pyplot as plt
        if raw.n_times < 2:
            raise ValueError("Zu wenige Samples für ein Spektrum.")
        raw.compute_psd(method="welch", fmin=0, fmax=100,
                        n_fft=min(1024, raw.n_times)).plot()
        plt.show(block=True)
    else:
        mne.viz.set_browser_backend("matplotlib")
        raw.plot(duration=min(10, raw.n_times / 250), n_channels=len(raw.ch_names),
                 scalings={"eeg": 50e-6}, block=True)


if __name__ == "__main__":
    main()
