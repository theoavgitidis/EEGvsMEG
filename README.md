# EEGvsMEG

Studienarbeit zur Unterscheidbarkeit motorischer und kognitiver Aufgaben mit einem Unicorn-Achtkanal-EEG und zum Vergleich mit dem MEGBCI2020-Paradigma.

Stand: 28. Oktober 2026.

| Bereich | Stand |
|---|---|
| Aktuelles Studienprotokoll | **Implementiert, Hardware-Abnahme offen:** `eeg-session-2.0`, 168 Trials in 45:04 min; linke/rechte Faust und Fuß-Dorsalflexion, motorisch und vorgestellt, ergänzt um beidseitige Imagery und kognitive MEG-Vergleichsaufgaben. |
| Ausführbare CLI | `start session` / `start session raw` starten Protokoll 2.0; Reihenfolge `motorik imagery` oder `imagery motorik`. |
| Aufnahme | `start session` verwendet OSCAR mit separat erhaltenen Rohdaten; `start session raw` den C-API-Recorder. Windows-/Headset-Abnahme steht aus. |
| Auswertung | Beide MNE-Viewer und explorative ML-Piloten vorhanden. Neue Aufgaben, Generalisierung und EEG–MEG-Leistungsvergleich sind noch nicht validiert. |

## Dokumentation

| Thema | Anleitung |
|---|---|
| Studienziel, neue Aufgaben, Zeitplan und wissenschaftliche Grenzen | [Versuchsprotokoll 2.0](docs/experiment-protocol.md) |
| Technische Verträge und Prüfstand | [Sitzungsspezifikation](docs/session-automation-plan.md) |
| Automatische Sitzung 2.0 und Eingriffe | [Sitzungsanleitung](gtec_Clib/terminal/SESSION_ANLEITUNG.md) |
| OSCAR-Einrichtung, Signalwahl und Hardware-Abnahme | [OSCAR-Aufnahme](acquisition/README.md) |
| Windows-Build und technische Übersicht | [Terminal-README](gtec_Clib/terminal/README.md) |
| CLI-Befehle und manuelle Aufnahme | [Verwendung](gtec_Clib/terminal/VERWENDUNG.md) |
| Beide EEG-Viewer, Filter, Wasserfallansicht und Export | [MNE-Anleitung](gtec_Clib/terminal/MNE_ANLEITUNG.md) |
| Dauerhafte Teilnehmer-IDs und Sitzungszuordnung | [ID-Schema](docs/participant-ids.md) |
| Teilnehmerangaben und Sitzungsnotizen | [Teilnehmerbogen](docs/participant-record-template.md) |
| Kurze manuelle Vorführung mit bisherigen Aufgaben | [Demo-Anleitung](presentations/Demo_Anleitung_DE.md) |

## Sitzung 2.0

Vier Motorikblöcke und vier Blöcke mit Imagery und mentalen Vergleichsaufgaben. Die acht unilateralen Bedingungen erhalten je 16 Trials, beidseitige Hand-/Fußvorstellung je zwölf, Wortgenerierung und einzelne Subtraktion je acht. Baselines und geplante Pausen sind in **45:04 Minuten** enthalten; Aufbau, Übung und Wiederholungen kommen hinzu.

Die beidseitige Hand-/Fußvorstellung erhält den gemeinsamen MEG-Kontrast. Die Seitenunterscheidung ist eine EEG-Erweiterung. Kognitive Aufgaben bleiben wegen der kleinen Trialzahlen explorativ. Die vollständigen Parameter werden im Versuchsprotokoll gepflegt. Der Ablauf ist hardwarefrei einschließlich vollständiger beschleunigter Sitzung geprüft. Auf dem Messrechner die EXE neu bauen; Windows-/Headset-Abnahme und wissenschaftlicher Pilot bleiben erforderlich.

## Bauen und starten

Benötigt werden Windows x64, Visual Studio 2022 beziehungsweise dessen C++-Buildtools mit Windows SDK, CMake und die mitgelieferte Unicorn-Bibliothek. Headset zuvor in Windows oder Unicorn Suite koppeln.

In PowerShell aus dem Repository-Stamm:

```powershell
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build-vs -G "Visual Studio 17 2022" -A x64
cmake --build gtec_Clib/terminal/build-vs --config Release
& .\gtec_Clib\terminal\build-vs\Release\unicorn_terminal.exe
```

Vor dem erneuten Bauen eine laufende CLI mit `quit` beenden.

Nach Einweisung, Übung und Prüfung der Signalqualität im **Unicorn-Terminal**:

```text
NewExp "EVM-P001"
scan paired
open DEINE_SERIENNUMMER
config
cue open
```

Alle acht EEG-Kanäle müssen aktiviert sein. Bei mehreren Monitoren das Teilnehmerfenster vor dem Start auf den vorgesehenen Bildschirm verschieben. Den ersten Laufmodus vorab erklären; nach einem aktuellen Release-Build startet dieser Befehl **Protokoll 2.0 mit 45:04 Minuten**:

```text
start session
```

Für neue Teilnehmende das Schema `EVM-P001`, `EVM-P002` usw. verwenden; dieselbe Person behält ihre ID über alle Termine. Vergabe und Sitzungszuordnung: [ID-Schema](docs/participant-ids.md).

Für einen vorhandenen Versuch `GoToExp "EVM-P001"` anstelle von `NewExp` verwenden. Seriennummer durch die Ausgabe von `scan paired` ersetzen. Neue Sitzungen erhalten automatisch eigene Dateinamen.

## Daten ansehen und erhalten

