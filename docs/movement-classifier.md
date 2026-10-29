# Eigener Bewegungsklassifikator: Training, Auswertung und Replay

Stand: 29.10.2026. Implementierte **explorative Offline-Baseline** für ausgeführte Bewegungen einer Person. Getestet mit synthetischen EEG-Sitzungen. Neue Sitzungen, unabhängige Ruheaufnahmen, Hardwarelatenz und Motorsteuerung sind noch nicht validiert. Es werden keine Motorbefehle an Hardware gesendet.

## Klassen und geeignete Daten

`python -m analysis.movement_classifier` verwendet die vorhandenen automatischen Sitzungsdateien von `eeg-session-2.0`:

| Option | Klassen |
|---|---|
| `--task hands` (Standard) | `rest`, `me_hand_left`, `me_hand_right` |
| `--task five` | zusätzlich `me_foot_left`, `me_foot_right` |

Imagery, kognitive Aufgaben und alte Arm-/Beinlabels werden nicht als ausgeführte Hand-/Fußbewegungen umgedeutet. Der Aufnahmeablauf und die beiden Viewer bleiben unverändert. Ein neues fokussiertes Aufnahmeprotokoll mit eigenen Ruhe-Trials ist damit noch nicht implementiert.

**Ruhe ist vorläufig abgeleitet:** Zu jedem ausgewählten vollständigen Motorik-Trial kommt ein gleich langes Fenster aus dessen später Erholung. Das sind keine separat erhobenen Ruhe-Trials. Füße werden im Handmodell weder als Hand noch als Ruhe verwendet. Allgemeine Alltagssituationen, andere Bewegungen und Blinzler bilden keine trainierte Unknown-Klasse.

Benötigt werden EEG-CSV, `.events.csv` und `.session.json`; Plan und OSCAR-Verarbeitungsdatei werden, soweit vorhanden, ebenfalls gehasht. Alle acht aktivierten EEG-Kanäle in aufgezeichneter Reihenfolge und bestätigten µV sowie 250 Hz sind Pflicht. `sample_index` und `nominal_time_s` müssen konsistent sein. Validation Indicator, nichtendliche Werte und Counter-Sprünge werden über die komplette Eingabehistorie geprüft. Ein ungültiges Aufgaben- **oder** Erholungsfenster schließt das ganze Paar aus. Invalidierte und unvollständige Attempts bleiben ausgeschlossen; Originaldateien werden nicht verändert.

Die reale Elektrodenplatzierung, Kontaktqualität und korrekte Ausführung werden dadurch nicht bestätigt. Sitzungszustand und Bewegungsversion erscheinen in der Herkunft. Auch aus abgebrochenen Sitzungen können vollständig abgeschlossene, nicht invalidierte Trials verwendet werden; dies muss anhand des Berichts fachlich geprüft werden.

## Verarbeitung und Modell

- Ein Aufgabenfenster von 0,5 bis 3,5 s nach Cue; die ersten 0,5 s dienen zusätzlich als Filtervorlauf.
- Erholungsfenster: die letzten 3,5 bis 0,5 s vor dem Erholungsende; zusätzlich 0,5 s Vorlauf vollständig innerhalb der Erholung. Frühe Erholung und Baseline werden nicht automatisch als Ruhe übernommen.
- Insgesamt jeweils **875 vergangene Samples = 3,5 s**: erstes Sample abziehen, kausaler Butterworth-Bandpass 4. Ordnung bei 7–35 Hz mit `sosfilt`, erste 125 Samples verwerfen. Filterzustand wird für jedes Fenster neu initialisiert. Keine zusätzliche Referenzierung, Amplitudenverwerfung oder zukünftige Samples.
- Logarithmische Welch-Bandpower bei 8–13 und 13–30 Hz, `nperseg=500`; 16 Merkmale über acht Kanäle. Die ersten acht gehören zum Mu-, die nächsten acht zum Beta-Band.
- Trainingsinterne Standardisierung und logistische Regression mit `C=1`, balancierten Klassengewichten, `max_iter=2000`, Seed 0. Kein Hyperparametervergleich und keine Modellauswahl anhand der Testwerte.

Die Filterparameter und der Vorlauf sind feste Entwicklungsentscheidungen, kein belegtes Optimum. Große Artefakte können trotz gültigem Validation Indicator bestehen bleiben. Die vorhandene Offline-Baseline `analysis.ml_feasibility` verwendet eine andere Filterung und liefert daher keine unmittelbar austauschbaren Werte.

