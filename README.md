# EEGvsMEG

EEG-Aufnahme und Pilotversuche mit dem Unicorn-Headset. Die Windows-CLI führt Motorik, Motor Imagery und stilles Kopfrechnen automatisch durch. Aufnahmen und Aufgabenmarker können anschließend mit Python/MNE angezeigt und als FIF exportiert werden.

Stand: 27. Oktober 2026. Sitzungsprotokoll: `eeg-session-1.0`.

`start session` verwendet jetzt standardmäßig **OSCAR** über einen Python-Aufnahmeprozess; Rohdaten und bereinigte Daten werden getrennt gespeichert. `start session raw` wählt ausdrücklich den bisherigen C-API-Rohdatenrecorder. Einrichtung und Windows-/Headset-Abnahme: [OSCAR-Aufnahme](acquisition/README.md). Die C++-Sitzungssteuerung und das Pilotprotokoll bleiben erhalten. Windows-/Hardwareabnahme steht noch aus.

## Dokumentation

| Thema | Anleitung |
|---|---|
| OSCAR-Einrichtung, Signalwahl und Hardware-Abnahme | [OSCAR-Aufnahme](acquisition/README.md) |
| Automatische Sitzung und Bedienung im Versuch | [SESSION_ANLEITUNG.md](gtec_Clib/terminal/SESSION_ANLEITUNG.md) |
| Windows-Build und technische Übersicht | [Terminal-README](gtec_Clib/terminal/README.md) |
| Alle CLI-Befehle und manuelle Aufnahme | [VERWENDUNG.md](gtec_Clib/terminal/VERWENDUNG.md) |
| EEG und Marker ansehen, filtern und exportieren | [MNE_ANLEITUNG.md](gtec_Clib/terminal/MNE_ANLEITUNG.md) |
| Aufgaben, Trialzahlen und wissenschaftlicher Pilotplan | [Versuchsprotokoll](docs/experiment-protocol.md) |
| Teilnehmer-IDs und Zuordnung mehrerer Sitzungen | [ID-Schema](docs/participant-ids.md) |
| Technischer Sitzungsplan, Zustände und Datenzuordnung | [Sitzungsspezifikation](docs/session-automation-plan.md) |
| Kurze manuelle Vorführung | [Demo-Anleitung](presentations/Demo_Anleitung_DE.md) |
| Frühere Ideen und mögliche zusätzliche Aufgaben | [Experimentkatalog](docs/plannedExperiments/README.md) |

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

Alle acht EEG-Kanäle müssen aktiviert sein. Bei mehreren Monitoren das Teilnehmerfenster vor dem Start auf den vorgesehenen Bildschirm verschieben. Dann:

```text
start session
```

Für neue Teilnehmende das Schema `EVM-P001`, `EVM-P002` usw. verwenden; dieselbe Person behält ihre ID über alle Termine. Vergabe und Sitzungszuordnung: [ID-Schema](docs/participant-ids.md).

Für einen vorhandenen Versuch `GoToExp "EVM-P001"` anstelle von `NewExp` verwenden. Seriennummer durch die Ausgabe von `scan paired` ersetzen. Neue Sitzungen erhalten automatisch eigene Dateinamen.

## Automatischer Ablauf

| Abschnitt | Umfang | Dauer einschließlich Blockpausen |
|---|---|---:|
| Anfangsbaseline | Fixationskreuz | 1:00 |
| Motorik | 60 Trials: je 20 Arme, Beine, Blinzeln | 15:15 |
| Experimentpause | Countdown für die Versuchsperson | 1:30 |
| Imagery | 40 Trials: je 20 Arme und Beine | 10:55 |
| Experimentpause | Countdown für die Versuchsperson | 1:30 |
| Kognitiv | 12 Rechen-Trials | 7:06 |
| Endbaseline | Fixationskreuz | 1:00 |
| **Gesamt** | **112 Aufgaben-Trials** | **38:16** |

