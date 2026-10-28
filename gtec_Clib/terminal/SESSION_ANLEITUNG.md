# Automatische Sitzung 2.0 mit `start session`

Stand: 28.10.2026. `start session` führt **`eeg-session-2.0` mit 168 Trials in 45:04 Minuten** aus. Softwareseitig hardwarefrei geprüft; Windows-Release-Build, Anzeige und vollständiger Echtzeitlauf mit Headset sind noch abzunehmen. Wissenschaftliche Bewegungsdefinitionen und Grenzen stehen im [Versuchsprotokoll](../../docs/experiment-protocol.md), Dateischemata in der [Sitzungsspezifikation](../../docs/session-automation-plan.md).

`start session` verwendet standardmäßig OSCAR über Python und erhält Rohdaten separat; `start session raw` wählt den C-API-Rohdatenrecorder. Einrichtung und Geräteübergabe: [OSCAR-Anleitung](../../acquisition/README.md). Beide Viewer bevorzugen bei bestätigten OSCAR-Sitzungen die bereinigte Variante; `--signal raw` wählt ausdrücklich Rohdaten.

## Vorbereitung und Start

Auf dem Windows-Messrechner den Release-Build gemäß [Terminal-README](README.md) **neu erstellen**; eine alte EXE führt weiterhin das alte Protokoll aus. Alle acht EEG-Kanäle aktivieren, Kontakte, Signalqualität und Einheiten prüfen. Teilnehmer-ID nach dem [ID-Schema](../../docs/participant-ids.md) vergeben, alle Aufgaben erklären und üben. Insbesondere Faustschließen/-öffnen, Vorfußheben bei aufliegender Ferse und kinästhetische Vorstellung unterscheiden.

Im Unicorn-Terminal:

```text
NewExp "EVM-P001"
scan paired
open DEINE_SERIENNUMMER
config
cue open
```

Für vorhandene Personen `GoToExp "EVM-P001"` verwenden. Teilnehmerfenster auf den vorgesehenen Monitor verschieben. Standardreihenfolge ist **Motorik → Imagery und mentale Vergleichsaufgaben**. Für die umgekehrte Reihenfolge vor dem Start:

```text
session order imagery motorik
```

Jeder der beiden Namen muss genau einmal vorkommen. Die Einstellung gilt bis zur nächsten Änderung oder bis Programmende. `kognitiv` ist kein eigener Lauf mehr; alte Dreilaufbefehle werden zurückgewiesen. Die konkrete Reihenfolge wird gespeichert. Der Versuchsperson **vor Start den ersten Modus nennen**, da die Anfangsbaseline nur ein Kreuz zeigt. Dann:

```text
start session
```

Der Start prüft Gerät, Kanäle und Dateien. Bei OSCAR wird das Gerät exklusiv an den Python-Prozess übergeben und auf erste gültige bereinigte Samples gewartet. Erst danach starten Baseline und Countdown. Vor einer weiteren OSCAR-Sitzung erneut `open DEINE_SERIENNUMMER` ausführen.

## Aufgaben und Zeitplan

| Abschnitt | Umfang | Dauer einschließlich Blockpausen |
|---|---|---:|
| Anfangsbaseline | Augen offen, Kreuz | 1:00 |
| Motorik | 4 Blöcke à 16 Trials: je 4 × linke/rechte Hand und linker/rechter Fuß | 16:07 |
| Laufwechsel | Pause mit Hinweis auf nächsten Modus | 1:30 |
| Imagery und mentale Aufgaben | 4 Blöcke à 26 Trials gemäß folgender Tabelle | 25:27 |
| Endbaseline | Augen offen, Kreuz | 1:00 |
| **Gesamt** | **168 Trials, sechs 45-s-Blockpausen und ein 90-s-Laufwechsel** | **45:04** |

Jeder mentale Block enthält:

| Aufgabe | Pro Block | Aufgabezeit |
|---|---:|---:|
| Linke/rechte Faust vorstellen | je 4 | 4 s |
| Linken/rechten Vorfuß vorstellen | je 4 | 4 s |
| Beide Hände / beide Füße gleichzeitig vorstellen | je 3 | 5 s |
| Wortgenerierung / einzelne Subtraktion | je 2 | 5 s |

