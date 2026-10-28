# Sitzungssteuerung: bestehende Verträge und Umsetzung von Protokoll 2.0

Stand: 28.10.2026. **Die CLI implementiert weiterhin `eeg-session-1.0`.** Das neue [Versuchsprotokoll](experiment-protocol.md) mit 168 Trials und 45:04 Minuten ist die Zielspezifikation, noch keine ausführbare Funktion. Die [Sitzungsanleitung](../gtec_Clib/terminal/SESSION_ANLEITUNG.md) beschreibt den aktuellen Befehl und dessen 112 Trials in 38:16 Minuten.

## 1. Bestehende Architektur und Aufnahme

| Komponente | Verantwortung |
|---|---|
| `gtec_Clib/terminal/session_plan.h` | Reproduzierbarer Plan, Phasen, Trials und Zeitmodell |
| `gtec_Clib/terminal/session.h` | Sitzungszustände, Anzeigen, Ereignisse und Dateizuordnung |
| `gtec_Clib/terminal/main.cpp` | CLI-Befehle, Laufreihenfolge und Befehlssperren |
| `gtec_Clib/terminal/cues.h`, `console.h` | Teilnehmerfenster und koordinierte Terminalanzeige |
| `gtec_Clib/terminal/recorder.h` | C-API-Rohdatenaufnahme und Ereignisprotokoll |
| `gtec_Clib/terminal/worker_process.h`, `acquisition/oscar_worker.py` | Exklusive Geräteübergabe und Python-Aufnahme mit OSCAR |
| `analysis/recording_files.py` | Gemeinsame Auswahl von Rohdaten und OSCAR-Ausgabe |
| `analysis/event_annotations.py` | Ereignisse und Attempt-Status für beide MNE-Viewer |

`start session` verwendet OSCAR; `start session raw` ausdrücklich den C-API-Recorder. Die Datenvarianten bleiben getrennt. Startfreigabe, Verzögerungszuordnung, Nachlauf und Fehlerverhalten sind in der [Aufnahmeanleitung](../acquisition/README.md) dokumentiert. Kein automatischer Rückfall auf Rohdaten.

## 2. Anforderungen an den neuen Plan

Aufgabenbeschreibungen, Kontingente und wissenschaftliche Grenzen werden ausschließlich im [Versuchsprotokoll](experiment-protocol.md) gepflegt. Der Generator muss daraus folgenden Vertrag erfüllen:

| Merkmal | Ziel für Protokoll 2.0 |
|---|---|
| Läufe | M: Ausführung; I: Imagery und mentale Vergleichsaufgaben; beide Reihenfolgen |
| Motorik | 4 Blöcke à 16 Trials = 64; 4 Bedingungen à 16 |
| Mentaler Lauf | 4 Blöcke à 26 Trials = 104; 4 unilaterale MI-Bedingungen à 16, 2 beidseitige à 12, 2 kognitive à 8 |
| Vorbereitung | 2 s Kreuz für alle Trials |
| Aufgabe | 4 s unilateral; 5 s für beidseitige MI und beide kognitiven Bedingungen |
| Erholung | 6/7/8 s mit exakt den Kontingenten aus dem Versuchsprotokoll |
| Blockdauer | M exakt 208 s; I exakt 348 s |
| Zusätzliche Pausen | 6 × 45 s zwischen Blöcken; 1 × 90 s zwischen Läufen |
| Baselines | Je 60 s vor und nach den Läufen |
| Gesamt | 168 geplante Trials; exakt 2704 s = 45:04 ohne Unterbrechungen |

Plan vollständig vorab erzeugen und mit Seed speichern. Klassen je Block ausgleichen, maximal zwei gleiche Bedingungen hintereinander auch über Blockgrenzen; Erholung und kognitive Inhalte unabhängig im Rahmen ihrer Kontingente zuweisen. Wiederholungen dürfen die restliche Liste nicht neu auslosen.

Protokoll 2.0 erhält eigene Labels aus dem Versuchsprotokoll. Alte Labels und Daten nicht umdeuten. Sprache, Bewegungsdefinition, kognitive Parameter und Software-/Protokollversion nachvollziehbar speichern. Die zusätzlichen Felder und ihre Schemaversion müssen bei der Implementierung konkret festgelegt werden; sie existieren derzeit nicht automatisch.

