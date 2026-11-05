"""Offline hand ERD/ERS in sensor space; no alteration of source recordings.

One-second periodic Hann PSDs (100 ms steps), physical µV²/Hz and integrated
µV². Percentage changes normalize the mean power, never the mean voltage or
the mean of single-trial ratios. Every included sensor uses the same trials.
"""
from functools import lru_cache
from importlib.resources import files
import hashlib
import json
from pathlib import Path

import mne
import numpy as np
import pandas as pd
from scipy.signal.windows import hann

from .recording_files import eeg_unit_scale, read_session_metadata, resolve_recording
from .session_conditions import CURRENT, protocol_for_events


SITES = ("Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8")
CONDITIONS = ("me_hand_left", "me_hand_right", "mi_hand_left", "mi_hand_right")
BANDS = (("mu", 8., 13.), ("beta", 13., 30.),
         ("mu_neuper", 8., 12.), ("beta_neuper", 13., 28.))
FS = 250
WINDOW = 250
HOP = 25
TIMES = np.arange(-375, 2376, HOP) / FS  # centers; actual phase support is checked
UNITS = {"uV": 1e-6, "µV": 1e-6, "μV": 1e-6, "mV": 1e-3, "V": 1.}


def json_safe(value):
    """Strict JSON: missing estimates remain null, including in exports."""
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def window_psd(samples_uv):
    """Last axis is exactly 250 samples; one-sided density including Nyquist."""
    values = np.asarray(samples_uv, dtype=float)
    if values.shape[-1] != WINDOW:
        raise ValueError('ERD/ERS benötigt vollständige 1-s-Fenster bei 250 Hz.')
    taper = hann(WINDOW, sym=False)
    transformed = np.fft.rfft((values - values.mean(axis=-1, keepdims=True)) * taper, axis=-1)
    density = abs(transformed) ** 2 / (FS * np.sum(taper ** 2))
    density[..., 1:-1] *= 2
    return density


def band_weights(low, high):
    """Fractional Fourier-bin energy; disjoint bands do not double-count edges."""
    frequency = np.fft.rfftfreq(WINDOW, 1 / FS)
    edges = np.r_[0., (frequency[:-1] + frequency[1:]) / 2, FS / 2]
    return np.maximum(0, np.minimum(edges[1:], high) - np.maximum(edges[:-1], low)) / np.diff(edges)


def percent(power, reference):
    with np.errstate(divide='ignore', invalid='ignore'):
        result = 100 * (np.asarray(power) / np.asarray(reference) - 1)
    return np.where(np.asarray(reference) > 0, result, np.nan)


@lru_cache(maxsize=1)
def head_geometry():
    """Template scalp and sensors in one MNE head coordinate frame (mm).

    The bundled surface requires no fsaverage download, MRI or 3D backend.
    Keep canonical positions separate from small display-only projections.
    """
    montage = mne.channels.make_standard_montage('fsaverage_1005')
    info = mne.create_info(list(SITES), FS, 'eeg')
    info.set_montage(montage)
    sensors = np.array([channel['loc'][:3] for channel in info['chs']])
    base = files('mne').joinpath('data', 'fsaverage')
    surface = mne.read_bem_surfaces(str(base.joinpath('fsaverage-head.fif')), verbose='ERROR')[0]
    transform = mne.read_trans(str(base.joinpath('fsaverage-trans.fif')), verbose='ERROR')
    vertices = mne.transforms.apply_trans(mne.transforms.invert_transform(transform), surface['rr'])
    # Project markers onto the template surface, lifting them by 2 mm solely
    # for visibility. Original template coordinates remain in exported metadata.
    from scipy.spatial import cKDTree
    nearest = vertices[cKDTree(vertices).query(sensors)[1]]
    center = vertices.mean(axis=0)
    normals = nearest - center
    display = nearest + .002 * normals / np.linalg.norm(normals, axis=1, keepdims=True)
    return dict(vertices=np.round(vertices * 1000, 3).tolist(),
                triangles=surface['tris'].tolist(), sensors_mm=(sensors * 1000).tolist(),
                display_mm=(display * 1000).tolist(), coordinate_frame='MNE head',
                montage='fsaverage_1005', source='MNE bundled fsaverage-head.fif',
                label='Standardpositionen – nicht individuell vermessen')


def _qc_settings(path):
    settings = json.loads(Path(path).read_text(encoding='utf-8')) if path else {}
    return _validate_qc(settings)


