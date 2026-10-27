# Automatische Sitzung mit `start session`

Die CLI kann das vollständige Pilotprotokoll automatisch durchführen: Anfangsbaseline, Motorik, Imagery, Kopfrechnen, Endbaseline. Ohne Unterbrechungen beträgt der Zeitplan **38:16 Minuten** einschließlich Erholung, acht Blockpausen und zwei Experimentpausen.

## Vorbereitung und Start

Windows-Build wie in [README.md](README.md) neu konfigurieren und erstellen. Für die echte Teilnehmeranzeige und das Unicorn-Headset ist 64-Bit-Windows erforderlich. Die acht EEG-Kanäle `EEG 1` bis `EEG 8` müssen aktiviert sein. Signalqualität, Elektrodenkontakte und Einheiten vor der Sitzung prüfen; das Programm bewertet diese nicht automatisch.

Für neue Teilnehmende wird eine dauerhafte ID wie `EVM-P001` verwendet. Dieselbe Person behält sie über weitere Termine und Laptops. Vergabe, Testordner und Bestandsdaten sind im [Teilnehmer-ID-Schema](../../docs/participant-ids.md) beschrieben.

Im Unicorn-Terminal:

```text
NewExp "EVM-P001"
scan paired
open DEINE_SERIENNUMMER
config
cue open
```

Bei zwei Monitoren das Teilnehmerfenster auf den gewünschten Bildschirm verschieben. Die Versuchsperson vorher einweisen und alle Aufgaben üben. Dann:

```text
start session
```

Der Befehl verwendet das verbundene Gerät und den ausgewählten Experimentordner. Er erstellt den vollständigen Plan, öffnet das Teilnehmerfenster, schaltet es auf dem aktuellen Monitor in den Vollbildmodus und beginnt die echte Aufnahme. Der Countdown startet zusammen mit der Anfangsbaseline. Keine zusätzliche Eingabe von `record` oder Aufgabenmarkern ist erforderlich.

Optional vor Sitzungsbeginn die Reihenfolge ändern:

```text
session order imagery motorik kognitiv
```

Jeder der drei Namen muss genau einmal vorkommen. Die Einstellung gilt bis zur nächsten Änderung oder bis zum Programmende; Standard beim Programmstart ist Motorik → Imagery → Kognitiv. Die konkrete Reihenfolge wird mit der Sitzung gespeichert. Die beiden Baselines bleiben an den Enden.

## Anzeigen

Im interaktiven Windows-Terminal werden Statuszeilen alle 100 ms aktualisiert. Die Eingabezeile bleibt für Befehle und Beobachtungen verfügbar. Das Terminal zeigt:

- Sitzungs-ID, Zustand, geplante Restzeit und tatsächlich verstrichene Zeit.
- Experiment, konkrete Anweisung und Trialnummer innerhalb des Experiments.
- Block, aktuelle Phase und deren Restzeit.
- Datei, abgeschlossene Trials, Wiederholungen und gegebenenfalls Fehlergrund.

Der Gesamt-Countdown ist nur für den Versuchsführer sichtbar. Für eine übersichtliche Anzeige ein ausreichend breites Terminal verwenden. Bei umgeleiteter Ein-/Ausgabe erfolgt keine fortlaufende Darstellung; `status` liefert einen Textstatus.

| Phase | Teilnehmeranzeige |
|---|---|
| Anfangs- und Endbaseline, je 60 s | `+` |
| Motorik-/Imagery-Vorbereitung, 2 s | `+` |
| Motorik-Aufgabe, 4 s | `ARME HEBEN`, `BEINE HEBEN`, `BLINZELN` |
| Imagery-Aufgabe, 4 s | `ARME VORSTELLEN`, `BEINE VORSTELLEN` |
| Motorik-/Imagery-Erholung, 6–8 s | `+` |
| Kognitive Vorbereitung, 2 s | `READY` |
| Kognitive Aufgabe, 10 s | beispielsweise `347 − 7` mit `FORTLAUFEND` |
| Kognitive Erholung, 15–17 s | `+` |
| Blockpause | `PAUSE` und Countdown ab `0:45` |
| Experimentwechsel | `PAUSE` und Countdown ab `1:30` |

Beim Wechsel auf das Kreuz Aufgabe sofort beenden. Es gibt kein zusätzliches STOPP. Beim Kopfrechnen bleiben die Zahlen während der gesamten Aufgabe sichtbar. Die Startzahlen werden ohne Wiederholung aus 300–899 gezogen; der Schritt ist 7. Diese pragmatische Pilotwahl ist keine individuell angepasste Schwierigkeitskalibrierung.

Motorik: vier Blöcke mit je 15 Trials, je fünf pro Aufgabe. Imagery: vier Blöcke mit je zehn Trials, je fünf pro Aufgabe. Kognitiv: drei Blöcke mit je vier Trials. Reihenfolgen und Erholung werden mit gespeichertem Zufallsseed ausgelost; ein konkreter Plan steht neben jeder Aufnahme.

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