Die bisherige Syntax `session order imagery motorik kognitiv` verlangt drei Läufe und konfiguriert **keinen** neuen Zweilaufplan. Parser, Metadaten, Terminalzählung und Planvalidator müssen gemeinsam angepasst werden. Noch keine neue CLI-Syntax als ausführbar dokumentieren.

## 3. Anzeige und Start

Teilnehmer sehen Kreuz, zentralen Aufgabenhinweis, geplante Pausen mit Countdown und gegebenenfalls PAUSE. Der globale Countdown bleibt im Terminal. Im neuen Plan beginnt jede Aufgabe mit dem Aufgabenhinweis und endet mit dessen Wechsel zum Kreuz; keine zusätzliche STOPP-Anzeige. Für denselben Körperteil in ME und MI identische Hinweise verwenden, den Modus vor dem Block erklären. Keine seitlich versetzten Pfeile. Neue Texte und Wort-/Zahlenparameter müssen in Plan und Ereignissen eindeutig zugeordnet sein.

Bestehende Startregeln erhalten: keine parallele Aufnahme; ausgewählter Experimentordner; verbundenes, ausdrücklich gewähltes Gerät; alle acht EEG-Kanäle; lesbare Konfiguration mit Einheiten; eindeutige Dateinamen und schreibbare Ausgaben; verfügbares Teilnehmerfenster. `cue open` vorab auf den Teilnehmermonitor verschieben. Die Sitzung startet erst nach erfolgreicher Aufnahmevorbereitung. Ein Fehler vor Freigabe darf keine laufende Aufgabe hinterlassen.

## 4. Zustände, Zeit und Datenintegrität

```text
idle → preparing → running ↔ paused → completed
                    │         │
                    └─────────┴────→ aborted / failed
```

Diese bestehenden Verträge gelten auch für die neue Umsetzung:

- Kontinuierliches EEG einschließlich aller Erholungen und Pausen; Aufnahme und Aufgabenablauf sind getrennte Zustände.
- `session pause` zeigt PAUSE, hält Plan/Countdown an und lässt EEG weiterlaufen. `mark TEXT` protokolliert nur eine Beobachtung. Manuelle Cue-, Geräte-, Konfigurations- und Experimentwechsel bleiben während der Sitzung gesperrt.
- Unterbrechung in irgendeiner Trialphase invalidiert den gesamten Attempt. Resume wiederholt denselben geplanten Trial einschließlich Vorbereitung und Erholung mit unveränderter Aufgabe und Parametern; nur Attempt-ID und Restzeit ändern sich.
- Unterbrochene Baseline vollständig neu beginnen; unterbrochene geplante Pause mit Restdauer fortsetzen. Ungültige Daten und frühere Marker erhalten.
- Monotone Ablaufuhr mit festen Phasenzielen; UTC für externe Zuordnung. Globalen Countdown aus dem tatsächlich verbleibenden Plan berechnen, bei Wiederholung verlängern und während ungeplanter Pause einfrieren.
- Bestehende Verspätungsschwelle: mehr als 250 ms bei Phasenwechsel einschließlich Anzeige/Marker-Schreiben erzeugt protokollierte Unterbrechung und Invalidierung. Erst erfolgreiche Abschlussmarker erhöhen den Trialzähler. Die Schwelle ist auf Windows zu prüfen und belegt keine physikalische Onset-Genauigkeit.
- Fensterverlust pausiert; Aufnahmefehler beendet als `failed`. Nach Aufnahmefehler kein Resume in dieselbe Datei. `stop`/`close`/`quit`/EOF finalisieren als Abbruch; `close` trennt zusätzlich das Gerät.
- Vor möglicherweise blockierendem Aufnahme-Stopp PAUSE anzeigen. Keine garantierte sofortige Rückkehr eines blockierenden Vendor-Aufrufs behaupten. Exklusive Gerätezugriffe, koordinierte UI/Terminalausgabe und geordnete Thread-/Prozessbeendigung erhalten.
- `completed`, `aborted` und `failed` unterscheiden; Absturzstatus `running` oder `paused` gilt nicht als erfolgreicher Abschluss. Dateifehler sichtbar melden, niemals Quelldateien überschreiben.

Marker erfassen Softwarezeit und empfangene Samples. Ohne unabhängige Messung sind sie weder physikalische Bildschirm-Onsets noch eine validierte EEG–MEG-Synchronisation.

## 5. Dateien und bestehende Schemata