Motorik und Imagery: 2 s Kreuz → 4 s Aufgabenanzeige → 6–8 s Erholung mit Kreuz. Kognitiv: 2 s `READY` → 10 s beispielsweise `347 − 7` mit `FORTLAUFEND` → 15–17 s Erholung mit Kreuz. Beim Wechsel zum Kreuz endet die Aufgabe; es gibt kein zusätzliches STOPP.

Der Gesamt-Countdown erscheint nur im Terminal. Die Versuchsperson sieht Aufgabenhinweise, das Kreuz und bei geplanten Pausen einen Countdown. EEG wird während der gesamten Sitzung einschließlich Pausen aufgezeichnet. Die Laufreihenfolge kann vor dem Start beispielsweise mit `session order imagery motorik kognitiv` geändert werden.

| Befehl während der Sitzung | Wirkung |
|---|---|
| `mark Husten` | Beobachtung protokollieren; Anzeige und Ablauf bleiben erhalten. |
| `session pause` | Ablauf und Restzeit anhalten; EEG läuft weiter, Teilnehmer sieht `PAUSE`. |
| `session resume` | Fortsetzen; unterbrochene Trials beziehungsweise Baselines vollständig wiederholen. |
| `status` | Sitzungs- und Aufnahmezustand prüfen. |
| `stop` | Zuerst `PAUSE` anzeigen, dann Sitzung und Aufnahme kontrolliert abbrechen. |

Ungeplante Pausen und Wiederholungen verlängern die Sitzung. Die vollständigen Regeln stehen in der [Sitzungsanleitung](gtec_Clib/terminal/SESSION_ANLEITUNG.md).

## Daten und Auswertung

Der Aufnahmeordner liegt neben dem Repository unter `recordings/<Versuchsname>/`; `Where` zeigt den beim Build festgelegten Pfad. Pro Sitzung werden EEG-CSV, Event-CSV, Phasenplan und JSON-Metadaten gespeichert.

Beide MNE-Viewer erhalten Aufgabenart, Trial und Wiederholungsversuch in den Annotationen. Eine spätere Invalidierung kennzeichnet auch frühere Marker desselben Attempts als ungültig. Beide verwenden getrennte EEG-Achsen mit sichtbaren µV-Bereichen, eine eigene Marker-Zeitleiste mit vollständigen Details und darunter ein Spektrogramm des ausgewählten Kanals auf derselben Zeitachse. Die automatische Amplitudenskalierung gilt pro Kanal und sichtbarem Ausschnitt; die Farbskala des Spektrogramms bleibt beim Blättern und Kanalwechsel fest. Der Viewer im Projektstamm unterstützt FIF-/PNG-Export; der Viewer unter `analysis/` bietet zusätzlich eine Spektrumsansicht. Installation und Einheitenprüfung: [MNE-Anleitung](gtec_Clib/terminal/MNE_ANLEITUNG.md).

Für die tägliche Nutzung `view_eeg.py` im Projektstamm verwenden. Nach Einrichtung der Mac-Umgebung lässt sich die vorhandene Aufnahme so öffnen; `uV` muss zuvor anhand von `config` oder den Sitzungsmetadaten bestätigt sein:

```bash
cd /Users/theoa/Desktop/Projects/EEGvsMEG
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" --unit uV
```

Für eine ausdrücklich gefilterte Ansicht der Sekunden 60–80 zusätzlich `--start 60 --duration 20 --highpass 1 --lowpass 40` angeben. Die [Viewer-Anleitung](gtec_Clib/terminal/MNE_ANLEITUNG.md) enthält die Einrichtung für Windows und macOS, die Dateiablage, alle Bedienelemente und Exportbefehle. Automatische Skalen gelten je Kanal; für direkte Amplitudenvergleiche einen gemeinsamen Bereich mit beispielsweise `--scale-uv 100` wählen und auf Abschneidehinweise achten. Darstellung und Filter verändern die Originaldateien nicht.

