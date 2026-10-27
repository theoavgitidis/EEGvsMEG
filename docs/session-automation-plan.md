# Automatische EEG-Sitzung: Spezifikation und Umsetzungsstand

Aufnahme-Erweiterung vom 27.10.2026: `start session` verwendet standardmäßig OSCAR und speichert zusätzlich Rohdaten; `start session raw` wählt den bisherigen Recorder. Aufgaben, Zeitplan und Trialregeln bleiben gleich. Implementierung und ausstehende Windows-/Headset-Abnahme: [OSCAR-Anleitung](../acquisition/README.md).

Stand: 19. Oktober 2026

Status: Spezifikation mit erster Implementierung und hardwarefreien Tests. Plan, CLI-Steuerung, Countdown, Anzeigeintegration, Aufnahme, Unterbrechung und Protokollierung sind umgesetzt. Die Windows-Anzeige, interaktive Terminaldarstellung und Vendor-Hardware müssen auf dem Messrechner validiert werden. Bedienung und tatsächliche Dateinamen: [SESSION_ANLEITUNG.md](../gtec_Clib/terminal/SESSION_ANLEITUNG.md).

Grundlage: [Pilotprotokoll](experiment-protocol.md), bestehende Unicorn-CLI und die vereinbarten Anzeigen. Beide Dokumente beschreiben nun denselben kognitiven Ablauf: 2 Sekunden READY, danach 10 Sekunden sichtbare Rechenanweisung, anschließend Fixationskreuz. Ein zusätzliches STOPP-Signal entfällt. Die folgenden Abschnitte definieren das Zielverhalten und dokumentieren die erste Implementierung; die offenen Prüfungen stehen in Abschnitt 17.

## 1. Ziel und Umfang

Nach Aufbau, Einweisung und Übung startet der Versuchsführer mit `start session` eine vollständige automatische EEG-Sitzung. Das Programm übernimmt Aufnahme, Baselines, Trials, Blockpausen, Experimentwechsel, Teilnehmeranzeige, Countdown und Ereignisprotokollierung.

Die geplante Dauer beträgt 38 Minuten und 16 Sekunden einschließlich aller vorgesehenen Erholungsphasen und Pausen. Aufbau, Einweisung, Übung, ungeplante Unterbrechungen und Wiederholungen sind darin nicht enthalten.

Die spätere wissenschaftliche Auswertung, Artefaktbereinigung, Klassifikation und ein EEG–MEG-Vergleich gehören nicht zu diesem Befehl.

## 2. Bereits vorhandene Komponenten

| Komponente | Implementierter Stand |
|---|---|
| `main.cpp` | Bestehende manuelle CLI sowie `start session`, Pause/Resume, Laufreihenfolge und Befehlssperren. |
| `session_plan.h` | Reproduzierbarer Plan-Generator und Zeitmodell mit Trials, Pausen, Invalidierung und Attempt-IDs. |
| `session.h` | Koordination von Aufnahme, Zeitplan, Anzeigen, Ereignissen, Dateien, Fehlern und Abschluss. |
| `recorder.h` | Kontinuierliche CSV-Aufzeichnung, strukturierter Status und erweiterte Ereignisse bei Sitzungsaufnahmen. |
| `cues.h` | Windows-Fenster mit Text, Kreuz und Vollbild; die Sitzung aktualisiert Aufgaben und Pausencountdown. |
| `console.h` | Aktualisierte Statuszeilen mit gleichzeitig verfügbarer Eingabe im interaktiven Windows-Terminal. |
| `experiments.h` | Experimentordner, Namensprüfung und Überschreibschutz; Sitzungsdateien werden in `session.h` zugeordnet. |
| `test_recorder.py`, `mock_api.cpp` | Hardwarefreie Tests für Recorder und bestehende manuelle CLI. |
| `test_session.cpp`, `test_session_runtime.cpp`, `test_session.py` | Planregeln, Laufzeitregressionen und vollständiger beschleunigter CLI-Durchlauf. |
| `view_eeg.py`, `analysis/view_eeg.py` | EEG-Import und gemeinsame Übernahme strukturierter Ereignisse über `analysis/event_annotations.py`. |
| `analysis/test_event_annotations.py` | Beide Viewer, Legacy-/manuelle Labels, Invalidierung und echter FIF-Speicher-/Ladetest. |

`start real` und `start test` bleiben manuelle Erfassungsbefehle. Die bisherige Cue-Zuordnung gilt außerhalb der automatischen Sitzung. Dort zeigen `baseline`, `rest` und `fixation` ein Kreuz; freie Labels können als Text erscheinen. Während einer Sitzung ist `mark LABEL` ausschließlich eine Beobachtung und manuelle `cue`-Bedienung ist gesperrt.