Pro Aufnahme gehören mindestens diese Dateien zusammen:

```text
session_….csv
session_….csv.events.csv
session_….csv.plan.csv
session_….csv.session.json
```

OSCAR ergänzt bereinigte CSV, Verarbeitungs-/Gerätemetadaten und Worker-Log gemäß Aufnahmeanleitung. Zuordnung über Teilnehmer-ID plus Sitzungs-ID und gemeinsamen Namensstamm. UTC-Ereigniszeiten und lokale Zeitzone dokumentieren; bei Namenskollision eindeutigen Zusatz vergeben. Session-Metadaten bereits am Start schreiben und bei Pause/Fortsetzung/Abschluss aktualisieren, möglichst durch atomaren Dateiersatz.

Die folgenden Schemata beschreiben **den bestehenden Stand**. Erweiterungen für 2.0 müssen abwärtskompatibel versioniert und zusammen mit Aufnahme, Import und Auswertung umgesetzt werden.

### EEG-CSV (bestehend)

Bestehendes Format beibehalten: `sample_index`, `nominal_time_s`, `host_read_utc_s` und aktivierte Kanalwerte. Einheiten und Konfiguration stehen zusätzlich in den Metadaten.

### Plan-CSV (bestehend)

Eine Zeile pro Phase, einschließlich Baselines und Pausen. Tatsächliche Spalten:

```text
session_id,phase_index,planned_start_s,run,block,trial,condition,phase,duration_s,start_number,subtract,protocol_version,seed
```

`planned_start_s` bezieht sich auf den ursprünglichen Plan ohne ungeplante Unterbrechungen. Vorbereitung, Aufgabe und Erholung stehen in getrennten Zeilen; `duration_s` enthält deren jeweilige Dauer. Bei Wiederholungen bleibt diese Datei unverändert, die tatsächlichen Attempts stehen in der Eventdatei.

### Session-JSON (bestehend)

Mindestens:

- Sitzungs-ID, pseudonyme Versuchsperson-ID und Dateizuordnung.
- Protokollversion und, soweit verfügbar, Software-/Git-Version.
- Zufallsseed und Reihenfolge der Hauptläufe.
- Start-/Endzeit in UTC, lokale Zeitzone.
- Abtastrate, Geräteseriennummer, API-/Firmwareversion soweit verfügbar.
- Vollständige aktive Kanalkonfiguration einschließlich Einheiten.
- Geplante Dauer, tatsächliche Dauer, ungeplante Pausendauer.
- Geplante Trials, gültig abgeschlossene Trials und Attempts/Wiederholungen.
- Abschlusszustand und Abbruch-/Fehlergrund.
- Samplezahl und Counter-Unterbrechungen, soweit verfügbar.

Metadaten bereits am Start mit Zustand `running` schreiben und bei relevanten Zustandswechseln aktualisieren. Dateiersatz möglichst atomar durchführen, damit ein Prozessabbruch nicht das einzige Metadatendokument zerstört. Nach Absturz darf `running` nicht fälschlich als erfolgreicher Abschluss interpretiert werden.

### Event-CSV (bestehend)

Die vorhandenen vier Spalten bleiben erhalten. Sitzungen schreiben dieses erweiterte CSV-Schema:

```text
host_utc_s,elapsed_s,samples_received,label,source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract
```

`label` enthält bei automatischen Ereignissen den Ereignistyp, bei manuellen Beobachtungen den eingegebenen Text. Die zusätzlichen Felder erhalten den Kontext. `planned_elapsed_s` beschreibt den Zielzeitpunkt der betreffenden Phase beziehungsweise ihrer Grenze im laufend angepassten Ablauf. Nach einer Unterbrechung kann er vom ursprünglichen `planned_start_s` der Plan-CSV abweichen. `elapsed_s` ist recorderbezogen, `actual_session_elapsed_s` sitzungsbezogen; die beiden Startzeitpunkte sind nicht exakt identisch.

`source` unterscheidet `automatic` und `manual`. Der Versuch ist über Lauf, Block, Trial und Attempt zuzuordnen; die Trialnummer beginnt pro Hauptlauf erneut. Ein ungültiger Attempt wird durch `trial_invalidated` dokumentiert. Beide MNE-Viewer übernehmen den Kontext in die Annotationsbeschreibung und leiten `status=invalid`, `completed` oder `incomplete` aus der vollständigen Ereignisdatei ab. Eine spätere Invalidierung gilt auch für vorherige Ereignisse desselben Attempts und hat Vorrang vor `trial_end`. Diese Angaben überstehen den FIF-Export. Es bleiben Punktannotationen; automatischer Ausschluss von EEG-Abschnitten ist damit nicht implementiert.

