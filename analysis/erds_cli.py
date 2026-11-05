"""Shared ERD/ERS CLI contract for both existing viewer entry points."""
from pathlib import Path


def add_erds_arguments(parser):
    parser.add_argument('--erds-qc', type=Path,
        help='JSON mit bad_channels, bad_trials, bad_intervals_s, montage_confirmed')
    parser.add_argument('--erds-export', type=Path,
        help='Neues Verzeichnis für ERD/ERS-JSON und numerische CSV-Tabellen')


def run_erds(args):
    if (getattr(args, 'filtered', False) or getattr(args, 'psd', False)
            or getattr(args, 'highpass', None) is not None or getattr(args, 'lowpass', None) is not None
            or getattr(args, 'save_fif', None) or getattr(args, 'snapshot', None)):
        raise ValueError('--view erds verwendet eigene unveränderte Eingangsdaten; Anzeige-Filter, --psd, '
                         '--save-fif und --snapshot sind hier nicht verfügbar. --erds-export/PNG-Schaltflächen verwenden.')
    if (args.start != 0 or args.duration != 10 or args.scale_uv is not None
            or args.spectrogram_channel is not None or args.spectrogram_max != 100
            or args.frequency_scale != 'log'):
        raise ValueError('--view erds verwendet Cue-/Offset-Zeitfenster und eigene Kanal-/Farbsteuerung; '
                         'Optionen der Zeitkurvenansicht weglassen.')
    # Also support `python analysis/view_eeg.py`, without a second implementation.
    if not __package__:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from analysis.erds_data import load_erds, export_erds
    signal = 'raw' if args.signal == 'raw' else 'oscar'
    result = load_erds(args.csv, args.unit, signal=signal, qc_path=args.erds_qc)
    print('Signal: ' + result['metadata']['signal_description'])
    print('ERD/ERS: ' + ', '.join(f'{key}: {value["n"]} Trials' for key, value in result['conditions'].items()))
    print(f'Ausschlüsse: {len(result["exclusions"])}; keine automatische Artefaktfreiheit bestätigt.')
    if args.erds_export:
        target = export_erds(result, args.erds_export)
        print('ERD/ERS-Export: ' + str(target.resolve()))
    if not args.no_show:
        from analysis.erds_browser import serve_erds
        serve_erds(result, title=args.csv.name)
