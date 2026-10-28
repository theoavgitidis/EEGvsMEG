# Sitzungssteuerung: Protokoll 2.0 und Dateiverträge

Stand: 28.10.2026. **Die CLI implementiert `eeg-session-2.0`: 168 Trials in 45:04 Minuten.** Plan, Zustände, Marker und Recorder sind hardwarefrei geprüft. Windows-Release-Build, Anzeige und vollständiger Echtzeitlauf mit Headset stehen aus. Wissenschaftliche Definitionen: [Versuchsprotokoll](experiment-protocol.md); Bedienung: [Sitzungsanleitung](../gtec_Clib/terminal/SESSION_ANLEITUNG.md).

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

## 2. Implementierter Plan

Aufgabenbeschreibungen, Kontingente und wissenschaftliche Grenzen werden ausschließlich im [Versuchsprotokoll](experiment-protocol.md) gepflegt. Der Generator muss folgenden Vertrag erfüllen; `Plan::validate()` prüft vor dem Start Gesamt-/Blockzeiten, Klassenkontingente und Phasenverknüpfungen:

| Merkmal | Protokoll 2.0 |
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

Protokoll 2.0 verwendet die eigenen Labels aus dem Versuchsprotokoll. Session-JSON meldet `schema_version=2`, `protocol_version=eeg-session-2.0`, `movement_version=fist-ankle-dorsiflexion-v1`, `task_language=de` und `planned_trials=168`. Sprache und Bewegungsdefinition beschreiben den Instruktionsstandard; die tatsächlich geübte Amplitude wird im Teilnehmerbogen dokumentiert. Alte Labels und Daten bleiben unverändert.

Aktuelle Syntax: `session order motorik imagery` oder `session order imagery motorik`. Standard ist Motorik zuerst. Alte Dreilaufbefehle, doppelte oder fehlende Läufe werden zurückgewiesen, ohne die konfigurierte Reihenfolge zu verändern.

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

Die folgenden Schemata beschreiben den implementierten Stand. Die bisherigen Spalten bleiben an ihren Positionen; Version 2 ergänzt Spalten am Ende. Die gemeinsamen Python-Importer unterstützen zusätzlich alte Dateien ohne diese Felder. Widersprüchliche Protokollversionen und gemischte alte/neue Aufgabenlabels werden in der ML-Auswertung zurückgewiesen.

### EEG-CSV (Version 2)

Bestehendes Format beibehalten: `sample_index`, `nominal_time_s`, `host_read_utc_s` und aktivierte Kanalwerte. Einheiten und Konfiguration stehen zusätzlich in den Metadaten.

### Plan-CSV (Version 2)

Eine Zeile pro Phase, einschließlich Baselines und Pausen. Tatsächliche Spalten:

```text
session_id,phase_index,planned_start_s,run,block,trial,condition,phase,duration_s,start_number,subtract,protocol_version,seed,mode,body_part,side,movement_version,language,word_letter,next_run
```

`planned_start_s` bezieht sich auf den ursprünglichen Plan ohne ungeplante Unterbrechungen. Vorbereitung, Aufgabe und Erholung stehen in getrennten Zeilen; `duration_s` enthält deren jeweilige Dauer. Bei Wiederholungen bleibt diese Datei unverändert, die tatsächlichen Attempts stehen in der Eventdatei.

### Session-JSON (Version 2)

Mindestens:

- Sitzungs-ID, pseudonyme Versuchsperson-ID und Dateizuordnung.
- Protokollversion, Schemaversion, Bewegungsversion, Aufgabensprache und feste Auswahlregeln für Zahlen/Buchstaben.
- Zufallsseed und Reihenfolge der Hauptläufe.
- Start-/Endzeit in UTC, lokale Zeitzone.
- Abtastrate, Geräteseriennummer, API-/Firmwareversion soweit verfügbar.
- Vollständige aktive Kanalkonfiguration einschließlich Einheiten.
- Geplante Trialzahl und Dauer, tatsächliche Dauer, ungeplante Pausendauer.
- Geplante Trials, gültig abgeschlossene Trials und Attempts/Wiederholungen.
- Abschlusszustand und Abbruch-/Fehlergrund.
- Samplezahl und Counter-Unterbrechungen, soweit verfügbar.

Metadaten bereits am Start mit Zustand `running` schreiben und bei relevanten Zustandswechseln aktualisieren. Dateiersatz möglichst atomar durchführen, damit ein Prozessabbruch nicht das einzige Metadatendokument zerstört. Nach Absturz darf `running` nicht fälschlich als erfolgreicher Abschluss interpretiert werden.

### Event-CSV (Version 2)

Die vorhandenen vier Spalten bleiben erhalten. Sitzungen schreiben dieses erweiterte CSV-Schema:

