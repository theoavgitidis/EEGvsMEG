"""Synthetic, hardware-free ERD/ERS numerical and session integrity regressions."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis.erds_data import (FS, TIMES, SITES, CONDITIONS, band_weights, baseline_detail, channel_trials,
                                compute_erds, export_erds, head_geometry, json_safe,
                                load_erds, trial_detail, window_psd)


def synthetic_session():
    """Two blocks, four hand conditions; only right-hand C3 is modulated."""
    n = 14 * FS * 8
    time = np.arange(n) / FS
    mu = np.full((8, n), 10.)
    beta = np.full((8, n), 6.)
    rows = []
    for j in range(8):
        condition = CONDITIONS[j % 4]
        run = 'Motorik' if condition.startswith('me') else 'Imagery'
        prep = j * 14 * FS
        cue = prep + 2 * FS
        off = cue + 4 * FS
        end = prep + 14 * FS
        if condition.endswith('right'):
            mu[1, cue:off] = 5.
            beta[1, off:off + 3 * FS] = 12.
        for label, phase, sample in [('trial_start', 'prepare', prep), ('cue_onset', 'task', cue),
                                    ('task_offset', 'task', off), ('trial_end', 'rest', end)]:
            rows.append(dict(source='automatic', run=run, block=j // 4 + 1, trial=j % 4 + 1,
                attempt=1, condition=condition, label=label, phase=phase, samples_received=sample,
                protocol_version='eeg-session-2.0'))
    data = mu * np.sin(2 * np.pi * 10 * time) + beta * np.sin(2 * np.pi * 20 * time)
    return data, pd.DataFrame(rows)


def write_session(directory, *, oscar=True):
    data, events = synthetic_session()
    path = Path(directory) / 'synthetic.csv'
    frame = pd.DataFrame(data.T, columns=[f'EEG {i+1}' for i in range(8)])
    frame.insert(0, 'sample_index', np.arange(len(frame)))
    frame['Counter'] = np.arange(len(frame))
    frame['Validation Indicator'] = 1
    frame.to_csv(path, index=False)
    events.to_csv(str(path) + '.events.csv', index=False)
    metadata = dict(protocol_version='eeg-session-2.0', sampling_rate_hz=250,
        participant_id='DEV-SYNTHETIC', session_id='synthetic', device={'channels': [
            dict(name=f'EEG {i+1}', enabled=True, unit='uV') for i in range(8)]})
    Path(str(path) + '.session.json').write_text(json.dumps(metadata), encoding='utf-8')
    if oscar:
        frame.to_csv(str(path) + '.oscar.csv', index=False)
        Path(str(path) + '.processing.json').write_text(json.dumps(dict(schema_version=1,
            mode='oscar', state='complete', sampling_rate_hz=250, raw_file=path.name,
            oscar_file=path.name + '.oscar.csv', oscar_samples=len(frame), oscar_delay_samples=83)), encoding='utf-8')
    return path


def synthetic_baseline_session():
    """Two complete resting baselines around the existing synthetic hand trials."""
    data, events = synthetic_session()
    time = np.arange(60 * FS) / FS
    rest = np.tile(10 * np.sin(2 * np.pi * 10 * time) + 6 * np.sin(2 * np.pi * 20 * time), (8, 1))
    end_rest = rest.copy()
    end_rest[1] += 10 * np.sin(2 * np.pi * 10 * time)  # +300% Mu at C3
    end_rest[3, :30 * FS] -= 5 * np.sin(2 * np.pi * 10 * time[:30 * FS])
    events.samples_received += len(time)
    rows = []
    for run, start in [('Anfangsbaseline', 0), ('Endbaseline', len(time) + data.shape[1])]:
        for label, sample in [('baseline_start', start), ('baseline_end', start + len(time))]:
            rows.append(dict(source='automatic', run=run, block=0, trial=0, attempt=1, condition='baseline',
                label=label, phase='baseline', samples_received=sample, protocol_version='eeg-session-2.0'))
    return np.concatenate([rest, data, end_rest], axis=1), pd.concat([pd.DataFrame(rows), events], ignore_index=True)


class ERDSBaselineTest(unittest.TestCase):
    def test_rest_preparation_and_explicit_reference_leave_hand_results_unchanged(self):
        data, events = synthetic_baseline_session()
        original = data.copy()
        result = compute_erds(data, events)
        rest = [s for s in result['baselines'] if s['kind'] == 'rest']
        prep = [s for s in result['baselines'] if s['kind'] == 'prepare']
        self.assertEqual(len(rest), 2); self.assertEqual(len(prep), 8)
        self.assertEqual([s['n_valid_windows'] for s in rest], [591, 591])
        self.assertEqual([s['n_windows'] for s in prep], [11] * 8)
        detail = baseline_detail(result, rest[1]['key'], rest[0]['key'], 'C3')
        self.assertAlmostEqual(detail['mean_power'][1, 0], 200)
        self.assertAlmostEqual(detail['reference'][1, 0], 50)
        self.assertAlmostEqual(detail['mean_percent'][1, 0], 300)
        np.testing.assert_allclose(detail['spectral_percent'][4, :], 300, atol=1e-8)
        self.assertTrue(np.isnan(detail['spectral_percent'][0]).all())  # no synthetic 6-Hz power
        self.assertEqual(len(detail['waveform_uv']), 60 * FS)
        self.assertEqual(detail['times'][0], .5); self.assertEqual(detail['times'][-1], 59.5)
        self_ref = baseline_detail(result, rest[1]['key'], rest[1]['key'], 'C3')
        self.assertAlmostEqual(self_ref['mean_percent'][1, 0], 0)
        for section in prep:
            t = result['_trial_data'][section['trial_key']]
            np.testing.assert_allclose(section['reference'], t['reference'])
        self.assertAlmostEqual(result['conditions']['me_hand_right']['task_percent'][1, 0], -75)
        np.testing.assert_array_equal(data, original)
        portable = json_safe(result)
        self.assertNotIn('_baseline_data', portable)
        self.assertIn('reference_windows', portable['baselines'][0])
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'export'
            export_erds(result, target)
            with (target / 'baselines.csv').open(encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            row = next(r for r in rows if r['key'] == rest[1]['key'] and r['channel'] == 'C3' and r['band'] == 'mu')
            self.assertAlmostEqual(float(row['power_uV2']), 200)
            self.assertAlmostEqual(float(row['reference_uV2']), 200)
            self.assertAlmostEqual(float(row['percent_of_own_section_mean']), 0)
            self.assertEqual(float(row['section_start_s']), rest[1]['start_s'])
        for key, ref, channel in [('unknown', rest[0]['key'], 'C3'), (rest[0]['key'], 'unknown', 'C3'),
                                  (rest[0]['key'], rest[0]['key'], 'unknown')]:
            with self.assertRaisesRegex(ValueError, 'Baseline'):
                baseline_detail(result, key, ref, channel)

    def test_baseline_gaps_qc_invalidated_incomplete_and_ambiguous_attempts(self):
        data, events = synthetic_baseline_session()
        valid = np.ones(data.shape[1], bool); valid[1000] = False
        result = compute_erds(data, events, valid, qc={'bad_channels': ['PO8']})
        first = result['baselines'][0]
        self.assertEqual(first['n_missing_windows'], 10)
        detail = baseline_detail(result, first['key'], first['key'], 'PO8')
        self.assertTrue(np.isnan(detail['waveform_uv']).all())
        self.assertTrue(np.isnan(detail['power'][7]).all())
        detail = baseline_detail(result, first['key'], first['key'], 'C3')
        self.assertEqual(np.isnan(detail['power'][1, 0]).sum(), 10)
        self.assertTrue(np.isnan(detail['waveform_uv'][1000]))
        self.assertAlmostEqual(detail['reference'][1, 0], 50)
        result = compute_erds(data, events, qc={'bad_intervals_s': [[0, 60]]})
        self.assertEqual(len([s for s in result['baselines'] if s['kind'] == 'rest']), 1)
        self.assertIn('no_valid_windows', [e['reason'] for e in result['baseline_exclusions']])
        start = events[events.run == 'Anfangsbaseline'].copy()
        invalid = start.iloc[[0]].copy(); invalid['label'] = 'baseline_invalidated'
        interrupted = pd.concat([events, invalid], ignore_index=True)
        result = compute_erds(data, interrupted)
        self.assertIn('invalidated', [e['reason'] for e in result['baseline_exclusions']])
        # Restarted baseline attempt survives; the old invalidated attempt does not.
        restarted = start.copy(); restarted.attempt = 2
        result = compute_erds(data, pd.concat([interrupted, restarted], ignore_index=True))
        self.assertEqual([s['attempt'] for s in result['baselines'] if s['kind'] == 'rest'], [2, 1])
        ambiguous = compute_erds(data, pd.concat([events, restarted], ignore_index=True))
        self.assertEqual(sum(s['kind'] == 'rest' for s in ambiguous['baselines']), 1)
        self.assertIn('multiple_completed_baseline_attempts', [e['reason'] for e in ambiguous['baseline_exclusions']])
        incomplete = events[~((events.run == 'Anfangsbaseline') & (events.label == 'baseline_end'))]
        result = compute_erds(data, incomplete)
        self.assertIn('missing_or_duplicate_baseline_end', [e['reason'] for e in result['baseline_exclusions']])
        # Invalidated hand trials must not reappear as selectable preparations.
        invalid = events[events.condition == 'me_hand_left'].iloc[[0]].copy(); invalid['label'] = 'trial_invalidated'
        result = compute_erds(data, pd.concat([events, invalid], ignore_index=True))
        self.assertEqual(sum(s['kind'] == 'prepare' for s in result['baselines']), 7)
        data[:, :60 * FS] = 0
        result = compute_erds(data, events)
        first = next(s for s in result['baselines'] if s['kind'] == 'rest')
        detail = baseline_detail(result, first['key'], first['key'], 'C3')
        self.assertEqual(detail['mean_power'][1, 0], 0)
        self.assertTrue(np.isnan(detail['mean_percent'][1, 0]))


class ERDSNumericalTest(unittest.TestCase):
    def setUp(self):
        self.data, self.events = synthetic_session()

    def test_psd_physical_normalization_and_fractional_band_edges(self):
        time = np.arange(FS) / FS
        psd = window_psd(10 * np.sin(2 * np.pi * 10 * time) + 1000)
        self.assertAlmostEqual(psd.sum(), 50)
        self.assertAlmostEqual(psd @ band_weights(8, 13), 50)
        np.testing.assert_allclose(band_weights(8, 13) + band_weights(13, 30), band_weights(8, 30))
        self.assertEqual(band_weights(8, 13)[13], .5)
        with self.assertRaises(ValueError):
            window_psd(np.ones(249))

    def test_c3_only_modulation_zero_null_sign_and_phase_support(self):
        original = self.data.copy()
        result = compute_erds(self.data, self.events)
        c = result['conditions']['me_hand_right']
        self.assertEqual(c['n'], 2)
        self.assertAlmostEqual(c['reference'][1, 0], 50)
        self.assertAlmostEqual(c['task_power'][1, 0], 12.5)
        self.assertAlmostEqual(c['task_percent'][1, 0], -75)
        self.assertAlmostEqual(c['rebound_percent'][1, 1], 300)
        np.testing.assert_allclose(c['task_percent'][[0, 2, 3, 4, 5, 6, 7]], 0, atol=1e-10)
        # No activity after the cue contaminates the baseline.
        self.assertAlmostEqual(c['reference'][1, 1], 18)
        left = result['conditions']['me_hand_left']
        np.testing.assert_allclose(left['task_percent'], 0, atol=1e-10)
        # Numerical roundoff in empty spectral bins must not become giant ERS.
        self.assertTrue(np.isnan(left['spectral_percent'][:, 0]).all())
        supported = np.isfinite(left['spectral_percent'])
        self.assertLess(np.max(np.abs(left['spectral_percent'][supported])), 1e-7)
        np.testing.assert_array_equal(self.data, original)

    def test_normalize_mean_power_not_mean_individual_ratios(self):
        # Second right-hand trial: baseline amplitude 20, task amplitude 15.
        cue = 5 * 14 * FS + 2 * FS
        t = np.arange(self.data.shape[1]) / FS
        mu = np.sin(2 * np.pi * 10 * t)
        self.data[1, cue - 2 * FS:cue] += 10 * mu[cue - 2 * FS:cue]
        self.data[1, cue:cue + 4 * FS] += 10 * mu[cue:cue + 4 * FS]
        result = compute_erds(self.data, self.events)
        c = result['conditions']['me_hand_right']
        self.assertAlmostEqual(c['reference'][1, 0], 125)
        self.assertAlmostEqual(c['task_power'][1, 0], 62.5)
        self.assertAlmostEqual(c['task_percent'][1, 0], -50)
        first = trial_detail(result, 'Motorik/1/2/1', 'C3')
        second = trial_detail(result, 'Motorik/2/2/1', 'C3')
        self.assertAlmostEqual(first['reference'][1, 0], 50)
        self.assertAlmostEqual(first['task_percent'][1, 0], -75)
        self.assertAlmostEqual(second['reference'][1, 0], 200)
        self.assertAlmostEqual(second['task_percent'][1, 0], -43.75)
        self.assertNotAlmostEqual(c['task_percent'][1, 0],
                                 (first['task_percent'][1, 0] + second['task_percent'][1, 0]) / 2)
        rows = channel_trials(result, 'C3', 'mu')['conditions']['me_hand_right']
        self.assertEqual([r['key'] for r in rows], [first['key'], second['key']])
        np.testing.assert_allclose(rows[1]['percent'], second['percent'][1, 0], equal_nan=True)
        self.assertEqual(rows[1]['task_percent'], second['task_percent'][1, 0])

    def test_trial_identity_waveform_tfr_and_private_cache_serialization(self):
        result = compute_erds(self.data, self.events)
        detail = trial_detail(result, 'Motorik/2/2/1', 'C3')
        summary = detail['trials'][0]
        self.assertEqual((summary['block'], summary['trial'], summary['attempt'], summary['ordinal']), (2, 2, 1, 2))
        self.assertEqual(summary['onset_s'], 72)
        self.assertEqual(detail['n'], 1)
        self.assertAlmostEqual(detail['rebound_percent'][1, 1], 300)
        self.assertEqual(detail['spectral_percent'].shape, (35, len(TIMES)))
        np.testing.assert_allclose(detail['spectral_percent'][4, TIMES == 2], -75)
        np.testing.assert_array_equal(detail['waveform_uv'], self.data[1, 70 * FS:82 * FS])
        self.assertEqual(detail['waveform_times'][0], -2)
        self.assertEqual(detail['waveform_times'][-1], 10 - 1 / FS)
        portable = json_safe(result)
        self.assertNotIn('_trial_data', portable)
        self.assertEqual(portable['conditions']['me_hand_right']['trials'][1]['key'], detail['key'])
        json.dumps(portable, allow_nan=False)
        with self.assertRaises(ValueError):
            trial_detail(result, 'Motorik/9/9/1', 'C3')
        with self.assertRaises(ValueError):
            trial_detail(result, detail['key'], 'unknown')
        with self.assertRaises(ValueError):
            channel_trials(result, 'C3', 'unknown')

    def test_reference_window_provenance_matches_actual_preparation_and_preserves_variation(self):
        # Preparation starts 100 ms late. The first nominal -1.5 s window is
        # therefore unavailable; actual reference support is -1.9 to 0 s.
        row = (self.events.run == 'Motorik') & (self.events.block == 1) & (self.events.trial == 1) & (self.events.label == 'trial_start')
        self.events.loc[row, 'samples_received'] += 25
        time = np.arange(2 * FS) / FS
        self.data[1, :2 * FS] += np.linspace(-4, 4, 2 * FS) * np.sin(2 * np.pi * 10 * time)
        original = self.data.copy()
        result = compute_erds(self.data, self.events)
        detail = trial_detail(result, 'Motorik/1/1/1', 'C3')
        windows = detail['trials'][0]['reference_windows']
        np.testing.assert_allclose(windows['eligible_interval_s'], [-1.9, 0])
        np.testing.assert_allclose(windows['support_s'], [-1.9, 0])
        np.testing.assert_allclose(windows['centers_s'], TIMES[1:11])
        self.assertEqual(windows['n_windows'], 10)
        indices = np.isin(TIMES, windows['centers_s'])
        self.assertGreater(np.ptp(detail['percent'][1, 0, indices]), 10)
        self.assertAlmostEqual(detail['percent'][1, 0, indices].mean(), 0)
        self.assertAlmostEqual(detail['power'][1, 0, indices].mean(), detail['reference'][1, 0])
        np.testing.assert_array_equal(self.data, original)

    def test_single_trial_exclusions_channels_and_late_gaps_are_preserved(self):
        valid = np.ones(self.data.shape[1], bool)
        valid[11 * FS] = False
        result = compute_erds(self.data, self.events, valid,
                              qc=dict(bad_trials=['Motorik/1/2/1'], bad_channels=['PO8']))
        with self.assertRaises(ValueError):
            trial_detail(result, 'Motorik/1/2/1', 'C3')
        detail = trial_detail(result, 'Motorik/1/1/1', 'C3')
        self.assertTrue(np.isnan(detail['power'][:, :, TIMES == 9]).all())
        self.assertTrue(np.isnan(detail['waveform_uv'][np.isclose(detail['waveform_times'], 9)]).all())
        self.assertTrue(np.isnan(detail['task_percent'][7]).all())
        self.assertTrue(np.isnan(trial_detail(result, detail['key'], 'PO8')['waveform_uv']).all())
        self.assertEqual(len(channel_trials(result, 'C3', 'mu')['conditions']['me_hand_right']), 1)

    def test_late_invalidation_and_missing_markers_exclude_whole_attempt(self):
        invalid = self.events.iloc[4].to_dict()
        invalid.update(label='trial_invalidated', samples_received=self.data.shape[1] + 999)
        events = pd.concat([self.events, pd.DataFrame([invalid])], ignore_index=True)
        events = events.drop(events.index[(events.block == 2) & (events.condition == 'me_hand_right') & (events.label == 'task_offset')])
        result = compute_erds(self.data, events)
        self.assertEqual(result['conditions']['me_hand_right']['n'], 0)
        self.assertEqual({e['reason'] for e in result['exclusions']}, {'invalidated', 'missing_or_duplicate_task_offset'})

    def test_nonfinite_quality_and_manual_exclusions_keep_common_cohort(self):
        self.data[7, 2 * FS + 10] = np.nan
        result = compute_erds(self.data, self.events)
        self.assertEqual(result['conditions']['me_hand_left']['n'], 1)
        qc = dict(bad_channels=['PO8'], bad_trials=[], bad_intervals_s=[], montage_confirmed=False)
        result = compute_erds(self.data, self.events, qc=qc)
        self.assertEqual(result['conditions']['me_hand_left']['n'], 2)
        self.assertIsNone(json_safe(result)['conditions']['me_hand_left']['task_percent'][7][0])
        qc['bad_trials'] = ['Motorik/1/1/1']
        result = compute_erds(self.data, self.events, qc=qc)
        self.assertEqual(result['conditions']['me_hand_left']['n'], 1)
        qc['bad_trials'] = ['Motorik/99/99/1']
        with self.assertRaisesRegex(ValueError, 'Unbekannte bad_trials'):
            compute_erds(self.data, self.events, qc=qc)

    def test_late_recovery_gap_remains_gap_without_partial_trial_averaging(self):
        valid = np.ones(self.data.shape[1], bool)
        valid[11 * FS] = False  # 9 s after cue: beyond summary/rebound, within display
        c = compute_erds(self.data, self.events, valid)['conditions']['me_hand_left']
        self.assertEqual(c['n'], 2)
        self.assertTrue(np.isnan(c['power'][:, :, TIMES == 9]).all())
        self.assertTrue(np.isfinite(c['task_power']).all())

    def test_pauses_exclude_attempt_even_without_invalidation_marker(self):
        pause = self.events.iloc[0].to_dict()
        pause.update(label='pause_start', trial=0, condition='', samples_received=1000)
        resume = dict(pause, label='pause_end', samples_received=1250)
        result = compute_erds(self.data, pd.concat([self.events, pd.DataFrame([pause, resume])]))
        self.assertEqual(result['conditions']['me_hand_left']['n'], 1)
        self.assertIn('pause_overlaps_attempt', {e['reason'] for e in result['exclusions']})

    def test_full_session_baselines_and_breaks_are_not_task_conditions(self):
        context = []
        for condition in ('baseline', 'block_break', 'run_break'):
            row = self.events.iloc[0].to_dict()
            row.update(condition=condition, label='phase_start', phase=condition,
                       trial=0, block=0, attempt=0, samples_received=0)
            context.append(row)
        events = pd.concat([pd.DataFrame(context), self.events], ignore_index=True)
        result = compute_erds(self.data, events)
        self.assertEqual([v['n'] for v in result['conditions'].values()], [2, 2, 2, 2])
        events.loc[0, 'protocol_version'] = 'eeg-session-1.0'
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            compute_erds(self.data, events)

    def test_offsets_are_actual_not_fixed_four_seconds(self):
        # Extend the annotated task by 100 ms, move rebound modulation with it.
        rows = (self.events.condition == 'me_hand_right') & (self.events.label == 'task_offset')
        self.events.loc[rows, 'samples_received'] += 25
        for j in (1, 5):
            off = (j * 14 + 6) * FS
            t = np.arange(off, off + 25) / FS
            self.data[1, off:off + 25] -= 6 * np.sin(2 * np.pi * 20 * t)
        c = compute_erds(self.data, self.events)['conditions']['me_hand_right']
        # 0.5–2.5 s centers after the recorded offset have final support at +3.1.
        self.assertLess(c['rebound_percent'][1, 1], 300)
        self.assertGreater(c['rebound_percent'][1, 1], 280)

    def test_reference_zero_legacy_and_ambiguous_attempts_fail_closed(self):
        data = self.data.copy(); data[1, :2 * FS] = 0
        result = compute_erds(data, self.events)
        self.assertEqual(result['conditions']['me_hand_left']['n'], 1)
        old = self.events.copy(); old['protocol_version'] = 'eeg-session-1.0'; old['condition'] = 'arms'
        with self.assertRaises(ValueError):
            compute_erds(self.data, old, protocol='eeg-session-1.0')
        duplicate = self.events.iloc[16:20].copy(); duplicate['attempt'] = 2
        result = compute_erds(self.data, pd.concat([self.events, duplicate]))
        self.assertEqual(result['conditions']['me_hand_left']['n'], 1)
        self.assertEqual(sum(e['reason'] == 'multiple_completed_attempts' for e in result['exclusions']), 2)

    def test_template_geometry_orientation_and_registration(self):
        g = head_geometry()
        sensors = np.array(g['sensors_mm'])
        self.assertLess(sensors[1, 0], 0); self.assertGreater(sensors[3, 0], 0)
        self.assertGreater(sensors[0, 1], sensors[6, 1])
        self.assertEqual(len(sensors), 8)
        self.assertGreater(len(g['triangles']), 1000)
        self.assertLess(np.linalg.norm(sensors - np.array(g['display_mm']), axis=1).max(), 15)


class ERDSFilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = write_session(self.temp.name)

    def test_oscar_default_and_explicit_raw_preserve_original_files(self):
        original = {p: p.read_bytes() for p in Path(self.temp.name).iterdir()}
        result = load_erds(self.path, 'uV')
        self.assertEqual(result['metadata']['signal'], 'oscar')
        self.assertEqual(load_erds(self.path, 'uV', 'raw')['metadata']['signal'], 'raw')
        Path(str(self.path) + '.processing.json').write_text('{}')
        with self.assertRaises(ValueError):
            load_erds(self.path, 'uV')
        self.assertEqual(load_erds(self.path, 'uV', 'raw')['metadata']['signal'], 'raw')
        for path, data in original.items():
            if path.suffix != '.json':
                self.assertEqual(path.read_bytes(), data)

    def test_legacy_windows_metadata_preserves_units_and_source_bytes(self):
        path = Path(str(self.path) + '.session.json')
        metadata = json.loads(path.read_text())
        metadata['device_description'] = 'Gerät geprüft – ältere Aufnahme'
        for channel in metadata['device']['channels']:
            channel['unit'] = 'µV'
        source = json.dumps(metadata, ensure_ascii=False).encode('cp1252')
        path.write_bytes(source)
        for signal in ('raw', 'oscar'):
            with self.subTest(signal=signal), self.assertWarnsRegex(UnicodeWarning, 'Windows-1252'):
                result = load_erds(self.path, 'uV', signal=signal)
            self.assertEqual(result['conditions']['me_hand_right']['n'], 2)
            self.assertAlmostEqual(result['conditions']['me_hand_right']['task_percent'][1, 0], -75)
        self.assertEqual(path.read_bytes(), source)

    def test_mixed_windows_encoding_unit_is_explicit_and_preserved_in_provenance(self):
        path = Path(str(self.path) + '.session.json')
        metadata = json.loads(path.read_text())
        metadata['device_description'] = 'Gerät'
        for channel in metadata['device']['channels']:
            channel['unit'] = 'ÂµV'
        source = json.dumps(metadata, ensure_ascii=False).encode('cp1252')
        path.write_bytes(source)
        with self.assertWarnsRegex(UnicodeWarning, 'Kodierungsfehler'):
            result = load_erds(self.path, 'uV', signal='raw')
        self.assertEqual(result['metadata']['recorded_channel_units']['EEG 1'], 'ÂµV')
        self.assertTrue(any('ÂµV' in note for note in result['warnings']))
        self.assertAlmostEqual(result['conditions']['me_hand_right']['reference'][1, 0], 50)
        self.assertEqual(path.read_bytes(), source)
        for channel in metadata['device']['channels']:
            channel['unit'] = 'unknown'
        path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, 'Einheit'):
            load_erds(self.path, 'uV', signal='raw')

    def test_unit_counter_validation_qc_and_non_overwriting_export(self):
        with self.assertRaisesRegex(ValueError, 'OSCAR'):
            load_erds(self.path, 'V')
        clean = Path(str(self.path) + '.oscar.csv')
        frame = pd.read_csv(clean)
        frame.loc[600, 'Validation Indicator'] = 0
        frame.loc[6000:, 'Counter'] += 1
        frame.to_csv(clean, index=False)
        result = load_erds(self.path, 'uV')
        self.assertTrue(result['exclusions'])
        target = Path(self.temp.name) / 'export'
        export_erds(result, target)
        restored = json.loads((target / 'report.json').read_text())
        self.assertEqual(restored['metadata']['signal'], 'oscar')
        self.assertIn('inputs', restored['metadata'])
        self.assertNotIn('_trial_data', restored)
        with (target / 'trials.csv').open(encoding='utf-8-sig') as handle:
            trials = list(csv.DictReader(handle))
        self.assertEqual(len(trials), sum(c['n'] for c in result['conditions'].values()) * 8 * 4)
        row = next(r for r in trials if r['key'] == 'Motorik/1/2/1' and r['channel'] == 'C3' and r['band'] == 'mu')
        self.assertAlmostEqual(float(row['task_percent']), -75)
        self.assertEqual(float(row['reference_support_start_s']), -2)
        self.assertEqual(float(row['reference_support_end_s']), 0)
        self.assertEqual(len(json.loads(row['reference_centers_s'])), 11)
        with (target / 'summary.csv').open(encoding='utf-8-sig') as handle:
            row = next(csv.DictReader(handle))
        self.assertIn('reference_uV2', row)
        with self.assertRaises(FileExistsError):
            export_erds(result, target)
        qc = Path(self.temp.name) / 'qc.json'
        qc.write_text(json.dumps(dict(bad_channels=['EEG 2'])))
        with self.assertRaisesRegex(ValueError, 'Positionsnamen'):
            load_erds(self.path, 'uV', qc_path=qc)


if __name__ == '__main__':
    unittest.main()