## 3. Verbindliches Anzeigeprinzip

### 3.1 Versuchsführer

Der Gesamt-Countdown erscheint ausschließlich im Terminal des Versuchsführers. Er beginnt bei `38:16`. Zusätzlich sichtbar sind Experiment, konkrete Handlungsanweisung, Trialnummer innerhalb des Experiments, Block, aktuelle Phase, Phasenrestzeit und Aufnahmezustand.

Beispiel:

```text
SITZUNG session_20261019_143000 | running | REST 31:42 | VERSTRICHEN 6:34
Motorik : ARME HEBEN – einmal anheben und ablegen : Trial 12/60 | Versuch 1
Block 1/4 | task Rest 0:03 | Aufnahme AKTIV
Datei: .../VP01/session_20261019_143000.csv | abgeschlossen 11/112 | Wiederholungen 0
[VP01] >
```

Die Statusfläche wird an derselben Stelle aktualisiert. Sie darf weder den Befehlsentwurf überschreiben noch den Terminalverlauf sekündlich mit neuen Zeilen füllen. Befehle und Fehlermeldungen bleiben lesbar. Alle Terminalausgaben benötigen koordinierte Ausgabe statt konkurrierender `std::cout`-Zugriffe.

### 3.2 Versuchsperson

Die Versuchsperson sieht keine globale Restzeit, Trialnummern, technischen Status oder Versuchsführerhinweise. Sichtbar sind nur Fixationskreuz, Aufgabenhinweis, READY, geplante Pause mit Countdown, ungeplante PAUSE oder Sitzungsende.

| Zustand | Teilnehmeranzeige |
|---|---|
| Baseline | `+` |
| Motorische/Imagery-Vorbereitung | `+` |
| Motorik Arme | `ARME HEBEN` |
| Motorik Beine | `BEINE HEBEN` |
| Motorik Blinzeln | `BLINZELN` |
| Imagery Arme | `ARME VORSTELLEN` |
| Imagery Beine | `BEINE VORSTELLEN` |
| Kognitive Vorbereitung | `READY` |
| Kognitive Aufgabe | beispielsweise `347 − 7` und darunter `FORTLAUFEND` |
| Erholung nach jeder Aufgabe | ausschließlich `+` |
| Geplante Blockpause | `PAUSE` und Countdown ab `0:45` |
| Geplanter Experimentwechsel | `PAUSE` und Countdown ab `1:30` |
| Ungeplante Unterbrechung | `PAUSE`, ohne Countdown |
| Erfolgreicher Abschluss | `SITZUNG BEENDET` |

Es gibt kein zusätzliches STOPP-Signal. Der Wechsel von der Aufgabenanzeige zum Kreuz beendet die Aufgabe. Insbesondere beim Rechnen bleiben die Zahlen während der zehnsekündigen Aufgabenzeit sichtbar. Die Versuchsperson hört auf zu rechnen, sobald das Kreuz erscheint.

Die sichtbaren Zahlen sind Bestandteil des kognitiven Paradigmas. Dieser Aufbau unterscheidet sich von einer Aufgabe, bei der Zahlen nur vorab gezeigt werden; dies ist in Protokoll und späterer Interpretation festzuhalten.

## 4. Voraussetzungen und Starttransaktion

Vor `start session` sind Headset vorbereitet und verbunden, Aufgaben eingeübt und ein Versuchsperson-/Experimentordner mit `NewExp` oder `GoToExp` ausgewählt. `start session` darf keine beliebige Seriennummer automatisch auswählen.

Startprüfungen:

1. Keine andere Sitzung, manuelle Erfassung oder Hintergrundaufnahme aktiv.
2. Ein gültiger Experimentordner ist ausgewählt.
3. Headsetverbindung besteht; Konfiguration kann gelesen werden.
4. Die für das konfigurierte Studienprotokoll erforderlichen EEG-Kanäle sind aktiviert. Die genaue Kanalmenge muss als Konfiguration festgelegt werden; fehlende Pflichtkanäle dürfen nicht stillschweigend ignoriert werden.
5. Kanalnamen, Einheiten, Abtastrate und aktivierte Gerätekanäle können dokumentiert werden.
6. Eindeutiger Dateinamensstamm ist reserviert; keine vorhandenen Dateien werden überschrieben.
7. Plan und Metadaten können gespeichert werden, EEG- und Eventausgaben lassen sich öffnen.
8. Teilnehmerfenster kann geöffnet werden und ist verfügbar.