Aufnahmen liegen neben dem Repository unter `recordings/<Teilnehmer-ID>/`; `Where` zeigt den beim Build festgelegten Pfad. EEG, Events, Plan und Sitzungsmetadaten zusammen aufbewahren, bei OSCAR auch die zugehörigen Verarbeitungs-/Gerätedateien. Originalaufnahmen bleiben unverändert.

Beispiel für eine vorhandene Aufnahme auf macOS, nach Einrichtung der dokumentierten Umgebung und Bestätigung der Einheit:

```bash
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" --unit uV
```

`--signal raw` wählt ausdrücklich Rohdaten; bei bestätigten OSCAR-Sitzungen verwendet der Standard die bereinigte Variante. Beide Viewer zeigen EEG mit sichtbaren µV-Skalen, Marker und Zeit-Frequenz-Ansichten. `--view waterfall` öffnet die interaktive Amplituden-/Bandpoweransicht; Installation, Bedienung, Filter, Einheiten und Export stehen in der MNE-Anleitung. Einzelne Frequenzbänder oder hohe Klassifikationswerte belegen keinen bestimmten mentalen Zustand und keine reine neuronale Erkennung.

## Auswertung neuer Sitzungen

Die Importer erhalten die neuen Bedingungen samt Protokollversion und schließen invalidierte/unvollständige Attempts aus. Alte Daten und Modelle bleiben Protokoll 1.0 zugeordnet. Vordefinierte Auswertungen für 2.0: `ME_HandSide`, `ME_FootSide`, `ME_FourClass`, `MI_HandSide`, `MI_FootSide`, `MI_FourClass`, `MI_Bilateral` und `Cognitive`. Ein gemeinsamer gemischter Imagery-Achtklassenwert wird nicht automatisch erzeugt.

```bash
python -m analysis.ml_feasibility PFAD_ZUR_SESSION.csv --signal raw --output NEUER_BERICHT.json
python -m analysis.cbramod_benchmark PFAD_ZUR_SESSION.csv --runs MI_Bilateral --output NEUER_ORDNER
```

Die Baseline verwendet bei 2.0 Mu-/Beta-Bandpower (8–13/13–30 Hz), bei alten Daten die bisherigen fünf Bänder. Gleiche 3-s-Fenster und zurückgehaltene Blöcke bleiben erhalten. Modellbenchmarks benötigen die dokumentierten ML-Abhängigkeiten und lokale Checkpoints; sie werden nicht während der Aufnahme ausgeführt. Modell- und Testdaten müssen dasselbe Protokoll und denselben Kontrast verwenden. `analysis.test_ml_pipeline` und `analysis.test_reve_pipeline` prüfen zusätzlich Datenaufteilung und Modelltraining mit kleinen synthetischen Eingaben, ohne neue Modellgewichte herunterzuladen.

## Bisherige Auswertungen

Diese datierten Berichte dokumentieren vorhandene Daten und Modellversuche mit den bisherigen Aufgaben. Sie sind keine Validierung des neuen Protokolls:

- [Machbarkeit und einfache EEG-/IMU-Baseline, 22.10.2026](docs/ml-feasibility-2026-10-22.md)
- [Modelloptionen und Recherche, 22.10.2026](docs/ml-options-review-2026-10-22.md)
- [CBraMod-Pilot, 22.10.2026](docs/cbramod-pilot-2026-10-22.md)
- [REVE-Pilot, 23.10.2026](docs/reve-pilot-2026-10-23.md)

## Tests und Prüfstand

Aus dem Repository-Stamm:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python gtec_Clib/terminal/test_oscar_session.py
python -m unittest analysis.test_session_protocol analysis.test_event_annotations analysis.test_time_frequency analysis.test_eeg_browser analysis.test_spectrogram_browser analysis.test_view_eeg_cli analysis.test_waterfall_cli analysis.test_waterfall_data analysis.test_waterfall_server
```

C++-Tests benötigen Clang++ oder MSVC `cl`; Viewer- und Annotationstests benötigen MNE, NumPy, pandas und Matplotlib; die HTTP-Tests der Wasserfallansicht benötigen zusätzlich Plotly. Optionale echte Browserprüfungen laufen mit `python -m unittest analysis.test_waterfall_ui analysis.test_waterfall_navigation`, wenn Playwright und ein installiertes Chrome verfügbar sind (`EEG_BROWSER_EXECUTABLE` kann den Browserpfad setzen). Die hardwarefreien Tests prüfen Protokoll 2.0 mit 168 Trials über 250 Zufallsseeds in beiden Laufreihenfolgen, einen vollständigen beschleunigten Sitzungsdurchlauf, Unterbrechungen, Fehler und die im Review korrigierten Timingfälle. Die Viewer-Regressionstests prüfen dichte Marker und Fenstergrößenänderungen, getrennte Kanalachsen, Skalierung und Abschneidehinweise, Navigation, unveränderte Daten sowie echte PNG-Ausgabe ohne Desktop und einen ungefilterten FIF-Speicher-/Ladetest. Die C++-Plan- und Laufzeittests bestanden außerdem mit Address-/UndefinedBehavior-Sanitizer auf macOS.

Die aktuelle Windows-Anzeige, interaktive Terminalbedienung, Vendor-DLL und ein Echtzeitlauf mit Headset sind noch auf dem Messrechner zu validieren. OSCAR ist implementiert und auf synthetischen Daten geprüft; seine EEG-Wirkung auf echte Artefakte ist noch zu untersuchen. Eine validierte EEG–MEG-Synchronisation und die wissenschaftliche Validierung von Protokoll 2.0 stehen aus; vorhandene ML-Auswertungen sind explorative Offline-Piloten.
