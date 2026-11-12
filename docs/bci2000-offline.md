# BCI2000 offline auf macOS und Windows

Stand: 12.11.2026. Implementiert sind ein eigener kalibrierter `.dat`-Reader, der Export vorhandener Projekt-Sitzungen für BCI2000Analysis, vollständige State-Exporte, beide Viewer-Einstiegspunkte und ein Runner für native Offline-Filter. **Aufnahme und Versuchssteuerung werden nicht geändert.**

Die Python-Werkzeuge laufen ohne Headset, Unicorn-DLL, MATLAB, Torch oder BCI2000-Installation. Für BCI2000Analysis und die originalen BCI2000-Filter benötigt man zusätzlich einen passenden nativen BCI2000-Build. Die Python-Funktionen sind auf macOS geprüft; ein Windows-Lauf und ein Lauf mit den nativen BCI2000-Programmen stehen noch aus.

## 1. Python-Umgebung

Die vorhandene MNE-Umgebung mit NumPy, pandas, SciPy, MNE und Matplotlib verwenden. Es kommen keine neuen Bibliotheken hinzu. Die Befehle werden aus dem Repository-Stamm ausgeführt.

macOS, vorhandene Umgebung:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline --help
```

Windows PowerShell, falls noch keine passende Umgebung existiert:

```powershell
$offlineEnv = Join-Path $env:LOCALAPPDATA 'EEGvsMEG\venvs\offline'
py -3 -m venv $offlineEnv
$offlinePython = Join-Path $offlineEnv 'Scripts\python.exe'
& $offlinePython -m pip install numpy pandas scipy mne matplotlib
& $offlinePython -m analysis.bci2000_offline --help
```

Bei vorhandener Umgebung `$offlinePython` auf deren `python.exe` setzen. Die folgenden Mac-Befehle lassen sich unter Windows durch `& $offlinePython` anstelle von `~/.venvs/eeg-mne/bin/python` ausführen; Pfade passend ersetzen. Ausgaben und neue Umgebungen außerhalb des synchronisierten Checkouts ablegen.

## 2. Unsere CSV-Sitzungen für BCI2000Analysis vorbereiten

Eingabe ist die ursprüngliche Projekt-CSV zusammen mit `.events.csv` und `.session.json`; Plan-, Geräte- und OSCAR-Dateien bleiben, soweit vorhanden, daneben. Automatische Sitzungen 1.0 und 2.0 werden anhand ihrer eigenen Labels behandelt. Manuelle Vier-Spalten-Marker werden nicht in erfundene Trials umgewandelt.

Zunächst einen Ausgabe-Elternordner anlegen. **Der konkrete Ergebnisordner darf noch nicht existieren.** Beispiel für zwei geeignete Imagery-Kontraste:

```bash
mkdir -p "$HOME/.local/share/EEGvsMEG/bci2000"
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline prepare \
  ../recordings/EVM-P001/DEINE_SITZUNG.csv \
  --signal raw --runs MI_HandSide MI_Bilateral \
  --output-dir "$HOME/.local/share/EEGvsMEG/bci2000/pilot-01"
```

Windows-Beispiel mit einer bereits vorhandenen Aufnahme:

```powershell
$bciOutput = Join-Path $env:LOCALAPPDATA 'EEGvsMEG\bci2000'
New-Item -ItemType Directory -Force $bciOutput | Out-Null
& $offlinePython -m analysis.bci2000_offline prepare `
  '..\recordings\EVM-P001\DEINE_SITZUNG.csv' `
  --signal raw --runs MI_HandSide MI_Bilateral `
  --output-dir (Join-Path $bciOutput 'pilot-01')
```

Dateinamen ersetzen. Bei fehlenden vollständigen Klassen wird ein ausdrücklich angeforderter Kontrast zurückgewiesen. Ohne `--runs` werden die verfügbaren Kontraste exportiert und nicht mögliche Kontraste mit Begründung unter `skipped_contrasts` aufgeführt.

Protokoll 2.0: `ME_HandSide`, `ME_FootSide`, `ME_FourClass`, `MI_HandSide`, `MI_FootSide`, `MI_FourClass`, `MI_Bilateral`, `Cognitive`. Protokoll 1.0: `Motorik`, `Imagery`, `Kognitiv` mit den bisherigen Aufgaben und gegebenenfalls zugehöriger später Erholung. Keine Zusammenlegung alter und neuer Aufgaben.