Der Ablauf-Countdown startet erst, wenn die Aufnahme erfolgreich begonnen hat und die Anfangsbaseline angezeigt werden kann. Schlägt die Vorbereitung fehl, startet keine laufende Sitzung. Bereits erzeugte Dateien müssen eindeutig als nicht gestarteter Versuch gekennzeichnet oder nur dann entfernt werden, wenn sicher keine Messdaten enthalten sind. Es darf keinen verwaisten Aufnahme-Thread geben.

Die aktuelle Bildschirmwahl erfolgt vor dem Start: mit `cue open` öffnen und das Fenster auf den Teilnehmermonitor verschieben. `start session` aktiviert Vollbild auf dem aktuellen Monitor des Fensters. Eine separate Monitor-ID ist nicht konfigurierbar; die tatsächliche Anordnung und das Verhalten nach erneutem Öffnen sind unter Windows zu prüfen.

## 5. Zeitplan

### 5.1 Standardreihenfolge

```text
Anfangsbaseline
Motorik
Experimentpause
Imagery
Experimentpause
Kognitiv
Endbaseline
```

Die Reihenfolge der drei Hauptläufe soll konfigurierbar sein und in den Metadaten stehen. Standard bleibt Motorik → Imagery → Kognitiv. Die beiden Baselines bleiben am Anfang und Ende. Die Syntax lautet beispielsweise `session order imagery motorik kognitiv`; sie gilt vor Sitzungsbeginn und bleibt bis zur nächsten Änderung oder bis Programmende bestehen. Jeder Lauf muss genau einmal vorkommen.

### 5.2 Gesamtdauer

| Element | Rechnung | Dauer |
|---|---|---:|
| Anfangsbaseline | 60 s | 1:00 |
| Motorik-Trials | 60 × durchschnittlich 13 s | 13:00 |
| Motorik-Blockpausen | 3 × 45 s | 2:15 |
| Wechsel Motorik → Imagery | 90 s | 1:30 |
| Imagery-Trials | 40 × durchschnittlich 13 s | 8:40 |
| Imagery-Blockpausen | 3 × 45 s | 2:15 |
| Wechsel Imagery → Kognitiv | 90 s | 1:30 |
| Kognitive Trials | 12 × durchschnittlich 28 s | 5:36 |
| Kognitive Blockpausen | 2 × 45 s | 1:30 |
| Endbaseline | 60 s | 1:00 |
| **Gesamt** | **2296 s** | **38:16** |

Nach dem letzten Block eines Hauptlaufs gibt es keine zusätzliche 45-Sekunden-Pause. Dort folgt nur die Experimentpause beziehungsweise nach dem letzten Hauptlauf die Endbaseline.

### 5.3 Motorik

60 Trials, aufgeteilt auf vier Blöcke mit je 15 Trials. Jeder Block enthält fünf Arm-, fünf Bein- und fünf Blinzel-Trials.

Jeder Trial:

1. Zwei Sekunden Fixationskreuz.
2. Vier Sekunden Aufgabenanzeige und Ausführung.
3. Sechs, sieben oder acht Sekunden Erholung mit Kreuz.

Aufgaben werden vorher eingeübt:

- Arme: beide Unterarme einmal mit kleiner Auslenkung anheben und wieder ablegen, kein längeres Halten.
- Beine: beide Füße einmal leicht anheben und wieder absetzen.
- Blinzeln: zweimal bewusst blinzeln, ungefähr eine und drei Sekunden nach Aufgabenbeginn.

Pro Aufgabenart: fünf Trials mit 6 s Erholung, zehn mit 7 s und fünf mit 8 s. Summe über alle Motorik-Trials exakt 780 s. Die Dauer eines einzelnen Blocks darf durch Randomisierung etwas vom Mittelwert 3:15 abweichen.

Zwischen den vier Blöcken jeweils 45 s Pause. Gesamtdauer einschließlich Blockpausen: 15:15.

### 5.4 Imagery

40 Trials, aufgeteilt auf vier Blöcke mit je zehn Trials. Jeder Block enthält fünf Arm- und fünf Bein-Trials.

Jeder Trial:

1. Zwei Sekunden Fixationskreuz.
2. Vier Sekunden Arm- oder Beinbewegung vorstellen.
3. Sechs, sieben oder acht Sekunden Erholung mit Kreuz.

Vorstellung aus eigener Körperperspektive mit Fokus auf Bewegungsgefühl; keine tatsächliche Bewegung. Die vorgestellte Bewegung entspricht der eingeübten motorischen Aufgabe.

Pro Aufgabenart: fünf Trials mit 6 s Erholung, zehn mit 7 s und fünf mit 8 s. Trialzeit insgesamt exakt 520 s. Mittlere Blockdauer 2:10, tatsächliche Blockdauern planabhängig.

Zwischen den vier Blöcken jeweils 45 s Pause. Gesamtdauer einschließlich Blockpausen: 10:55.

