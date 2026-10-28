"""Readable, read-only EEG browsing using MNE data and public Matplotlib APIs.

Signal lanes have independent, clipped axes. Compact event labels are only a
presentation layer: original annotations and recorded samples are never edited.
"""
from dataclasses import dataclass
import math
import textwrap

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullLocator
from matplotlib.widgets import Button, Slider, TextBox

if __package__:
    from .time_frequency import compute_spectrogram
else:
    from time_frequency import compute_spectrogram


FREQUENCY_BANDS = (("Delta", .5, 4), ("Theta", 4, 8), ("Alpha", 8, 13),
                   ("Beta", 13, 30), ("Gamma", 30, 100))


def clock_time(seconds):
    minutes, seconds = divmod(max(0.0, seconds), 60)
    return f"{int(minutes):02d}:{seconds:06.3f}"


def _number(value):
    return f"{value:.3g}"


def _parts(description):
    """Only structured annotation fields use ' | key=value' separators."""
    fields = {}
    pieces = description.split(" | ")
    for piece in pieces[1:]:
        key, separator, value = piece.partition("=")
        if separator:
            fields[key] = value
    return pieces[0], fields


def _short_label(description):
    label, fields = _parts(description)
    names = {
        "session_start": "Session start", "session_end": "Session end",
        "baseline_start": "Baseline", "baseline_end": "Baseline end",
        "run_start": "Run start", "run_end": "Run end",
        "block_start": "Block start", "block_end": "Block end",
        "trial_start": "Ready", "trial_end": "Trial end",
        "task_onset": "Task", "task_offset": "Rest", "rest_end": "Rest end",
        "break_start": "Pause", "break_end": "Pause end",
        "phase_start": "Phase start", "phase_end": "Phase end",
        "cue_onset": "Cue", "trial_invalidated": "Invalid trial",
    }
    name = names.get(label, label)
    if label == "task_onset":
        name = {"arms": "Raise arms", "legs": "Raise legs", "blink": "Blink",
                "imagine_arms": "Imagine arms", "imagine_legs": "Imagine legs",
                "mental_arithmetic": "Arithmetic",
                "me_hand_left": "ME Hand L", "me_hand_right": "ME Hand R",
                "me_foot_left": "ME Fuss L", "me_foot_right": "ME Fuss R",
                "mi_hand_left": "MI Hand L", "mi_hand_right": "MI Hand R",
                "mi_foot_left": "MI Fuss L", "mi_foot_right": "MI Fuss R",
                "mi_hands_bilateral": "MI beide Haende", "mi_feet_bilateral": "MI beide Fuesse",
                "word_generation": "Wortgenerierung", "mental_subtraction_single": "Einzelne Subtraktion"}.get(fields.get("condition"), name)
    if fields.get("trial", "0") not in ("", "0"):
        name += " #" + fields["trial"]
    name = " ".join(name.split())
    return name if len(name) <= 28 else name[:25] + "..."


def _priority(description):
    label, fields = _parts(description)
    if "status=invalid" in description or "pause" in label or "abort" in label:
        return 0
    if not fields:  # operator observations deserve prominent labels
        return 1
    return {"task_onset": 2, "baseline_start": 3, "break_start": 3,
            "run_start": 4, "trial_start": 5, "task_offset": 6}.get(label, 9)


@dataclass(frozen=True)
class MarkerGroup:
    onset: float
    indices: tuple
    label: str


def _envelope(times, values, columns):
    """Reduce drawing cost without discarding narrow positive/negative peaks."""
    if len(values) <= columns * 4:
        return times, values
    edges = np.linspace(0, len(values), columns + 1, dtype=int)
    keep = [0]
    for first, last in zip(edges[:-1], edges[1:]):
        bucket = values[first:last]
        keep.extend(sorted((first + int(np.argmin(bucket)), first + int(np.argmax(bucket)))))
    keep.append(len(values) - 1)
    keep = np.unique(keep)
    return times[keep], values[keep]


