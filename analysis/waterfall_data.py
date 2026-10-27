"""Read-only, recording-anchored data for the interactive EEG waterfall viewer.

MNE supplies volts; display amplitudes are µV and integrated band powers µV².
Power uses complete periodic-Hann windows on a sample-zero-anchored grid. No
edge padding, interpolation over missing samples, or additional filtering is
performed. All returned times are relative to the supplied recording, including
cropped Raw objects whose ``first_time`` is nonzero.
"""
import math
from numbers import Integral

import numpy as np
from mne.time_frequency import psd_array_welch


UNICORN_POSITIONS = ("Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8")
_MAX_POINTS = 12_000
_BATCH_SAMPLE_BUDGET = 1_000_000


def channel_metadata(raw):
    """Map documented Unicorn channel names, preserving every original name.

    Generic names other than the exact ``EEG 1`` … ``EEG 8`` convention are
    deliberately left unmapped. Existing site names are case-insensitive.
    """
    sites = {name.casefold(): name for name in UNICORN_POSITIONS}
    numbered = {f"EEG {index + 1}": name
                for index, name in enumerate(UNICORN_POSITIONS)}
    result = []
    for index, name in enumerate(raw.ch_names):
        label = numbered.get(name, sites.get(name.casefold()))
        result.append({"index": index, "name": name,
                       "label": label if label is not None else name,
                       "mapped": label is not None})
    return result


def _finite_number(value, name, *, positive=False):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} muss eine endliche Zahl sein.")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} muss eine endliche Zahl sein.") from exc
    if not math.isfinite(value) or (positive and value <= 0):
        suffix = "positiv und endlich" if positive else "endlich"
        raise ValueError(f"{name} muss {suffix} sein.")
    return value


def _json_values(values):
    return [float(value) if math.isfinite(value) else None for value in values]