## Training

Die vorhandene Umgebung `~/.venvs/eeg-ml` enthält die benötigten gepinnten Abhängigkeiten aus `analysis/requirements-ml.lock.txt`. Keine neuen Pakete oder Modellgewichte erforderlich. Befehle aus dem Repository-Stamm ausführen; auf Windows den entsprechenden Python-Pfad verwenden.

Modelle und größere Ausgaben möglichst außerhalb des synchronisierten Checkouts ablegen. Beispiel auf macOS nach Anlegen des Ausgabe-Elternordners:

```bash
mkdir -p "$HOME/.local/share/EEGvsMEG/movement"

~/.venvs/eeg-ml/bin/python -m analysis.movement_classifier train \
  PFAD_ZUR_GEEIGNETEN_SITZUNG.csv \
  --task hands --signal raw \
  --output-dir "$HOME/.local/share/EEGvsMEG/movement/hands-v1"
```

Nur eine Sitzung: Leave-one-block-out, mindestens zwei vollständige Blöcke. Mehrere Sitzungen derselben Person als weitere Positionsargumente: Leave-one-session-out. Jede Trainings- und Testpartition muss alle Klassen enthalten. Aufgabe und zugehörige Erholung bleiben zusammen. Doppelte Sitzungskennungen und identische EEG-Dateien werden zurückgewiesen; mehrere Personen oder verschiedene Bewegungsversionen werden nicht gepoolt.

Ausgaben im **neuen**, zuvor nicht vorhandenen Ordner:

- `report.md`: lesbare Metriken, Konfusionsmatrix, Fold-Ergebnisse und Grenzen.
- `report.json`: zusätzlich vollständige Herkunft, Datei-Hashes, Ausschlüsse, Verarbeitung, Versionen und Klassenzahlen.
- `predictions.csv`: ausschließlich zurückgehaltene Testvorhersagen mit Sitzung, Block, Trial, Attempt, Samplegrenzen und Labelherkunft.
- `movement-model.npz`: anschließend auf allen Eingabefenstern trainiertes Modell, numerische Parameter und JSON-Vertrag; Laden mit `allow_pickle=False`. Modellparameter werden durch `.gitignore` vor versehentlichem Commit geschützt.

Die Ruheklasse hat ein Fenster pro Bewegungs-Trial und damit mehr Beispiele als jede einzelne Bewegungsklasse. Klassengewichte gleichen dies beim Training aus; **Balanced Accuracy**, Macro-F1 und klassenweise Precision/Recall ergänzen die normale Accuracy. Die vielen EEG-Samples sind keine unabhängigen Trainingsbeispiele.

### Bekannte Qualitätsprobleme

Mit `--after-marker "EXAKTES LABEL" --settle-seconds 10` werden ganze Trials ausgeschlossen, wenn ihr Cue vor dem eindeutigen manuellen Marker plus Wartezeit liegt. Der Marker muss in jeder übergebenen Sitzung existieren; Sampleindizes bleiben unverändert. Die Wartezeit ist keine bestätigte Einschwingzeit.

**P003 vom 29.10.2026 reicht nach `ground placed` für dieses Training nicht aus:** Es bleiben zu wenige Motorikdaten und beim Handseitenvergleich fehlt eine Klasse. Das Programm lehnt die Auswertung ab. Den fehlerhaften Anfangsabschnitt nicht einschließen, um einen Wert zu erhalten. Siehe [P003-Bericht](ml-feasibility-P003-2026-10-29.md).

`--signal raw` ist bewusst der Standard. `--signal oscar` verlangt bestätigte, vollständig verarbeitete OSCAR-Dateien und verwendet deren ausgerichtete Rohsample-Zeitachse. Training und Anwendung müssen dieselbe Signalvariante verwenden. Ein kausaler Klassifikator allein bestätigt weder die Kausalität einer vorgelagerten Bereinigung noch die gesamte Geräte-/OSCAR-Verzögerung.

## Unabhängiger Test ohne Nachtraining