Automatische Ereignisse:

- `session_start`, `session_end`, `session_abort`, `session_error`
- `baseline_start`, `baseline_end`
- `run_start`, `run_end`
- `block_start`, `block_end`
- `trial_start`, `trial_end`
- `cue_onset`, `task_onset`, `task_offset`, `rest_end`
- `break_start`, `break_end`
- `pause_start`, `pause_end`
- `trial_invalidated`, `trial_repeat`
- Fensterschließung und relevante Timingabweichungen

Semantik ausschließlich für Protokoll 1.0: `trial_start` und READY beginnen gemeinsam. Nach zwei Sekunden erscheinen Zahlen; dort liegen `cue_onset` und angewiesener `task_onset`. Nach zehn Sekunden beginnt mit dem Kreuz die Erholung. Für die bisherigen Motorik-/Imagery-Trials erscheint die Aufgabeninstruktion nach der zweisekündigen Fixation. Im Zielprotokoll 2.0 beginnt jede Aufgabe nach zwei Sekunden Kreuz; die vier Vergleichsbedingungen dauern fünf Sekunden und benötigen neue Parameter.

Zeitpunkte beschreiben die angezeigte Anweisung, nicht den tatsächlich beobachteten Beginn einer Bewegung oder eines Gedankens.

Manuelle Beobachtungen:

```text
mark Husten
mark Elektrode geprüft
mark Versuchsperson fragt nach
```

Diese werden während einer Sitzung protokolliert, ohne Anzeige, Phase oder Countdown zu verändern. Das gilt auch für Labels wie `baseline`, die außerhalb der Sitzung eine Cue-Zuordnung haben. Organisatorische automatische Marker dürfen ebenfalls keinen beliebigen Text auf dem Teilnehmerbildschirm auslösen.

## 6. Umsetzungsreihenfolge und Abnahme

1. Plan-Generator, neue Labels, Laufreihenfolgen und 2704-s-Zeitmodell umsetzen; Validierung über viele Seeds und beide Reihenfolgen.
2. CLI, Teilnehmeranzeige, Terminalzählung und kognitive Parameter gemeinsam erweitern.
3. Metadatenschema versionieren; Seite, Körperteil, Modus, Sprache und Bewegungsversion erhalten. Trial/Attempt-Zuordnung nicht durch neue Labels verlieren.
4. Beide Viewer-Einstiegspunkte und ML-Labelauswahl prüfen. Alte Sitzungen bleiben Protokoll 1.0; neue und alte Bewegungen nicht stillschweigend poolen. Rohdaten und OSCAR-Variante ausdrücklich unterscheiden.
5. Hardwarefreie Regressionen für Zeitkontingente, alle Phasen, Pause/Repeat, Timingfehler, Fensterverlust, Aufnahme-/Dateifehler und vollständige Sitzung ausführen. Syntax und Anleitungen erst mit tatsächlich implementierter Bedienung angleichen.
6. Windows-Release-Build, Vendor-DLL, zwei Monitore, Umlaute/Zahlen, laufende Terminaleingabe, Software-/Display-Timing und einen vollständigen Echtzeitlauf mit Headset abnehmen. Signalqualität und wissenschaftliche Eignung separat bewerten.

Passende bestehende Prüfkommandos:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python gtec_Clib/terminal/test_oscar_session.py
python -m unittest analysis.test_event_annotations analysis.test_signal_selection analysis.test_view_eeg_cli analysis.test_waterfall_cli
```

Die bestehenden Sessiontests prüfen noch 112 Trials, 2296 Sekunden und sechs Laufreihenfolgen. Frühere erfolgreiche Mock-/Sanitizer-Prüfungen validieren das bisherige Protokoll, nicht den neuen Plan. Ein echter FIF-Speicher-/Ladetest prüft die Erhaltung der Annotationen, nicht deren automatische Verwendung als Ausschlussmaske.

Die Umsetzung von Protokoll 2.0 und ihre Tests stehen aus. Der aktuelle Windows-/Headset-Abnahmestand und die bisherigen OSCAR-Prüfungen sind in der Aufnahmeanleitung festgehalten.
