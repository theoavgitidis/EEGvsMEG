"""Synthetic, hardware-free ERD/ERS numerical and session integrity regressions."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis.erds_data import (FS, TIMES, SITES, CONDITIONS, band_weights, compute_erds,
                                export_erds, head_geometry, json_safe, load_erds, window_psd)


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
        c = compute_erds(self.data, self.events)['conditions']['me_hand_right']
        self.assertAlmostEqual(c['reference'][1, 0], 125)
        self.assertAlmostEqual(c['task_power'][1, 0], 62.5)
        self.assertAlmostEqual(c['task_percent'][1, 0], -50)

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
