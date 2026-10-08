"""Display Unicorn CSV recordings and approximate event positions in MNE."""
import argparse
from pathlib import Path
import re

import mne
import numpy as np
import pandas as pd


def load_recording(path, unit):
    path = Path(path)
    table = pd.read_csv(path)
    names = sorted((c for c in table.columns if re.fullmatch(r"EEG \d+", c)),
                   key=lambda c: int(c.split()[-1]))
    if table.empty or not names:
        raise ValueError("CSV needs samples and EEG columns named 'EEG 1', etc.")
    if "sample_index" in table:
        if not np.array_equal(table.sample_index.to_numpy(), np.arange(len(table))):
            raise ValueError("sample_index must be continuous starting at zero.")
    data = table[names].to_numpy(dtype=float).T
    if not np.isfinite(data).all():
        raise ValueError("EEG contains missing or nonfinite values.")
    data *= {"uV": 1e-6, "mV": 1e-3, "V": 1.0}[unit]
    raw = mne.io.RawArray(data, mne.create_info(names, 250.0, "eeg"))
    if "Counter" in table:
        count = np.count_nonzero(np.diff(table.Counter.to_numpy(dtype=float)) != 1)
        print(f"Counter discontinuities (including resets/wraps): {count}")
    event_path = path.with_name(path.name + ".events.csv")
    if event_path.exists():
        events = pd.read_csv(event_path, keep_default_na=False)
        if not {"samples_received", "label"}.issubset(events.columns):
            raise ValueError("Event CSV needs samples_received and label.")
        positions = pd.to_numeric(events.samples_received, errors="raise").to_numpy(dtype=float)
        onsets = positions / raw.info["sfreq"]
        valid = np.isfinite(onsets) & (onsets >= 0) & (onsets <= raw.times[-1])
        if not valid.all():
            print(f"Skipped {np.count_nonzero(~valid)} markers outside the sample timeline.")
        raw.set_annotations(mne.Annotations(onsets[valid], np.zeros(valid.sum()),
                                           events.loc[valid, "label"].astype(str).tolist()))
        print("\nLabels (positions are approximate):")
        print(events[["samples_received", "label"]].to_string(index=False))
    else:
        print("No event CSV found; displaying EEG without labels.")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to the EEG CSV")
    parser.add_argument("--unit", required=True, choices=["uV", "mV", "V"],
                        help="EEG unit reported by the terminal's config command")
    parser.add_argument("--start", type=float, default=0, help="Display start in seconds")
    parser.add_argument("--duration", type=float, default=10, help="Display window in seconds")
    parser.add_argument("--highpass", type=float, help="Optional high-pass frequency in Hz")
    parser.add_argument("--lowpass", type=float, help="Optional low-pass frequency in Hz")
    parser.add_argument("--scale-uv", type=float, help="Fixed display scale in microvolts")
    parser.add_argument("--save-fif", type=Path, help="Save imported EEG and labels (before optional filtering)")
    parser.add_argument("--snapshot", type=Path, help="Save browser view as a PNG")
    parser.add_argument("--no-show", action="store_true", help="Import/export without an interactive window")
    args = parser.parse_args()
    try:
        for output in (args.save_fif, args.snapshot):
            if output and output.exists():
                raise ValueError(f"Output already exists: {output}")
        raw = load_recording(args.csv, args.unit)
        print(f"\nCSV: {args.csv.resolve()}\nChannels: {raw.ch_names}")
        print(f"Samples: {raw.n_times}; nominal duration: {raw.n_times / 250:.3f} s; labels: {len(raw.annotations)}")
        print(f"Assumed CSV unit: {args.unit}; MNE data unit: V")
        if args.duration <= 0 or not 0 <= args.start <= raw.times[-1]:
            raise ValueError("duration must be positive and start within the recording.")
        if args.scale_uv is not None and args.scale_uv <= 0:
            raise ValueError("scale-uv must be positive.")
        for cutoff in (args.highpass, args.lowpass):
            if cutoff is not None and not 0 < cutoff < 125:
                raise ValueError("Filter frequencies must be between 0 and 125 Hz.")
        if args.highpass and args.lowpass and args.highpass >= args.lowpass:
            raise ValueError("highpass must be lower than lowpass.")
        if args.save_fif:
            raw.save(args.save_fif, overwrite=False)
        display = raw
        if args.highpass is not None or args.lowpass is not None:
            display = raw.copy().filter(args.highpass, args.lowpass)
        if args.snapshot or not args.no_show:
            if args.no_show:
                import matplotlib
                matplotlib.use("Agg")
            mne.viz.set_browser_backend("matplotlib")
            figure = display.plot(start=args.start, duration=min(args.duration, raw.n_times / 250),
                                  n_channels=len(raw.ch_names),
                                  scalings={"eeg": args.scale_uv * 1e-6 if args.scale_uv else "auto"},
                                  title=args.csv.name, show=not args.no_show, block=False)
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
