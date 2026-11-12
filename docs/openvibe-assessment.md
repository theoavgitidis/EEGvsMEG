# OpenViBE: Einsatzmöglichkeiten im EEGvsMEG-Projekt

Stand: 12.11.2026. **Recherche und Architekturvorschlag; keine OpenViBE-Integration implementiert oder mit dem Headset geprüft.**

## Empfehlung

OpenViBE ist für dieses Projekt vor allem als **Ergänzung für Live-Monitoring, klassische Motor-Imagery-Pipelines und gesonderte Feedback-Demos** interessant. Der grafische Aufbau erleichtert es, Signalverarbeitung zu erklären und interaktiv zu erproben. Für die bestehende Studienaufnahme und die nachvollziehbare Offline-Auswertung ist der zusätzliche Nutzen kleiner: Diese Aufgaben sind bereits projektspezifisch umgesetzt.

Empfohlene Reihenfolge: erst ein synthetischer beziehungsweise dateibasierter Replay mit klarer Signal- und Markerprüfung, dann ein eigenständiger Unicorn-Verbindungstest unter Windows. Eine dauerhafte LSL-Ausgabe des eigenen Recorders lohnt sich erst, wenn der Pilot einen konkreten Vorteil gegenüber dem bestehenden Python-Weg zeigt. Ein Austausch der Sitzungssteuerung wäre ein deutlich größeres Vorhaben.

## 1. Ausgangslage im Repository

Die Einordnung beruht auf README, Versuchsprotokoll, Sitzungsspezifikation, Teilnehmer-ID-Schema und Terminal-/Aufnahmeanleitungen sowie einer gezielten Sichtung der Implementierung:

| Vorhandene Komponente | Bedeutung für OpenViBE |
|---|---|
| Windows-C++-CLI mit `eeg-session-2.0` | Steuert 168 geplante Trials in 45:04 Minuten, Cues, Pausen, Wiederholungen und Dateien. Die Dokumentation weist die Windows-/Headset-Abnahme weiterhin als offen aus. |
| `start session` mit Python-/OSCAR-Worker; `start session raw` mit C-API-Recorder | Aufnahmequelle besitzt das Gerät exklusiv; Roh- und bereinigte Daten bleiben getrennt. Ein zusätzlicher Verbraucher sollte denselben Datenstrom erhalten. |
| Acht EEG-Kanäle bei 250 Hz, bestätigte µV | Stream muss diese Metadaten explizit erhalten. Die im Projekt angenommene Montage Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 ersetzt keine Prüfung der tatsächlichen Platzierung. |
| `view_eeg.py` und `analysis/view_eeg.py` | Vorhandene Offline-Viewer mit gemeinsamer Ereignisaufbereitung, Zeit-/Frequenzansichten und Export; zusätzlich Hand-ERD/ERS. |
| `analysis.ml_feasibility`, CBraMod-/REVE-Piloten | Bereits vorhandene explorative Auswertungswege mit protokollspezifischen Kontrasten. OpenViBE würde eine weitere Pipeline ergänzen. |
| `analysis.movement_classifier` und `analysis.movement_features` | Vorhandene kausale Merkmale und Datei-Replay für ausgeführte Bewegungen. Kein implementierter Headset-Livebetrieb und keine validierte kontinuierliche Imagery-Erkennung. |
| Recherche nach `LSL`/`OpenViBE` im Projektcode | Keine vorhandene OpenViBE-/LSL-Anbindung gefunden; die OSCAR-Dokumentation erwähnt Hersteller-LSL als mögliche Alternative. |

Projektquellen: [Versuchsprotokoll](experiment-protocol.md), [Datei- und Zustandsverträge](session-automation-plan.md), [OSCAR-Aufnahme](../acquisition/README.md), [Bewegungsklassifikator](movement-classifier.md), [ERD/ERS-Viewer](erds-viewer.md), [Teilnehmer-IDs](participant-ids.md).

## 2. Was OpenViBE beiträgt

