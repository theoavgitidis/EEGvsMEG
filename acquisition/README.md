# OSCAR-Aufnahme für die Windows-Sitzungs-CLI

`start session` startet standardmäßig den Python-Worker mit OSCAR. `start session raw` wählt ausdrücklich den bisherigen C-API-Recorder. Die Sitzungssteuerung bleibt C++ und führt [Protokoll 2.0](../docs/experiment-protocol.md) mit 168 Trials und 45:04 Minuten aus. Die EXE auf dem Messrechner neu bauen. Die Aufnahmeintegration ist hardwarefrei und mit dem echten OSCAR-Modell auf synthetischen Daten geprüft. Windows-Build, vorhandene Kundenlizenz und echtes Headset müssen noch auf dem Messrechner abgenommen werden.

## Einrichtung in PowerShell

Aus dem Projektstamm, mit Python 3.12 und den bisherigen C++-Buildtools:

```powershell
$oscarEnv = Join-Path $env:LOCALAPPDATA 'EEGvsMEG\venvs\oscar'
py -3.12 -m venv $oscarEnv
$env:EEG_OSCAR_PYTHON = Join-Path $oscarEnv 'Scripts\python.exe'
& $env:EEG_OSCAR_PYTHON -m pip install -r .\acquisition\requirements.txt
$env:EEG_OSCAR_WORKER = (Resolve-Path .\acquisition\oscar_worker.py).Path
& $env:EEG_OSCAR_PYTHON -c 'from gtec_licensing import api; print(api.check_license("Unicorn Python Hybrid Black").name)'
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build-vs -G 'Visual Studio 17 2022' -A x64
cmake --build gtec_Clib/terminal/build-vs --config Release
& .\gtec_Clib\terminal\build-vs\Release\unicorn_terminal.exe
```

Die Lizenzprüfung muss `SUCCESS` liefern. Falls nötig: vorhandene Unicorn-Python-Lizenz auf **diesem Rechner und Benutzerkonto** aktivieren. Die [Aktivierungsanleitung](../docs/oscar-integration.md) enthält die Herstellerquellen und eine verdeckte lokale Schlüsseleingabe. Schlüssel nicht ins Projekt schreiben.

Die Umgebungsvariablen gelten für diese PowerShell und ihre gestartete CLI. `EEG_OSCAR_PYTHON` ist ausschließlich der Pfad zur ausführbaren Python-Datei, ohne zusätzliche Argumente. CMake hinterlegt bereits den absoluten Worker-Pfad; `EEG_OSCAR_WORKER` ist eine explizite Alternative, etwa nach einem Rechnerwechsel. Die Projektdateien müssen lokal verfügbar bleiben. Kein separates manuelles Starten des Workers erforderlich.

## Bedienung

Im Unicorn-Terminal:

```text
NewExp "EVM-P001"
scan paired
open DEINE_SERIENNUMMER
config
cue open
start session
status
```

