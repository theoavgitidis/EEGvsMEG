# Unicorn-Terminal: Bedienungsanleitung

## Voraussetzungen

- Windows, 64 Bit: Die mitgelieferte `Unicorn.dll` ist eine Windows-x64-Bibliothek.
- Kompatibles Unicorn-Headset, eingeschaltet und geladen.
- Funktionierender Bluetooth-Adapter und zuvor gekoppeltes Headset.
- Zum Bauen: Visual Studio 2022 oder dessen Build Tools mit „Desktopentwicklung mit C++“, Windows SDK und CMake. Der Quellcode benötigt C++17.

Die Bibliothek ersetzt keinen Bluetooth-Treiber. Windows muss den Adapter erkennen.
Falls mehrere Adapter vorhanden sind, kann der interne Adapter im Geräte-Manager
deaktiviert werden, damit der mitgelieferte Dongle verwendet wird. Das kann andere
Bluetooth-Geräte trennen. Kopple das Headset über Windows oder Unicorn Suite und
beende andere Anwendungen, die eine Aufnahme mit dem Headset durchführen.

## Bauen, starten und aktualisieren

Öffne PowerShell im Stammordner des Projekts `EEGvsMEG`:

```powershell
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build-vs -G "Visual Studio 17 2022" -A x64
cmake --build gtec_Clib/terminal/build-vs --config Release
& .\gtec_Clib\terminal\build-vs\Release\unicorn_terminal.exe
```

`-G "Visual Studio 17 2022"` wählt ausdrücklich das Buildsystem von Visual Studio
2022 aus; `-A x64` legt einen 64-Bit-Build fest. Ohne `-G` kann CMake automatisch
NMake auswählen. NMake unterstützt `-A` nicht und meldet dann „does not support
platform specification“. Der Ordner `build-vs` vermeidet die Wiederverwendung
einer früheren NMake-Konfiguration im Ordner `build`.
Mit `cmake --help` kannst du die Generatoren anzeigen. Für eine andere
Visual-Studio-Version wähle den entsprechenden Generatornamen.

CMake kopiert `Unicorn.dll` neben die EXE. Beim Weitergeben müssen beide Dateien
zusammenbleiben. Die passende Visual-C++-Laufzeit muss auf dem Zielrechner verfügbar sein.
Nach Quellcodeänderungen genügt normalerweise der zweite Befehl zum erneuten Bauen.
Bei Änderungen am Buildsystem führe auch den ersten Befehl erneut aus.

Falls `cmake` nicht gefunden wird, installiere CMake bzw. füge seinen `bin`-Ordner
zu PATH hinzu und öffne ein neues Terminal. Falls kein C++-Compiler gefunden wird,
ergänze die C++-Buildtools im Visual Studio Installer. Bei einem Generator-Konflikt
verwende einen neuen Buildordner, etwa `build-new`, in allen drei Befehlen.

Nach dem Start erscheinen `>` und eine Befehlsübersicht. Gib Befehle einzeln ein
und bestätige mit Enter. Diese Befehle gehören in das laufende Programm, nicht in
PowerShell. Befehle ignorieren Groß-/Kleinschreibung; Namen und Labels bleiben unverändert. `quit` oder `exit` beendet es.

## Versuche und Speicherort

Alle neuen Aufnahmen liegen unter `EEG/recordings/<Versuchsname>/`, also hier:
`C:\Users\DHBWQ\Desktop\EEG\recordings`. Der Basisordner wird beim
CMake-Konfigurieren festgelegt und bleibt unabhängig vom Startordner gleich.
Nach einem Umzug des Projekts oder auf einen anderen Rechner erneut konfigurieren
und bauen. Alte Aufnahmen werden nicht automatisch verschoben.

```text
NewExp "Pilotversuch 01"
Where
ListExp
GoToExp "Pilotversuch 01"
```