Alle Trials: **2 s Kreuz → 4 oder 5 s Aufgabe → 6/7/8 s Erholung mit Kreuz**. Mit dem Wechsel zurück zum Kreuz endet die Aufgabe. Keine zusätzliche STOPP-Anzeige und keine separaten Rest-Trials. Trialreihenfolge und Erholung werden mit gespeichertem Seed und exakten Blockkontingenten erzeugt; motorische Blöcke dauern 3:28, mentale Blöcke 5:48 ohne Blockpause.

## Anzeigen und Anweisungen

Der globale Countdown und Trial-/Attempt-Zähler sind nur im Terminal sichtbar. Die Versuchsperson sieht:

| Phase / Aufgabe | Anzeige |
|---|---|
| Baseline, Vorbereitung und Erholung | `+` |
| Unilaterale Handaufgabe, ausgeführt oder vorgestellt | `HAND LINKS` / `HAND RECHTS` |
| Unilaterale Fußaufgabe, ausgeführt oder vorgestellt | `FUSS LINKS` / `FUSS RECHTS` |
| Beidseitige Imagery | `BEIDE HAENDE` / `BEIDE FUESSE` |
| Wortgenerierung | z. B. `WORT MIT B` |
| Einzelne Subtraktion | z. B. `83 − 27`, darunter `EINMAL RECHNEN` |
| Geplante Pause | `PAUSE`, Countdown und `DANACH: BEWEGEN` bzw. `VORSTELLEN / DENKAUFGABEN` |
| Ungeplante Unterbrechung | `PAUSE` ohne Countdown |
| Erfolgreicher Abschluss | `SITZUNG BEENDET` |

Gleiche unilaterale Hinweise gelten in Motorik und Imagery; der bekannte Laufmodus bestimmt, ob bewegt oder vorgestellt wird. Faust locker schließen/öffnen beziehungsweise Vorfuß anheben/absenken, ungefähr zwei Zyklen in 4 s. In Imagery dieselbe Bewegung aus eigener Körperperspektive vorstellen und körperlich ruhig bleiben. Kein kräftiges Pressen oder Anheben des ganzen Arms/Beins.

Wortgenerierung: still ein deutsches Wort zum angezeigten Buchstaben finden, ohne Lippenbewegung. Pro Sitzung acht verschiedene Buchstaben aus `BDFGHKLMNRST`. Subtraktion: einmal rechnen und danach das Ergebnis still prüfen; kein fortlaufendes Abziehen von 7. Acht unterschiedliche Zahlenpaare, Minuend 60–199 und Subtrahend 12–59, stets positives Ergebnis. Das sind feste Pilotparameter, keine individuelle Schwierigkeitskalibrierung. Antworten oder Rückfragen nur außerhalb der Aufgaben-/Erholungsfenster.

## Eingreifen und Beobachtungen protokollieren

```text
mark Husten
mark Elektrode geprüft
session pause
session resume
status
stop
```

Während einer automatischen Sitzung sind `mark`-Einträge reine Beobachtungen. Sie verändern weder Anzeige noch Trial noch Countdown. Auch `mark baseline` zeigt in diesem Modus kein neues Kreuz. Außerhalb der Sitzung bleibt die bisherige manuelle Cue-Zuordnung erhalten.

`session pause` hält den Ablauf an. Die EEG-Aufnahme läuft weiter, der globale Countdown friert ein und die Versuchsperson sieht `PAUSE` ohne Zeitangabe. Nach `session resume`:

- Wird ein unterbrochener Trial vollständig wiederholt, einschließlich Vorbereitung und Erholung. Aufgabe, Zahlenpaar, Wortbuchstabe und alle Phasendauern bleiben gleich.
- Beginnt eine unterbrochene Baseline erneut mit 60 s.
- Läuft eine unterbrochene geplante Pause mit ihrer Restdauer weiter.

