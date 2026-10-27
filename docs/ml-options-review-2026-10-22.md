# Optionen für EEG-Aufgabenerkennung: erneute Prüfung

Stand: 22.10.2026. Grundlage: lokale Daten und Baseline, Original-Repositories, veröffentlichte Modellgewichte und offizielle Datensatz-/Bibliotheksdokumentation. Die Rangfolge unten ist eine Einschätzung der Eignung und des Implementierungsaufwands, kein gemessener Leistungsvergleich. In dieser Recherche wurden keine weiteren Modelle trainiert oder Modellgewichte geladen.

Nachfolgende Umsetzung: Der [erste CBraMod-Vergleich](cbramod-pilot-2026-10-22.md) wurde inzwischen ausgeführt, mit eingefrorenem Encoder, Fine-Tuning des letzten Blocks und zwei Bandpower-Baselines. Der verlinkte Bericht enthält die gemessenen Ergebnisse und Reproduktionsbefehle.

**Empfehlung:** Transfer Learning jetzt als gleichwertigen Entwicklungsweg aufnehmen. Zunächst CBraMod und REVE als eingefrorene Merkmalsextraktoren sowie mit begrenztem Fine-Tuning prüfen. Für Imagery zusätzlich ein kleines EEGNet auf passenden öffentlichen Hand-/Fußdaten vortrainieren und auf P-001 anpassen. Die bereits vorhandene klassische Baseline bleibt der Vergleichsmaßstab.

## 1. Ausgangslage und Aussagegrenzen

Im Aufnahmeordner liegt weiterhin eine Sitzung von P-001: acht EEG-Kanäle, 250 Hz, ca. 38 Minuten, 60 Motorik-, 40 Imagery- und zwölf Kopfrechen-Trials. Die vorgesehene Unicorn-Montage ist Fz, C3, Cz, C4, Pz, PO7, Oz, PO8. Der Viewer verwendet diese Reihenfolge; die CSV selbst nennt lediglich EEG 1–8. Die tatsächlich verwendete Verkabelung/Positionierung muss mit dem Aufbau übereinstimmen, bevor räumliche Modellinformationen verwendet werden.

Die bestehende Ridge-/Bandpower-Baseline erzielte blockweise getrennt 66,7 % Balanced Accuracy für Motorik, 47,5 % für Imagery und 58,3 % für Rechnen gegen spätes Rest. IMU allein erreichte 96,7 % für Motorik. Das sind Ergebnisse einer einfachen Pipeline, keine Leistungsobergrenze des Datensatzes. Vollständige Ergebnisse: [Baseline-Bericht](ml-feasibility-2026-10-22.md), [JSON](../analysis/results/ml_feasibility_P001.json).

Der bisherige Test verwendet bekannte Aufgabenfenster. Er prüft weder unbekannte Personen noch neue Sitzungen oder die kontinuierliche Erkennung unbekannter Aufgabenbeginne. Verschiedene Hauptläufe sind zeitlich getrennt: Ein Sechsklassen-Modell kann dadurch Lauf-/Zeitunterschiede ausnutzen. Alle sechs Aufgaben lassen sich technisch gemeinsam trainieren, aber diese Sitzung trennt neuronale Aufgabeninformation nicht eindeutig von diesem Zusammenhang.

## 2. Trainingsstrategien

| Strategie | Was wird gelernt? | Eignung jetzt |
|---|---|---|
| Klassisches ML | Kleine Klassifikatoren auf Bandpower, CSP- oder Kovarianzmerkmalen | Sofort sinnvoll; schnelle, kontrollierbare Referenz |
| Kleines Netz von Grund auf | Alle Gewichte z. B. von EEGNet oder ShallowFBCSPNet | Sinnvoller Vergleich, aber datenknapp |
| Eingefrorener vortrainierter Encoder | Nur neuer Klassifikationskopf auf vortrainierten Merkmalen | Sehr guter erster Transfer-Versuch |
| Teilweises Fine-Tuning | Kopf und ausgewählte letzte Schichten | Direkt als zweite Transfer-Variante testen |
| Adapter / LoRA | Kleine zusätzliche Anpassungsmatrizen/-module | Möglich; zusätzliche Integration und Modellwahl nötig |
| Vollständiges Fine-Tuning | Alle vortrainierten Gewichte | Möglich, bei 40 Imagery-Trials hohe Varianz zu erwarten |
| Aufgabenbezogenes Vortraining auf öffentlichen Daten | Kleines oder vortrainiertes Netz lernt zuerst ähnliche Aufgaben | Besonders interessant für Hände/Füße |
| Selbstüberwachtes Weitertraining | Rekonstruktion/Maskierung ohne Aufgabenlabels | Mit mehr eigenen Sitzungen interessanter; 38 Minuten sind wenig zusätzliche Vielfalt |
| Klassisches Transfer Learning | Anpassung von Kovarianzverteilungen zwischen Personen/Sitzungen | Alternative ohne großes Netz |
| Ensemble / multimodale Fusion | Kombination von Modellen oder EEG und IMU | Nach Einzelmodellen prüfen; keine Lösung für fehlerhafte Testaufteilungen |