Im Spektrogramm zeigt die Farbe die Leistungsdichte über Zeit und Frequenz. Delta, Theta, Alpha, Beta und Gamma sind eingezeichnet; standardmäßig reicht die logarithmische Frequenzachse bis 100 Hz. Eine EEG-Spur anklicken oder die Kanal-Schaltflächen rechts verwenden, um ihren Frequenzverlauf zu sehen. Für einen bestimmten Startkanal beispielsweise `--spectrogram-channel "EEG 3"` ergänzen; `--frequency-scale linear` schaltet auf eine lineare Frequenzachse um. Das Spektrogramm verwendet dieselben Anzeigefilter wie die EEG-Spuren. Es zeigt 2-s-Fenster und damit zeitlich geglättete Aktivität; Bewegungs-, Muskel- und Augenartefakte können die Farben mitbestimmen. Einzelne Frequenzbänder belegen keinen bestimmten mentalen Zustand.

### Interaktive Wasserfallansicht

Die zusätzliche Ansicht zeigt Amplitude und Bandpower pro Sensor nebeneinander. MNE übernimmt das Einlesen, die optionale Filterung und die Spektralschätzung; Plotly stellt die drehbaren 3D-Kurven und die alternative 2D-Ansicht dar. Dafür Plotly in derselben Python-Umgebung installieren:

```bash
~/.venvs/eeg-mne/bin/python -m pip install 'plotly>=6,<7'
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" --unit uV \
  --view waterfall --start 60 --duration 20 --scale-uv 100
```

Unter Windows:

```powershell
& .\.venv-mne\Scripts\python.exe -m pip install "plotly>=6,<7"
& .\.venv-mne\Scripts\python.exe .\view_eeg.py ".\test_session01.csv" --unit uV --view waterfall
```

Der Viewer öffnet sich im Browser. Sein lokaler, nur auf diesem Rechner erreichbarer Dienst liest die Aufnahme; CSV und Ereignisdatei bleiben unverändert. Nach der Installation werden keine Internetverbindung und keine externen Skripte benötigt. Das Terminal während der Nutzung geöffnet lassen und den Dienst anschließend mit **Strg+C** beenden. `--view traces` bleibt die Standardansicht. `--view waterfall --no-show` prüft und importiert die Aufnahme ohne Browser oder Dienst; `--save-fif` kann weiterhin den ungefilterten Import exportieren. `--snapshot` gilt für die Zeitkurvenansicht; die Wasserfallansicht hat eigene PNG-Schaltflächen.

| Einstellung | Wirkung |
|---|---|
| Zeitstart und Fensterlänge | Ausschnitt für beide Ansichten gemeinsam wählen und vor-/zurückblättern. |
| Kanalauswahl, Reihenfolge und Abstand | Einzelne Sensoren vergleichen oder alle acht übersichtlich trennen. |
| 3D / 2D | Perspektive drehen und zoomen oder eine flache Darstellung ohne Verdeckungen verwenden. |
| Frequenzband und eigene Bandgrenzen | Standardband auswählen oder den für die Fragestellung benötigten Frequenzbereich einstellen. |
| PSD-Fenster und Schrittweite | Frequenzauflösung und zeitliche Glättung der Bandpower steuern. |
| Gemeinsamer Amplitudenbereich | Sensoramplituden mit demselben µV-Maßstab vergleichen; `--scale-uv` setzt den Startwert. |
| Bandpower linear / dB und Wertebereich | Einheit und Skala für den Leistungsvergleich bewusst einstellen. |

Die große **Gesamtübersicht** zeigt die komplette Aufnahme mit Markern und hebt den sichtbaren Ausschnitt hervor. Ein Klick verschiebt den Ausschnitt zur gewählten Position. Die vergrößerte **Ereigniszeitachse** darunter zeigt die Marker des Ausschnitts mit anklickbaren Beschriftungen; die Markerlinien sind auch ohne Auswahl in beiden Plots sichtbar. Die feste Navigationsleiste zeigt Ausschnitt und genaue Cursorposition als Zeitcode und in Sekunden. Nach Auswahl eines Markers erscheinen zusätzlich seine vollständigen Ereignisdetails; gleichzeitige Marker bleiben einzeln auswählbar.