Die bereits aufgezeichneten Abschnitte bleiben erhalten. Ungültige Trials und Wiederholungen erhalten Ereignisse und eigene Attempt-IDs. Die notwendige Wiederholungszeit wird zum verbleibenden Zeitplan hinzugefügt. Die Sitzung kann dadurch länger als 45:04 dauern.

`stop` zeigt zunächst `PAUSE` und beendet anschließend Sitzung und Aufnahme als abgebrochen. Damit bleibt bei einem blockierenden Geräteaufruf keine Aufgabenanweisung stehen. `close` trennt zusätzlich das Headset, `quit`/`exit` beenden das Programm. Eingabe-EOF führt ebenfalls zum kontrollierten Abbruch. Erzwungenes Prozessbeenden oder ein blockierender Vendor-Aufruf können sauberes Aufräumen verhindern.

Während einer Sitzung sind manuelle `cue`-Befehle, Konfigurationsänderungen, Experimentwechsel und parallele Erfassungsstarts gesperrt. `help`, `Where`, `ListExp` und `status` bleiben möglich.

## Fehlerbehandlung und Timing

Wenn das Teilnehmerfenster geschlossen wird, pausiert die Sitzung automatisch. `session resume` versucht das Fenster wieder zu öffnen; unterbrochene Trials beziehungsweise Baselines beginnen neu.

Ein Aufnahmefehler beendet die Sitzung als `failed`. Anschließend kann dieselbe Sitzung nicht fortgesetzt werden; ein neuer Start erhält neue Dateien. Die vorhandenen Daten bleiben erhalten.

Die Zeitsteuerung verwendet eine monotone Uhr und feste Phasenzielzeiten. Bei einer erkannten Verspätung von mehr als 250 ms beim Phasenwechsel wird pausiert, statt Phasen zu überspringen. Die Prüfung umfasst auch die Anzeige und das synchrone Schreiben der Übergangsmarker. Ein dadurch unterbrochener Trial wird invalidiert und beim Fortsetzen vollständig wiederholt; erst nach erfolgreichen Abschlussmarkern zählt er als abgeschlossen. Der Vorfall wird gespeichert und erfordert `session resume`. Die Schwelle ist eine technische Pilotvorgabe und muss unter Windows überprüft werden.

Marker enthalten Softwarezeitpunkte und den zuletzt empfangenen Samplezähler. Sie sind keine präzise Messung des physikalischen Bildschirm-Onsets und keine validierte EEG–MEG-Synchronisation.

## Gespeicherte Dateien

Im ausgewählten Ordner entstehen beispielsweise:

```text
session_20261019_143000.csv
session_20261019_143000.csv.events.csv
session_20261019_143000.csv.plan.csv
session_20261019_143000.csv.session.json
session_20261019_143000.csv.oscar.csv
session_20261019_143000.csv.processing.json
session_20261019_143000.csv.device.json
session_20261019_143000.csv.worker.log
```

Bei gleichen Zeitstempeln wird ein nummerierter Zusatz verwendet. Bestehende Dateien werden nicht überschrieben. Die pseudonyme Versuchsperson-ID wird aus dem ausgewählten Ordnernamen übernommen.

- EEG-CSV: bisheriges Format mit Sampleindex, nominaler Zeit, Empfangszeit und Kanälen.
- Event-CSV: bisherige vier Spalten plus Quelle, Lauf, Block, Trial, Attempt, Bedingung, Phase, Ziel-/Ist-Zeit, Grund und Rechenparameter. `source=manual` unterscheidet Beobachtungen von automatischen Ereignissen.
- Plan-CSV: jede vorgesehene Phase mit Dauer, Aufgabe, Startzahl, Seed und Protokollversion.
- Session-JSON: Gerätekonfiguration einschließlich Einheiten, Dateizuordnung, Zeitstempel, Reihenfolge und Abschlussstatus.

Das JSON wird bei Start, Pause, Fortsetzung und Abschluss aktualisiert. Bei einem Speicherfehler kann auch die Aktualisierung des Abschlussstatus scheitern; der Fehler wird im Terminal gemeldet. Zwischen diesen Zeitpunkten ist es kein Live-Status; dafür `status` verwenden. Bei einem Prozessabsturz kann der letzte Status `running` oder `paused` bleiben und darf nicht als erfolgreicher Abschluss gewertet werden.