Ein eingefrorener Encoder plus neuem Kopf ist Transfer Learning beziehungsweise Linear Probing, sofern der Kopf linear ist. Das ist noch kein Fine-Tuning des Encoders. Alle Varianten lassen sich auf denselben unabhängigen Testblöcken vergleichen. LoRA verringert die Zahl trainierbarer Parameter, beweist aber keinen Vorteil für diese EEG-Daten. [PEFT/LoRA-Dokumentation](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora).

CSP ist in MNE verfügbar; Kovarianzklassifikation und Transfer-Verfahren stehen in pyRiemann bereit. Eine mögliche klassische Pipeline ist geschrumpfte Kovarianz → Tangentialraum → regularisierte logistische Regression. Zentrierung/Ausrichtung zwischen Datensätzen ist ebenfalls möglich, muss aber auf den erlaubten Trainings-/Kalibrierungsdaten geschätzt werden. [MNE CSP](https://mne.tools/stable/generated/mne.decoding.CSP.html), [pyRiemann Transfer](https://pyriemann.readthedocs.io/en/latest/generated/pyriemann.transfer.TLRotate.html).

## 3. Konkret verfügbare vortrainierte Modelle

### CBraMod: erster Kandidat für einen kompakten Versuch

- Originalcode und veröffentlichte Gewichte vorhanden; der Braindecode-Checkpoint umfasst ungefähr 4,92 Mio. Parameter.
- Der Originalencoder verarbeitet die Form Batch × Kanäle × Zeitsegmente × 200 Samples. Die Kanalzahl wird im Forward-Pass aus der Eingabe gelesen. Damit ist eine Eingabe mit acht Kanälen strukturell plausibel; ein tatsächlicher Checkpoint-Lauf mit unseren Daten steht aus.
- Die übliche Verarbeitung verwendet 200 Hz und 1-s-Patches. Unser 3-s-Fenster lässt sich nach echtem Resampling als 8 × 3 × 200 darstellen.
- Das offizielle Klassifikationsbeispiel enthält einen großen, auf 22 Kanäle und vier Sekunden zugeschnittenen Kopf. Diesen müssen wir ersetzen; für uns zunächst Pooling und ein kleiner regularisierter Kopf. Die Kanalreihenfolge bleibt relevant.
- Autoren-Checkpoint auf Hugging Face mit Apache-2.0 ausgewiesen; Code und konvertierter Checkpoint haben eigene Lizenzangaben. Für reproduzierbare Experimente konkrete Quelle und Revision speichern.

Quellen: [Originalcode](https://github.com/wjq-learning/CBraMod), [Encoder](https://github.com/wjq-learning/CBraMod/blob/main/models/cbramod.py), [Originalgewichte](https://huggingface.co/weighting666/CBraMod), [Braindecode-Gewichte](https://huggingface.co/braindecode/cbramod-pretrained).

### REVE: besonders interessant wegen der räumlichen Eingabe

- Veröffentlichtes Modell `brain-bzh/reve-base`, etwa 69,2 Mio. Parameter und ca. 277 MB Repositoryumfang.
- Eingabe enthält Signal und Elektrodenkoordinaten; die Architektur ist auf verschiedene Kanalzahlen und Anordnungen ausgelegt. Vorgabe: 200 Hz.
- Die Autoren veröffentlichen ein Fine-Tuning-Tutorial für EEGMAT, also mentales Rechnen. Das erleichtert den Einstieg, garantiert aber keinen Transfer auf unseren Ablauf.
- Für den ersten Versuch Merkmale einmal extrahieren und zwischenspeichern. Größeres Modell als CBraMod, aber kein Anlass, sofort umfangreiches eigenes Pretraining zu betreiben.
- Eigene REVE Responsible Use License; die Model Card beschreibt Nutzung und Veröffentlichung angepasster Modelle unter ihren Bedingungen. Keine Kontoanmeldung oder Lizenzannahme wurde hier durchgeführt.

Quellen: [Model Card und Gewichte](https://huggingface.co/brain-bzh/reve-base), [Projekt mit Tutorial](https://brain-bzh.github.io/reve/).

### EEGPT: weiterhin geeignet, mit genauer Eingabeanpassung

- Autoren veröffentlichen einen ungefähr 10-Mio.-Parameter-Checkpoint und Skripte für Linear Probing und Fine-Tuning.
- Der veröffentlichte Checkpoint wurde mit 58 Kanälen, 256 Hz, vier Sekunden und 64-Sample-Patches vortrainiert.
- Im Originalcode wurden alle acht vorgesehenen Unicorn-Namen im `CHANNEL_DICT` gefunden. Das sind gültige Kanal-IDs; es ist kein Nachweis guter Erkennung mit acht Elektroden.
- Encoder-Abmessungen müssen zur konfigurierten Kanal- und Patchzahl passen. Unser 3-s-Fenster wäre bei 256 Hz 768 Samples lang. Diese Konfiguration ist vor dem Benchmark mit dem Checkpoint zu prüfen. Keinesfalls drei Sekunden durch zeitliches Strecken in vier Sekunden verwandeln: Das würde Frequenzen verändern.
- Die Kanalzahl beim Pretraining ist keine pauschale Anforderung, 58 echte Elektroden nachzuliefern. Gleichzeitig sollte eine mögliche Anpassung nicht als bereits erfolgreich erprobt dargestellt werden.

Quellen: [Originalrepository mit Checkpoint-Link](https://github.com/BINE022/EEGPT), [Kanal-IDs und Encoder](https://github.com/BINE022/EEGPT/blob/main/downstream/Modules/models/EEGPT_mcae_finetune.py).

### LaBraM: geeigneter weiterer Vergleich

- Originalgewichte und Braindecode-Konvertierung veröffentlicht; konvertierter Base-Checkpoint etwa 5,82 Mio. Parameter.
- 200-Hz-Verarbeitung; Auswahl gelernter Positionsinformationen anhand der Elektrodennamen.
- Alle acht vorgesehenen Unicorn-Namen stehen in der ursprünglichen Kanalliste. Unsere acht gemessenen Kanäle können daher grundsätzlich als Teilmenge adressiert werden, statt fehlende Kanäle als Messungen zu erfinden.
- Patchverarbeitung, Amplitudenskalierung und Checkpoint-Konvertierung sind vor einem Leistungsvergleich zu prüfen.

Quellen: [Originalrepository](https://github.com/935963004/LaBraM), [Kanalliste](https://github.com/935963004/LaBraM/blob/main/utils.py), [veröffentlichter Base-Checkpoint](https://huggingface.co/braindecode/labram-pretrained).

### Weitere verfügbare Kandidaten

| Modell | Was dafür spricht | Warum zunächst zweite Reihe |
|---|---|---|
| LUNA | Verschiedene Elektrodenanordnungen; Base-Variante ca. 7 Mio. Parameter | Model Card erlaubt interne Anpassung, schränkt die Weitergabe modifizierter Gewichte ein; anderer Schwerpunkt der veröffentlichten Aufgaben |
| BENDR | Etablierter selbstüberwachter Encoder; Gewichte veröffentlicht | Standard-Checkpoint verwendet ein festes Eingangsschema; mehr Montageanpassung bei acht Kanälen |
| BIOT | Flexible Architektur und mehrere veröffentlichte Checkpoints | Verfügbare Gewichte verwenden überwiegend konkrete bipolare Ableitungen aus klinischen/Schlafdaten; diese sind nicht mit unseren acht referenzierten Kanälen gleichzusetzen |
| BrainOmni | Gemeinsame Verarbeitung von EEG und MEG; Tiny/Base-Gewichte veröffentlicht | Für spätere EEG–MEG-Fragen interessant; derzeit keine lokalen MEG-Daten, zusätzlicher Integrationsaufwand |
| ZUNA / ZUNA1.1 | Rekonstruktion und Entrauschung bei unterschiedlichen Montagen | Kein fertiger Aufgabenklassifikator; generierte Kanäle sind Schätzungen und keine neuen Messungen |

Quellen: [LUNA](https://huggingface.co/PulpBio/LUNA), [BENDR-Originalrepository](https://github.com/SPOClab-ca/BENDR), [BIOT-Originalrepository und Ableitungen](https://github.com/ycq091044/BIOT), [BrainOmni](https://github.com/OpenTSLab/BrainOmni), [ZUNA](https://github.com/Zyphra/zuna).

Diese Auswahl deckt die wesentlichen praktisch unterschiedlichen Wege ab; sie ist keine Behauptung, jedes veröffentlichte EEG-Modell aufgelistet oder getestet zu haben. Architektur vorhanden, Gewichte veröffentlicht, lokal ladbar und auf unseren Daten nützlich sind vier verschiedene Nachweisstufen. Insbesondere ist `braindecode/EEGNet` ein Architekturangebot ohne mitgelieferte vortrainierte Gewichte. [EEGNet-Model-Card](https://huggingface.co/braindecode/EEGNet/blob/main/README.md).

## 4. Öffentliche Daten als besonders wertvolle zusätzliche Möglichkeit

### Motorik und Imagery

PhysioNet EEG Motor Movement/Imagery enthält 64-Kanal-Daten bei 160 Hz mit tatsächlich ausgeführten und vorgestellten Bewegungen beider Hände beziehungsweise Füße. Das ist für unsere beidseitigen Aufgaben näherliegend als ausschließlich Links-/Rechtshand-Daten. Die konkreten Bewegungen unterscheiden sich jedoch: Fäuste öffnen/schließen ist nicht Unterarme heben. Außerdem unterscheiden sich Cue-Anordnung, Messgerät und Referenzierung.

Vorgehen: geeignete Runs auswählen → Aufgabenlabels pro Run korrekt zuordnen → gemeinsame echte Elektroden auswählen → kleines EEGNet vortrainieren → Kopf/letzte Schichten mit eigenen Trainingstrials anpassen. Daten von externen Personen für Quelltraining/Validierung trennen; P-001-Testblöcke erst für die festgelegte Auswertung verwenden. Die tatsächlichen Kanalnamen der geladenen EDF-Dateien prüfen.

Weibo2014 bietet ebenfalls beide Hände, Füße und Rest als Imagery-Bedingungen. BNCI2014_001/BCI-IV-2a ist ein nützlicher Benchmark, hat aber andere Klassen und ist kein gleichwertiger Ersatz für unser Paradigma.

Quellen: [PhysioNet Originaldatensatz](https://physionet.org/content/eegmmidb/1.0.0/), [Weibo2014-Dokumentation](https://moabb.neurotechx.com/docs/generated/moabb.datasets.Weibo2014.html).

### Kopfrechnen

Shin2017B bietet Subtraktion und ausdrücklich angeleitete Ruhe-Trials für 29 Personen. Das Aufgabenparadigma ist verwandt, aber die Montage hat viele andere Positionen; in der dokumentierten Liste sind Cz und Pz gemeinsame EEG-Positionen, Fz ist dort Ground. Unser Rest ist Erholung nach Rechnen, kein eigenständiger randomisierter Ruhe-Trial. Ein direktes Zusammenwerfen der Labels wäre methodisch schwach.

EEGMAT bietet Aufnahmen vor und während seriellen Rechnens und einen Einstieg über das REVE-Tutorial. Auch hier sind Blockstruktur, Aufgabe und Aufnahmebedingungen gesondert abzugleichen. Das ist eine Quelle für Transfer, kein Beleg für ein fertiges Modell unseres Rechenprotokolls.

Quellen: [Shin2017B](https://moabb.neurotechx.com/docs/generated/moabb.datasets.Shin2017B.html), [EEGMAT](https://physionet.org/content/eegmat/1.0.0/).

### Innerhalb unserer Daten übertragen

Eine weitere Hypothese lautet: Arme/Beine aus tatsächlicher Bewegung lernen und anschließend an Imagery anpassen. Das nutzt die vorhandene Klassenverwandtschaft, kann aber bewegungsbedingte Artefakte übertragen. Daher nur mit einer separat ausgewerteten Imagery-Testmenge und IMU-Kontrolle. Die geringe eigene Motorik-Datenmenge macht dies zu einer Zusatzanalyse, nicht zur Hauptquelle für Vortraining.

## 5. Modellgestaltung und ergänzende Verfahren

- **Separate Köpfe oder getrennte Modelle:** Motorik, Imagery, Rechnen zunächst getrennt auswerten. Ein gemeinsamer Encoder mit drei Köpfen ist später möglich; ein zur Laufzeit vorgegebener Hauptlauf zählt dann als zusätzliche Systeminformation.
- **Multimodal:** EEG-only, IMU-only und EEG+IMU vergleichen. Für praktische Bewegungserkennung kann Fusion sinnvoll sein; bei Imagery IMU vorrangig als Kontrolle auf ungewollte Bewegung verwenden.
- **Zeitlicher Ablauf:** Fenster-Vorhersagen mit Glättung und Ablehnungsentscheidung kombinieren. Auf unbekannten Ruhe-/Übergangsphasen Fehlalarme pro Minute und Latenz messen, nicht nur die Genauigkeit ausgeschnittener Trials.
- **Few-shot-Personalisierung:** Bei neuen Sitzungen einen vorab definierten Kalibrierungsblock zur Anpassung verwenden; auf dem restlichen Termin testen. Ein eigener Weg zwischen vollständig personenspezifischem Training und Nutzung ohne Kalibrierung.
- **Augmentation:** Nur plausible Veränderungen wie geringe Rauschbeimischung oder kleine zeitliche Verschiebungen innerhalb der Aufgabe verwenden. Keine Klassen durch Links-/Rechtstausch oder große Frequenzverschiebungen unbeabsichtigt verändern. Alle Ableitungen eines Trials bleiben im selben Fold.
- **Selbstüberwachte Anpassung:** Unbeschriftete Trainingsabschnitte können helfen. Wenn dafür Testaufnahmen verwendet werden, ist die Evaluation transduktiv und muss ausdrücklich so bezeichnet werden; für den primären Test bleiben sie ausgeschlossen.
- **Ensembles und Distillation:** Nach einem nachgewiesenen Gewinn mehrerer Modelle beziehungsweise eines großen Encoders interessant. Mit nur wenigen Testtrials können zusätzliche Kombinationsparameter leicht auf den Test optimiert werden.
- **Generische Zeitreihen-/Bildmodelle:** Technisch auf Rohzeitreihen oder numerische Spektrogramme anwendbar. Gegenüber EEG-spezifischen Gewichten kein belegter Vorteil für uns; mit wenigen Trials zunächst geringe Priorität. Screenshots mit Cue-Texten oder Achsenbeschriftungen wären ungeeignete Eingaben.
- **Zero-shot:** Ein vortrainierter Merkmalsextraktor liefert ohne passenden Klassifikationskopf keine automatische semantische Zuordnung zu unseren sechs Aufgaben. Dafür müsste eine passende bereits gelernte Aufgabenentscheidung oder eine gesondert validierte Zuordnung vorhanden sein.
- **Neue Paradigmen:** SSVEP/P300 wären alternative zukünftige BCI-Experimente. Die erforderlichen Stimuli wurden hier nicht systematisch erhoben; die bestehenden Aufgaben lassen sich nicht nachträglich zu einem solchen Datensatz umetikettieren.

## 6. Gemeinsame Anforderungen für einen fairen Vergleich

1. Eingabevertrag festlegen: echte Elektrodennamen und Reihenfolge, µV versus V, Referenzierung, physische Fenstergrenzen, Resampling und Labeldefinition. Beim 250→200/256-Hz-Resampling bleibt die reale Dauer erhalten.
2. Baseline und Transfer zunächst auf gleichen 3-s-Aufgabenfenstern vergleichen. Falls ein Checkpoint eine andere Dauer erzwingt, Vergleichsbaseline auf exakt denselben Fenstern erneut auswerten und als eigene Analyse kennzeichnen. Kein Auffüllen mit Nachaufgabenzeit nur für ein Modell.
3. Alle Modelle auf denselben äußeren Blöcken testen. Hyperparameter, Early Stopping, Kanalwahl und Normalisierungen nur in den Trainingsblöcken bestimmen. Wegen der kleinen Blockzahl nur wenige vorab definierte Konfigurationen verwenden.
4. Ergebnisse aller festgelegten Kandidaten und Zufallsseeds berichten. Beste Testwerte aus vielen Experimenten sind keine unabhängige Bestätigung. Vortraining-Überlappung mit öffentlichen Benchmark-Testpersonen prüfen, wenn solche Benchmarks berichtet werden.
5. Bewegungssensoren als separate Kontrolle; Cue-/Zeitmetadaten nicht als EEG-Eingabe. Artefaktbereinigung als eigene Analyse dokumentieren: Blinzeln ist bei Motorik selbst eine Zielklasse und würde durch aggressives Entfernen von Augenaktivität verändert.
6. Beste Pipeline auf einer neuen Sitzung prüfen. Die bisherige Sitzung bleibt Entwicklungsdatenbasis. Personenübergreifende Aussagen benötigen entsprechend vollständig neue Personen.

## 7. Aufwand auf dem vorhandenen Rechner

Lokal erkannt: Apple M3, 16 GiB RAM. In `~/.venvs/eeg-mne` sind MNE, NumPy, SciPy und pandas vorhanden; PyTorch, Braindecode, scikit-learn und pyRiemann fehlen. Eine getrennte ML-Umgebung wäre sinnvoll.

Klassische Modelle und gespeicherte Encodermerkmale sind plausible lokale Einstiegswege. Für CBraMod/LaBraM und REVE-Inferenz sollte ein kleiner Batch zunächst auf CPU beziehungsweise unterstütztem Apple-Backend geprüft werden; Laufzeit und Speicherverbrauch wurden hier nicht gemessen. Vollständiges Fine-Tuning und wiederholtes externes Vortraining können auf einer GPU praktischer sein. Ein kostenpflichtiger Cloud-Lauf ist für die erste Machbarkeitsprüfung nicht vorausgesetzt.

## 8. Priorisierte Entscheidung

| Priorität | Experiment | Erkenntnisgewinn |
|---|---|---|
| 1 | CBraMod eingefroren + kleiner Kopf, danach letzte Schichten anpassen | Schneller konkreter Test, ob vortrainierte EEG-Muster helfen |
| 1 | REVE eingefroren + kleiner Kopf | Vergleich mit expliziten Elektrodenkoordinaten; passender Einstieg für Kopfrechnen |
| 1 | Bestehende Bandpower-Baseline, ergänzt um CSP oder Kovarianzpipeline | Prüft, ob der Transfer die zusätzliche Komplexität rechtfertigt |
| 2 | EEGNet auf öffentlichen bilateralen Hand-/Fußdaten vortrainieren und anpassen | Aufgabenbezogener Transfer speziell für Imagery |
| 2 | EEGPT oder LaBraM als weiterer Encoder | Robustheit der Schlussfolgerung gegenüber der Modellfamilie |
| 3 | LoRA, LUNA, Ensemble, eigene selbstüberwachte Anpassung | Erweiterungen, falls die ersten Vergleiche einen konkreten Bedarf zeigen |
| Später | BrainOmni mit echten MEG-Daten, kontinuierliche Erkennung, große eigene Netze | Neue Projektziele beziehungsweise deutlich erweiterte Datenbasis |

Die Rangfolge bevorzugt eine überschaubare Zahl verschiedener Hypothesen. Sie setzt nicht voraus, dass die klassischen Verfahren zuerst vollständig abgearbeitet werden. Fine-Tuning ist bereits jetzt sinnvoll testbar; seine Überlegenheit gegenüber einem eingefrorenen Encoder oder einem kleinen klassischen Modell bleibt eine empirische Frage.


## Ergänzung vom 23.10.2026

Der [REVE-Pilot](reve-pilot-2026-10-23.md) ist abgeschlossen: Rechnen gegen Ruhe erreicht mit eingefrorenem Encoder und beim Finetuning des letzten Blocks jeweils 54,2 % Balanced Accuracy. CBraMod bleibt mit 77,8 % beim bisherigen Finetuning der aussichtsreichere Kandidat für die Prüfung an einem neuen Aufnahmetag. Beide Ergebnisse stammen aus derselben kleinen Sitzung.