`--signal raw` ist hier bewusst Standard. `--signal oscar` verlangt die bestätigte vollständige Verarbeitung; `--signal auto` verwendet den vorhandenen Projektvertrag und fällt bei unvollständigem OSCAR nicht still auf Rohdaten zurück. Beim OSCAR-Export bleiben die originalen Rohsample-Indizes maßgeblich; Marker werden nicht zusätzlich um die Modellverzögerung verschoben.

Bekannte Kontaktprobleme lassen sich explizit berücksichtigen:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline prepare \
  PFAD_ZUR_SESSION.csv --signal raw --runs MI_Bilateral \
  --after-marker 'ground placed' --settle-seconds 10 \
  --output-dir NEUER_ORDNER
```

Der Marker muss genau einmal als manuelle Beobachtung vorhanden sein. Die Wartezeit ist eine Ausschlussentscheidung, keine belegte Einschwingzeit. Eine frühe Aufgabe verwirft den gesamten zugehörigen Trial einschließlich eventueller Restfenster.

### Was exportiert wird

```text
pilot-01/
  manifest.json
  spectral.prm
  session001/
    MI_HandSide-block01.dat
    MI_HandSide-block01.dat.metadata.json
    ... weitere Blöcke/Kontraste ...
    source.events.csv
    source.session.json
    source.plan.csv                 # sofern vorhanden
    source.device.json             # sofern vorhanden
    source.processing.json         # sofern vorhanden
    source.auxiliary.npz
    source.auxiliary.json
    retained-windows.csv