def _envelope_indices(values, max_points):
    """Keep extrema in temporal order, inserting a gap whenever one is crossed.

    Each temporal bucket contributes both finite extrema. The spare budget
    allows an explicit missing sample between any retained finite pair, so a
    narrow NaN/Inf gap can never turn into an artificial connecting line.
    """
    if len(values) <= max_points:
        return np.arange(len(values))
    finite = np.isfinite(values)
    bins = max(1, (max_points - 3) // 4)
    boundaries = np.linspace(0, len(values), bins + 1, dtype=int)
    candidates = {0, len(values) - 1}
    for first, last in zip(boundaries[:-1], boundaries[1:]):
        indices = np.flatnonzero(finite[first:last]) + first
        if indices.size:
            candidates.add(int(indices[np.argmin(values[indices])]))
            candidates.add(int(indices[np.argmax(values[indices])]))
    keep = []
    for index in sorted(candidates):
        if keep and finite[keep[-1]] and finite[index]:
            missing = np.flatnonzero(~finite[keep[-1] + 1:index])
            if missing.size:
                keep.append(int(keep[-1] + 1 + missing[0]))
        keep.append(index)
    return np.asarray(keep, dtype=int)


def _annotation_data(raw, total_duration):
    events, bad = [], []
    annotations = getattr(raw, "annotations", None)
    if annotations is None:
        return events, bad
    first_time = float(getattr(raw, "first_time", 0.0))
    for onset, duration, description in zip(annotations.onset,
                                             annotations.duration,
                                             annotations.description):
        onset = float(onset) - first_time
        duration = float(duration)
        if not math.isfinite(onset):
            continue
        if -1e-9 <= onset <= total_duration + 1e-9:
            events.append({"onset": min(total_duration, max(0.0, onset)),
                           "description": str(description)})
        if str(description).casefold().startswith("bad") and math.isfinite(duration):
            bad.append((onset, onset + max(0.0, duration)))
    return events, bad


def _band_weights(frequencies, resolution, nyquist, low, high):
    # PSD samples represent Fourier-bin energy P[i] * df. At DC and even-N
    # Nyquist the one-sided geometric cells are half-width, so normalize their
    # overlap fraction to preserve their complete energy when fully selected.
    edges = np.concatenate(([0.0], (frequencies[:-1] + frequencies[1:]) / 2,
                            [nyquist]))
    widths = np.diff(edges)
    overlap = np.maximum(0.0, np.minimum(edges[1:], high)
                         - np.maximum(edges[:-1], low))
    return resolution * overlap / widths


def build_waterfall_data(raw, *, start=0.0, duration=10.0, channels=None,
                         band=(8.0, 13.0), window=2.0, hop=0.25,
                         center=True, max_points=1600):
    """Return a JSON-safe viewport containing amplitude and absolute bandpower.

    ``channels`` contains zero-based Raw channel indices, in display order.
    ``start`` is recording-relative and must fall inside the recording;
    ``duration`` is clipped at its end. Amplitude centering removes the median
    of finite samples in the visible interval and reports it as ``offset_uv``.
    Bandpower is unaffected by this display-only operation.

    Window/hop durations are rounded to available samples. Estimates use every
    complete analysis window whose center lies in the viewport, drawing on real
    adjacent recorded samples when needed. FFT batches have a bounded sample
    budget; amplitude reads are limited to one selected channel and viewport.
    ``max_points`` limits amplitude and bandpower points per channel and is
    capped at 12,000; extrema and nonfinite gaps survive reduction. Bandpower
    reduction occurs after every complete analysis window has been computed.
    Nonfinite outputs become null.
    """
    start = _finite_number(start, "Startzeit")
    duration = _finite_number(duration, "Anzeigedauer", positive=True)
    window = _finite_number(window, "Analysefenster", positive=True)
    hop = _finite_number(hop, "Fensterschritt", positive=True)
    sfreq = _finite_number(raw.info["sfreq"], "Abtastrate", positive=True)
    if not isinstance(center, (bool, np.bool_)):
        raise ValueError("Zentrierung muss ein boolescher Wert sein.")
    if not isinstance(max_points, Integral) or isinstance(max_points, (bool, np.bool_)) \
            or max_points < 8:
        raise ValueError("Die maximale Punktzahl muss eine ganze Zahl von mindestens 8 sein.")
    requested_points = int(max_points)
    max_points = min(requested_points, _MAX_POINTS)
    if raw.n_times <= 0 or not raw.ch_names:
        raise ValueError("Die Aufnahme benötigt mindestens einen Messwert und einen Kanal.")
    total_duration = raw.n_times / sfreq
    if start < 0 or start >= total_duration:
        raise ValueError("Die Startzeit muss innerhalb der Aufnahme liegen.")
    stop = min(total_duration, start + duration)
    metadata = channel_metadata(raw)
    if channels is None:
        channels = list(range(len(metadata)))
    else:
        try:
            channels = list(channels)
        except TypeError as exc:
            raise ValueError("Die Kanalauswahl muss eine nichtleere Liste von Kanalindizes sein.") from exc
    if not channels or any(not isinstance(index, Integral)
                           or isinstance(index, (bool, np.bool_))
                           or not 0 <= index < len(metadata) for index in channels):
        raise ValueError("Die Kanalauswahl muss gültige, bei null beginnende Kanalindizes enthalten.")
    channels = [int(index) for index in channels]
    if len(set(channels)) != len(channels):
        raise ValueError("Die Kanalauswahl darf keine doppelten Indizes enthalten.")
    try:
        if len(band) != 2:
            raise ValueError
        low = _finite_number(band[0], "Untere Bandgrenze")
        high = _finite_number(band[1], "Obere Bandgrenze")
    except (TypeError, ValueError, IndexError, KeyError) as exc:
        raise ValueError("Das Frequenzband muss zwei endliche Frequenzen enthalten.") from exc
    nyquist = sfreq / 2
    if low < 0 or high <= low or high > nyquist:
        raise ValueError(f"Das vollständige Band muss 0 ≤ unten < oben ≤ {nyquist:g} Hz (Nyquist) erfüllen.")
    # Reject under-sampled settings rather than silently inventing resolution.
    if not math.isfinite(window * sfreq) or not math.isfinite(hop * sfreq) \
            or max(window * sfreq, hop * sfreq) > np.iinfo(np.int64).max:
        raise ValueError("Analysefenster und Fensterschritt überschreiten die unterstützte Messwertanzahl.")
    samples_per_window = int(math.ceil(window * sfreq))
    hop_samples = int(round(hop * sfreq))
    if samples_per_window < 2:
        raise ValueError("Das Analysefenster muss mindestens zwei aufgezeichnete Messwerte enthalten.")
    if hop_samples < 1:
        raise ValueError("Der Fensterschritt muss mindestens einen aufgezeichneten Messwert enthalten.")
    actual_window = samples_per_window / sfreq
    actual_hop = hop_samples / sfreq
    resolution = sfreq / samples_per_window
    frequencies = (np.fft.rfftfreq(samples_per_window, 1 / sfreq)
                   if samples_per_window <= raw.n_times else np.empty(0))
    weights = (_band_weights(frequencies, resolution, nyquist, low, high)
               if frequencies.size else np.empty(0))
    warnings = []
    if requested_points > _MAX_POINTS:
        warnings.append(f"Die Darstellung ist auf {_MAX_POINTS} Punkte je Kanal und Ansicht begrenzt.")
    if frequencies.size and (high - low < resolution
                            or not np.any((frequencies >= low) & (frequencies <= high))):
        warnings.append(f"Das gewählte Band ist feiner als die Frequenzauflösung von {resolution:g} Hz. "
                        "Ein längeres Analysefenster verbessert die Auflösung.")
    highpass = raw.info.get("highpass", 0.0)
    lowpass = raw.info.get("lowpass", nyquist)
    highpass = 0.0 if highpass is None else float(highpass)
    lowpass = nyquist if lowpass is None else float(lowpass)
    if low < highpass or high > lowpass:
        warnings.append(f"Das gewählte Band reicht über den Filterdurchlassbereich der Aufnahme "
                        f"von {highpass:g}–{lowpass:g} Hz hinaus.")
    events, bad_intervals = _annotation_data(raw, total_duration)
    first_window = max(0, int(math.ceil((start * sfreq - samples_per_window / 2)
                                       / hop_samples - 1e-10)))
    last_window = min((raw.n_times - samples_per_window) // hop_samples,
                      int(math.floor((stop * sfreq - samples_per_window / 2)
                                     / hop_samples + 1e-10)))
    window_indices = np.arange(first_window, max(first_window, last_window + 1), dtype=int)
    starts = window_indices * hop_samples
    power_times = (starts + samples_per_window / 2) / sfreq
    annotation_bad = np.zeros(len(starts), dtype=bool)
    for onset, end in bad_intervals:
        if end > onset:
            annotation_bad |= (starts / sfreq < end) & ((starts + samples_per_window) / sfreq > onset)
        else:
            annotation_bad |= (starts / sfreq <= onset) & ((starts + samples_per_window) / sfreq > onset)
    if raw.n_times < samples_per_window:
        warnings.append(f"Die Aufnahme ist kürzer als das Analysefenster von {actual_window:g} s; "
                        "Bandpower ist nicht verfügbar.")
    elif not len(starts):
        warnings.append("In diesem Ausschnitt liegt kein Mittelpunkt eines vollständigen Analysefensters; "
                        "Bandpower ist nicht verfügbar.")
    if annotation_bad.any():
        warnings.append(f"{int(annotation_bad.sum())} Bandpower-Fenster überschneiden sich mit "
                        "BAD-Markierungen und werden als Lücken angezeigt.")
    first_sample = int(math.ceil(start * sfreq - 1e-10))
    last_sample = min(raw.n_times, int(math.ceil(stop * sfreq - 1e-10)))
    if first_sample >= last_sample:
        raise ValueError("Der gewählte Ausschnitt enthält keine aufgezeichneten Messwerte.")
    count_per_batch = max(1, min(256, _BATCH_SAMPLE_BUDGET
                               // max(samples_per_window, hop_samples)))
    result_channels = []
    for index in channels:
        values = np.asarray(raw.get_data(picks=[index], start=first_sample,
                                         stop=last_sample)[0], dtype=float) * 1e6
        finite = np.isfinite(values)
        offset = float(np.median(values[finite])) if center and finite.any() else 0.0
        selected = _envelope_indices(values, max_points)
        amplitude = values[selected] - offset
        times = (first_sample + selected) / sfreq
        power = np.full(len(starts), np.nan)
        invalid_count = 0
        for first in range(0, len(starts), count_per_batch):
            batch_starts = starts[first:first + count_per_batch]
            # Gaps between windows are never materialized when hop > window.
            if hop_samples > samples_per_window:
                batches = [(int(sample), raw.get_data(picks=[index], start=int(sample),
                            stop=int(sample + samples_per_window))[0]) for sample in batch_starts]
                windows = np.asarray([data for _, data in batches], dtype=float)
            else:
                batch_data = np.asarray(raw.get_data(picks=[index], start=int(batch_starts[0]),
                                        stop=int(batch_starts[-1] + samples_per_window))[0], dtype=float)
                windows = np.lib.stride_tricks.sliding_window_view(batch_data, samples_per_window)[::hop_samples]
            valid = np.all(np.isfinite(windows), axis=1)
            invalid_count += int(np.count_nonzero(~valid & ~annotation_bad[first:first + len(batch_starts)]))
            valid &= ~annotation_bad[first:first + len(batch_starts)]
            if valid.any():
                density, _ = psd_array_welch(windows[valid] * 1e6, sfreq=sfreq,
                                             n_fft=samples_per_window,
                                             n_per_seg=samples_per_window,
                                             n_overlap=0, window="hann",
                                             remove_dc=True, average="mean", verbose="ERROR")
                # A row-wise reduction is invariant to viewport/batch shape;
                # BLAS matrix-vector multiplication may change last bits when
                # a different number of windows happens to be requested.
                power[first + np.flatnonzero(valid)] = np.sum(density * weights, axis=-1)
        if invalid_count:
            warnings.append(f"{metadata[index]['label']}: {invalid_count} Bandpower-Fenster enthalten "
                            "nichtendliche Messwerte und werden als Lücken angezeigt.")
        if not finite.all():
            warnings.append(f"{metadata[index]['label']}: Nichtendliche Amplitudenwerte werden als Lücken angezeigt.")
        power_selected = _envelope_indices(power, max_points)
        if len(power) > max_points:
            warnings.append(f"{metadata[index]['label']}: Die Bandpower-Anzeige wurde von {len(power)} auf "
                            f"{len(power_selected)} Punkte reduziert; alle vollständigen Analysefenster "
                            "wurden berechnet. Extrema und Datenlücken bleiben erhalten.")
        result_channels.append({**{key: metadata[index][key] for key in ("index", "name", "label")},
                                "times": _json_values(times),
                                "amplitude": _json_values(amplitude), "offset_uv": offset,
                                "power_times": _json_values(power_times[power_selected]),
                                "bandpower": _json_values(power[power_selected])})
    return {"start": start, "stop": stop, "total_duration": total_duration,
            "channels": result_channels, "window_seconds": actual_window,
            "hop_seconds": actual_hop, "frequency_resolution": resolution,
            "band": [low, high], "warnings": warnings, "events": events}