OpenViBE ist eine grafisch programmierbare Plattform für BCI und neurophysiologische Echtzeitverarbeitung. Der **Acquisition Server** übernimmt den Datenzugang; im **Designer** werden Verarbeitungsschritte als verbundene Boxen zu Szenarien zusammengestellt. Das Inria-Tutorial beschreibt Aufnahme, Verarbeitung, Visualisierung und Feedback als zentrale Arbeitsabläufe. [Inria-Tutorial 2024](https://neuroergonomics2024.inria.fr/files/2024/06/NEC24_OpenViBE-tutorial_Part1.pdf)

Klassische Motor-Imagery-Szenarien mit CSP sind dokumentiert. CSP lernt räumliche Kombinationen der Elektroden, welche Klassen anhand ihrer Varianz unterscheiden sollen. Eine passende Vergleichspipeline wäre Bandpass → CSP → logarithmische Varianz → LDA; Parameter und tatsächliche Boxen im gewählten Paket prüfen. Ein solches Szenario ist ein Ausgangspunkt für unsere Aufgaben und unsere acht Kanäle. [Motor-Imagery-CSP-Anleitung von David Medine/Brain Products](https://bci.plus/micsp/)

## 3. Konkrete Use Cases und Priorität

Die Prioritäten sind eine projektspezifische Bewertung, keine gemessenen Leistungszusagen. Aufwand bezeichnet zusätzliche Arbeit gegenüber dem vorhandenen Projekt; Installation und Hardwarezugang können ihn erhöhen.

| Use Case | Konkrete Anwendung bei uns | Nutzen / Aufwand | Einordnung |
|---|---|---|---|
| **Live-Signalmonitor für die Versuchsleitung** | EEG-Zeitkurven, Spektrum und Mu-/Beta-Leistung während Aufbau und Pilot beobachten; Blinzeln/Kiefer-/Kopfbewegung als Kontrollbeispiele zeigen. | Hoch bei fehlender Live-Ansicht / niedrig eigenständig, mittel integriert | Gute erste Live-Anwendung. Skalen, Filter und Roh-/OSCAR-Variante sichtbar halten. Kein Ersatz für gerätespezifische Kontakt-/Impedanzmessung. |
| **Klassischer MI-Vergleich mit CSP/LDA** | `MI_Bilateral` als EEG–MEG-Anker sowie `MI_HandSide` als separaten EEG-Kontrast untersuchen. | Mittel bis hoch / mittel | Fachlich passend. Beidseitige MI hat nur zwölf Trials je Klasse, unilaterale MI je 16 vor Ausschlüssen; keine große Parametersuche. |
| **Nachvollziehbarer Pipeline-Replay** | Dieselben gültigen Trials in Python und OpenViBE abspielen; Ereignisse, Merkmale und Vorhersagen vergleichen. | Hoch als Integrationsprüfung / mittel | Empfohlener erster Projektpilot ohne zusätzliche Personenaufnahme. CSV-Adapter oder LSL-Replay erforderlich. |
| **Mu-/Beta-Neurofeedback** | In eigener Übungssitzung einen Balken aus Bandpower oder ERD/ERS anzeigen, zunächst ohne Klassifikator. | Hoch für eine anschauliche Demo / mittel | Eigene Sitzung mit dokumentierter Referenz und Verarbeitungsverzögerung. Eine Kurvenänderung bestätigt keinen mentalen Zustand. |
| **Virtuelle BCI-Steuerung** | Nach Kalibrierung einen virtuellen Zeiger oder ein einfaches Spiel steuern. | Mittel / mittel bis hoch | Erst mit unabhängigen Testdaten und kontinuierlichem Ruhe-/Unknown-Test sinnvoll bewerten. Vorgegebene Zweiklassenfenster reichen dafür nicht. |
| **Unity-/externe Anwendung** | Vorhersagescores oder Ereignisse an eine bestehende Visualisierung geben. | Mittel bei konkretem Demo-Ziel / mittel | LSL-Kommunikation mit Unity ist durch ein OpenViBE-Beispiel dokumentiert. Eine neue Game-Engine bringt für die Studienauswertung allein wenig Mehrwert. |
| **Kognitive Aufgaben** | Wortgenerierung gegen Subtraktion mit eigener Merkmals-/Klassifikationskette prüfen. | Eher gering / mittel | Technisch als überwachte Klassifikation denkbar; nur acht Trials je Klasse. Kein fertiger verlässlicher „Denken-/Rechnen-Detektor“. |
| **P300-/SSVEP-Demo** | Separates ERP-/Flicker-Paradigma als Lehr- oder Anschlussprojekt. | Gering für die aktuelle Fragestellung / mittel bis hoch | OpenViBE bietet Beispiele für diese BCI-Familien. Benötigt neue Stimuli, Labels und Timingprüfung; die vorhandenen MI-Aufnahmen liefern diese Daten nicht. |
| **EEG–MEG-Vergleich** | Gemeinsamen Aufgaben-Kontrast und reproduzierbare Klassifikationsidee zeigen. | Gering für die Hauptauswertung / hoch bei vollständiger Übertragung | Die harmonisierte Offline-Analyse bleibt im bestehenden MNE-/Python-Weg sinnvoll. OpenViBE beseitigt keine Unterschiede in Sensoren, Kohorten, Trialzahlen oder Timing. |
| **Komplette Sitzung ersetzen** | Den gesamten 2.0-Ablauf im Designer/Lua neu bauen. | Aktuell gering / hoch | Keine Priorität: projektspezifische Zustände und Datenverträge müssten erneut umgesetzt und abgenommen werden. |

Belege für die Softwaremöglichkeiten: [MI-CSP-Szenario](https://bci.plus/micsp/), [OpenViBE-Unity-LSL-Beispiel](https://openvibe.gitlabpages.inria.fr/unity-games/hello-bidirectionnal/), [Inria-gepflegter OpenViBE-Eintrag mit P300-/SSVEP-/MI-Beispielen](https://www.nitrc.org/projects/openvibe/). Die wissenschaftlichen Grenzen ergeben sich aus unserem [Protokoll](experiment-protocol.md).

**Feedback gehört nicht in die derzeitige Hauptmessung:** Das Protokoll sieht ausdrücklich kein EEG-Klassifikationsfeedback während der Hauptaufnahme vor. Feedback kann Strategie und Signale verändern; ein solches Experiment benötigt eine eigene Kennzeichnung und gegebenenfalls eine neue Protokollversion.

## 4. Unicorn-Anbindung: vier realistische Wege

### A. Eigenständiger Betrieb mit nativem Unicorn-Treiber

```text
Unicorn → OpenViBE Acquisition Server → Designer → Anzeige/Klassifikator
```

Ein g.tec-Unicorn-Treiber ist bereits im Inria-Jahresbericht 2020 als Beitrag dokumentiert. Deshalb ist die direkte Anbindung eine reale Option. Ob der Treiber im konkret verfügbaren Windows-Paket enthalten ist und mit unserer Vendor-DLL sowie Geräteversion läuft, wurde nicht geprüft. Unterstützung für g.USBamp allein wäre dafür kein ausreichender Nachweis. [Inria/NEUROSYS 2020](https://rex-radar.inria.fr/report/2020/neurosys/uid0.html)

Dies wäre ein schlanker Verbindungstest. Unsere CLI darf dabei keine zweite Geräteaufnahme starten. OSCAR-Bereinigung und unser vollständiges Sitzungsformat sind durch den nativen Gerätezugang nicht automatisch enthalten; der Signalpfad muss ausdrücklich geprüft und dokumentiert werden.

### B. Hersteller-LSL-Quelle

```text
Unicorn → UnicornLSL.exe → LSL-Eingang im Acquisition Server → Designer
```

Der Hersteller dokumentiert `UnicornLSL.exe` unter DevTools der Unicorn Suite: Gerät wählen, öffnen und Übertragung starten. Der OpenViBE-Acquisition-Server bietet einen LSL-Eingang; ein Hardwarehersteller beschreibt diesen Weg mit anschließender `Acquisition client`-Box im Designer. [Unicorn-LSL-Anleitung](https://github.com/unicorn-bi/Unicorn-Network-Interfaces-Hybrid-Black/blob/main/LSL/unicorn-lsl-interface.md), [Mentalab-Integrationsanleitung](https://wiki.mentalab.com/mentalab-wiki/15-integrations/2-integrations-analysis/10-open-vibe.html)

Die Unicorn-Anleitung belegt den Transport, aber keine Gleichheit mit unserer ausgerichteten OSCAR-Ausgabe. Vor Nutzung Einheiten, Kanalbelegung, Counter, Vorverarbeitung und Zeitstempel prüfen. Auch diese Quelle besitzt den Gerätezugang; unsere aktuelle CLI kann sie nicht als Aufnahmebackend konsumieren. Eine Parallelaufnahme über CLI und Suite ist daher kein vorgeschlagener Integrationsweg.

### C. Eigenen Recorder um LSL-Ausgabe ergänzen

```text
                         ┌→ bestehende Original-/OSCAR-Dateien
Unicorn → eigener Recorder
                         └→ LSL-EEG → OpenViBE → Live-Anzeige
C++-Sitzungssteuerung ─────→ Markeradapter ──────→ OpenViBE
```

**Bevorzugtes Ziel bei dauerhaftem Livebedarf; noch zu implementieren.** Der vorhandene Prozess behält den exklusiven Gerätezugang. Im OSCAR-Modus bietet `acquisition/oscar_worker.py` bereits Hooks für rohe und bereinigte Blöcke (`build_pipeline`, `DualWriter`); im RAW-Modus wäre die Ausleitung am Datenempfang in `gtec_Clib/terminal/recorder.h` zu ergänzen. Publizieren muss entkoppelt erfolgen, damit ein langsamer OpenViBE-Verbraucher die Originalaufnahme nicht blockiert. Überlauf oder Verbindungsverlust der zusätzlichen Ausgabe müssen sichtbar werden.

Für einen ersten integrierten Pilot nur eine fest gewählte Signalvariante übertragen. Bei später zwei Streams getrennte Identitäten und eindeutige Metadaten verwenden. Acht EEG-Kanäle bleiben der primäre Eingang; IMU, Counter und Validation sind getrennte Kontrollinformationen. Eine unbeabsichtigte Nutzung als EEG-Merkmale könnte Bewegungsartefakte zur scheinbaren Aufgabenerkennung machen.

### D. Abgeschlossene Dateien als Replay

```text
Sitzungsdateien → geprüfter Adapter → OpenViBE-Dateiimport oder LSL-Replay
```

**Empfohlener erster Pilot.** Unsere CSV-Dateien enthalten Zeit-/Indexspalten und Hilfskanäle; sie sind kein bereits bestätigter OpenViBE-Importvertrag. Einen Adapter gegen die konkrete Reader-Version prüfen. Alternativ kann ein LSL-Replay aus einer geprüften MNE-Datenstruktur erzeugt werden. MNE-LSL dokumentiert dafür `PlayerLSL`, auch mit separater Annotationenausgabe. Die Übernahme dieser Annotationen in OpenViBE-Stimulationen muss zusätzlich geprüft werden. [MNE-LSL-Replay-Dokumentation](https://mne.tools/mne-lsl/stable/generated/tutorials/00_introduction.html)

Originaldateien ausschließlich lesen, abgeleitete Ausgaben in neue Ordner schreiben und den vollständigen Sitzungsverbund erhalten. Für den technischen Start synthetische Daten einschließlich Pause, Wiederholung und später Invalidierung verwenden.

## 5. Die wesentlichen Integrationsgrenzen

### Signal und Zeitbezug

- Samplingrate, Einheit, Referenzierung und Kanalreihenfolge aus bestätigten Metadaten übernehmen. Eine V-/µV-Verwechslung verändert Amplituden um den Faktor eine Million und Leistung um eine Billion. Keine pauschale Umrechnung ohne bestätigten Eingangsvertrag.
- Empfangszeit eines Blocks und physikalische Samplezeit unterscheiden. Im RAW-Recorder teilen 25 Samples einen Host-Empfangszeitpunkt; `nominal_time_s` ist eine aus dem Index abgeleitete Zeit. Unsere Marker sind Softwareereignisse, keine gemessenen Display-Onsets.
- OSCAR-Werte werden verzögert verfügbar, behalten in den Dateien aber die zugehörigen Rohsample-Indizes. Ein Liveadapter muss Ursprungszeit und Verfügbarkeit auseinanderhalten. Bereits ausgerichtete Marker nicht nochmals um die OSCAR-Verzögerung verschieben. Für Live-Epoching Marker gegebenenfalls bis zum passenden Signal puffern; die Empfängertoleranz für verzögert eintreffende Samples prüfen.
- Die LSL-Dokumentation nennt ein historisches, möglicherweise versionsabhängiges Problem beim Überschreiben von Zeitstempeln in der **LSL-Ausgabe des OpenViBE Acquisition Servers**. Das ist kein Nachweis, dass jede aktuelle LSL-Eingangskette defekt ist. Konkrete Version und verwendete Richtung prüfen. [LSL: OVAS-Zeitstempel und Blocklatenz](https://labstreaminglayer.readthedocs.io/info/ovas.html)
- Ende-zu-Ende-Latenz umfasst Geräte-/Bluetooth-Puffer, Verarbeitung, Übertragung, Fenster und Anzeige. Ein kleines LSL-Paket garantiert keine entsprechend schnelle Entscheidung. Die vorhandenen Bewegungsmerkmale benötigen 875 vergangene Samples, also 3,5 s Historie; 200-ms-Replay-Schritte sind keine gemessene Erkennungslatenz.

### Marker und nachträgliche Invalidierung

Die Sitzungssteuerung muss eine einzige maßgebliche Quelle bleiben. OpenViBE darf im integrierten Betrieb keinen unabhängigen Trialgenerator parallel zur CLI betreiben. Für den ausgewählten LSL-/Stimulationseingang sind Datentyp und Codierung zu prüfen: Ein beliebiger JSON-String ist kein bestätigter Ersatz für einen erwarteten numerischen Stimulation-Identifier.

Ein Adapter braucht eine versionierte Abbildung von Aufgaben und Zuständen auf Marker sowie eine vollständige Nebenablage mit `session_id`, `protocol_version`, `run`, `block`, `trial`, `attempt`, `condition`, Samplebezug und Invalidierungsgrund. Die vorhandenen Events/Plan-/Sessiondateien bleiben maßgeblich; ein reiner Klassen-Code verliert zu viel Kontext.

Besonders wichtig: `trial_invalidated` kann einen bereits begonnenen Attempt rückwirkend ausschließen. Für Training und Evaluation erst nach vollständiger Prüfung übernehmen; bei Livebetrieb bis zum Abschluss puffern oder spätere Ausschlüsse explizit nachführen. Nach Pause/Countersprung keine alten Filter-/Entscheidungszustände ungeprüft weiterverwenden. EEG läuft während einer Sitzungspause weiter, der Aufgabenplan steht.

### Fairer Modellvergleich

CSP, Skalierung, Merkmalsauswahl und Klassifikator ausschließlich auf Trainingsdaten fitten. Dieselben ganzen Blöcke, Sitzungen beziehungsweise Personen wie im Python-Vergleich zurückhalten; überlappende Fenster desselben Trials zusammenlassen. Eine Standard-Kreuzvalidierung innerhalb einer OpenViBE-Box bestätigt nicht automatisch diese Gruppenaufteilung.

Zuerst denselben Kontrast, dieselben gültigen Attempts und das gemeinsame 0,5–3,5-s-Aufgabenfenster verwenden. Filterphase, Filterzustand, Referenz und Bandpowerdefinition können zwischen Boxen und Python abweichen; Gleichheit muss numerisch geprüft werden. CBraMod-/REVE-Piloten verwenden teilweise eigene Offline-Vorverarbeitung und sind keine unverändert übertragbaren Live-Szenarien.

Bei virtueller Steuerung zusätzlich Fehlalarme pro Minute, verpasste Aktionen und Verzögerung auf kontinuierlichen unabhängigen Daten messen. Ein Zweiklassenmodell für bekannte Aufgabenfenster besitzt weder automatisch eine Ruhe-/Unknown-Klasse noch kalibrierte Wahrscheinlichkeiten.

## 6. Sinnvoller Pilot mit überprüfbaren Ergebnissen

| Schritt | Ergebnis | Kriterium zum Weitergehen |
|---|---|---|
| 1. Windows-Paket prüfen | Version, installierte Boxen, Unicorn-/LSL-Treiber und DLL-Konfiguration dokumentiert | Designer und gewählter Datenzugang starten; die tatsächlich installierte Konfiguration ist reproduzierbar festgehalten. |
| 2. Synthetisches Replay | Acht Kanäle bei 250 Hz, bekannte Amplitude/Frequenz, Aufgabenmarker sowie Pause/Repeat/Invalidierung | Werte, Kanalreihenfolge und Anzahl stimmen; Marker sind innerhalb einer vorab definierten Transporttoleranz zugeordnet; ungültiger Attempt gelangt nicht ins Training. Das prüft keinen physikalischen Onset. |
| 3. Vorhandene Sitzungsdatei abspielen | Vergleich einer festen Signalvariante mit Python | Dieselben gültigen Trials und Fenster; Verarbeitungsabweichungen erklärt und quantifiziert; Quellen unverändert. |
| 4. Feste klassische MI-Pipeline | Bandpower/linearer Klassifikator, optional ein vorab festgelegter CSP/LDA-Vergleich | Ganze zurückgehaltene Blöcke; Balanced Accuracy, Macro-F1, Konfusionsmatrix und Ausschlüsse nachvollziehbar. Kein Mindestleistungswert vorgetäuscht. |
| 5. Eigenständiger Unicorn-Live-Test | Datenfluss, Skalen, Counter und Laufzeitverhalten auf Windows geprüft | Keine konkurrierende Geräteaufnahme; tatsächliche Signalvariante und beobachtete Transport-/Verarbeitungsverzögerungen dokumentiert. |
| 6. Integrationsentscheidung | Konkreter Nutzen gegenüber Python benannt | Erst dann LSL-Ausgabe des eigenen Recorders samt Markeradapter und passenden Regressionen entwickeln. |

Als wissenschaftliche MI-Auswertung mit `MI_Bilateral` oder `MI_HandSide` starten; für einen reinen Transporttest ist keine erfolgreiche Klassifikation erforderlich. Ein schwaches MI-Ergebnis sollte zu Signal-/Protokollprüfung führen. Der dokumentierte [Pilot von Protokoll 1.0](ml-feasibility-2026-10-22.md) fand bei seiner einfachen Imagery-Baseline keine überzufällige Leistung und starke Trennbarkeit der ausgeführten Aufgaben allein mit Bewegungssensoren; er validiert Protokoll 2.0 nicht.

## 7. Wann der bestehende Python-Weg günstiger ist

Für reproduzierbare Offline-Auswertungen, unsere komplexen Attempt-Ausschlüsse und CBraMod-/REVE-Experimente ist der vorhandene Weg eng an die Datenverträge angepasst. Für die bestehenden Bewegungsmerkmale spart deren Wiederverwendung außerdem eine zweite numerisch abzugleichende Implementierung.

Die vorhandenen `.npz`-Bewegungsmodelle und CBraMod-/REVE-Checkpoints besitzen keinen im Projekt implementierten OpenViBE-Importer. Ein möglicher Hybrid wäre Python-Inferenz mit Ausgabe von Scores an OpenViBE zur Darstellung; auch dieser Adapter und seine Laufzeit müssten entwickelt und geprüft werden. Eine neue CSP/LDA-Pipeline ist ein anderes Modell und ersetzt diesen Import nicht.

Wenn ausschließlich Liveverarbeitung der vorhandenen Python-Modelle benötigt wird, ist ein direkter LSL-Verbraucher eine naheliegende Alternative. MNE-LSL bietet dafür Streams, Ereignis-Epoching und kausale Filter; es ist ebenfalls eine zusätzliche, hier nicht praktisch geprüfte Integrationsoption. OpenViBE ist besonders attraktiv, wenn die **grafische Pipeline, bedienbare Szenarien oder fertige BCI-Demos** das eigentliche Ziel sind. [MNE-LSL-API](https://mne.tools/mne-lsl/stable/api/index.html), [StreamLSL](https://mne.tools/mne-lsl/stable/generated/api/mne_lsl.stream.StreamLSL.html)

## 8. Quellenstand und durchgeführte Prüfung

- Die Recherche bestätigt OpenViBE **3.6.0 als 2024 veröffentlicht**; derselbe Inria-Bericht nennt damalige Arbeiten an 3.7.0. Daraus folgt keine Aussage zur neuesten stabilen Version am 12.11.2026. Die Projektwebsite war über den Recherchezugang nicht abrufbar; der aktuelle GitLab-Zugriff wurde durch Anubis abgewiesen. Deshalb bleiben aktuelles Installationspaket, Release-Status und enthaltene Treiber vor Ort zu prüfen. [Inria/POTIOC 2024](https://radar.inria.fr/report/2024/potioc/index.html)
- Das Inria-Tutorial 2024 beschreibt einen Windows-Installer sowie Source-Builds für Linux/OSX mit damals noch jungem OSX-Support. Für unseren ohnehin auf Windows laufenden Recorder ist Windows deshalb der naheliegende Pilotstandort. Ein aktueller macOS-Build oder Apple-Silicon-Support wurde nicht geprüft. [Inria-Tutorial](https://neuroergonomics2024.inria.fr/files/2024/06/NEC24_OpenViBE-tutorial_Part1.pdf)
- Geprüft wurden Projektdokumentation, relevante Aufnahme-/Marker-/Merkmalsimplementierungen und die oben verlinkten Hersteller-/Entwicklerquellen. Nur Dokumentation wurde ergänzt; keine Abhängigkeiten, Szenarien oder Aufnahmedaten verändert. Lokale Dokumentlinks und Diff wurden geprüft.
- OpenViBE wurde im Rahmen dieser Untersuchung nicht installiert oder gestartet. Kein Windows-Build, Headsetlauf, Import-Roundtrip, Modellbenchmark oder Latenztest durchgeführt. Der Bericht beschreibt Machbarkeit und offene Abnahmekriterien.