def _validate_qc(settings):
    settings = dict(settings) if isinstance(settings, dict) else settings
    allowed = {'bad_channels', 'bad_trials', 'bad_intervals_s', 'montage_confirmed'}
    if not isinstance(settings, dict) or set(settings) - allowed:
        raise ValueError('Unbekannte ERD/ERS-QC-Felder.')
    for key in ('bad_channels', 'bad_trials'):
        values = settings.setdefault(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError(f'{key} muss eine Liste von Bezeichnern sein.')
    if set(settings['bad_channels']) - set(SITES):
        raise ValueError('bad_channels verwendet Positionsnamen: ' + ', '.join(SITES))
    if not isinstance(settings.setdefault('montage_confirmed', False), bool):
        raise ValueError('montage_confirmed muss true oder false sein.')
    if not isinstance(settings.setdefault('bad_intervals_s', []), list):
        raise ValueError('bad_intervals_s muss eine Liste von Zeitintervallen sein.')
    for interval in settings['bad_intervals_s']:
        if (not isinstance(interval, list) or len(interval) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in interval)
                or not np.isfinite(interval).all() or not 0 <= interval[0] < interval[1]):
            raise ValueError('bad_intervals_s benötigt endliche [Start, Ende]-Paare in Sekunden.')
    return settings


def load_erds(path, unit, signal='oscar', qc_path=None):
    """Load all session context; resolve auto as OSCAR, never as a raw fallback."""
    if unit not in UNITS:
        raise ValueError('Unbekannte EEG-Einheit.')
    selected = resolve_recording(path, 'oscar' if signal == 'auto' else signal)
    if selected.signal == 'oscar' and unit != 'uV':
        raise ValueError('OSCAR-Ausgabe benötigt --unit uV.')
    metadata = read_session_metadata(selected.session)
    if metadata.get('sampling_rate_hz') != FS:
        raise ValueError('ERD/ERS benötigt bestätigte 250 Hz aus den Sitzungsmetadaten.')
    frame = pd.read_csv(selected.data)
    selected.validate_length(len(frame))
    if 'sample_index' not in frame or not np.array_equal(frame.sample_index, np.arange(len(frame))):
        raise ValueError('sample_index muss lückenlos ab 0 sein.')
    device = {c['name']: c for c in metadata.get('device', {}).get('channels', [])}
    channels = []
    for i, site in enumerate(SITES):
        candidates = [name for name in (f'EEG {i + 1}', site) if name in frame]
        if len(candidates) > 1:
            raise ValueError(f'Doppelte Zuordnung für {site}.')
        name = candidates[0] if candidates else None
        if name and (name not in device or not device[name].get('enabled')
                     or eeg_unit_scale(device[name].get('unit')) != UNITS[unit]):
            raise ValueError(f'Einheit/aktivierter Kanal nicht bestätigt: {name}.')
        channels.append(name)
    data = np.full((8, len(frame)), np.nan)
    for i, name in enumerate(channels):
        if name:
            data[i] = frame[name].to_numpy(dtype=float) * UNITS[unit] * 1e6
    valid = np.ones(len(frame), dtype=bool)
    notes = []
    recorded_units = {name: device[name].get('unit') for name in channels if name}
    if 'ÂµV' in recorded_units.values():
        notes.append("Metadateneinheit 'ÂµV' ausdrücklich als µV interpretiert; Originalschreibweise im Bericht erhalten.")
    if 'Validation Indicator' in frame:
        valid &= frame['Validation Indicator'].to_numpy() == 1
    else:
        notes.append('Validation Indicator fehlt; technische Samplequalität nicht vollständig prüfbar.')
    if 'Counter' in frame:
        counter = frame.Counter.to_numpy(dtype=float)
        valid &= np.isfinite(counter)
        gaps = np.flatnonzero(np.diff(counter) != 1)
        valid[gaps] = False
        valid[gaps + 1] = False
    else:
        notes.append('Counter fehlt; Transportlücken nicht vollständig prüfbar.')
    events = pd.read_csv(selected.events, keep_default_na=False)
    result = compute_erds(data, events, valid, channels=channels,
                          protocol=metadata.get('protocol_version'), qc=_qc_settings(qc_path))
    sources = [selected.data, selected.events, selected.session]
    if selected.signal == 'oscar':
        sources.append(selected.processing)
    if qc_path:
        sources.append(Path(qc_path))
    result['metadata'].update(signal=selected.signal, signal_description=selected.label,
                              participant_id=metadata.get('participant_id'), session_id=metadata.get('session_id'),
                              source_unit=unit, processing=selected.metadata,
                              recorded_channel_units=recorded_units,
                              inputs={str(p.resolve()): _sha256(p) for p in sources},
                              software={'mne': mne.__version__, 'numpy': np.__version__})
    result['warnings'].extend(notes)
    return result


