"""Open Unicorn CSV recordings as traces, spectra or interactive waterfalls."""
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
    parser.add_argument("--view", choices=["traces", "waterfall"], default="traces",
                        help="Zeitkurven/Spektrogramm oder interaktive Amplituden-/Bandpower-Wasserfälle")
    parser.add_argument("--start", type=float, default=0, help="Start des Anzeigefensters in Sekunden")
    parser.add_argument("--duration", type=float, default=10, help="Länge des Anzeigefensters in Sekunden")
    parser.add_argument("--scale-uv", type=float,
                        help="Gemeinsamer +/- Bereich in µV um den Median jedes Kanals")
    parser.add_argument("--no-show", action="store_true", help="Aufnahme und Optionen ohne Anzeige prüfen")
    parser.add_argument("--filtered", action="store_true", help="Anzeigekopie: 50-Hz-Notch und 0.5–30-Hz-Bandpass")
    parser.add_argument("--psd", action="store_true", help="Frequenzspektrum statt Zeitkurven anzeigen")
    parser.add_argument("--spectrogram-channel", help="Startkanal des Spektrogramms, z. B. 'EEG 3'")
    parser.add_argument("--frequency-scale", choices=["log", "linear"], default="log",
                        help="Frequenzachse des Spektrogramms (Standard: log)")
    parser.add_argument("--spectrogram-max", type=float, default=100,
                        help="Spektrogramm-Obergrenze in Hz, begrenzt durch Nyquist (Standard: 100)")
    args = parser.parse_args()
    if args.psd and args.view == "waterfall":
        parser.error("--psd und --view waterfall können nicht gemeinsam verwendet werden.")
    try:
        raw = load_recording(args.csv, args.unit)
        print(f"Kanäle: {raw.ch_names}; Samples: {raw.n_times}; nominale Dauer: {raw.n_times / 250:.3f} s")
        if not np.isfinite(args.duration) or args.duration <= 0 or not np.isfinite(args.start) or not 0 <= args.start <= raw.times[-1]:
            raise ValueError("duration muss positiv sein und start innerhalb der Aufnahme liegen.")
        if args.scale_uv is not None and (not np.isfinite(args.scale_uv) or args.scale_uv <= 0):
            raise ValueError("scale-uv muss positiv sein.")
        if args.spectrogram_channel is not None and args.spectrogram_channel not in raw.ch_names:
            raise ValueError(f"Unbekannter Spektrogrammkanal: {args.spectrogram_channel}. Auswahl: {raw.ch_names}.")
        if not np.isfinite(args.spectrogram_max) or args.spectrogram_max <= .5:
            raise ValueError("spectrogram-max muss endlich und größer als 0.5 Hz sein.")
        if args.filtered:
            raw = raw.copy().notch_filter(50).filter(0.5, 30)
            print("Gefilterte Anzeigekopie; die CSV bleibt unverändert. Kein OSCAR/keine Bewegungskorrektur.")
        if args.no_show:
            return
        if args.psd:
            import matplotlib.pyplot as plt
            if raw.n_times < 2:
                raise ValueError("Zu wenige Samples für ein Spektrum.")
            raw.compute_psd(method="welch", fmin=0, fmax=100,
                            n_fft=min(1024, raw.n_times)).plot()
            plt.show(block=True)
        elif args.view == "waterfall":
            if __package__:
                from .waterfall_browser import serve_waterfall
            else:
                from waterfall_browser import serve_waterfall
            serve_waterfall(raw, start=args.start, duration=args.duration,
                            scale_uv=args.scale_uv, title=args.csv.name,
                            filter_label="50 Hz notch + 0.5–30 Hz band-pass" if args.filtered else "Unfiltered")
        else:
            from matplotlib import pyplot as plt
            if __package__:
                from .eeg_browser import create_browser
            else:
                from eeg_browser import create_browser
            create_browser(raw, start=args.start, duration=args.duration,
                           scale_uv=args.scale_uv, title=args.csv.name,
                           filter_label="50 Hz notch + 0.5–30 Hz band-pass" if args.filtered else "Unfiltered",
                           spectrogram_channel=args.spectrogram_channel,
                           frequency_scale=args.frequency_scale, spectrogram_max=args.spectrogram_max)
            plt.show(block=True)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