```

- `.dat`: acht EEG-Kanäle in aufgezeichneter Reihenfolge, bestätigte Einheiten nach µV umgerechnet, ohne zusätzlichen Filter oder Referenzierung. Die Originaldateien bleiben unverändert. `float32` ist ein abgeleitetes Austauschformat; der maximale Rundungsfehler wird je Datei dokumentiert.
- Eine Datei enthält den zusammenhängenden Abschnitt eines ursprünglichen Blocks, einschließlich nicht ausgewählter/ungültiger Abschnitte innerhalb dieses Blocks. Baselines außerhalb der exportierten Blöcke bleiben in den Originalen. Es werden keine Trials zusammengeschnitten oder künstlichen Samples ergänzt.
- Automatische Phasen-, Trial- und Attempt-Informationen stehen in eigenen States; vollständige Ereignistexte und nachträgliche Invalidierungen bleiben zusätzlich im unverändert kopierten Eventlog.
- Hilfsspalten einschließlich ursprünglicher Empfangszeitstempel, IMU, Counter und Validation bleiben in `source.auxiliary.npz`; `source.auxiliary.json` ordnet die numerischen Arraynamen den ursprünglichen Spaltennamen zu. Es sind keine EEG-Modellmerkmale.
- `manifest.json` enthält Eingabe-/Ausgabehashes, Einheiten, Ausschlüsse, Trialzahlen, Signalvariante, Parameterherkunft und Folds. Nur ein erfolgreich abgeschlossener Export veröffentlicht den neuen Ergebnisordner.

### Zeitfenster und States

Invalidierte und unvollständige Attempts werden vor der Auswahl ausgeschlossen, einschließlich später Invalidierungen außerhalb der EEG-Datei. Validierung und Counter werden geprüft; ein fehlerhaftes Sample im Analysefenster verwirft alle Fenster desselben Attempts. Der Datenstrom selbst wird nicht repariert.

| State | Bedeutung |
|---|---|
| `TargetCode` | Kontrastspezifische Klasse 1…N innerhalb gültiger Analysefenster; sonst 0. Mapping in `manifest.json` und Header. |
| `EvmWindow`, `Feedback` | 1 innerhalb des gültigen 3-s-Fensters, sonst 0. `Feedback` ist nur eine Offline-Kompatibilitätsmarkierung. |
| `EvmAnalysis` | Ein einzelnes Sample am Ende jedes gültigen 3-s-Fensters; für eine Spektralbeobachtung je Trial. |
| `EvmRun`, `EvmCondition`, `EvmPhase` | Numerische Kontextwerte mit dokumentiertem Header-Mapping. |
| `EvmBlock`, `EvmTrial`, `EvmAttempt` | Ursprünglicher Kontext, auch für ausgeschlossene Attempts. |
| `EvmStatus` | 0 ohne Trialstatus, 1 abgeschlossen, 2 invalidiert, 3 unvollständig; spätere Invalidierung hat Vorrang. |
| `EvmQuality` | Sampleprüfung aus Validation und Counter; keine umfassende Artefakterkennung. |
| `Counter`, `Validation` | Originalwerte als States, sofern im jeweiligen Abschnitt exakt als unsigned 32-Bit-Integer darstellbar; sonst ausschließlich im vollständigen Hilfsspaltenexport. |
| `Running`, `SourceTime`, `StimulusTime` | Erforderliche Austausch-/Kompatibilitätswerte. Die Uhren sind **synthetische nominale Samplezeiten mit 16-Bit-Wrap**, keine gemessenen Aufnahme-/Displayzeiten oder UTC-Werte. |

Die Aufgabenfenster bleiben 0,5–3,5 s nach dem angewiesenen Cue. `SampleBlockSize=1` erhält die Grenzen und die einzelne Endmarkierung ohne Blockrundung oder Padding. Das ist für Offline-Verarbeitung gewählt und kann langsamer als größere Blöcke sein. Nicht als getestete Echtzeitkonfiguration verwenden.

## 3. Training und Test in BCI2000Analysis

BCI2000Analysis ist das native Offline-Analyseprogramm. Einen aktuellen passenden Build über die [offizielle BCI2000-Seite](https://www.bci2000.org/mediawiki/index.php/Main_Page) beziehen; Downloads verlangen ein Benutzerkonto. Für macOS ist ggf. ein eigener Build nötig. Originale Filterwerkzeuge werden mit `BUILD_COMMANDLINE_FILTERS` gebaut; den konkreten Build auf dem Zielrechner prüfen. [BCI2000-Offline-Werkzeuge](https://www.bci2000.org/mediawiki/index.php/User_Reference:Command_Line_Processing)

1. `manifest.json` öffnen und für den gewünschten Kontrast **einen Fold** wählen. Dessen `train`-Dateien als Analyse-/Trainingsdateien, `test`-Dateien ausschließlich als Testdateien laden. Alle Pfade gelten relativ zum Exportordner.
2. Für den Einstieg einen Zweiklassenkontrast wie `MI_HandSide` verwenden. Den SMR-/Spektral-Filtergraph bewusst auswählen; ein automatisch vorgeschlagener Graph ist noch keine bestätigte Projektpipeline.
3. `spectral.prm` als Ausgangskonfiguration verwenden bzw. die darin dokumentierten Parameter einstellen: 3-s-Historie, Mittelwertentfernung, Leistungsspektrum, 8–30 Hz, 1-Hz-Bins, AR-Ordnung 16. Diese Einstellungen sind eine feste technische Referenz, kein nach Testleistung ausgewähltes Optimum.
4. Die beiden `analysis_conditions` aus dem Manifest übernehmen, z. B. `EvmAnalysis == 1 && TargetCode == 1` und entsprechend Klasse 2. Dadurch entsteht eine Beobachtung pro gültigem Trial am Ende seines Fensters.
5. Falls CSP untersucht wird, die `csp_conditions` mit `EvmWindow` verwenden und CSP ausschließlich auf den Trainingsdateien schätzen. Anschließend denselben trainierten räumlichen Filter unverändert auf Testdateien anwenden.
6. Klassifikator nur mit Trainingsdaten lernen, auf den Testdateien prüfen und pro Fold Konfusionsmatrix, Klassenzahlen und Einstellungen sichern. Alle festgelegten Folds durchlaufen; Ergebnisse auf Trialebene zusammenführen, nicht wiederholt überlappende Spektren als unabhängige Trials zählen.

Ein Input erzeugt Leave-one-block-out. Mehrere Aufnahmen **derselben Person** erzeugen Leave-one-session-out; alle Blockdateien einer Testsitzung bleiben gemeinsam zurückgehalten. Doppelte Sitzungen oder identische Datenkopien werden zurückgewiesen. Beispiel:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline prepare \
  TERMIN_1.csv TERMIN_2.csv --signal raw --runs MI_HandSide \
  --output-dir NEUER_ORDNER
```

Unterschiedliche Personen, Protokolle oder Signalvarianten werden nicht gepoolt. Fehlen in einer Trainings-/Testpartition Klassen oder gibt es nur einen Block, werden keine gültigen Folds behauptet; `evaluation_unavailable` erklärt den Grund. Für die langfristige Generalisierung weiterhin eine vorher unangetastete Sitzung verwenden.