- Wird ein unterbrochener Trial vollständig wiederholt, einschließlich Vorbereitung und Erholung. Aufgabe und Rechenzahl bleiben gleich.
- Beginnt eine unterbrochene Baseline erneut mit 60 s.
- Läuft eine unterbrochene geplante Pause mit ihrer Restdauer weiter.

Die bereits aufgezeichneten Abschnitte bleiben erhalten. Ungültige Trials und Wiederholungen erhalten Ereignisse und eigene Attempt-IDs. Die notwendige Wiederholungszeit wird zum verbleibenden Zeitplan hinzugefügt. Die Sitzung kann dadurch länger als 38:16 dauern.

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
```

Bei gleichen Zeitstempeln wird ein nummerierter Zusatz verwendet. Bestehende Dateien werden nicht überschrieben. Die pseudonyme Versuchsperson-ID wird aus dem ausgewählten Ordnernamen übernommen.

- EEG-CSV: bisheriges Format mit Sampleindex, nominaler Zeit, Empfangszeit und Kanälen.
- Event-CSV: bisherige vier Spalten plus Quelle, Lauf, Block, Trial, Attempt, Bedingung, Phase, Ziel-/Ist-Zeit, Grund und Rechenparameter. `source=manual` unterscheidet Beobachtungen von automatischen Ereignissen.
- Plan-CSV: jede vorgesehene Phase mit Dauer, Aufgabe, Startzahl, Seed und Protokollversion.
- Session-JSON: Gerätekonfiguration einschließlich Einheiten, Dateizuordnung, Zeitstempel, Reihenfolge und Abschlussstatus.

Das JSON wird bei Start, Pause, Fortsetzung und Abschluss aktualisiert. Bei einem Speicherfehler kann auch die Aktualisierung des Abschlussstatus scheitern; der Fehler wird im Terminal gemeldet. Zwischen diesen Zeitpunkten ist es kein Live-Status; dafür `status` verwenden. Bei einem Prozessabsturz kann der letzte Status `running` oder `paused` bleiben und darf nicht als erfolgreicher Abschluss gewertet werden.

Beide mitgelieferten MNE-Viewer übernehmen bei automatischen Ereignissen zusätzlich Lauf, Bedingung, Block, Trial, Attempt, Phase und gegebenenfalls Rechenparameter in die Annotationsbeschreibung. Diese Informationen bleiben beim FIF-Export erhalten. `status=invalid` kennzeichnet einen invalidierten Versuch; `status=completed` bedeutet, dass ein `trial_end` ohne Invalidierung vorhanden ist, und `status=incomplete` kennzeichnet fehlenden Abschluss. Eine spätere Invalidierung gilt auch für die früheren Marker desselben Versuchs. Manuelle Labels und ältere vier-spaltige Eventdateien bleiben unverändert.

Die Annotationen sind weiterhin einzelne Zeitpunkte. Die Statusangabe bewertet weder Signalqualität noch schließt sie automatisch Daten aus der MNE-Auswertung aus; dazu müssen die betreffenden Trials ausdrücklich ausgewählt beziehungsweise ausgeschlossen werden.

## Tests und aktueller Prüfstand

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python -m unittest analysis.test_event_annotations
```

Benötigt werden Python sowie Clang++ oder MSVC `cl`. Die Annotationstests benötigen zusätzlich MNE, NumPy und pandas und prüfen beide Viewer einschließlich eines echten FIF-Speicher-/Ladevorgangs. Die Tests erzeugen temporäre Dateien und verwenden ausschließlich die Mock-API. Der Sitzungstest kompiliert explizit mit `UNICORN_SESSION_TEST`; nur dieser Build enthält eine simulierte Teilnehmeranzeige und eine beschleunigbare Uhr. Der normale CMake-Build enthält diese Funktionen nicht.

Geprüft werden Planregeln über 250 Seeds, alle sechs Laufreihenfolgen, Phasengrenzen, Pausen, Wiederholungen, vollständiger beschleunigter Durchlauf, automatische/manuelle Marker, Dateizuordnung, Fensterverlust, Aufnahmefehler, fehlende Kanäle, erneuter Start, zu große Timingabweichungen, Metadaten-Schreibfehler und EOF. Zusätzliche Regressionstests verzögern gezielt Anzeige und Marker-Schreiben während eines Phasenwechsels und prüfen die PAUSE-Anzeige, während der Aufnahme-Stopp noch blockiert.

**Windows-Fenster, interaktive Terminaldarstellung, Vendor-DLL und ein vollständiger Echtzeitlauf mit Headset müssen auf dem Messrechner geprüft werden.** Die hardwarefreien Tests bestätigen diese Punkte nicht. Vor Durchführung mit Versuchspersonen diese Prüfung und einen Pilotlauf abschließen.