```bash
~/.venvs/eeg-ml/bin/python -m analysis.movement_classifier evaluate \
  "$HOME/.local/share/EEGvsMEG/movement/hands-v1/movement-model.npz" \
  PFAD_ZUR_NEUEN_SITZUNG.csv --signal raw \
  --output-dir "$HOME/.local/share/EEGvsMEG/movement/hands-test-tag3"
```

Die neue Sitzung muss dieselbe Person, Signalvariante, Bewegungsversion und alle Modellklassen enthalten. Die Trainingssitzung beziehungsweise eine identische EEG-Kopie wird als unabhängiger Test zurückgewiesen. Skalierung und Modell bleiben unverändert; es wird kein weiteres Modell exportiert. Bei OSCAR zusätzlich `--signal oscar` verwenden.

Ein neuer Tag ist die relevante nächste Prüfung; blockweise Kreuzvalidierung innerhalb einer Sitzung belegt noch keine Übertragbarkeit über Tage. Parameteränderungen nach Betrachtung eines Tests erfordern neue Bestätigungsdaten.

## Diagnose-Replay als Vorbereitung für Echtzeit

```bash
~/.venvs/eeg-ml/bin/python -m analysis.movement_classifier replay \
  "$HOME/.local/share/EEGvsMEG/movement/hands-v1/movement-model.npz" \
  PFAD_ZUR_SITZUNG.csv \
  --step-samples 50 --threshold 0.8 --confirmations 3 \
  --output "$HOME/.local/share/EEGvsMEG/movement/replay-tag3.csv"
```

Der Replay verarbeitet alle 50 Samples = 200 ms ausschließlich die jeweils letzten 875 Samples mit derselben Merkmalsfunktion und denselben exportierten Modellparametern. Er läuft so schnell wie möglich über eine Datei; er simuliert keinen gemessenen Hardware-Datenstrom. Die CSV enthält Endsample, Datenzeit, Vorhersage, unkalibrierten Modellscore, bestätigten Zustand und ein optionales `event`. Modell-/Datenhash, Schwelle, Bestätigungszahl und `seen_in_training` werden mitgeschrieben. Ein Zeitstempel ist keine gemessene Rechen- oder Bewegungserkennungslatenz.

Die Ereignislogik beginnt gesperrt. Drei hinreichend sichere Ruhevorhersagen schalten sie frei; anschließend erzeugen drei gleiche Bewegungsvorhersagen ein einziges Ereignis. Weitere Bewegungsvorhersagen erzeugen bis zur erneuten bestätigten Ruhe kein Ereignis. Unsicherheit oder ungültige Samples sperren die Logik erneut. Nach ungültigen Samples ist zunächst eine vollständige saubere Historie nötig. Schwelle und Bestätigungszahl sind unvalidierte Entwicklungswerte; überlappende Vorhersagen sind nicht unabhängig.

Der Replay kann auch auf Trainingsdaten ausgeführt werden und kennzeichnet dies ausdrücklich. Bei bekannten Trainingssitzungen wird der gespeicherte Qualitäts-Cutoff übernommen. Für neue Sitzungen sind Kontaktprobleme und andere Ausschlüsse vor Interpretation gesondert zu prüfen; der Replay übernimmt keine manuell nachträglich gesetzte Ausschlussregel aus einem separaten Auswertungsbericht.

**Die Ereignisse sind Diagnoseausgaben, keine freigegebenen Motorbefehle.** Diese Version misst keine kontinuierlichen Fehlalarme pro Minute oder Ereignis-Latenzen: Dafür fehlen unabhängig markierte Ruhe-/Störsituationen und gemessene Bewegungsbeginne. Sie erkennt zunächst mehrsekündige Bewegungsphasen; die zuverlässige Erkennung einzelner kurzer Gesten ist separat zu untersuchen. Für echte Hardware fehlen noch der Live-Adapter, unabhängige Stopp-/Timeout-Logik und Hardwaretests.

## Regressionstests

```bash
~/.venvs/eeg-ml/bin/python -m unittest analysis.test_movement_classifier
```

Synthetische Daten prüfen Klassen inklusive Füßen, Invalidierung, vollständige Paare, Filtervorlauf, Samples/Einheiten, Qualitätsmarker, Block-/Sitzungstrennung, Modellpersistenz, unabhängige Auswertung, kausalen Replay und Ereignissperre. Das ersetzt keine fachliche Validierung mit echten EEG-Daten und keinen Windows-/Headset-Lauf.