Die BCI2000Analysis-Oberfläche arbeitet mit zwei Analysebedingungen. Vier-/Mehrklassenexporte benötigen ausdrücklich definierte paarweise Analysen oder eine eigene geeignete Mehrklassenauswertung; der Export allein trainiert keinen Mehrklassenklassifikator. Die nativen Funktionen und Bedienung sind in der [BCI2000Analysis-Referenz](https://www.bci2000.org/mediawiki/index.php/User_Reference:BCI2000Analysis) beschrieben.

**Methodenvergleich:** BCI2000-AR-/FFT-Spektren und kontinuierliche Filterzustände sind nicht identisch mit unserer fensterweisen Welch-/Bandpower-Baseline. Gleiche Trialfenster und Splits machen die Methoden vergleichbar, beweisen aber keine numerische Gleichheit. Zusätzliche Filter, CSP und Modellwahl vollständig dokumentieren und ausschließlich aus Trainingsdaten bestimmen. Ein physischer Bewegungsbeginn oder neuronale Herkunft wird damit nicht bestätigt.

## 4. Native `.dat`-Dateien auf Mac oder Windows untersuchen

Metadaten, Kalibrierbarkeit und alle States prüfen:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline inspect AUFNAHME.dat
```

Beide Viewer können `.dat` direkt öffnen. **`--unit` und `--signal` weglassen**: die Kalibrierung kommt aus `SourceChGain` und `SourceChOffset` des Headers. Samplingrate und Kanalnamen werden ebenfalls aus dem Header gelesen; fehlende/ungültige Kalibrierung wird zurückgewiesen. Ein fehlender/leerer Kanalnamenparameter liefert ausdrücklich generische `EEG 1` usw., keine erfundenen Elektrodenpositionen.

```bash
~/.venvs/eeg-mne/bin/python view_eeg.py AUFNAHME.dat
~/.venvs/eeg-mne/bin/python -m analysis.view_eeg AUFNAHME.dat --psd
~/.venvs/eeg-mne/bin/python view_eeg.py AUFNAHME.dat \
  --no-show --save-fif NEUE_AUFNAHME_raw.fif
```

Bei nicht erkennbaren EEG-Namen die tatsächlich vorhandenen Namen ausdrücklich angeben:

```bash
~/.venvs/eeg-mne/bin/python view_eeg.py AUFNAHME.dat --bci-channels KanalA KanalB
```

Die Anzeige und Spektren zeigen nur ausgewählte EEG-Kanäle in Volt/µV. Sämtliche numerischen States bleiben im importierten MNE-Objekt als dimensionslose `misc`-Kanäle mit Präfix `BCI::` erhalten; der Hauptviewer speichert sie im FIF mit doppelter Genauigkeit. Sie werden nicht als µV-Kurven dargestellt. Namen und Kanaltypen vor eigener MNE-Verarbeitung prüfen und EEG ausdrücklich mit `raw.copy().pick('eeg')` auswählen.

Bei unseren Exporten werden die vollständigen Originalevents aus der hashgeprüften Begleitdatei einschließlich Attempt-Status importiert und zum Blockanfang verschoben. Bei fremden `.dat` ohne Begleitvertrag werden Änderungen von `StimulusCode`, `TargetCode` und gegebenenfalls `EvmClass` als numerische Annotationen dargestellt; daraus werden keine Aufgabenbezeichnungen oder vollständigen gültigen Trials erfunden. Bei PhysioNet entspricht `TargetCode` nur zusammen mit dem jeweiligen Lauf einer konkreten Aufgabe.

Vollständiger numerischer Export:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline convert AUFNAHME.dat \
  --output-dir NEUER_ORDNER
```

Erzeugt `calibrated-signals-uV.csv`, `states.npz`, `metadata.json` und `recording_raw.fif`. `metadata.json` ordnet die Arraynamen `state_000` usw. den ursprünglichen States zu und erhält alle Parameterzeilen. Mit `--no-fif` ist nur der numerische Export möglich, auch wenn ein 64-Bit-State die exakte Ganzzahldarstellung in float64 überschreitet. Der CSV-Export ist **kein künstlich vervollständigtes Projekt-Sitzungsformat**; die bestehenden Studienmodelle benötigen weiterhin ihren bestätigten Protokoll-/Ereignisvertrag.

Unterstützte native Formate: BCI2000 1.0/1.1, Little Endian `int16`, `int32`, `float32`; Integer-States bis 64 Bit, einschließlich Bitfeldern über Bytegrenzen. Aktivierte Kanalzeitausrichtung (`AlignChannels`) wird beim MNE-Import zurückgewiesen, da keine unbemerkte Interpolation erfolgen soll. Daten mit gemischten Sensorarten/MEG nicht pauschal als EEG auswählen; dieser Weg behandelt ausgewählte, entsprechend kalibrierte EEG-Kanäle.

## 5. Originale BCI2000-Filter offline ausführen

Zunächst vorhandene Programme finden, z. B. auf Windows:

```powershell
& $offlinePython -m analysis.bci2000_offline doctor 'C:\BCI2000'
```

Auf macOS entsprechend den tatsächlichen nativen Installations-/Buildpfad angeben. `doctor` startet keine Programme und bestätigt lediglich vorhandene Dateien, Hashes und grundsätzliche Ausführbarkeit. Eine Windows-`.exe` ist kein nativer Mac-Build.

Unverarbeitete, **headerkalibrierte** Daten durch die originalen Formatkonverter als Tabelle ausgeben:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline run-chain AUFNAHME.dat \
  --bci2000-dir /PFAD/ZU/BCI2000 --output-dir NEUER_ORDNER
```

AR-Spektren mit dem mitgelieferten Ausgangsparametersatz, sofern `bci_arfilter` vorhanden ist:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.bci2000_offline run-chain BLOCK.dat \
  --bci2000-dir /PFAD/ZU/BCI2000 --filter bci_arfilter \
  --parameters EXPORTORDNER/spectral.prm --output-dir NEUER_ORDNER
```

`--filter` kann mehrfach in gewünschter Reihenfolge angegeben werden. Verwendet werden nur vorhandene `bci_*`-Offline-Werkzeuge. Die Suche berücksichtigt den angegebenen Ordner, `tools/cmdline`, `Tools/cmdline` und `prog`, unter Windows auch `.exe`. Die binären Pipes laufen in Python, ohne textverändernde PowerShell-Weiterleitung und ohne Shell-Auswertung von Pfaden.

Bei Erfolg entstehen `data.tsv`, separate stderr-Logs und `run.json` mit Hashes, Befehlen und Exitcodes. Fehler/Timeout veröffentlichen keine vollständige Tabelle; `data.tsv.partial`, Logs und `run.json` mit Zustand `failed` dienen der Diagnose. Standardtimeout 300 s, mit `--timeout` veränderbar. Es wird kein Operator, Source-Modul oder Experiment gestartet.

## 6. Prüfstand

```bash
~/.venvs/eeg-mne/bin/python -m unittest analysis.test_bci2000 \
  analysis.test_event_annotations analysis.test_signal_selection \
  analysis.test_view_eeg_cli analysis.test_waterfall_cli
```

Tests verwenden synthetische Daten und unabhängig mit `struct` geschriebene native Testdateien: Kalibrierung/Einheiten, 32-Bit-States, Bitgrenzen, beschädigte Dateien, ungültige Attempts, ganze Blöcke/Sitzungen, Hashfehler, Überschreibschutz, beide Viewer und FIF. Binäre Prozessketten, Fehler und Timeout werden mit synthetischen Python-Prozessen geprüft; das ersetzt keinen Lauf der echten BCI2000-Tools.

Zusätzlich wurde der Reader auf der öffentlichen MNE-Referenzdatei geprüft: BCI2000 1.0, zwei EEG-Kanäle, 256 Hz, 9248 Samples, 24 States; SHA-256 `8efc7b5f700660a044086cb1449806ca408c2e6d32d9338c32e1bf31ce3ca9cb`. Sie liegt außerhalb Git im lokalen Cache. Herkunft: [MNE-Importbeispiel](https://mne.tools/stable/auto_examples/io/read_bci2k.html). Diese Untersuchung nutzt bewusst den eigenen Reader und umgeht die im [Recherchebericht](bci2000-integration-review-2026-11-12.md) dokumentierten Grenzen des damals vorhandenen MNE-Readers.

Offen: native BCI2000Analysis-/Filterausführung und GUI-Parameterübernahme auf einem installierten Mac-/Windows-Build, Windows-Python-Lauf sowie fachliche Bewertung mit geeigneten Studiendaten. Es wird keine neue Klassifikationsleistung oder Hardwarevalidierung behauptet.