```text
host_utc_s,elapsed_s,samples_received,label,source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract,protocol_version,mode,body_part,side,movement_version,language,word_letter
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

In Protokoll 2.0 beginnt jeder Trial mit zwei Sekunden Kreuz. Danach liegen `cue_onset` und angewiesener `task_onset`; nach vier beziehungsweise fünf Sekunden markiert `task_offset` den Wechsel zurück zum Kreuz. `start_number` und `subtract` enthalten das tatsächliche Zahlenpaar, `word_letter` den tatsächlichen Buchstaben. Wiederholte Attempts behalten dieselben Parameter. `next_run` benennt in Plan-Pausen den danach anzuzeigenden Modus.

`mode` ist `motor_execution`, `motor_imagery` oder `cognitive`; `body_part` ist `hand` oder `foot`, `side` ist `left`, `right` oder `bilateral`. Für nicht zutreffende Phasen bleiben Felder leer. Kognitive Trials tragen `language=de`. Baselines und Pausen erhalten weiterhin die Protokollversion. Alte 1.0-Dateien behalten ihren ursprünglichen READY-/Seriensubtraktionsablauf und werden nicht umetikettiert.

Zeitpunkte beschreiben die angezeigte Anweisung, nicht den tatsächlich beobachteten Beginn einer Bewegung oder eines Gedankens.

Manuelle Beobachtungen:

```text
mark Husten
mark Elektrode geprüft
mark Versuchsperson fragt nach
```

Diese werden während einer Sitzung protokolliert, ohne Anzeige, Phase oder Countdown zu verändern. Das gilt auch für Labels wie `baseline`, die außerhalb der Sitzung eine Cue-Zuordnung haben. Organisatorische automatische Marker dürfen ebenfalls keinen beliebigen Text auf dem Teilnehmerbildschirm auslösen.

## 6. Import und Auswertung

Beide Viewer-Einstiegspunkte erhalten sämtliche neuen Kontextfelder in Annotationen einschließlich FIF-Export und zeigen kompakte, unterscheidbare Aufgabenlabels. Punktannotationen allein schließen keine EEG-Abschnitte automatisch aus. ML-Importer schließen invalidierte und unvollständige Attempts aus, prüfen eindeutige Phasenmarker und verlangen vollständig innerhalb der Aufgabe liegende 3-s-Fenster (0,5–3,5 s nach Cue). Nur alte Kognitiv-Trials erzeugen zusätzlich ein zugehöriges spätes Restfenster.

`analysis/session_conditions.py` definiert die getrennten 2.0-Kontraste `ME_HandSide`, `ME_FootSide`, `ME_FourClass`, `MI_HandSide`, `MI_FootSide`, `MI_FourClass`, `MI_Bilateral` und `Cognitive`. Block-/Trial-IDs bleiben beim Auswählen erhalten. Ein gemischter mentaler Achtklassenvergleich wird nicht als Standard ausgewertet. Alte `Motorik`-/`Imagery`-/`Kognitiv`-Modelle gelten weiterhin nur für 1.0. Neue Checkpoints speichern die Protokollversion; Predict-CLIs prüfen zusätzlich die Klassen des gespeicherten Kontrasts.

Baseline: Mu-/Beta-Bandpower für 2.0; die bisherige Fünfband-Baseline für alte Daten bleibt erhalten. CBraMod-/REVE-Vorverarbeitung wird dadurch nicht umdefiniert; der jeweilige Bericht dokumentiert Merkmalsbänder und Verarbeitung. Kein automatisches Training während der Aufnahme.

## 7. Prüfstand und offene Hardware-Abnahme

Hardwarefreie Prüfkommandos:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python gtec_Clib/terminal/test_oscar_session.py
python -m unittest analysis.test_session_protocol analysis.test_event_annotations analysis.test_signal_selection analysis.test_view_eeg_cli analysis.test_waterfall_cli
python -m unittest analysis.test_ml_pipeline analysis.test_reve_pipeline
```

Die C++-Tests prüfen 250 Seeds in beiden Reihenfolgen, exakte Rest-/Klassenkontingente, alle Aufgabenanzeigen und gespeicherten Parameter sowie eine vollständige beschleunigte 168-Trial-Sitzung. Pause/Repeat wird auch für alle mentalen Bedingungen in jeder Trialphase geprüft. Langsame Anzeige/Marker, blockierter Recorder-Stop, Fensterverlust, Aufnahme-/Metadatenfehler und EOF bleiben abgesichert. Die Python-Tests prüfen neue Kontraste, alte Dateien, widersprüchliche Protokolle, Ausschlüsse, Testtrennung und die Erhaltung der Zusatzfelder über beide Viewer und FIF. Modellpipeline-Tests verwenden kleine synthetische Eingaben ohne Checkpoint-Download.

Unter Windows ausstehend: aktueller Release-Build und Vendor-DLL, zwei Monitore/Vollbild, lesbare neue Hinweise und Pausentexte, laufende Terminaleingabe, tatsächliches Display-/Softwaretiming, Lizenzzugang sowie kompletter Echtzeitlauf mit Headset einschließlich OSCAR-Nachlauf. Diese Abnahme und die wissenschaftliche Signal-/Aufgabenvalidierung werden durch hardwarefreie Tests nicht ersetzt. OSCAR-Abnahme: [Aufnahmeanleitung](../acquisition/README.md).