class EEGBrowser:
    """Interactive display with separate signal, marker, overview and detail areas.

    Automatic scales fit *all* visible samples per channel. ``scale_uv`` instead
    specifies a common +/- range. Median centering affects only displayed data;
    the removed offset is explicitly printed next to every channel.
    """

    def __init__(self, raw, start=0, duration=10, scale_uv=None, title=None,
                 filter_label="Unfiltered", spectrogram_channel=None,
                 frequency_scale="log", spectrogram_max=100):
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be finite and positive.")
        if not math.isfinite(start) or start < 0:
            raise ValueError("start must be finite and nonnegative.")
        if scale_uv is not None and (not math.isfinite(scale_uv) or scale_uv <= 0):
            raise ValueError("scale-uv must be finite and positive.")
        if not raw.n_times or not len(raw.ch_names):
            raise ValueError("The browser needs at least one sample and channel.")
        if spectrogram_channel is not None and spectrogram_channel not in raw.ch_names:
            raise ValueError(f"Unknown spectrogram channel: {spectrogram_channel}. Choose from {raw.ch_names}.")
        if frequency_scale not in ("log", "linear"):
            raise ValueError("frequency-scale must be log or linear.")
        if not math.isfinite(spectrogram_max) or spectrogram_max <= .5:
            raise ValueError("spectrogram-max must be finite and greater than 0.5 Hz.")
        self.raw = raw
        self.sfreq = float(raw.info["sfreq"])
        self.spectrogram_channel = raw.ch_names.index(spectrogram_channel) if spectrogram_channel else 0
        self.frequency_scale = frequency_scale
        self.spectrogram_max = min(float(spectrogram_max), self.sfreq / 2)
        self.spectral_norm = Normalize(-20, 40)
        self.spectral_cmap = plt.get_cmap("magma").with_extremes(bad="#dce3eb")
        self.spectral_result = None
        self._spectral_key = None
        self.spectral_mesh = None
        self.band_artists = []
        self.total_duration = raw.n_times / self.sfreq
        self.duration = min(duration, self.total_duration)
        self.start = min(start, self.max_start)
        self.scale_uv = scale_uv
        self.gain = 1.0
        self.filter_label = filter_label
        self.descriptions = list(raw.annotations.description)
        self.onsets = np.asarray(raw.annotations.onset) - raw.first_time
        self.selected_event = int(np.argmin(np.abs(self.onsets - self.start))) if len(self.onsets) else None
        self.detail_scroll = 0
        self.groups = []
        for onset in np.unique(self.onsets):
            indices = tuple(np.flatnonzero(self.onsets == onset))
            representative = min(indices, key=lambda i: _priority(self.descriptions[i]))
            label = _short_label(self.descriptions[representative])
            if len(indices) > 1:
                label += f" (+{len(indices) - 1})"
            self.groups.append(MarkerGroup(float(onset), indices, label))
        if self.groups:
            nearest = min(self.groups, key=lambda group: abs(group.onset - self.start))
            self.selected_event = min(nearest.indices, key=lambda i: _priority(self.descriptions[i]))
        self._syncing = False
        self._widgets = []  # widgets use weak callbacks; keep them alive
        self._title = title or "EEG recording"
        self.figure = plt.figure(figsize=(15, 10.5), facecolor="#f5f7fa")
        self.figure.canvas.manager.set_window_title(self._title)
        self.heading = self.figure.text(.09, .963, "", fontsize=13, weight="bold", va="top")
        self.subtitle = self.figure.text(.09, .925, "", fontsize=9, color="#475569", va="top")
        grid = self.figure.add_gridspec(len(raw.ch_names) + 1, 1, left=.115, right=.755,
                                       bottom=.225, top=.878, hspace=.16,
                                       height_ratios=[1.35] + [1] * len(raw.ch_names))
        self.grid = grid
        self.marker_axis = self.figure.add_subplot(grid[0])
        self.marker_axis.set_facecolor("#edf2f7")
        self.marker_axis.set_yticks([])
        self.marker_axis.tick_params(axis="x", bottom=False, labelbottom=False)
        self.marker_axis.set_ylabel("Events", rotation=0, ha="right", va="center", labelpad=15, fontsize=10)
        self.marker_axis.set_ylim(0, 3)
        self.signal_axes, self.lines, self.clip_texts = [], [], []
        for channel, name in enumerate(raw.ch_names):
            axis = self.figure.add_subplot(grid[channel + 1], sharex=self.marker_axis)
            axis.set_facecolor("white" if channel % 2 == 0 else "#f0f5fa")
            axis.grid(axis="x", color="#cbd5e1", alpha=.55, linewidth=.5)
            axis.axhline(0, color="#94a3b8", linewidth=.5)
            axis.tick_params(labelsize=8, axis="y", length=2, pad=3)
            axis.tick_params(axis="x", labelbottom=False, bottom=False, labelsize=9)
            axis.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _number(v)))
            line, = axis.plot([], [], color="#153e63", linewidth=.65, clip_on=True)
            self.lines.append(line)
            self.signal_axes.append(axis)
            self.clip_texts.append(axis.text(.99, .94, "", transform=axis.transAxes,
                                            va="top", ha="right", color="#a33b12", fontsize=8,
                                            bbox=dict(facecolor="white", alpha=.85, edgecolor="none"),
                                            clip_on=True))
            for spine in axis.spines.values():
                spine.set_color("#cbd5e1")
        self.spectrogram_axis = self.figure.add_axes([.115, .225, .64, .21],
                                                     sharex=self.marker_axis, facecolor="#dce3eb")
        self.spectrogram_axis.set_xlabel("Time in recording (s)", fontsize=9)
        self.spectrogram_axis.tick_params(labelsize=8)
        self.spectral_title = self.figure.text(.115, .45, "", fontsize=9, weight="bold", color="#334155")
        self.spectral_message = self.spectrogram_axis.text(.5, .5, "", ha="center", va="center",
                                transform=self.spectrogram_axis.transAxes, fontsize=9,
                                bbox=dict(facecolor="#f5f7fa", edgecolor="none", alpha=.95), zorder=8)
        self.selected_lines = [axis.axvline(0, color="#d05c18", linewidth=.8, alpha=.8,
                                            linestyle="--", zorder=7)
                               for axis in [*self.signal_axes, self.spectrogram_axis]]
        self.marker_texts = []
        self.marker_ticks = LineCollection([], colors="#64748b", linewidths=.7)
        self.marker_axis.add_collection(self.marker_ticks)
        self.marker_selected = self.marker_axis.axvline(0, color="#d05c18", linewidth=1.8)
        self.event_note = self.figure.text(.755, .884, "", ha="right", fontsize=8, color="#475569")
        self.figure.text(.79, .873, "MARKER DETAILS", fontsize=10, weight="bold", color="#334155")
        self.detail_axis = self.figure.add_axes([.79, .345, .19, .51], facecolor="white")
        self.detail_axis.set_axis_off()
        self.detail_text = self.detail_axis.text(.02, .98, "", transform=self.detail_axis.transAxes,
                                               va="top", fontsize=9, linespacing=1.4,
                                               clip_on=True, fontfamily="DejaVu Sans")
        self.detail_text.set_clip_path(self.detail_axis.patch)
        self.detail_footer = self.figure.text(.79, .322, "", fontsize=8, color="#64748b")
        self.previous_event_button = self._button([.79, .274, .09, .033], "< Event", lambda _: self.step_event(-1))
        self.next_event_button = self._button([.89, .274, .09, .033], "Event >", lambda _: self.step_event(1))
        self.instructions = self.figure.text(.79, .245, "Click a marker to inspect it.\nScroll here for longer details.\nOrange tick = selected event.",
                         va="top", fontsize=8, linespacing=1.5, color="#475569")
        self.channel_heading = self.figure.text(.79, .45, "", fontsize=10, weight="bold", color="#087e8b")
        self.channel_previous = self._button([.79, .40, .09, .03], "< Channel", lambda _: self.step_channel(-1))
        self.channel_next = self._button([.89, .40, .09, .03], "Channel >", lambda _: self.step_channel(1))
        self.color_fit_button = self._button([.79, .36, .06, .03], "Fit colors", lambda _: self.fit_spectral_colors())
        self.color_reset_button = self._button([.855, .36, .06, .03], "Reset colors", lambda _: self.reset_spectral_colors())
        self.frequency_button = self._button([.92, .36, .06, .03], "Log Hz", lambda _: self.toggle_frequency_scale())
        self.spectral_info = self.figure.text(.79, .33, "", fontsize=8, va="top", color="#475569", linespacing=1.4)
        self.color_axis = self.figure.add_axes([.80, .24, .17, .012])
        self.colorbar = self.figure.colorbar(ScalarMappable(norm=self.spectral_norm, cmap=self.spectral_cmap),
                                            cax=self.color_axis, orientation="horizontal", extend="both")
        self.colorbar.ax.tick_params(labelsize=7, length=2, pad=2)
        self.color_label = self.figure.text(.79, .28, "PSD · dB re 1 µV²/Hz\nColors stay fixed while browsing", fontsize=8,
                                             color="#475569", va="top")
        self.overview_axis = self.figure.add_axes([.115, .132, .64, .036], facecolor="#e2e8f0")
        self.overview_axis.set_xlim(0, self.total_duration)
        self.overview_axis.set_ylim(0, 1)
        self.overview_axis.set_yticks([])
        self.overview_axis.tick_params(axis="x", labelsize=8)
        self.overview_axis.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v // 60):02d}:{int(v % 60):02d}"))
        self.overview_axis.vlines([g.onset for g in self.groups], 0, 1, color="#64748b", linewidth=.5)
        self.overview_window = Rectangle((self.start, 0), self.duration, 1,
                                         color="#38bdf8", alpha=.45)
        self.overview_axis.add_patch(self.overview_window)
        slider_axis = self.figure.add_axes([.115, .077, .64, .018])
        self.slider = Slider(slider_axis, "Start (s)", 0, max(self.max_start, 1 / self.sfreq),
                             valinit=self.start, valfmt="%.2f", color="#2e719c")
        self.slider.valtext.set_position((.995, .5))
        self.slider.valtext.set_horizontalalignment("right")
        self.slider.valtext.set_bbox(dict(facecolor="#f5f7fa", edgecolor="none", pad=1))
        self.slider.on_changed(lambda value: None if self._syncing else self.set_start(value))
        self._widgets.append(self.slider)
        self.bottom_buttons = [
            self._button([.115, .021, .092, .033], "< Window", lambda _: self.set_start(self.start - self.duration)),
            self._button([.213, .021, .092, .033], "Window >", lambda _: self.set_start(self.start + self.duration)),
            self._button([.332, .021, .048, .033], "-", lambda _: self.change_gain(1 / 1.5)),
            self._button([.386, .021, .048, .033], "+", lambda _: self.change_gain(1.5)),
            self._button([.44, .021, .062, .033], "Auto", lambda _: self.auto_fit()),
        ]
        duration_axis = self.figure.add_axes([.645, .021, .11, .033])
        self.duration_box = TextBox(duration_axis, "Window (s) ", initial=f"{self.duration:g}")
        self.duration_box.on_submit(self._submit_duration)
        self._widgets.append(self.duration_box)
        self.keyboard_help = self.figure.text(.79, .153, "Arrows: half window\nShift + arrows: whole window\nHome / End: first / last\n+ / -: gain     A: auto fit",
                         fontsize=8, va="top", linespacing=1.5, color="#475569")
        # Native toolbar pan/zoom bypasses sample loading and scale calculation.
        # Keep toolbar saving available, but route navigation through this controller.
        for axis in self.figure.axes:
            axis.set_navigate(False)
        self._callbacks = [
            self.figure.canvas.mpl_connect("key_press_event", self._on_key),
            self.figure.canvas.mpl_connect("button_press_event", self._on_click),
            self.figure.canvas.mpl_connect("resize_event", self._on_resize),
            self.figure.canvas.mpl_connect("scroll_event", self._on_scroll),
        ]
        self.figure.canvas.draw()
        self._update()

    def select_channel(self, channel):
        """Select one recorded channel, with no spatial mixing or data changes."""
        if isinstance(channel, str):
            if channel not in self.raw.ch_names:
                raise ValueError(f"Unknown EEG channel: {channel}")
            channel = self.raw.ch_names.index(channel)
        if not isinstance(channel, (int, np.integer)) or not 0 <= channel < len(self.raw.ch_names):
            raise ValueError("Channel index is outside the recording.")
        self.spectrogram_channel = int(channel)
        self._update()

    def step_channel(self, step):
        self.select_channel((self.spectrogram_channel + step) % len(self.raw.ch_names))

    def toggle_frequency_scale(self):
        self.frequency_scale = "linear" if self.frequency_scale == "log" else "log"
        self._update()

    def fit_spectral_colors(self):
        """Fit only on request; never change colors as a side effect of navigation."""
        result = self.spectral_result
        if result is None or not result.times.size:
            return
        low = max(.5, float(self.raw.info["highpass"]))
        high = min(self.spectrogram_max, float(self.raw.info["lowpass"]))
        selected = result.power_db[(result.frequencies >= low) & (result.frequencies <= high)]
        visible = ((result.time_edges[:-1] < self.start + self.duration)
                   & (result.time_edges[1:] > self.start))
        selected = selected[:, visible]
        finite = selected[np.isfinite(selected)]
        if not finite.size:
            return
        lower, upper = np.percentile(finite, [5, 99])
        if upper - lower < 10:
            center = (upper + lower) / 2
            lower, upper = center - 5, center + 5
        self.spectral_norm = Normalize(float(lower), float(upper))
        self._draw_spectrogram()
        self.figure.canvas.draw_idle()

    def reset_spectral_colors(self):
        self.spectral_norm = Normalize(-20, 40)
        self._draw_spectrogram()
        self.figure.canvas.draw_idle()

    @property
    def max_start(self):
        return max(0.0, self.total_duration - self.duration)

    def _button(self, bounds, label, callback):
        button = Button(self.figure.add_axes(bounds), label, color="#e2e8f0", hovercolor="#cbd5e1")
        button.label.set_fontsize(9)
        button.on_clicked(callback)
        self._widgets.append(button)
        return button

    def set_start(self, value):
        if not math.isfinite(value):
            raise ValueError("start must be finite.")
        self.start = float(np.clip(value, 0, self.max_start))
        self._update()

    def set_duration(self, value):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("duration must be finite and positive.")
        self.duration = min(max(value, 1 / self.sfreq), self.total_duration)
        self.start = min(self.start, self.max_start)
        self._syncing = True
        try:
            self.duration_box.set_val(f"{self.duration:g}")
        finally:
            self._syncing = False
        self._update()

    def _submit_duration(self, value):
        if self._syncing:
            return
        try:
            self.set_duration(float(value))
        except ValueError:
            self._syncing = True
            try:
                self.duration_box.set_val(f"{self.duration:g}")
            finally:
                self._syncing = False

    def auto_fit(self):
        self.scale_uv = None
        self.gain = 1.0
        self._update()

    def change_gain(self, factor):
        self.gain = float(np.clip(self.gain * factor, 1e-6, 1e6))
        self._update()

    def select_event(self, index, jump=True):
        if not self.descriptions:
            return
        self.selected_event = int(np.clip(index, 0, len(self.descriptions) - 1))
        self.detail_scroll = 0
        onset = self.onsets[self.selected_event]
        if jump and not self.start <= onset < self.start + self.duration:
            self.start = float(np.clip(onset - self.duration * .2, 0, self.max_start))
        self._update()

    def step_event(self, step):
        if self.selected_event is not None:
            self.select_event(self.selected_event + step)

    def _update(self):
        first = min(int(math.floor(self.start * self.sfreq)), self.raw.n_times - 1)
        last = min(self.raw.n_times, max(first + 1, int(math.ceil((self.start + self.duration) * self.sfreq))))
        data = self.raw.get_data(start=first, stop=last) * 1e6
        times = np.arange(first, last) / self.sfreq
        self.offsets = np.median(data, axis=1)
        centered = data - self.offsets[:, None]
        extents = np.max(np.abs(centered), axis=1)
        ranges = np.maximum(extents * 1.08, 1.0) if self.scale_uv is None else np.full(len(data), self.scale_uv)
        ranges = ranges / self.gain
        self.clipped_counts = np.sum(np.abs(centered) > ranges[:, None], axis=1)
        self.marker_axis.set_xlim(self.start, self.start + self.duration)
        columns = max(100, int(self.signal_axes[0].bbox.width))
        compact = self.figure.bbox.height < 780 * self.figure.dpi / 100
        for channel, (axis, line, values, extent) in enumerate(zip(self.signal_axes, self.lines, centered, ranges)):
            t, y = _envelope(times, values, columns)
            line.set_data(t, y)
            axis.set_ylim(-extent, extent)
            axis.set_yticks([-extent * .6, extent * .6])
            label = (f"{self.raw.ch_names[channel]} · ±{_number(extent)} · DC {_number(self.offsets[channel])} µV"
                     if compact else f"{self.raw.ch_names[channel]} · ±{_number(extent)} µV\nDC {_number(self.offsets[channel])} µV")
            axis.set_ylabel(label, rotation=0, ha="right", va="center", fontsize=7 if compact else 8, labelpad=9)
            axis.tick_params(axis="y", labelleft=not compact)
            clipped = self.clipped_counts[channel]
            self.clip_texts[channel].set_text(f"CLIPPED: {100 * clipped / len(values):.1f}%" if clipped else "")
            active = channel == self.spectrogram_channel
            line.set_color("#087e8b" if active else "#153e63")
            axis.yaxis.label.set_color("#087e8b" if active else "#334155")
            axis.spines["left"].set_color("#087e8b" if active else "#cbd5e1")
            axis.spines["left"].set_linewidth(2 if active else .8)
        scale = "Auto / channel" if self.scale_uv is None else f"Shared ±{_number(self.scale_uv / self.gain)} µV"
        if self.scale_uv is None and self.gain != 1:
            scale += f" · gain {self.gain:.2g}×"
        self._layout()
        self._draw_header(scale)
        self._draw_spectrogram()
        self.overview_window.set_x(self.start)
        self.overview_window.set_width(self.duration)
        self._syncing = True
        try:
            self.slider.valmax = max(self.max_start, 1 / self.sfreq)
            self.slider.ax.set_xlim(0, self.slider.valmax)
            self.slider.set_val(self.start)
            self.slider.set_active(self.max_start > 0)
        finally:
            self._syncing = False
        self._draw_markers()
        self._draw_details()
        self.figure.canvas.draw_idle()

    def _draw_spectrogram(self):
        key = (self.spectrogram_channel, self.start, self.duration, self.spectrogram_max)
        if key != self._spectral_key:
            self.spectral_result = compute_spectrogram(self.raw, self.spectrogram_channel,
                                                       self.start, self.start + self.duration,
                                                       max_frequency=self.spectrogram_max)
            self._spectral_key = key
            if self.spectral_mesh is not None:
                self.spectral_mesh.remove()
                self.spectral_mesh = None
            result = self.spectral_result
            if result.times.size and result.frequencies.size:
                self.spectral_mesh = self.spectrogram_axis.pcolormesh(
                    result.time_edges, result.frequency_edges, np.ma.masked_invalid(result.power_db),
                    shading="flat", cmap=self.spectral_cmap, norm=self.spectral_norm,
                    rasterized=True, zorder=1)
        axis, result = self.spectrogram_axis, self.spectral_result
        if self.spectral_mesh is not None:
            self.spectral_mesh.set_norm(self.spectral_norm)
        upper = max(.51, self.spectrogram_max)
        axis.set_yscale(self.frequency_scale)
        axis.set_ylim(.5, upper)
        axis.set_xlim(self.start, self.start + self.duration)
        middle_ticks = ((4, 8, 13, 30, 100) if self.frequency_scale == "log"
                        else MaxNLocator(nbins=5).tick_values(.5, upper))
        ticks = sorted(set([.5, upper] + [f for f in middle_ticks if .5 < f < upper]))
        axis.set_yticks(ticks)
        axis.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        axis.yaxis.set_minor_locator(NullLocator())
        axis.set_ylabel("Frequency (Hz)\n" + self.frequency_scale + " scale", fontsize=8)
        for artist in self.band_artists:
            artist.remove()
        self.band_artists = []
        visible_bands = [(name, lower, min(higher, self.spectrogram_max))
                         for name, lower, higher in FREQUENCY_BANDS if self.spectrogram_max > lower]
        for index, (name, lower, high) in enumerate(visible_bands):
            if lower > .5:
                self.band_artists.append(axis.axhline(lower, color="white", linewidth=.6, alpha=.7, zorder=3))
            if self.frequency_scale == "log":
                compact_bands = axis.bbox.height < 150 * self.figure.dpi / 100
                self.band_artists.append(axis.text(.987, math.sqrt(lower * high), name,
                                    transform=axis.get_yaxis_transform(), ha="right", va="center",
                                    fontsize=7 if compact_bands else 8, color="#f8fafc", zorder=5, clip_on=True,
                                    bbox=dict(facecolor="#0f172a", alpha=.65, edgecolor="none",
                                              pad=.3 if compact_bands else 1.5)))
            else:
                # Linear low-frequency bands are too short for stacked labels.
                self.band_artists.append(axis.text(index / len(visible_bands), 1.012,
                                    f"{name} {lower:g}–{high:g}", transform=axis.transAxes,
                                    ha="left", va="bottom", fontsize=7 if axis.bbox.width > 600 else 6,
                                    color="#475569", zorder=5))
        # A reference guide identifies mains interference without removing it.
        if self.spectrogram_max > 50:
            self.band_artists.append(axis.axhline(50, color="#67e8f9", linewidth=.7, linestyle=":", zorder=3))
            self.band_artists.append(axis.text(.012, 50, "50 Hz", transform=axis.get_yaxis_transform(),
                                    fontsize=7, va="bottom", color="#a5f3fc", zorder=4, clip_on=True))
        highpass, lowpass = float(self.raw.info["highpass"]), float(self.raw.info["lowpass"])
        excluded = []
        for lower, higher in ((.5, min(highpass, upper)), (max(lowpass, .5), upper)):
            if higher > lower:
                self.band_artists.append(axis.axhspan(lower, higher, facecolor="#94a3b8", alpha=.3,
                                    edgecolor="#e2e8f0", hatch="////", linewidth=0, zorder=4))
                excluded.append(f"{lower:g}–{higher:g}")
        self.channel_heading.set_text(f"SPECTROGRAM · {self.raw.ch_names[self.spectrogram_channel]}")
        self.frequency_button.label.set_text("Log Hz" if self.frequency_scale == "log" else "Linear Hz")
        self.spectral_title.set_text(f"{self.raw.ch_names[self.spectrogram_channel]} · frequency power over time"
                                     f"     |     {result.window_seconds:g} s Hann · {result.frequency_resolution:g} Hz bins")
        self.spectral_info.set_text("Click an EEG trace to select it.\n"
                                   f"{result.window_seconds:g} s window · {result.hop_seconds:g} s steps\n"
                                   f"±{result.window_seconds / 2:g} s temporal context\n"
                                   + ("Hatched: outside filter passband" if excluded else "Gray edges: no full 2 s window"))
        message = result.unavailable_reason or ""
        if self.spectrogram_max <= .5:
            message = "Sampling rate too low for the displayed EEG bands."
        self.spectral_message.set_text(message)
        self.spectral_message.set_visible(bool(message))
        self.colorbar.update_normal(ScalarMappable(norm=self.spectral_norm, cmap=self.spectral_cmap))
        self._layout_spectral_sidebar()

    def _layout_spectral_sidebar(self):
        """Pack actual text extents between the controls and the colorbar.

        The heatmap gets shorter before the compact layout takes over. Fixed
        text offsets alone can make its four-line note collide with PSD units,
        especially in a maximized Retina window. Keep the colorbar below the
        heatmap and reserve measured text heights, including at higher DPI.
        """
        renderer = self.figure.canvas.get_renderer()
        width, height = self.figure.bbox.width, self.figure.bbox.height
        px = lambda value: value * self.figure.dpi / 100
        compact = height < px(780)
        bounds = self.spectrogram_axis.get_window_extent(renderer)
        self.spectral_info.set_fontsize(8 if width >= px(1150) else 6)
        self.spectral_info.set_position((.79, (bounds.y1 - px(76)) / height))
        self.spectral_info.set_visible(not compact)
        bar_bottom = bounds.y0 + px(4 if compact else -30)
        bar_height = px(11)
        self.color_axis.set_position([.80, bar_bottom / height, .17, bar_height / height])
        label_height = self.color_label.get_window_extent(renderer).height
        label_top = bar_bottom + bar_height + px(8) + label_height
        self.color_label.set_position((.79, label_top / height))
        # Different backends can give the same point size slightly different
        # line heights. Fit using the rendered bounds, not an assumed height.
        while (not compact and self.spectral_info.get_fontsize() > 6
               and self.spectral_info.get_window_extent(renderer).y0 < label_top + px(8)):
            self.spectral_info.set_fontsize(self.spectral_info.get_fontsize() - .5)

    def _layout(self):
        """Reserve physical space for text and controls as a window is resized."""
        renderer = self.figure.canvas.get_renderer()
        width, height = self.figure.bbox.width, self.figure.bbox.height
        dpi_scale = self.figure.dpi / 100
        # Pixel distances below scale with DPI, just as text point sizes do.
        px = lambda value: value * dpi_scale
        label_width = max(axis.yaxis.label.get_window_extent(renderer).width for axis in self.signal_axes)
        tick_width = max((renderer.get_text_width_height_descent(label.get_text(), label.get_fontproperties(), False)[0]
                         for axis in self.signal_axes for label in axis.get_yticklabels()), default=0)
        left = max(.115, (label_width + tick_width + px(33)) / width)
        left = min(left, .35)
        bottom = min(.42, px(200) / height)
        top = max(bottom + .2, 1 - px(108) / height)
        spectral_height = min(px(225), max(px(96), (top - bottom) * height * .32)) / height
        spectral_top = bottom + spectral_height
        signal_bottom = spectral_top + px(51) / height
        self.grid.update(left=left, bottom=signal_bottom, top=top)
        plot_width = .755 - left
        self.spectrogram_axis.set_position([left, bottom, plot_width, spectral_height])
        self.spectral_title.set_position((left, spectral_top + px(23 if self.frequency_scale == "linear" else 12) / height))
        self.spectral_title.set_verticalalignment("bottom")
        self.spectral_title.set_fontsize(9 if width >= px(1150) else 7)
        compact = height < px(780)
        for axis in self.signal_axes:
            axis.yaxis.label.set_fontsize(7 if compact else 8)
            axis.tick_params(axis="y", labelsize=6 if compact else 8)
        self.heading.set_position((.09, 1 - px(18) / height))
        self.subtitle.set_position((.09, 1 - px(48) / height))
        self.event_note.set_position((.755, top + px(6) / height))
        self.event_note.set_verticalalignment("bottom")
        marker_heading = next(text for text in self.figure.texts if text.get_text() == "MARKER DETAILS")
        marker_heading.set_position((.79, top))
        marker_heading.set_verticalalignment("bottom")
        detail_bottom = signal_bottom + px(113 if not compact else 42) / height
        self.detail_axis.set_position([.79, detail_bottom, .19, max(px(24) / height, top - detail_bottom - px(18) / height)])
        self.detail_footer.set_position((.79, detail_bottom - px(17) / height))
        self.detail_footer.set_fontsize(6 if compact else 8)
        self.previous_event_button.ax.set_position([.79, detail_bottom - px(55) / height, .09, px(28) / height])
        self.next_event_button.ax.set_position([.89, detail_bottom - px(55) / height, .09, px(28) / height])
        self.instructions.set_position((.79, detail_bottom - px(66) / height))
        self.instructions.set_visible(not compact)
        self.channel_heading.set_position((.79, spectral_top + px(12) / height))
        self.channel_heading.set_verticalalignment("bottom")
        self.channel_heading.set_fontsize(9 if width >= px(1150) else 7)
        for button, x in ((self.channel_previous, .79), (self.channel_next, .89)):
            button.ax.set_position([x, spectral_top - px(28) / height, .09, px(27) / height])
        for button, x, span in ((self.color_fit_button, .79, .06), (self.color_reset_button, .855, .06),
                               (self.frequency_button, .92, .06)):
            button.ax.set_position([x, spectral_top - px(62) / height, span, px(27) / height])
            button.label.set_fontsize(8 if width >= px(1150) else 6)
        for button in (self.channel_previous, self.channel_next):
            button.label.set_fontsize(8 if width >= px(1150) else 6)
        self.color_label.set_text("PSD · dB re 1 µV²/Hz\nColors stay fixed while browsing" if not compact else "PSD · dB re 1 µV²/Hz")
        self.color_label.set_fontsize(8 if width >= px(1150) else 6)
        self.keyboard_help.set_position((.79, px(110) / height))
        self.overview_axis.set_position([left, bottom - px(74) / height, plot_width, px(28) / height])
        self.slider.ax.set_position([left, bottom - px(119) / height, plot_width, px(18) / height])
        for button, x, fraction in zip(self.bottom_buttons, [0, .155, .345, .43, .515], [.145, .145, .075, .075, .095]):
            button.ax.set_position([left + plot_width * x, px(16) / height,
                                    plot_width * fraction, px(30) / height])
            button.label.set_fontsize(7 if width < px(1150) else 9)
        self.duration_box.ax.set_position([left + plot_width * .84, px(16) / height,
                                           plot_width * .16, px(30) / height])

    def _draw_header(self, scale):
        renderer = self.figure.canvas.get_renderer()
        available = self.figure.bbox.width * .89
        title = self._title
        self.heading.set_text(title)
        while self.heading.get_window_extent(renderer).width > available and len(title) > 8:
            title = title[:-5]
            self.heading.set_text(title + "...")
        first = (f"{clock_time(self.start)} – {clock_time(self.start + self.duration)} / {clock_time(self.total_duration)}"
                 f"    |    {self.filter_label}    |    {scale}")
        second = "µV per channel · display removes the shown median DC · original data unchanged"
        self.subtitle.set_text(first + "\n" + second)
        # Preserve two lines above the marker lane when a window is narrowed.
        size = 9
        self.subtitle.set_fontsize(size)
        while self.subtitle.get_window_extent(renderer).width > available and size > 6:
            size -= .5
            self.subtitle.set_fontsize(size)

    def _draw_markers(self):
        for text in self.marker_texts:
            text.remove()
        self.marker_texts = []
        visible = [g for g in self.groups if self.start <= g.onset <= self.start + self.duration]
        self.marker_ticks.set_segments([[(g.onset, 0), (g.onset, .35)] for g in visible])
        if self.selected_event is not None:
            self.marker_selected.set_xdata([self.onsets[self.selected_event]] * 2)
        self.marker_selected.set_visible(self.selected_event is not None)
        for line in self.selected_lines:
            if self.selected_event is not None:
                line.set_xdata([self.onsets[self.selected_event]] * 2)
            line.set_visible(self.selected_event is not None)
        renderer = self.figure.canvas.get_renderer()
        box = self.marker_axis.get_window_extent(renderer)
        # Pixel coordinates make packing follow both window size and HiDPI scale.
        hidden = 0
        selected = self.selected_event
        ordered = sorted(visible, key=lambda group: (selected not in group.indices, group.onset))
        for group in ordered:
            text = self.marker_axis.text(group.onset, .65, group.label, fontsize=8,
                                         color="#a33b12" if selected in group.indices else "#334155",
                                         va="center", clip_on=True)
            width = text.get_window_extent(renderer).width
            text_height = text.get_window_extent(renderer).height
            x = self.marker_axis.transData.transform((group.onset, 0))[0] + 5
            x = min(max(x, box.x0 + 3), box.x1 - width - 3)
            # The selected event gets a lane first, then intervals pack around it.
            chosen = None
            for lane in range(3):
                y = box.y0 + box.height * .16 + text_height / 2 + lane * (text_height + 3)
                if y + text_height / 2 > box.y1 - 2:
                    break
                occupied = [other.get_window_extent(renderer) for other in self.marker_texts
                            if getattr(other, "_eeg_lane", None) == lane]
                if x >= box.x0 and x + width <= box.x1 and all(
                        x + width + 9 < other.x0 or x > other.x1 + 9 for other in occupied):
                    chosen = lane
                    break
            if chosen is None:
                text.remove()
                hidden += 1
                continue
            px_to_data = self.marker_axis.transData.inverted()
            text.set_x(px_to_data.transform((x, 0))[0])
            text.set_y(px_to_data.transform((0, box.y0 + box.height * .16 + text_height / 2 + chosen * (text_height + 3)))[1])
            text._eeg_lane = chosen
            text._eeg_indices = group.indices
            self.marker_texts.append(text)
        count = sum(len(g.indices) for g in visible)
        self.event_note.set_text(f"{count} events · {len(visible)} timestamps" +
                                 (f" · {hidden} labels omitted; click ticks for details" if hidden else " · click ticks for details"))
        self.event_note.set_fontsize(8)
        while self.event_note.get_window_extent(renderer).width > box.width and self.event_note.get_fontsize() > 5:
            self.event_note.set_fontsize(self.event_note.get_fontsize() - .5)

    def _draw_details(self):
        renderer = self.figure.canvas.get_renderer()
        box = self.detail_axis.get_window_extent(renderer)
        char_width = renderer.get_text_width_height_descent("M", self.detail_text.get_fontproperties(), False)[0]
        columns = max(12, int(box.width / char_width) - 1)
        lines = []
        if self.selected_event is None:
            lines = ["No event annotations.", "", "Signal browsing is available."]
        else:
            i = self.selected_event
            same = np.flatnonzero(self.onsets == self.onsets[i])
            lines = [f"Event {i + 1} / {len(self.descriptions)}", clock_time(self.onsets[i]),
                     f"{self.onsets[i]:.3f} seconds", f"{len(same)} event(s) at this timestamp", ""]
            for part in self.descriptions[i].split(" | "):
                # Preserve every character, including Unicode and explicit newlines.
                for paragraph in part.split("\n"):
                    lines.extend(textwrap.wrap(paragraph, columns, replace_whitespace=False,
                                               drop_whitespace=False) or [""])
                lines.append("")
        line_height = self.detail_text.get_fontsize() * self.figure.dpi / 72 * 1.4
        capacity = max(1, int(box.height / line_height) - 1)
        self._detail_capacity = capacity
        self.detail_scroll = int(np.clip(self.detail_scroll, 0, max(0, len(lines) - capacity)))
        self.detail_text.set_text("\n".join(lines[self.detail_scroll:self.detail_scroll + capacity]))
        more = len(lines) > capacity
        self.detail_footer.set_text(f"Lines {self.detail_scroll + 1}–{min(len(lines), self.detail_scroll + capacity)} / {len(lines)} · scroll for more"
                                    if more else "All marker details shown")

    def _on_resize(self, _event):
        self.figure.canvas.draw()
        self._update()

    def _on_click(self, event):
        if event.button != 1 or event.xdata is None:
            return
        if event.inaxes == self.overview_axis:
            self.set_start(event.xdata - self.duration / 2)
        elif event.inaxes in self.signal_axes:
            self.select_channel(self.signal_axes.index(event.inaxes))
        elif event.inaxes == self.marker_axis and self.groups:
            indices = next((text._eeg_indices for text in self.marker_texts if text.contains(event)[0]), None)
            if indices is None:
                indices = min(self.groups, key=lambda g: abs(g.onset - event.xdata)).indices
            if self.selected_event in indices:
                index = indices[(indices.index(self.selected_event) + 1) % len(indices)]
            else:
                index = indices[0]
            self.select_event(index)

    def _on_scroll(self, event):
        if event.inaxes == self.detail_axis:
            step = min(3, self._detail_capacity)
            self.detail_scroll += -step if event.button == "up" else step
            self._draw_details()
            self.figure.canvas.draw_idle()

    def _on_key(self, event):
        if self.duration_box.capturekeystrokes:
            return
        key = event.key
        if key in ("left", "right", "shift+left", "shift+right"):
            step = self.duration if key.startswith("shift+") else self.duration / 2
            self.set_start(self.start + (step if key.endswith("right") else -step))
        elif key in ("home", "end"):
            self.set_start(0 if key == "home" else self.max_start)
        elif key in ("+", "=", "-"):
            self.change_gain(1 / 1.5 if key == "-" else 1.5)
        elif key in ("a", "A"):
            self.auto_fit()


def create_browser(raw, **kwargs):
    browser = EEGBrowser(raw, **kwargs)
    # The Figure owns its controller even when callers keep only the figure.
    browser.figure._eeg_browser = browser
    return browser