def compute_erds(data_uv, events, sample_valid=None, *, channels=None, protocol=CURRENT, qc=None):
    """Pure numerical entry point. Arrays are eight sensors × recorded samples.

    Only complete windows inside recorded phases are used. No per-trial time
    warping: time curves are cue-aligned, rebound summaries are offset-aligned.
    A time bin missing in any accepted trial is a gap for the whole condition.
    """
    data = np.asarray(data_uv, dtype=float)
    if data.ndim != 2 or data.shape[0] != 8:
        raise ValueError('Erwartet werden acht Sensoren × Samples in µV.')
    required = {'source', 'run', 'block', 'trial', 'attempt', 'condition', 'label', 'phase', 'samples_received'}
    if not required <= set(events.columns):
        raise ValueError('Vollständige strukturierte Sitzungsmarker erforderlich.')
    automatic = events[events.source == 'automatic'].copy()
    # Baseline/break events carry condition names too, but are not task classes.
    # Retain their protocol versions so conflicts anywhere in the file still fail.
    protocol_events = automatic.copy()
    nontrial = pd.to_numeric(protocol_events.trial, errors='raise') == 0
    protocol_events.loc[nontrial, 'condition'] = ''
    version, _ = protocol_for_events(protocol_events, protocol)
    if version != CURRENT:
        raise ValueError('ERD/ERS-Handbedingungen benötigen eeg-session-2.0; alte Armaufgaben bleiben separat.')
    qc = _validate_qc(qc or {})
    channels = channels if channels is not None else [f'EEG {i+1}' for i in range(8)]
    active = np.array([name is not None and site not in qc['bad_channels'] for name, site in zip(channels, SITES)])
    if not active.any():
        raise ValueError('Mindestens ein zugeordneter, eingeschlossener EEG-Kanal erforderlich.')
    valid = np.ones(data.shape[1], bool) if sample_valid is None else np.asarray(sample_valid, dtype=bool).copy()
    if valid.shape != (data.shape[1],):
        raise ValueError('Samplequalität und EEG-Länge stimmen nicht überein.')
    valid &= np.all(np.isfinite(data[active]), axis=0)
    for start, stop in qc['bad_intervals_s']:
        valid[int(np.floor(start * FS)):int(np.ceil(stop * FS))] = False
    cumulative_bad = np.r_[0, np.cumsum(~valid)]
    frequency = np.fft.rfftfreq(WINDOW, 1 / FS)
    freq_mask = (frequency >= 6) & (frequency <= 40)
    weights = np.array([band_weights(lo, hi) for _, lo, hi in BANDS])
    trials = {condition: [] for condition in CONDITIONS}
    exclusions = []
    seen = set()
    pauses = []
    pause_start = None
    for row in automatic[automatic.label.isin(['pause_start', 'pause_end'])].to_dict('records'):
        sample = float(row['samples_received'])
        if not np.isfinite(sample) or sample != int(sample):
            raise ValueError('Ungültiger Pausenmarker.')
        if row['label'] == 'pause_start':
            if pause_start is not None:
                raise ValueError('Überlappende Pausenmarker.')
            pause_start = int(sample)
        elif pause_start is not None:
            if int(sample) < pause_start:
                raise ValueError('Rückwärts laufende Pausenmarker.')
            pauses.append((pause_start, int(sample)))
            pause_start = None
    if pause_start is not None:
        pauses.append((pause_start, data.shape[1]))

    def spectra(centers):
        starts = np.asarray(centers, dtype=int) - WINDOW // 2
        good = (starts >= 0) & (starts + WINDOW <= data.shape[1])
        clipped = np.clip(starts, 0, max(0, data.shape[1] - WINDOW))
        good &= cumulative_bad[clipped + WINDOW] == cumulative_bad[clipped]
        density = np.full((8, len(starts), len(frequency)), np.nan)
        if good.any():
            indices = starts[good, None] + np.arange(WINDOW)
            density[active[:, None] & good[None, :]] = window_psd(data[active][:, indices]).reshape(-1, len(frequency))
        return density

    grouped = automatic.groupby(['run', 'block', 'trial', 'attempt'], sort=False)
    for key, group in grouped:
        labels = set(group.label)
        conditions = set(group.condition) - {''}
        if not conditions.intersection(CONDITIONS):
            continue
        trial_key = '/'.join(str(v) for v in key)
        reason = None
        try:
            if 'trial_invalidated' in labels:
                raise ValueError('invalidated')
            if trial_key in qc['bad_trials']:
                raise ValueError('manual_trial_exclusion')
            if len(conditions) != 1:
                raise ValueError('inconsistent_condition')
            condition = next(iter(conditions))
            if key[0] != ('Motorik' if condition.startswith('me_') else 'Imagery'):
                raise ValueError('inconsistent_run')
            if any(int(v) != float(v) or int(v) < 1 for v in key[1:]):
                raise ValueError('invalid_trial_identity')
            if 'trial_end' not in labels:
                raise ValueError('incomplete')

            def marker(label):
                rows = group[group.label == label]
                if len(rows) != 1:
                    raise ValueError('missing_or_duplicate_' + label)
                value = float(rows.iloc[0].samples_received)
                if not np.isfinite(value) or value != int(value):
                    raise ValueError('invalid_marker_sample')
                return int(value)

            prep, onset, offset, end = [marker(k) for k in ('trial_start', 'cue_onset', 'task_offset', 'trial_end')]
            if not (0 <= prep <= onset - WINDOW < onset < offset and offset + 3 * FS <= end <= data.shape[1]):
                raise ValueError('invalid_phase_bounds')
            if abs((offset - onset) / FS - 4) > .3:
                raise ValueError('unexpected_hand_task_duration')
            if abs((onset - prep) / FS - 2) > .3:
                raise ValueError('unexpected_preparation_duration')
            if any(start < end and stop > prep for start, stop in pauses):
                raise ValueError('pause_overlaps_attempt')
            if ((cumulative_bad[offset + 3 * FS] - cumulative_bad[max(prep, onset - 2 * FS)]) != 0):
                raise ValueError('invalid_samples_in_reference_task_or_rebound')
            logical = key[:3]
            if logical in seen:
                raise ValueError('multiple_completed_attempts')
            centers = onset + np.rint(TIMES * FS).astype(int)
            inside = (centers - 125 >= prep) & (centers + 125 <= end)
            density = spectra(centers)
            density[:, ~inside] = np.nan
            ref = (centers - 125 >= max(prep, onset - 2 * FS)) & (centers + 125 <= onset)
            task = (centers - 125 >= onset) & (centers + 125 <= offset)
            if not ref.any() or not task.any():
                raise ValueError('missing_reference_or_task_windows')
            bp = np.einsum('ctf,bf->cbt', density, weights)
            reference = bp[:, :, ref].mean(axis=2)
            spectral_reference = density[:, ref, :][:, :, freq_mask].mean(axis=1)
            # Relative machine-precision floor, not a biological/noise threshold.
            # A pure synthetic sinusoid leaves roundoff (~1e-28) in other bins;
            # dividing by that would paint fictitious enormous percent changes.
            floor = np.finfo(float).eps * density[:, ref, :].mean(axis=1).sum(axis=1)
            if (np.any(reference[active] <= floor[active, None])
                    or not np.isfinite(reference[active]).all()):
                raise ValueError('nonpositive_reference')
            spectral_reference = np.where(spectral_reference > floor[:, None], spectral_reference, np.nan)
            rebound = spectra(offset + np.arange(125, 626, HOP))
            rebound_bp = np.einsum('ctf,bf->cbt', rebound, weights).mean(axis=2)
            if (not np.isfinite(bp[active][:, :, task]).all()
                    or not np.isfinite(rebound_bp[active]).all()):
                raise ValueError('nonfinite_power')
            trials[condition].append(dict(key=trial_key, block=int(key[1]),
                onset_sample=onset, offset_sample=offset, reference=reference,
                spectral_reference=spectral_reference, power=bp,
                task_power=bp[:, :, task].mean(axis=2), rebound_power=rebound_bp,
                spectrum=density[:, :, freq_mask].transpose(0, 2, 1)))
            seen.add(logical)
        except (ValueError, TypeError, OverflowError) as error:
            reason = str(error)
        if reason:
            exclusions.append(dict(key=trial_key, reason=reason))

    # A second completed attempt makes the logical trial ambiguous; exclude both.
    ambiguous = {e['key'].rsplit('/', 1)[0] for e in exclusions if e['reason'] == 'multiple_completed_attempts'}
    for condition in CONDITIONS:
        retained = []
        for trial in trials[condition]:
            if trial['key'].rsplit('/', 1)[0] in ambiguous:
                exclusions.append(dict(key=trial['key'], reason='multiple_completed_attempts'))
            else:
                retained.append(trial)
        trials[condition] = retained
    conditions = {}
    for condition, accepted in trials.items():
        if not accepted:
            conditions[condition] = dict(n=0, trials=[], unavailable_reason='Keine vollständigen gültigen Trials.')
            continue
        def mean(field):
            return np.mean([t[field] for t in accepted], axis=0)
        reference = mean('reference')
        power = mean('power')
        spectrum = mean('spectrum')
        spectral_reference = mean('spectral_reference')
        conditions[condition] = dict(n=len(accepted), power=power, reference=reference,
            percent=percent(power, reference[:, :, None]),
            spectral_power=spectrum, spectral_reference=spectral_reference,
            spectral_percent=percent(spectrum, spectral_reference[:, :, None]),
            task_power=mean('task_power'), rebound_power=mean('rebound_power'),
            task_percent=percent(mean('task_power'), reference),
            rebound_percent=percent(mean('rebound_power'), reference),
            trials=[{k: t[k] for k in ('key', 'block', 'onset_sample', 'offset_sample', 'reference', 'task_power', 'rebound_power')} for t in accepted])
    if not any(c['n'] for c in conditions.values()):
        raise ValueError('Keine gültigen Hand-Trials: ' + '; '.join(sorted({e['reason'] for e in exclusions})))
    unused = set(qc['bad_trials']) - {t['key'] for group in trials.values() for t in group} - {e['key'] for e in exclusions}
    if unused:
        raise ValueError('Unbekannte bad_trials: ' + ', '.join(sorted(unused)))
    return dict(schema_version=1, times=TIMES, frequencies=frequency[freq_mask],
        bands=[dict(id=k, low=lo, high=hi) for k, lo, hi in BANDS],
        channels=[dict(site=s, name=n, included=bool(a)) for s, n, a in zip(SITES, channels, active)],
        conditions=conditions, exclusions=exclusions,
        metadata=dict(protocol_version=version, sampling_rate_hz=FS, window_seconds=1., hop_seconds=.1,
            frequency_grid_hz=1., hann_enbw_hz=1.5, reference='Vollständige Fenster in Vorbereitung, frühestens -2 s bis Cue',
            numerical_reference_floor='float64 epsilon × summed mean reference PSD per channel; unresolvable TF bins stay missing',
            task_window='Fenstermitten ab Cue + 0.5 s bis tatsächliches Aufgabenende - 0.5 s',
            rebound_window='Fenstermitten 0.5–2.5 s nach tatsächlichem task_offset',
            normalization='100 * (mean trial power / mean trial reference - 1)',
            rereference='as recorded; no additional rereferencing',
            preprocessing='1 s periodic Hann; remove window mean; one-sided PSD; fractional band edges; no padding',
            montage='fsaverage_1005', montage_confirmed=qc['montage_confirmed'], qc=qc,
            time_reference='Software-Cue; kein gemessener Bewegungsbeginn; keine Zeitstreckung',
            cohort='Gemeinsame Trialmenge für alle eingeschlossenen Kanäle/Bänder; Zeitlücken bei unvollständiger Unterstützung',
            statistics='Deskriptive Mittelwerte; Farben sind kein Signifikanztest'),
        warnings=['Referenz kann Vorbereitungsaktivität enthalten; Erholung ist keine garantierte Ruhe.',
                  'Signalqualität visuell prüfen; keine automatische Muskel-/Augenartefaktfreiheit.',
                  'Standardpositionen – nicht individuell vermessen; keine Quellenlokalisation.'])


