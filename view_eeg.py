"""Display Unicorn EEG as traces with a spectrogram or interactive waterfall plots."""
import argparse
from pathlib import Path
import re

import mne
import numpy as np
import pandas as pd
from analysis.event_annotations import event_descriptions
from analysis.recording_files import resolve_recording


def load_recording(path, unit, signal="auto"):
    selected = resolve_recording(path, signal)
    if selected.signal == "oscar" and unit != "uV":
        raise ValueError("OSCAR output is in uV; use --unit uV.")
    path = selected.data
    table = pd.read_csv(path)
    selected.validate_length(len(table))
    print(f"Signal: {selected.label}; Datei: {path}")
    names = sorted((c for c in table.columns if re.fullmatch(r"EEG \d+", c)),
                   key=lambda c: int(c.split()[-1]))
    if table.empty or not names:
        raise ValueError("CSV needs samples and EEG columns named 'EEG 1', etc.")
    if "sample_index" in table:
        if not np.array_equal(table.sample_index.to_numpy(), np.arange(len(table))):
            raise ValueError("sample_index must be continuous starting at zero.")
    data = table[names].to_numpy(dtype=float, copy=True).T
    if not np.isfinite(data).all():
        raise ValueError("EEG contains missing or nonfinite values.")
    data *= {"uV": 1e-6, "mV": 1e-3, "V": 1.0}[unit]
    raw = mne.io.RawArray(data, mne.create_info(names, 250.0, "eeg"))
    if "Counter" in table:
        count = np.count_nonzero(np.diff(table.Counter.to_numpy(dtype=float)) != 1)
        print(f"Counter discontinuities (including resets/wraps): {count}")
    raw.info["description"] = selected.label
    event_path = selected.events
    if event_path.exists():
        events = pd.read_csv(event_path, keep_default_na=False)
        if not {"samples_received", "label"}.issubset(events.columns):
            raise ValueError("Event CSV needs samples_received and label.")
        positions = pd.to_numeric(events.samples_received, errors="raise").to_numpy(dtype=float)
        onsets = positions / raw.info["sfreq"]
        valid = np.isfinite(onsets) & (onsets >= 0) & (onsets <= raw.times[-1])
        if not valid.all():
            print(f"Skipped {np.count_nonzero(~valid)} markers outside the sample timeline.")
        descriptions = event_descriptions(events.to_dict("records"))
        raw.set_annotations(mne.Annotations(onsets[valid], np.zeros(valid.sum()),
                                           [text for text, keep in zip(descriptions, valid) if keep]))
        print(f"Imported {int(valid.sum())} event markers (sample positions are approximate).")
        print("Select markers in the viewer for their full descriptions.")
    else:
        print("No event CSV found; displaying EEG without labels.")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to the EEG CSV")
    parser.add_argument("--signal", choices=["auto", "raw", "oscar"], default="auto",
                        help="Neue OSCAR-Sitzungen: bereinigte Daten; raw wählt ausdrücklich Rohdaten")
    parser.add_argument("--unit", required=True, choices=["uV", "mV", "V"],
                        help="EEG unit reported by the terminal's config command")
    parser.add_argument("--view", choices=["traces", "waterfall"], default="traces",
                        help="Display traces/spectrogram or interactive amplitude/bandpower waterfalls")
    parser.add_argument("--start", type=float, default=0, help="Display start in seconds")
    parser.add_argument("--duration", type=float, default=10, help="Display window in seconds")
    parser.add_argument("--highpass", type=float, help="Optional high-pass frequency in Hz")
    parser.add_argument("--lowpass", type=float, help="Optional low-pass frequency in Hz")
    parser.add_argument("--scale-uv", type=float, help="Shared +/- display range in microvolts, around each channel's median")
    parser.add_argument("--spectrogram-channel", help="Initial spectrogram channel, e.g. 'EEG 3' (default: first channel)")
    parser.add_argument("--frequency-scale", choices=["log", "linear"], default="log",
                        help="Spectrogram frequency axis (default: log)")
    parser.add_argument("--spectrogram-max", type=float, default=100,
                        help="Highest displayed frequency in Hz, capped at Nyquist (default: 100)")
    parser.add_argument("--save-fif", type=Path, help="Save imported EEG and labels (before optional filtering)")
    parser.add_argument("--snapshot", type=Path, help="Save browser view as a PNG")
    parser.add_argument("--no-show", action="store_true", help="Import/export without an interactive window")
    args = parser.parse_args()
    try:
        if args.view == "waterfall" and args.snapshot:
            raise ValueError("--snapshot is only available for --view traces; use the waterfall viewer's PNG buttons.")
        for output in (args.save_fif, args.snapshot):
            if output and output.exists():
                raise ValueError(f"Output already exists: {output}")
        raw = load_recording(args.csv, args.unit, args.signal)
        print(f"\nCSV: {args.csv.resolve()}\nChannels: {raw.ch_names}")
        print(f"Samples: {raw.n_times}; nominal duration: {raw.n_times / 250:.3f} s; labels: {len(raw.annotations)}")
        print(f"Assumed CSV unit: {args.unit}; MNE data unit: V")
        if not np.isfinite(args.duration) or args.duration <= 0 or not np.isfinite(args.start) or not 0 <= args.start <= raw.times[-1]:
            raise ValueError("duration must be positive and start within the recording.")
        if args.scale_uv is not None and (not np.isfinite(args.scale_uv) or args.scale_uv <= 0):
            raise ValueError("scale-uv must be positive.")
        for cutoff in (args.highpass, args.lowpass):
            if cutoff is not None and (not np.isfinite(cutoff) or not 0 < cutoff < 125):
                raise ValueError("Filter frequencies must be between 0 and 125 Hz.")
        if args.highpass and args.lowpass and args.highpass >= args.lowpass:
            raise ValueError("highpass must be lower than lowpass.")
        if args.spectrogram_channel is not None and args.spectrogram_channel not in raw.ch_names:
            raise ValueError(f"Unknown spectrogram channel: {args.spectrogram_channel}. Choose from {raw.ch_names}.")
        if not np.isfinite(args.spectrogram_max) or args.spectrogram_max <= .5:
            raise ValueError("spectrogram-max must be finite and greater than 0.5 Hz.")
        if args.save_fif:
            raw.save(args.save_fif, overwrite=False)
        display = raw
        if args.highpass is not None or args.lowpass is not None:
            display = raw.copy().filter(args.highpass, args.lowpass)
        cutoffs = []
        if args.highpass is not None:
            cutoffs.append(f"high-pass {args.highpass:g} Hz")
        if args.lowpass is not None:
            cutoffs.append(f"low-pass {args.lowpass:g} Hz")
        filter_label = ((raw.info.get("description") + "; ") if raw.info.get("description") else "") + (", ".join(cutoffs) if cutoffs else "Unfiltered")
        if args.view == "waterfall":
            if not args.no_show:
                from analysis.waterfall_browser import serve_waterfall
                serve_waterfall(display, start=args.start, duration=args.duration,
                                scale_uv=args.scale_uv, title=args.csv.name,
                                filter_label=filter_label)
            return
        if args.snapshot or not args.no_show:
            if args.no_show:
                import matplotlib
                matplotlib.use("Agg")
            from analysis.eeg_browser import create_browser
            browser = create_browser(display, start=args.start, duration=args.duration,
                                     scale_uv=args.scale_uv, title=args.csv.name,
                                     filter_label=filter_label,
                                     spectrogram_channel=args.spectrogram_channel,
                                     frequency_scale=args.frequency_scale, spectrogram_max=args.spectrogram_max)
            figure = browser.figure
            if args.snapshot:
                figure.savefig(args.snapshot, dpi=150)
                print(f"PNG saved: {args.snapshot}")
            if not args.no_show:
                import matplotlib.pyplot as plt
                plt.show(block=True)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