- `NewExp "NAME"`: Erstellt und aktiviert einen neuen Versuchsordner. Existiert er bereits, verwende `GoToExp`.
- `GoToExp "NAME"`: Aktiviert einen vorhandenen Versuchsordner.
- `ListExp`: Listet Versuche auf; `*` markiert den aktiven.
- `Where`: Zeigt den vollständigen Speicherort.

Der Prompt zeigt ständig `[Pilotversuch 01] >`. Beim Programmstart steht dort
`[Kein Versuch ausgewählt] >`; wähle vor `record` oder `start` einen Versuch.
Alle Befehle akzeptieren Groß- und Kleinschreibung. Namen dürfen Leerzeichen und
Umlaute enthalten; Namen mit Leerzeichen in Anführungszeichen setzen. Ungültige
Windows-Namen, Sonderzeichen und Pfade wie `..\` werden abgelehnt.
Während einer Aufnahme ist ein Versuchswechsel gesperrt; `Where` und `ListExp`
funktionieren weiterhin.

`record` und `read` akzeptieren ausschließlich Dateinamen, keine abweichenden
Pfade. Bei `record 60 "session01.csv" real` entstehen im aktiven Versuchsordner
`session01.csv` und `session01.csv.events.csv`. Die Spalte `label` in der Event-Datei
enthält die Markierungen. Vorhandene Dateien werden auch bei `read` nicht überschrieben.

Eine laufende EXE lässt sich unter Windows nicht neu bauen. Beende sie zuerst mit
`quit` oder verwende zum Bauen einen separaten Buildordner.

## Erster Funktionstest

```text
version
bluetooth
NewExp "Pilotversuch 01"
scan paired
open YOUR_SERIAL
info
config
record 5 "test01.csv" test
```

Ersetze `YOUR_SERIAL` durch die von `scan paired` ausgegebene Seriennummer.
Warte mindestens fünf Sekunden, gib `status` ein und prüfe anschließend die Datei.
Erwartet sind bei erfolgreicher Aufnahme 1250 Datenzeilen zuzüglich Kopfzeile.
Auch der Testsignalmodus benötigt ein verbundenes Headset; er ist keine Simulation.
Für eine echte Messung verwende `real` statt `test` und einen neuen Dateinamen.

## Alle Befehle

| Befehl | Wirkung und Voraussetzungen |
|---|---|
| `help` | Zeigt die Kurzreferenz; jederzeit möglich. |
| `version` | Gibt die API-Version aus; keine Verbindung nötig. |
| `error` | Gibt den letzten Fehlertext der Bibliothek aus; keine Verbindung nötig. Ein früherer Fehlertext kann weiter vorhanden sein. |
| `bluetooth` | Adaptername, Hersteller, Empfehlungsflag und Problemflag; keine Headset-Verbindung nötig. |
| `scan paired` | Listet gekoppelte Headsets; keine Verbindung nötig. |
| `scan unpaired` | Sucht nicht gekoppelte Headsets; kann lange blockieren. Koppelt sie nicht automatisch. |
| `open SERIAL` | Öffnet ein Headset. Zuerst eine bestehende Verbindung mit `close` schließen. |
| `close` | Stoppt eine laufende Aufnahme und schließt die Verbindung. |
| `info` | Seriennummer, Firmware-, Geräte-, PCB- und Gehäuseversion sowie EEG-Kanalzahl. Verbindung erforderlich. |
| `config` | Kanalnamen, Einheiten, Wertebereiche und Aktivierungszustände. Verbindung erforderlich. |
| `channels` | Anzahl aktuell erfasster Kanäle. Verbindung erforderlich. |
| `index EEG 1` | Position des benannten Kanals im aktuellen Datenstrom. Namen exakt wie in `config` angeben. |
| `enable INDEX 0` | Deaktiviert einen Kanal über seinen Konfigurationsindex 0–16. Aufnahme muss gestoppt sein. |
| `enable INDEX 1` | Aktiviert den Kanal. Aufnahme muss gestoppt sein. |
| `start real` | Startet manuelle Messwerterfassung; anschließend zeitnah `read` aufrufen. |
| `start test` | Startet manuelle Erfassung eines Testsignals. |
| `read SCANS` | Liest 1–2500 Scans nach `start`; zeigt die ersten fünf im Terminal. |
| `read SCANS "datei.csv"` | Liest und speichert zusätzlich CSV im aktiven Versuch. Vorhandene Dateien werden abgelehnt. |
| `stop` | Stoppt manuelle oder Hintergrundaufnahme, hält die Verbindung offen. |
| `record SEKUNDEN "datei.csv" [real\|test]` | Hintergrundaufnahme; Modus standardmäßig `real`. Dauer 0–86400 Sekunden. 0 bedeutet bis zum Stoppen. |
| `mark LABEL` | Speichert den gesamten Text hinter `mark` als Ereignislabel. Nur während Hintergrundaufnahme. |
| `status` | Zeigt den Zustand und die zuletzt erfassten Werte der Hintergrundaufnahme; keine Verbindung nötig. |
| `outputs` | Liest die acht digitalen Ausgangsbits als Dezimalzahl. Verbindung erforderlich. |
| `outputs WERT` | Setzt die Bits mit einer Dezimalzahl 0–255 und liest sie zurück. Hardwareunterstützung erforderlich. |
| `quit` / `exit` | Versucht Aufnahme zu stoppen und Gerät zu schließen, dann Programmende. |

Während einer Hintergrundaufnahme sind nur `Where`, `ListExp`, `help`, `status`, `mark`, `stop`,
`close`, `quit` und `exit` erlaubt. Die Bibliothek wird ausschließlich vom
Aufnahmethread verwendet. Nach automatischem Aufnahmeende sind die anderen
Befehle wieder verfügbar. Eine manuelle Aufnahme muss vor `record` gestoppt werden.

### Kanalindizes

Die Konfiguration umfasst acht EEG-Kanäle (0–7), drei Beschleunigungskanäle (8–10),
drei Gyroskopkanäle (11–13), Batterie (14), Zähler (15) und Validierungsindikator (16).
`enable` verwendet diese Konfigurationsindizes. `index` liefert dagegen die Position
im Datenstrom; durch deaktivierte Kanäle können beide Indizes voneinander abweichen.
Lies Einheiten und Wertebereiche mit `config`, statt sie im Auswertungscode anzunehmen.
Die Abtastrate ist 250 Hz. Ein Scan enthält einen Wert pro aktivem Kanal.

### Digitale Ausgänge

`outputs 1` setzt Bit 0, `outputs 170` die Bits 1, 3, 5 und 7, `outputs 255` alle
Bits, `outputs 0` setzt alle auf niedrig. Die API-Funktionen garantieren nicht,
dass dein Headset physisch nutzbare Ausgänge besitzt. Das Programm setzt diese
Ausgänge beim Beenden nicht automatisch zurück. Sie sind keine Ereignismarker
in den gespeicherten EEG-Daten.

## Experiment aufnehmen

```text
open YOUR_SERIAL
record 0 "participant01_session01.csv" real
mark baseline_start
status
mark baseline_end
mark motor_imagery_left_trial_01_start
mark motor_imagery_left_trial_01_end
stop
status
close
quit
```

Bei `record 60 ...` endet die Erfassung automatisch nach 15000 Scans.
Allgemein wird eine positive Dauer auf `ceil(Sekunden * 250)` Scans gerundet.
Die Dauer beschreibt die angeforderte Samplezahl, nicht eine garantierte Wanduhrdauer.
Es erscheint keine asynchrone Abschlussmeldung; prüfe mit `status`, ob
`Recording: 0` angezeigt wird und ob ein Fehler vorliegt.

`stop` wartet auf den aktuellen Bibliotheksaufruf. Normalerweise werden Blöcke
von 25 Scans gelesen, entsprechend 100 ms nominaler Signaldauer. Wenn der
Bibliotheksaufruf bei einem Verbindungsproblem blockiert, kann auch `stop` warten.
Fehler bei Erfassung oder Dateiausgabe beenden die Hintergrundaufnahme; Details
erscheinen in `status`. Es gibt keinen automatischen Wiederverbindungsversuch.

## Dateien, Pfade und Datenformat

Dateinamen beziehen sich immer auf den aktiven Versuchsordner unter
`EEG/recordings`. Absolute Pfade und Unterordner sind nicht erlaubt.
Setze Dateinamen mit Leerzeichen in doppelte Anführungszeichen, zum Beispiel
`record 60 "session 01.csv" real`.

Eine Hintergrundaufnahme erzeugt:

- `versuch01.csv`: Messwerte mit Kopfzeile.
- `versuch01.csv.events.csv`: Ereignislog mit Kopfzeile, auch ohne Marker.

Existiert eine dieser Dateien bereits, wird die Aufnahme abgelehnt. Verwende
einen neuen Namen. Ein Fehler beim Start kann bereits angelegte Dateien hinterlassen;
prüfe diese vor einem neuen Versuch. Auch der manuelle Befehl `read` schützt vorhandene Dateien. `read` exportiert ausschließlich Kanalwerte.

### Spalten der Hintergrundaufnahme

| Spalte | Bedeutung |
|---|---|
| `sample_index` | Fortlaufender, bei 0 beginnender Index empfangener Scans. |
| `nominal_time_s` | `sample_index / 250`; berücksichtigt keine verlorenen Samples. |
| `host_read_utc_s` | Unix-Zeit in Sekunden beim Empfang eines Blocks; alle Scans eines Blocks haben denselben Wert. |
| Weitere Spalten | Aktive Gerätekanäle in der mit `GetChannelIndex` ermittelten Reihenfolge. |

### Spalten des Ereignislogs

| Spalte | Bedeutung |
|---|---|
| `host_utc_s` | Unix-Zeit bei Verarbeitung des Markerbefehls. |
| `elapsed_s` | Monoton verstrichene Zeit seit Anforderung des Aufnahmestarts. |
| `samples_received` | Anzahl bereits verarbeiteter Scans bei Eingabe des Markers; kein exakter Marker-Sampleindex. |
| `label` | Gesamter Text hinter `mark`; Kommas und Anführungszeichen werden für CSV maskiert. |

Beispiel: `mark trial 1, left hand` speichert das Label `trial 1, left hand`.
Zusätzliche Anführungszeichen um Markertexte werden Teil des Labels.
CSV verwendet Kommas als Trenner und Punkte als Dezimalzeichen. Beim Import in
deutsches Excel diese Einstellungen ausdrücklich wählen.

Messwerte werden ungefähr einmal pro Sekunde und beim normalen Abschluss
geschrieben bzw. geflusht; Marker werden nach jeder Eingabe geflusht. Ein
Prozessabbruch oder Stromausfall kann die letzten gepufferten Werte verlieren.
Dateien speichern keine Teilnehmermetadaten, Kanaleinheiten, Firmwareversion
oder Versuchsprotokolle; diese separat dokumentieren.

## Status, Qualität und Zeitgenauigkeit

`status` zeigt Aktivität, empfangene Samplezahl, nominale Signaldauer,
Zählerunterbrechungen und gegebenenfalls letzte Batterie-/Validierungswerte.
Die Werte stammen aus dem zuletzt verarbeiteten Block. Zählerunterbrechungen
werden nur bei aktivem `Counter`-Kanal erfasst und zählen Abweichungen von +1,
einschließlich Rücksetzungen und Überläufen; sie sind keine genaue Anzahl
fehlender Samples. Batterie und Validierung werden unverändert ausgegeben,
ohne automatische Grenzwertwarnung oder Interpretation.

Die Software bietet keine Impedanzmessung, automatische Artefaktentfernung,
Livegrafik, Klassifikation oder automatische Versuchssteuerung. Der Status
allein bestätigt deshalb keine wissenschaftlich ausreichende Signalqualität.

Host-Zeitstempel beschreiben Empfang bzw. Befehlsverarbeitung. Bluetooth-Puffer,
Blockgröße und menschliche Reaktionszeit erzeugen Unsicherheit. Die UTC-Uhr kann
durch Zeitsynchronisierung korrigiert werden; `elapsed_s` verwendet eine monotone
Uhr. Für genaue EEG–MEG-Synchronisation sind gemeinsame Trigger oder eine andere
validierte Zeitreferenz erforderlich.

## Fehlerbehebung

| Problem | Nächster Schritt |
|---|---|
| DLL fehlt | `Unicorn.dll` neben die EXE kopieren bzw. neu mit CMake bauen. |
| Fehlende Laufzeit-DLL | Passende Microsoft Visual C++ x64-Laufzeit installieren. |
| Adapterproblem / API-Code 2 oder 3 | Dongle im Windows-Geräte-Manager prüfen; `bluetooth` nach gestoppter Aufnahme ausführen. |
| Keine Geräte gefunden | Headset einschalten und koppeln; `scan paired` erneut ausführen. |
| Öffnen fehlgeschlagen / Code 4 | Seriennummer prüfen, andere Aufnahmesoftware schließen und Verbindung kontrollieren. |
| Ungültige Konfiguration / Code 5 | Aufnahme stoppen, `config` prüfen und gültige Kanäle aktivieren. |
| Pufferüberlauf / Code 6 | `stop`; Aufnahme neu beginnen. Bei längeren Aufnahmen `record` statt manueller Eingabepausen verwenden. |
| Pufferunterlauf / Code 7 | Aufnahmezustand und Verbindung prüfen; Fehlertext beachten. |
| Verbindungsproblem / Code 9 | `status` prüfen, Aufnahme beenden, Gerät/Dongle prüfen und neu verbinden. |
| Nicht unterstütztes Gerät / Code 10 | Kompatibilität des Headsets mit der mitgelieferten API prüfen. |
| Datei kann nicht erstellt werden | Pfad, vorhandene Dateien, Ordner und Schreibrechte prüfen. |
| Fehler beim Schreiben | Freien Speicherplatz und Laufwerk prüfen; Aufnahme kann unvollständig sein. |

Weitere API-Fehler werden als Code plus `UNICORN_GetLastErrorText` ausgegeben.
Ein abgefangener Fehler beendet das interaktive Programm normalerweise nicht.
Prüfe nach einem Aufnahmefehler immer `status` und die gespeicherten Dateien.
Beende regulär mit `stop` und `quit`; Strg+C bzw. Fenster-Schließen garantiert
keinen geordneten Abschluss.

## Technische Einschränkungen und Prüfung

Das Herstellerbeispiel übergibt die Länge des `GetData`-Puffers in Bytes,
der Header beschreibt sie als Floatanzahl. Das Programm folgt dem Beispiel
und reserviert viermal die benötigte Floatanzahl, damit beide Interpretationen
innerhalb der Speicherreservierung liegen. Die tatsächliche DLL-Semantik muss
auf Windows geprüft werden; exportiert werden nur die angeforderten Scans.

Alle 18 Funktionen des mitgelieferten Headers sind über Terminalbefehle abgedeckt.
C++17-Syntaxprüfung und simulierte Integrationstests wurden auf macOS bestanden.
Die Simulation prüft zeitbegrenzte Aufnahme, Marker/CSV-Maskierung, Ausschluss
gleichzeitiger API-Aufrufe, Stoppen, Überschreibschutz und Verbindungsfehler.
Windows-Build, Laden der echten DLL und Hardwareverhalten sind noch nicht geprüft.

Die Simulation lässt sich mit Python 3 und `clang++` ausführen:

```sh
python3 gtec_Clib/terminal/test_recorder.py
```

`mock_api.cpp` ist ausschließlich für diese Tests; der normale CMake-Build
verwendet immer die Herstellerbibliothek.