### 5.5 Kognitiv

Zwölf Trials, aufgeteilt auf drei Blöcke mit je vier Trials.

Jeder Trial:

1. Zwei Sekunden `READY`. Startzahl ist noch nicht sichtbar; noch nicht rechnen.
2. Zehn Sekunden sichtbare Rechenanweisung, etwa `347 − 7` mit `FORTLAUFEND`. Ab Erscheinen still seriell subtrahieren: 340, 333, 326 usw. Weder sprechen noch Tasten drücken.
3. Wechsel auf `+`: sofort aufhören und 15, 16 oder 17 Sekunden erholen.

Für jeden Trial wird vorab eine neue dreistellige Startzahl festgelegt. Subtraktionsschritt standardmäßig 7. Implementiertes Zahlenintervall ist 300–899 ohne Wiederholung innerhalb der Sitzung. Diese Pilotwahl liefert noch keine individuell kalibrierte Rechenschwierigkeit; keine spontane Schwierigkeitsänderung während der Sitzung.

Erholung insgesamt: drei Trials mit 15 s, sechs mit 16 s und drei mit 17 s. Trialzeit exakt 336 s. Mittlere Blockdauer 1:52, tatsächliche Blockdauern planabhängig.

Zwischen den drei Blöcken jeweils 45 s Pause. Gesamtdauer einschließlich Blockpausen: 7:06. Zusätzliche mündliche Leistungsabfragen sind nicht Teil des automatischen Standardablaufs.

## 6. Randomisierung und reproduzierbarer Plan

Der gesamte Plan wird vor Aufnahmebeginn erzeugt und gespeichert. Keine spontane Neuauslosung bei jedem Phasenwechsel.

Regeln:

- Festgelegte Aufgabenhäufigkeiten je Block einhalten.
- In Motorik und Imagery höchstens zwei unmittelbar aufeinanderfolgende Trials derselben Aufgabe, einschließlich Blockgrenzen.
- Diese Regel gilt nicht für Kognitiv, da dort alle Trials Rechenaufgaben sind.
- Erholungsdauern unabhängig von Aufgabenreihenfolge zuweisen; Kontingente pro Aufgabenart exakt erfüllen.
- Rechenstartzahlen vorab erzeugen und speichern, ohne Wiederholung innerhalb derselben Sitzung.
- Zufallsseed, Protokollversion und tatsächlich erzeugte Reihenfolge speichern.
- Wiederholungen verwenden dieselbe Aufgabe und dieselben Parameter wie der unterbrochene Trial.

Der Generator muss seinen Plan validieren und insbesondere die Gesamtdauer 2296 s prüfen. Bei ungültigem Plan darf die Sitzung nicht starten.

## 7. Befehle und Zustände

| Befehl | Zielverhalten |
|---|---|
| `start session` | Vollständige Standardsitzung starten |
| `session pause` | Ungeplante Unterbrechung einleiten |
| `session resume` | Kontrolliert fortsetzen |
| `status` | Aufnahme- und Sitzungsstatus anzeigen |
| `mark TEXT` | Zusätzliche Beobachtung speichern, Ablauf und Anzeige unverändert lassen |
| `stop` | Sitzung abbrechen und Aufnahme kontrolliert stoppen |
| `close` | Sitzung gegebenenfalls abbrechen, Aufnahme stoppen, Headset trennen |
| `quit` / `exit` | Sitzung gegebenenfalls abbrechen und Programm sauber beenden |

`help`, `Where` und `ListExp` bleiben verfügbar. Änderungen des aktiven Experiments, der Kanalkonfiguration und manuelle Erfassungsstarts sind während der Sitzung gesperrt. Manuelle `cue`-Befehle sind ebenfalls gesperrt, damit sie die automatische Anzeige nicht überschreiben.

Außerhalb einer Sitzung bleibt die bisherige manuelle CLI erhalten. Insbesondere `start real`, `start test`, `record`, `read` und manuelle Cue-Nutzung behalten ihre Funktion.

Vorgesehene Zustände:

```text
idle → preparing → running ↔ paused → completed
                    │         │
                    └─────────┴────→ aborted / failed
```

`completed`, `aborted` und `failed` sind unterschiedliche Abschlusszustände und müssen in den Metadaten erkennbar sein. Doppelte Starts, Resume ohne Pause und Pause ohne Sitzung liefern verständliche Fehlermeldungen.

## 8. Ungeplante Unterbrechung

### 8.1 Allgemeines

`session pause` hält den Ablauf an und zeigt `PAUSE` ohne Countdown. Die EEG-Aufnahme läuft weiter. Pausenbeginn, Grund und aktive Phase werden protokolliert.

