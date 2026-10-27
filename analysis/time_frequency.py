"""Channel-local, recording-anchored time–frequency power for the EEG browser.

Input follows MNE's EEG convention (volts); output is a one-sided power
spectral density in µV²/Hz. Estimates use full 2 s periodic Hann windows with
their means removed and approximately 0.25 s spacing. Neither recording edges
nor nonfinite samples are padded or interpolated. Window centers and display
cells stay on the same recording-relative grid when the viewport moves.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal.windows import hann


WINDOW_SECONDS = 2.0
HOP_SECONDS = 0.25
_BATCH_WINDOWS = 256
_POWER_FLOOR = 1e-30


@dataclass(frozen=True)
class Spectrogram:
    """Arrays use ``(frequency, time)`` order, ready for ``pcolormesh``.

    ``times`` are window centers in seconds from the beginning of the supplied
    Raw recording, matching its trace time axis even when ``raw.first_time``
    is nonzero. ``time_edges`` span the display cells; every estimate still
    uses the full ``window_seconds`` centered on its time. A short viewport can
    therefore use adjacent recorded samples as context. ``hop_seconds`` is
    display spacing, not independent temporal resolution.

    ``power_db`` references 1 µV²/Hz. Its -300 dB floor applies only to finite
    zero/underflow values; invalid windows remain NaN gaps. ``available`` means
    full analysis windows exist, even if some or all contain invalid data.
    """

    times: np.ndarray
    frequencies: np.ndarray
    power: np.ndarray
    time_edges: np.ndarray
    frequency_edges: np.ndarray
    window_seconds: float
    hop_seconds: float
    frequency_resolution: float
    nyquist: float
    unavailable_reason: str = ""

    @property
    def available(self):
        return bool(self.times.size and self.frequencies.size)

    @property
    def power_db(self):
        return 10 * np.log10(np.maximum(self.power, _POWER_FLOOR))

    @property
    def invalid_window_count(self):
        return int(np.count_nonzero(~np.all(np.isfinite(self.power), axis=0)))


def compute_spectrogram(raw, channel, start, stop, *, max_frequency=100.0):
    """Compute just one channel and the full windows touching a time interval.

    ``channel`` is a channel name or zero-based index; ``start`` and ``stop``
    use recording-relative seconds. Requests outside the recording produce an
    unavailable result, as do recordings shorter than the fixed 2 s analysis
    window. Frequency is limited to ``max_frequency`` and the actual Nyquist
    frequency. A low sample rate is never upsampled to invent higher bands.

    Windows are anchored to sample zero, independently of the viewport. Only
    the requested channel and interval plus adjacent window context are read.
    FFT work is batched to bound temporary allocations; browser controllers
    can memoize results by (channel, start, stop) for redraws and backtracking.
    The function neither changes Raw samples nor applies an additional filter.
    """
    start, stop = float(start), float(stop)
    max_frequency = float(max_frequency)
    if not math.isfinite(start) or not math.isfinite(stop) or start < 0 or stop <= start:
        raise ValueError("The time interval must be finite with 0 <= start < stop.")
    if not math.isfinite(max_frequency) or max_frequency <= 0:
        raise ValueError("max_frequency must be finite and positive.")
    sfreq = float(raw.info["sfreq"])
    if not math.isfinite(sfreq) or sfreq <= 0:
        raise ValueError("The sampling frequency must be finite and positive.")
    if isinstance(channel, str):
        try:
            channel = raw.ch_names.index(channel)
        except ValueError as exc:
            raise ValueError(f"Unknown channel: {channel!r}") from exc
    if not isinstance(channel, (int, np.integer)) or not 0 <= channel < len(raw.ch_names):
        raise ValueError("channel must name a channel or be a valid channel index.")

    # Rounding upward keeps the physical window at least 2 s at noninteger Hz.
    samples_per_window = max(2, int(math.ceil(WINDOW_SECONDS * sfreq)))
    hop_samples = max(1, int(round(HOP_SECONDS * sfreq)))
    window_seconds = samples_per_window / sfreq
    hop_seconds = hop_samples / sfreq
    resolution = sfreq / samples_per_window
    nyquist = sfreq / 2
    frequencies = rfftfreq(samples_per_window, 1 / sfreq)
    frequencies = frequencies[frequencies <= min(max_frequency, nyquist)]
    frequency_edges = np.concatenate((
        [max(0.0, frequencies[0] - resolution / 2)],
        frequencies + resolution / 2,
    ))
    frequency_edges[-1] = min(frequency_edges[-1], max_frequency, nyquist)

    def unavailable(reason):
        return Spectrogram(np.empty(0), frequencies, np.empty((len(frequencies), 0)),
                           np.empty(0), frequency_edges, window_seconds,
                           hop_seconds, resolution, nyquist, reason)

    if raw.n_times < samples_per_window:
        return unavailable("At least 2 s of recorded data are needed for the spectrogram.")
    # Include cells intersecting the viewport, retaining their original centers.
    # Adjacent context is real recorded data, never a zero-padded edge estimate.
    half_window = samples_per_window / 2
    half_hop = hop_samples / 2
    first_window = max(0, int(math.ceil((start * sfreq - half_hop - half_window)
                                      / hop_samples - 1e-12)))
    last_window = min((raw.n_times - samples_per_window) // hop_samples,
                      int(math.floor((stop * sfreq + half_hop - half_window)
                                     / hop_samples + 1e-12)))
    if first_window > last_window:
        return unavailable("No full 2 s analysis windows intersect this interval.")

    first_sample = first_window * hop_samples
    last_sample = last_window * hop_samples + samples_per_window
    data_uv = np.asarray(raw.get_data(picks=[int(channel)], start=first_sample,
                                      stop=last_sample)[0], dtype=float) * 1e6
    count = last_window - first_window + 1
    power = np.full((len(frequencies), count), np.nan)
    taper = hann(samples_per_window, sym=False)
    density_scale = 1 / (sfreq * np.sum(taper * taper))
    # Each row is a zero-copy view of a complete original analysis window.
    windows = np.lib.stride_tricks.sliding_window_view(data_uv, samples_per_window)[::hop_samples]
    for first in range(0, count, _BATCH_WINDOWS):
        batch = windows[first:first + _BATCH_WINDOWS]
        finite = np.all(np.isfinite(batch), axis=1)
        if not finite.any():
            continue
        values = batch[finite]
        values = (values - values.mean(axis=1, keepdims=True)) * taper
        transformed = rfft(values, axis=1)
        density = np.square(np.abs(transformed)) * density_scale
        # Account for the negative-frequency half, except DC and even-N Nyquist.
        density[:, 1:-1 if samples_per_window % 2 == 0 else None] *= 2
        power[:, first + np.flatnonzero(finite)] = density[:, :len(frequencies)].T

    times = ((np.arange(first_window, last_window + 1) * hop_samples + half_window)
             / sfreq)
    time_edges = np.concatenate(([times[0] - hop_seconds / 2], times + hop_seconds / 2))
    return Spectrogram(times, frequencies, power, time_edges, frequency_edges,
                       window_seconds, hop_seconds, resolution, nyquist)