**Vorheriger / nächster Marker** springt durch die gesamte Aufnahme, auch über Ausschnittgrenzen hinweg. Außerhalb der Bedienelemente blättern **← / →** zwischen Ausschnitten, **Alt+← / Alt+→** zwischen Markern. **Amplitude einpassen** und **Bandpower einpassen** bleiben in der festen Navigationsleiste sichtbar und passen die jeweilige Skala an die aktuell angezeigten Werte an.

Das **Mausrad scrollt die Seite**, auch über den Plots. Die 3D-Perspektive lässt sich mit der Maus drehen und über **3D − / +** zoomen. Die Darstellung bündelt schnelle Regleränderungen und verwendet eine reduzierte WebGL-Pixelauflösung, damit auch Browser mit langsamer Grafikdarstellung bedienbar bleiben; Messwerte und Marker werden dadurch nicht verändert.

Die Amplituden werden nicht pro Kanal normalisiert. Eine Medianzentrierung dient nur der Darstellung und ist im Viewer gekennzeichnet. Bandpower entsteht durch Integration der spektralen Leistungsdichte im ausgewählten Band; ihre Zeitpunkte beziehen sich auf die Mitte des jeweiligen Analysefensters. Längere Fenster glätten schnelle Änderungen. Die Kanalachse gibt die gewählte Reihenfolge wieder, keine echten Abstände am Kopf. Eine kleine Kopfskizze mit den acht Unicorn-Positionen liegt in einem eigenen Bereich am Rand und verdeckt keine Kurven. Ohne explizite Filteroption bleibt die Ansicht ungefiltert; es erfolgt keine automatische Artefaktkorrektur oder neue Referenzierung.

Alternativ funktionieren `python -m analysis.view_eeg DATEI --unit uV --view waterfall` und der direkte Skriptaufruf unter `analysis/`; dort aktiviert `--filtered` die bestehende 50-Hz-Notch-/0.5–30-Hz-Filterkopie. `--psd` und `--view waterfall` sind getrennte Ansichten und können nicht gemeinsam verwendet werden.

## Tests und Prüfstand

Aus dem Repository-Stamm:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python -m unittest analysis.test_event_annotations analysis.test_time_frequency analysis.test_eeg_browser analysis.test_spectrogram_browser analysis.test_view_eeg_cli analysis.test_waterfall_cli analysis.test_waterfall_data analysis.test_waterfall_server
```

C++-Tests benötigen Clang++ oder MSVC `cl`; Viewer- und Annotationstests benötigen MNE, NumPy, pandas und Matplotlib; die HTTP-Tests der Wasserfallansicht benötigen zusätzlich Plotly. Optionale echte Browserprüfungen laufen mit `python -m unittest analysis.test_waterfall_ui analysis.test_waterfall_navigation`, wenn Playwright und ein installiertes Chrome verfügbar sind (`EEG_BROWSER_EXECUTABLE` kann den Browserpfad setzen). Die hardwarefreien Tests umfassen 250 Zufallsseeds, alle sechs Laufreihenfolgen, einen vollständigen beschleunigten Sitzungsdurchlauf, Unterbrechungen, Fehler und die im Review korrigierten Timingfälle. Die Viewer-Regressionstests prüfen dichte Marker und Fenstergrößenänderungen, getrennte Kanalachsen, Skalierung und Abschneidehinweise, Navigation, unveränderte Daten sowie echte PNG-Ausgabe ohne Desktop und einen ungefilterten FIF-Speicher-/Ladetest. Die C++-Plan- und Laufzeittests bestanden außerdem mit Address-/UndefinedBehavior-Sanitizer auf macOS.

Die aktuelle Windows-Anzeige, interaktive Terminalbedienung, Vendor-DLL und ein Echtzeitlauf mit Headset sind noch auf dem Messrechner zu validieren. Automatische Artefaktbereinigung, Klassifikation und eine validierte EEG–MEG-Synchronisation gehören noch nicht zum implementierten Funktionsumfang.