Währenddessen friert die geplante Restzeit ein. Die tatsächlich verstrichene Zeit läuft weiter. `session resume` beendet die Unterbrechung und stellt die korrekte Anzeige wieder her.

### 8.2 Unterbrechung eines Trials

Ein Trial gilt als zusammenhängende Einheit aus Vorbereitung, Aufgabe und Erholung. Unterbrechung in irgendeiner dieser Phasen markiert den Versuch als ungültig. Nach Resume beginnt derselbe geplante Trial vollständig neu, einschließlich Vorbereitung und vollständiger Erholung.

Geplante Trial-ID bleibt gleich; jeder Versuch erhält eine eigene Attempt-ID. Ungültige Abschnitte und Marker werden nicht gelöscht. Die Anzahl geplanter gültiger Trials bleibt 60/40/12. Wiederholungen werden zusätzlich gezählt.

Restzeit wird um den bereits verbrauchten Anteil des zu wiederholenden Trials erhöht, sodass die vollständige Wiederholung wieder enthalten ist. Auch mehrfache Unterbrechungen müssen korrekt behandelt werden.

### 8.3 Andere Phasen

- Baseline unterbrochen: vollständige 60 Sekunden erneut durchführen; bisherigen Versuch ungültig markieren.
- Geplante Pause unterbrochen: verbleibende Pausendauer nach Resume fortsetzen.
- Experiment- und Blockwechsel: atomare Übergänge; kein versehentlich doppeltes Start-/Endereignis.

## 9. Countdown und Zeitbasis

Die globale Restzeit entspricht der verbleibenden geplanten Ablaufzeit inklusive noch ausstehender geplanter Pausen. Zu Beginn 2296 s. Sie ist keine Garantie einer festen Uhrzeit für das Sitzungsende.

Regeln:

- Während normalem Ablauf und geplanter Pause herunterzählen.
- Während ungeplanter Unterbrechung einfrieren.
- Bei notwendiger Wiederholung verbleibende Zeit neu berechnen.
- Bei regulärem Ende 00:00 anzeigen; keine negativen Werte.
- Sekundenanzeige mit konsistenter Aufrundung, damit eine eben gestartete Phase nicht sofort eine Sekunde kürzer erscheint.
- Globalen Countdown aus demselben Zeitplan ableiten wie die Phasen, nicht unabhängig sekündlich dekrementieren.

Zeitsteuerung mit `std::chrono::steady_clock` oder gleichwertiger monotoner Uhr. UTC nur für externe Zuordnung und Dateimetadaten verwenden. Systemuhränderungen dürfen Phasenlängen nicht verändern.

Feste Phasenzielzeiten verhindern kumulative Drift durch wiederholte `sleep(duration)`-Aufrufe. Synchrone Anzeige- oder Schreiboperationen können auf dem Betriebssystem verzögert werden. Die Implementierung prüft deshalb die Übergangszeit vor und nach diesen Operationen gegen denselben Zielzeitpunkt. Mehr als 250 ms Verspätung erzeugen `timing_deviation` und eine Unterbrechung. Ein betroffener Trial wird invalidiert und vollständig wiederholt. Die Zählung abgeschlossener Trials wird erst nach erfolgreichen Abschlussmarkern erhöht. Die Schwelle ist auf dem Messrechner zu prüfen; die Tests bestätigen keine physikalische Onset-Genauigkeit.

Der vorhandene Recorder liest blockweise. Hostzeit und Sampleempfang sind keine genaue Messung des physikalischen Bildschirm-Onsets. Die bestehende synchrone Fensteraktualisierung ersetzt keine Photodiode oder validierte gemeinsame Trigger für EEG–MEG-Synchronisation.

## 10. Aufnahme und Nebenläufigkeit

Aufzeichnung kontinuierlich über Baselines, Aufgaben, Erholung, geplante und ungeplante Pausen. Das Ende des automatischen Ablaufs beendet die Aufnahme kontrolliert. Dafür ist ein Sitzungsende anhand der Ablaufuhr nötig; eine starre Recorder-Samplegrenze von 2296 × 250 allein wäre bei Unterbrechungen falsch.

Trennung der Verantwortlichkeiten:

- Recorder besitzt exklusiv die laufenden Geräte-API-Aufrufe.
- Sitzungssteuerung besitzt Plan, Zustand und Phasenwechsel.
- Teilnehmerfenster verarbeitet UI-Ereignisse auf seinem UI-Thread.
- Terminalrenderer und Eingabe werden koordiniert.
- Ereignisprotokoll synchronisiert automatische und manuelle Einträge.