def export_erds(result, directory):
    """New directory only; machine-readable provenance and numerical CSV tables."""
    import csv
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    report = json_safe(result)
    (target / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    common = ['condition', 'channel', 'band', 'n', 'reference_uV2']
    with (target / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(common + ['task_uV2', 'task_percent', 'rebound_uV2', 'rebound_percent'])
        for condition, values in report['conditions'].items():
            if not values['n']:
                continue
            for ci, channel in enumerate(report['channels']):
                for bi, band in enumerate(report['bands']):
                    writer.writerow([condition, channel['site'], band['id'], values['n'], values['reference'][ci][bi],
                        values['task_power'][ci][bi], values['task_percent'][ci][bi],
                        values['rebound_power'][ci][bi], values['rebound_percent'][ci][bi]])
    with (target / 'bandpower.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(common + ['cue_time_s', 'power_uV2', 'percent'])
        for condition, values in report['conditions'].items():
            if values['n']:
                for ci, channel in enumerate(report['channels']):
                    for bi, band in enumerate(report['bands']):
                        for ti, time in enumerate(report['times']):
                            writer.writerow([condition, channel['site'], band['id'], values['n'], values['reference'][ci][bi],
                                time, values['power'][ci][bi][ti], values['percent'][ci][bi][ti]])
    return target