Der Start prüft zunächst wie bisher die acht EEG-Kanäle. Anschließend schließt C++ seinen Gerätehandle; nur der Python-Prozess öffnet das gewählte Headset. Er aktiviert für die Aufnahme alle 17 Kanäle (EEG, Beschleunigung, Gyroskop, Batterie, Counter, Validation). Die tatsächliche Python-Gerätekonfiguration wird gespeichert. Die Anzeige bleibt bei `AUFNAHME WIRD VORBEREITET`, bis erste gültige bereinigte Samples bestätigt sind. Erst danach beginnen Anfangsbaseline und Sitzungsuhr. Die Vorbereitung ist auf 120 Sekunden begrenzt. Der am 28.10.2026 beobachtete Windows-Starttimeout ist durch längeres Warten bisher nicht behoben; Befunde und nächste Abnahme stehen im [Fehlerbericht](../docs/oscar-hardwareless-handoff-2026-10-28.md#hardware-free-investigation-update).

`status` und die laufende Sitzungsanzeige zeigen `OSCAR` beziehungsweise `RAW`; bei OSCAR zusätzlich Rohsample-Zahl, bereinigte Sample-Zahl und gemessene Verzögerung. Eine gültige Bestätigung `READY 1 <positive Verzögerung>` über stdout **oder** die atomar bereitgestellte Datei `.ready` gibt den Start frei. Auch nach stdout-Freigabe überwacht C++ die Datei weiter. Identische Bestätigungen sind idempotent, widersprüchliche Verzögerungen führen zum Fehler. Die Datei wird vollständig geprüft, vor dem Löschen geschlossen und bei gültiger Annahme entfernt. Ungültige oder widersprüchliche Dateien bleiben als Fehlerbeleg erhalten; Löschfehler erscheinen im Startlog. Vorhandene `.ready`, `.ready.tmp` oder `.startup.log` am gewählten Dateistamm verhindern einen neuen Start ohne Überschreiben.

`session pause`, `session resume`, `mark`, `stop`, `close` und `quit` behalten ihre Sitzungsbedeutung. Pause hält ausschließlich den Aufgabenablauf an, die Verarbeitung läuft durch.

Bei OSCAR-Fehlern wird kein Rohdatenmodus als Ersatz gestartet. Ein Startfehler verhindert die Baseline; ein Laufzeitfehler beendet die Sitzung als `failed`. Eine erst nach Freigabe eintreffende widersprüchliche Bestätigung ist ein Laufzeitfehler; bereits geschriebene Ereignisse bleiben erhalten. Auch `DONE` vor Bereitschaft oder vor angefordertem Stop, Prozessende ohne `DONE`, ein nicht erfolgreicher Exitcode, unpassende Sample-Zuordnung oder ein nicht bestätigter Abschluss sind Fehler. Ein ausbleibender Worker-Status wird nach sechs Sekunden erkannt, bei Dateifreigabe ab deren Annahme; Stillstand der Datenströme prüft der Worker nach fünf Sekunden. Der C++-Stop wartet höchstens acht Sekunden auf das Kind und beendet es danach als Fehler.

Nach einer OSCAR-Sitzung ist kein C-API-Gerätehandle mehr geöffnet. Vor einer weiteren Sitzung oder manuellen Gerätebefehlen erneut `open DEINE_SERIENNUMMER` ausführen. Zum ausdrücklichen Rohdatenbetrieb:

```text
open DEINE_SERIENNUMMER
start session raw
```

Der manuelle Befehl `record` bleibt unverändert und verwendet Rohdaten.

## Dateien und Zeitbezug

Neben den bisherigen Plan-, Event- und Sessiondateien entstehen:

| Datei | Inhalt |
|---|---|
| `session_….csv` | Unveränderte Rohwerte vom Python-Treiber, 17 Kanäle |
| `session_….csv.oscar.csv` | OSCAR-Ausgabe, gleiche Spalten und Rohsample-Indizes |
| `session_….csv.processing.json` | Versionen, Zustand, Verzögerung, Sample-Zahlen, Stop-Ziel, Einheiten und gegebenenfalls g.Pype-Nutzungsmarkierung |
| `session_….csv.device.json` | Tatsächlich vom Python-Treiber gemeldete Gerätekonfiguration |
| `session_….csv.worker.log` | stderr/Diagnosen des Workers |
| `session_….csv.startup.log` | C++-Startdiagnose: Build-Kennung, Windows-EXE-Pfad, Python-/Worker-/Ready-Pfad, Worker-PID, monotone Zeiten, erste Sample-Zähler, beobachtete READY-Quelle, Löschung und Fehlerursache |

Im Workerlog ergänzen JSON-Zeilen mit Präfix `OSCAR_STARTUP` den Startablauf: tatsächlicher Python-Pfad, PID, absolute Ausgabepfade, monotone Zeiten, Pipeline-Start, erfolgreicher `.ready`-Ersatz sowie Beginn/Ende der ersten Protokollausgaben. stdout bleibt ausschließlich Protokolltransport. Logs zusammen mit den Sitzungsdateien aufbewahren; sie enthalten lokale Pfade und gehören nicht ungeprüft in öffentliche Berichte.

OSCAR gibt eine verzögerte Folge aus. Die Software verwirft die Anlaufwerte und prüft **jedes** bereinigte Sample anhand sämtlicher Hilfskanäle, einschließlich Counter, gegen das passende Rohsample. Die Verzögerung wird aus dem Modell gelesen, nicht fest auf 83 gesetzt. Sind Annahmen oder Reihenfolge nicht erfüllt, wird abgebrochen. Auch Counter-Unterbrechungen und -Wraps werden derzeit als Fehler behandelt.

Die bereinigte Datei beginnt wie die Rohdatei bei `sample_index=0`; ihre Indizes bezeichnen die ursprünglichen Rohsample-Positionen. Marker werden deshalb nicht zusätzlich um die OSCAR-Verzögerung verschoben. Ihre Erfassung bleibt eine Näherung: C++ verwendet den zuletzt bestätigten Rohsample-Stand des Workers, der etwa alle 40 ms aktualisiert wird, zuzüglich Queue-, IPC- und Scheduling-Latenz. Das ist keine neue Präzisionsmessung des Anzeigezeitpunkts.

Beim Stop liest der Worker weitere **echte** Samples, bis die bereinigte Folge den beim Stop erfassten Rohsample-Stand abdeckt. Rohdatei und bereinigte Datei haben deshalb unterschiedliche Endlängen; Metadaten beschreiben beide. Keine synthetischen Samples werden zum Auffüllen verwendet. Ein begrenzter Schreibpuffer verhindert unbeschränktes Speicherwachstum; Überlauf führt zum Fehler.

## Viewer und ML

Den bisherigen Roh-CSV-Namen angeben. Beide Viewer und die ML-Importer wählen bei OSCAR-Sitzungen automatisch die bestätigte bereinigte Datei und verwenden die gemeinsame ursprüngliche Ereignisdatei:

```powershell
python .\view_eeg.py PFAD_ZUR_SESSION.csv --unit uV
python .\view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --signal raw
python .\analysis\view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --signal oscar
python -m analysis.ml_feasibility PFAD_ZUR_SESSION.csv --signal raw --output bericht.json
```

`auto` ist Standard, `raw` und `oscar` sind explizit wählbar. Alte Sitzungen bleiben standardmäßig Rohdaten. Bei unvollständiger/fehlgeschlagener OSCAR-Verarbeitung oder fehlender Datei verweigert `auto` den Import, statt still auf Rohdaten zurückzufallen. `--signal raw` erlaubt die explizite Untersuchung vorhandener Rohdaten. Bei OSCAR ist `--unit uV` verpflichtend. Anzeige und FIF-Beschreibung benennen die Datenvariante; Anzeige-Filter kommen erst danach. `--save-fif` exportiert die **gewählte** Variante vor zusätzlichen Anzeigefiltern. Modell-Benchmarks und Predict-CLIs haben ebenfalls `--signal`; ihr Datenprovenienzbericht hält die Variante und Verarbeitungsmetadaten fest.

Blinzeln ist eine eigene Bedingung des bisherigen Protokolls 1.0; in Protokoll 2.0 entfällt sie. Bei alten Blinzelaufnahmen Rohdaten und bereinigte Daten vergleichen: OSCAR kann genau das beabsichtigte Augensignal unterdrücken. Vorhandene auf Rohdaten trainierte Modelle werden durch den OSCAR-Standard nicht automatisch für bereinigte Ausgaben oder neue Aufgaben validiert.

## Prüfungen und Hardware-Abnahme

Hardwarefrei:

```text
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python gtec_Clib/terminal/test_oscar_session.py
python -m unittest analysis.test_oscar_recording analysis.test_signal_selection analysis.test_view_eeg_cli analysis.test_waterfall_cli analysis.test_event_annotations
```

Die letzte Gruppe benötigt die Viewer-/ML-Datenabhängigkeiten (MNE, NumPy, pandas, SciPy und scikit-learn). Die optionalen `VendorOscarTest`-Tests benötigen die gepinnten Herstellerpakete, aber keine Hardware und keinen Kundenschlüssel. Sie ersetzen **ausschließlich den Treiber durch eine synthetische Quelle**; OSCAR und die g.Pype-Authentifizierung laufen unverändert. Sie prüfen außerdem READY, reales Nachlaufen und vollständige Verarbeitungsmetadaten. Die C++-Prozesstests verwenden einen separaten synthetischen Protokollpartner und behaupten keine Artefaktkorrektur.

Die C++-Tests auf Windows in einer **x64 Developer PowerShell / Developer Command Prompt für Visual Studio 2022** ausführen (`cl` muss verfügbar sein). Sie bauen eigene Mock-Programme im temporären Verzeichnis, einschließlich Unicode-Pfaden. `test_oscar_session.py` prüft zusätzlich Datei ohne stdout-READY, beide Reihenfolgen, doppelte Bestätigung, späte Dateifreigabe ohne vorherigen Status, ungültige/widersprüchliche Bestätigungen, vorzeitiges Ende, Timeout, kontrollierten Stop und Schutz vorhandener Startartefakte. Die Test-Zeitbegrenzung ist ausschließlich im Mock-Build mit `UNICORN_SESSION_TEST` einstellbar; der Release-Build behält 120 Sekunden.

Dokumentierter Prüfstand der Integration vom 27.10.2026 unter macOS: Recorder-/Sessionregressionen einschließlich 250 Seeds und beschleunigter 112-Trial-Sitzung bestanden; synthetische OSCAR-Prozesstests für READY, Stop, Fehler, Exitcode, Geräteübergabe und Statusstillstand bestanden. Die damalige Viewer-/Datengruppe umfasste 46 Tests, davon 44 bestanden und zwei optionale Herstellerpaket-Tests übersprungen. Separat mit gepinnten Herstellerpaketen bestanden alle zehn OSCAR-Tests einschließlich echtem Modell und synthetischem Treiber. Vollständige Modelltrainingstests waren in der Viewer-Umgebung wegen fehlendem torch nicht ausführbar. Diese Angaben dokumentieren den früheren Integrationsstand. Für Protokoll 2.0 wurden Recorder-/Session-/OSCAR-Prozesstests erneut ausgeführt; ein voller Echtzeitlauf mit Headset bleibt ausstehend.

Abnahme auf dem Windows-Messrechner:

1. Lizenzprüfung `SUCCESS`, aktueller Release-Build und richtig gekoppeltes Headset bestätigen.
2. Kurze Sitzung mit `start session` starten: Vorbereitungsanzeige, anschließend Baseline und `processing=OSCAR` prüfen. Roh- und OSCAR-Zähler müssen wachsen.
3. `mark hardware_check`, `session pause`, `session resume`, dann `stop` testen. Aufnahme muss während der Pause weiterlaufen. Sessionzustand ist bei diesem absichtlichen Stop `aborted`, Verarbeitung dagegen `complete`; `oscar_samples >= stop_target_raw_samples` prüfen.
4. Dateien im Viewer automatisch als OSCAR und mit `--signal raw` öffnen. Markerpositionen, Einheiten und unterschiedliche Signale prüfen.
5. Kontrolliert einen ungültigen Python-Pfad konfigurieren: `start session` muss ohne Baseline fehlschlagen. Danach richtigen Pfad wieder setzen und Headset neu öffnen. Kein stiller Fallback.
6. `start session raw` testen; danach erneut öffnen und einen vollständigen OSCAR-Durchlauf über alle 168 Trials durchführen. Sample-Zuordnung, Protokoll, Logs und Abschlussstatus aufbewahren.

Offen bis zur Abnahme: Windows-Prozessstart/Build, tatsächlicher Lizenzschlüssel, Bluetooth-Verhalten, CPU-/Schreibleistung über 45:04 Minuten und EEG-Wirkung auf echte Artefakte. Die Modellpipeline-Regressionen mit kleinen synthetischen Trainingsdaten wurden separat in der vorhandenen torch-Umgebung geprüft; das validiert keine Modellleistung auf neuen Aufnahmen.