Keine konkurrierenden Gerätezugriffe aus Timer- oder UI-Threads. Keine ungeschützten gemeinsamen Zustände. Beim Stoppen gilt: weitere Übergänge verhindern, Teilnehmeranzeige nach Möglichkeit auf `PAUSE` setzen, Abschlussereignis schreiben, Recorder stoppen und Threads verbinden, Dateien finalisieren. Die Anzeige wird vor potenziell blockierenden Schreib-/Aufräumoperationen geändert. Keine Sperre über einen synchronen UI-Aufruf halten, wenn daraus ein Deadlock entstehen könnte.

Ein blockierender Vendor-`GetData`-Aufruf kann das Beenden der Aufnahme verzögern. Die Teilnehmeranzeige wird bereits vorher geändert; eine sofortige Rückkehr des Befehls ist nicht garantiert. Die tatsächliche Stop-Latenz bleibt Teil der Windows-/Hardwareprüfung.

## 11. Fehler und Schließen des Teilnehmerfensters

### Aufnahmefehler

Bei Datenlese-, Schreib- oder sonstigem fatalem Aufnahmefehler:

1. Keine weiteren Aufgaben beginnen.
2. Teilnehmeranzeige nach Möglichkeit auf `PAUSE` setzen.
3. Terminal deutlich als fehlerhaft kennzeichnen.
4. Fehlergrund und letzte aktive Phase sichern, soweit Dateizugriff noch möglich.
5. Sitzung als `failed` abschließen, vorhandene Daten erhalten.

Nach einem Aufnahmefehler kein Resume in derselben Datei. Erneuter Aufnahmebeginn benötigt eine neue Sitzungs-ID. Verlorene Daten werden nicht als durchgehende Messung ausgegeben.

### Teilnehmerfenster geschlossen

Schließen während aktiver Sitzung löst eine ungeplante Unterbrechung aus. EEG läuft nach Möglichkeit weiter. Das Terminal meldet den Grund. Vor Fortsetzung muss das Teilnehmerfenster wieder geöffnet sein; `session resume` soll dies versuchen und bei Misserfolg pausiert bleiben.

Ein beim Schließen unterbrochener Trial beziehungsweise eine Baseline wird wie bei manueller Pause wiederholt. Das Fenster darf nicht unbemerkt verschwinden, während Aufgaben weiterlaufen.

### Manueller Abbruch

`stop`, `close`, `quit`, `exit` und Eingabe-EOF dürfen keine verwaiste Sitzungssteuerung hinterlassen. Bereits gespeicherte Daten bleiben erhalten. Grund und Abschlusszustand `aborted` werden gesichert. Bei `close` zusätzlich Headset trennen; bei `quit`/`exit` UI und Programm beenden.

## 12. Dateien, Sitzungs-ID und Zuordnung

Beispiel im ausgewählten Experimentordner:

```text
session_20261019_143000.csv
session_20261019_143000.csv.events.csv
session_20261019_143000.csv.plan.csv
session_20261019_143000.csv.session.json
```

Alle Dateien gehören über denselben Namensstamm und eine explizite Sitzungs-ID zusammen. Der Zeitstempel im Namen verwendet lokale Zeit mit dokumentierter Zeitzone; maschinenlesbare Ereigniszeiten werden in UTC gespeichert. Bei Namenskollisionen einen eindeutigen Zusatz verwenden, niemals überschreiben. Die Versuchsperson-ID stammt in der aktuellen Implementierung aus dem ausgewählten Experimentordner; keine unkontrollierte Annahme über Klarnamen.

### EEG-CSV

Bestehendes Format beibehalten: `sample_index`, `nominal_time_s`, `host_read_utc_s` und aktivierte Kanalwerte. Einheiten und Konfiguration stehen zusätzlich in den Metadaten.

### Plan-CSV

Eine Zeile pro Phase, einschließlich Baselines und Pausen. Tatsächliche Spalten:

```text
session_id,phase_index,planned_start_s,run,block,trial,condition,phase,duration_s,start_number,subtract,protocol_version,seed
```

`planned_start_s` bezieht sich auf den ursprünglichen Plan ohne ungeplante Unterbrechungen. Vorbereitung, Aufgabe und Erholung stehen in getrennten Zeilen; `duration_s` enthält deren jeweilige Dauer. Bei Wiederholungen bleibt diese Datei unverändert, die tatsächlichen Attempts stehen in der Eventdatei.

### Session-JSON

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

## 13. Ereignisprotokoll und manuelle Marker

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

Semantik kognitiv: `trial_start` und READY beginnen gemeinsam. Nach zwei Sekunden erscheinen Zahlen; dort liegen `cue_onset` und angewiesener `task_onset`. Nach zehn Sekunden beginnt mit dem Kreuz die Erholung. Für Motorik/Imagery erscheint die Aufgabeninstruktion nach der zweisekündigen Fixation.