Beide mitgelieferten MNE-Viewer übernehmen bei automatischen Ereignissen zusätzlich Lauf, Bedingung, Block, Trial, Attempt, Phase, Protokollversion, Modus, Körperteil, Seite, Bewegungsversion und gegebenenfalls Rechenparameter, Sprache und Wortbuchstabe in die Annotationsbeschreibung. Diese Informationen bleiben beim FIF-Export erhalten. `status=invalid` kennzeichnet einen invalidierten Versuch; `status=completed` bedeutet, dass ein `trial_end` ohne Invalidierung vorhanden ist, und `status=incomplete` kennzeichnet fehlenden Abschluss. Eine spätere Invalidierung gilt auch für die früheren Marker desselben Versuchs. Manuelle Labels und ältere vier-spaltige Eventdateien bleiben unverändert.

Die Annotationen sind weiterhin einzelne Zeitpunkte. Die Statusangabe bewertet weder Signalqualität noch schließt sie automatisch Daten aus der MNE-Auswertung aus; dazu müssen die betreffenden Trials ausdrücklich ausgewählt beziehungsweise ausgeschlossen werden.

## Tests und aktueller Prüfstand

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python -m unittest analysis.test_session_protocol analysis.test_event_annotations
```

Benötigt werden Python sowie Clang++ oder MSVC `cl`. Die Annotationstests benötigen zusätzlich MNE, NumPy und pandas und prüfen beide Viewer einschließlich eines echten FIF-Speicher-/Ladevorgangs. Die Tests erzeugen temporäre Dateien und verwenden ausschließlich die Mock-API. Der Sitzungstest kompiliert explizit mit `UNICORN_SESSION_TEST`; nur dieser Build enthält eine simulierte Teilnehmeranzeige und eine beschleunigbare Uhr. Der normale CMake-Build enthält diese Funktionen nicht.

Geprüft werden Planregeln über 250 Seeds, beide Laufreihenfolgen, Phasengrenzen, Pausen, Wiederholungen, vollständiger beschleunigter Durchlauf, automatische/manuelle Marker, Dateizuordnung, Fensterverlust, Aufnahmefehler, fehlende Kanäle, erneuter Start, zu große Timingabweichungen, Metadaten-Schreibfehler und EOF. Zusätzliche Regressionstests verzögern gezielt Anzeige und Marker-Schreiben während eines Phasenwechsels und prüfen die PAUSE-Anzeige, während der Aufnahme-Stopp noch blockiert.

**Windows-Fenster, interaktive Terminaldarstellung, Vendor-DLL und ein vollständiger Echtzeitlauf mit Headset müssen auf dem Messrechner geprüft werden.** Die hardwarefreien Tests bestätigen diese Punkte nicht. Vor Durchführung mit Versuchspersonen diese Prüfung und einen Pilotlauf abschließen.

## Bestehende Aufnahmen aus Protokoll 1.0

Alte Aufnahmen bleiben unverändert: 112 Trials in 38:16 Minuten, je 20 beidseitige Arm-/Beinbewegungen und Blinzeln, je 20 Arm-/Beinvorstellungen sowie zwölf zehnsekündige Trials mit fortlaufendem Abziehen von 7. Die alte Version wird nicht mehr durch `start session` erzeugt und nicht auf neue Labels umgedeutet.

Für ältere Teilnehmerbögen bedeuten die Reihenfolgegruppen: A = Motorik/Imagery/Kognitiv, B = Motorik/Kognitiv/Imagery, C = Imagery/Motorik/Kognitiv, D = Imagery/Kognitiv/Motorik, E = Kognitiv/Motorik/Imagery, F = Kognitiv/Imagery/Motorik. Neue Sitzungen dokumentieren stattdessen die konkrete Zweilaufreihenfolge. Alte Bewegungen und Ergebnisse sind kein direkter Nachweis für die neuen Bedingungen.