Zeitpunkte beschreiben die angezeigte Anweisung, nicht den tatsächlich beobachteten Beginn einer Bewegung oder eines Gedankens.

Manuelle Beobachtungen:

```text
mark Husten
mark Elektrode geprüft
mark Versuchsperson fragt nach
```

Diese werden während einer Sitzung protokolliert, ohne Anzeige, Phase oder Countdown zu verändern. Das gilt auch für Labels wie `baseline`, die außerhalb der Sitzung eine Cue-Zuordnung haben. Organisatorische automatische Marker dürfen ebenfalls keinen beliebigen Text auf dem Teilnehmerbildschirm auslösen.

## 14. Abschlussbericht

Bei regulärem Ende:

1. Endbaseline abschließen und Abschlussmarker schreiben.
2. Während des Beendens vorübergehend `PAUSE` anzeigen; Aufnahme kontrolliert beenden und Dateien flushen/schließen.
3. Teilnehmeranzeige auf `SITZUNG BEENDET` setzen, sofern kein Aufnahmefehler vorliegt.
4. Metadaten mit Abschlussstatus speichern; bei Fehlern stattdessen `failed` und Fehlergrund.
5. Terminal zeigt Status, Speicherort, tatsächliche Dauer, abgeschlossene Trials, Wiederholungen und Fehler; die Recorder-Zeile von `status` nennt Samplezahl und Counter-Unterbrechungen. Das JSON enthält zusätzlich die Trialzahlen je Hauptlauf.

Headset kann anschließend verbunden bleiben, damit der Versuchsführer weitere Diagnostik durchführen kann. Eine neue Sitzung darf erst beginnen, wenn alle vorherigen Worker beendet und Dateien geschlossen sind.

## 15. Umsetzungsreihenfolge

1. Protokollmodell und validierten Plan-Generator erstellen; kognitiven Ablauf in der übrigen Dokumentation angleichen.
2. Strukturierte Recorder-Status-/Fehlerschnittstelle und Ereignisschema ergänzen.
3. Sitzungszustandsmaschine mit injizierbarer Uhr implementieren.
4. CLI-Befehle und Sperren integrieren, vorhandene manuelle Befehle erhalten.
5. Teilnehmeranzeigen und geplanten Pausencountdown integrieren.
6. Terminalrenderer mit gleichzeitig benutzbarer Eingabe implementieren.
7. Unterbrechungen, Wiederholungen, Fensterverlust und Aufnahmefehler integrieren.
8. Metadatenfinalisierung und Abschlussbericht ergänzen.
9. Automatisierte Tests und Windows-Prüfung durchführen.
10. Dokumentation mit tatsächlicher Syntax und geprüften Grenzen aktualisieren.

Diese Reihenfolge beschreibt das Umsetzungsvorgehen. Die softwareseitigen Schritte sind in einer ersten Implementierung vorhanden; Windows- und Hardwareprüfung bleiben erforderlich.

## 16. Abnahmekriterien und Tests

### Plan und Zeiten

- Exakt 60 Motorik-, 40 Imagery- und 12 Rechen-Trials.
- Blockgrößen und Klassenkontingente stimmen.
- Erholungszeitkontingente stimmen exakt.
- Ohne Unterbrechung geplante Dauer exakt 2296 Sekunden.
- Zwei Baselines à 60 s, acht Blockpausen à 45 s und zwei Experimentpausen à 90 s.
- Keine zusätzliche Blockpause am Laufende.
- Seed reproduziert denselben Plan; Trialwiederholung verändert nicht die übrige Reihenfolge.

### Anzeigen und Marker

- Teilnehmer sieht alle vereinbarten Texte und ausschließlich das Kreuz während Erholung.
- Kognitiv zeigt zwei Sekunden READY und zehn Sekunden Zahlen mit FORTLAUFEND.
- Keine STOPP-Anzeige.
- Globaler Countdown nur im Terminal, Pausencountdown auch im Teilnehmerfenster.
- Jede Phase besitzt korrekte Ereigniszuordnung; manuelle Marker ändern keine Anzeige.
- Eventdateien bleiben im MNE-Viewer importierbar.

### Unterbrechung und Abschluss

- Pause in Vorbereitung, Aufgabe und Erholung wiederholt den vollständigen Trial.
- Pause in Baseline wiederholt diese vollständig.
- Pause in geplanter Pause erhält deren Restdauer.
- Mehrfache Unterbrechung erzeugt eindeutige Attempt-IDs und korrekte Restzeiten.
- Stop/Close/Quit/EOF führen zu korrekter Finalisierung.
- Fensterverlust verhindert weiteres unbeobachtetes Fortschreiten.
- Aufnahmefehler beendet den Ablauf; keine stille Weiterführung oder automatische Datenverkettung.
- Namenskollisionen überschreiben nichts; Schreibfehler sind sichtbar.

### Prüfverfahren

Hardwarefreie Tests mit Mock-API und simulierter Uhr verwenden, um Zeitplan und Fehlerfälle ohne 38-minütige Wartezeit zu prüfen. Das ersetzt keinen echten Echtzeitlauf.

Unter Windows zusätzlich prüfen: Build, DLL-Anbindung, zwei Monitore, Vollbild, Textdarstellung einschließlich Umlauten/Minuszeichen, Terminaleingabe während Countdown, tatsächliche Phasenwechsel, Fensterverlust und kontrolliertes Stoppen. Abschließend vollständiger Pilotlauf mit Headset; Anzeige-/Timingqualität und Signalqualität getrennt beurteilen.

## 17. Offene Validierung auf dem Messrechner

Die früher offenen Implementierungsentscheidungen sind in Abschnitt 18 konkretisiert. Vor Nutzung des automatischen Protokolls müssen die tatsächliche Windows-Oberfläche, Terminaldarstellung, Monitoranordnung, Vendor-DLL und ein vollständiger Echtzeitlauf mit Headset geprüft werden. Dabei die Eignung der technischen 250-ms-Schwelle und der Rechenschwierigkeit im Pilot beurteilen.

Ein blockierender `GetData`-Aufruf kann die Finalisierung verzögern. Die Teilnehmeranzeige wechselt beim Abbruch vorher auf `PAUSE`; daraus folgt keine garantierte sofortige Rückkehr des Stop-Befehls. Präzise Bildschirm-Onsets und EEG–MEG-Synchronisation sind durch diese Implementierung nicht hardwarevalidiert.

Signalqualität, Elektrodenzuordnung, wissenschaftliche Auswertung und ausreichende Datenmenge sind weiterhin eigenständige Aufgaben. Eine Änderung des Pilotprotokolls erfordert neue dokumentierte Parameter und eine angepasste Zeitplanung.

## 18. Konkretisierte Entscheidungen der ersten Implementierung

- `session order motorik imagery kognitiv` konfiguriert vor Aufnahmebeginn jede der sechs Permutationen.
- Versuchsperson-ID stammt aus dem ausgewählten Experimentordner. Alle acht Kanäle `EEG 1` bis `EEG 8` sind Pflicht.
- Rechenstartzahlen: einmalig aus 300–899, Schritt 7.
- Teilnehmerfenster vor Start mit `cue open` auf den gewünschten Monitor verschieben; Sitzungsstart aktiviert Vollbild auf diesem Monitor.
- Phasenverspätung über 250 ms führt zur protokollierten Unterbrechung. Geprüft werden auch verzögerte Anzeige- und Schreiboperationen innerhalb des Übergangs; kein unbemerktes Verkürzen des nächsten Aufgabenfensters.
- Tatsächliche Dateinamen verwenden `.csv.plan.csv` und `.csv.session.json` neben `.csv.events.csv`.
- Event-CSV erhält zusätzliche Spalten bei Erhalt der bisherigen vier Spalten. Beide Viewer übernehmen den Kontext und die Attempt-Invalidierung in exportierbare MNE-Annotationen; alte und manuelle Labels bleiben erhalten.
- Keine Hardwarevalidierung oder Aussage über garantierte Stop-Latenz der Vendor-DLL aus den Mock-Tests ableiten.

## 19. Nachgewiesene softwareseitige Prüfungen

- `python gtec_Clib/terminal/test_recorder.py`: bestehende manuelle Befehle, Aufnahme, Marker, Pfade und Fehler.
- `python gtec_Clib/terminal/test_session.py`: 250 Seeds, sechs Reihenfolgen, Zustandswechsel, Wiederholungen, vollständige beschleunigte Sitzung und Fehlerpfade. Das Skript baut außerdem `test_session_runtime.cpp` und prüft gezielt langsame Anzeige, langsame Übergangsmarker, verzögerten Trialabschluss und PAUSE während eines blockierten Recorder-Stopps.
- `python -m unittest analysis.test_event_annotations`: beide MNE-Viewer einschließlich echten FIF-Speicherns/Ladens, Legacy-/manuelle Labels und Invalidierung früherer Marker. Benötigt MNE, NumPy und pandas.
- Plan- und Laufzeitregressionen bestanden mit Address-/UndefinedBehavior-Sanitizer unter Clang auf macOS.

Alle Tests verwenden temporäre Dateien. C++-Tests verwenden die Mock-API; der normale Windows-Build verwendet die Herstellerbibliothek. Diese Ergebnisse ersetzen nicht die offenen Prüfungen aus Abschnitt 17.
