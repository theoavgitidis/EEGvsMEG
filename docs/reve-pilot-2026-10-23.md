# REVE-Vergleich: Rechnen gegen Ruhe

Historischer Ergebnisbericht zur seriellen Rechenaufgabe von Protokoll 1.0. Die neue einzelne Subtraktion in [Protokoll 2.0](experiment-protocol.md) ist eine andere Bedingung und wurde hier nicht untersucht.

Stand: 23.10.2026. Der lokale Vergleich ist abgeschlossen. In dieser festgelegten Konfiguration liefert REVE keinen Vorteil gegenüber CBraMod oder Bandpower. CBraMod bleibt der aussichtsreichere Kandidat für eine Prüfung an einem neuen Aufnahmetag.

## Ergebnisse

Balanced Accuracy über außerhalb des Trainings gehaltene Blöcke, eine Person und eine Sitzung. Zufallsniveau: 50 %. Neuronale Ergebnisse sind Mittelwerte aus drei Trainingsinitialisierungen, keine drei unabhängigen Stichproben.

| Verfahren | Balanced Accuracy | Spanne der drei Initialisierungen |
|---|---:|---:|
| Bandpower, ursprüngliche Vorverarbeitung | 58,3 % | – |
| Bandpower, gemeinsame Modell-Vorverarbeitung | 62,5 % | – |
| CBraMod, eingefrorener Encoder | 76,4 % | 75,0–79,2 % |
| CBraMod, letzter Block nachtrainiert | 77,8 % | 70,8–83,3 % |
| REVE, eingefrorener Encoder | 54,2 % | 50,0–58,3 % |
| REVE, letzter Block nachtrainiert | 54,2 % | 50,0–58,3 % |

REVE erreicht für Seeds 11/22/33 jeweils 54,2/58,3/50,0 %. Beide Trainingsvarianten ergeben dieselben diskreten Testvorhersagen. Die Gewichte wurden beim Finetuning tatsächlich aktualisiert (L2-Änderung je äußerem Fold 0,057–0,108); beim eingefrorenen Encoder blieb die Änderung exakt null. Gleiche Vorhersagen bedeuten hier nicht identische trainierte Modelle.

Das ist ein Befund für diesen Pilotaufbau. Es belegt weder eine allgemeine Überlegenheit von CBraMod noch die grundsätzliche Untauglichkeit von REVE. Vollständiges Finetuning, LoRA, andere Köpfe oder in inneren Folds ausgewählte Skalierungen wurden nicht getestet. Nach Sichtung dieses Ergebnisses wurden keine weiteren Einstellungen auf den Testblöcken optimiert.

## Daten und Vergleichbarkeit

- Aufnahme: `P-001/session_20261021_194704.csv`, 12 Rechenaufgaben mit jeweils einer zugehörigen Ruhephase, 24 Fenster in drei Blöcken.
- Exakt dieselben Fenster und dieselben inneren/äußeren Blockaufteilungen wie beim CBraMod-Pilot; automatisch abgeglichen.
- Drei Sekunden pro Fenster, Aufgabenbeginn +0,5 bis +3,5 Sekunden; Ruhefenster 3,5 bis 0,5 Sekunden vor Ruheende. Aufgabe und Ruhe desselben Trials bleiben immer zusammen.
- CAR über acht Kanäle, fensterweiser Butterworth-Bandpass 0,3–40 Hz, Resampling 250 auf 200 Hz. Filterung ist offline und nicht kausal.
- Angenommene Montage: Fz, C3, Cz, C4, Pz, PO7, Oz, PO8. Alle Positionen wurden im offiziellen Position Bank gefunden. Die tatsächliche Elektrodenanordnung wurde nicht unabhängig bestätigt.
- REVE erhält µV/1000. Dies entspricht der offiziellen Mental-Arithmetic-Konfiguration; der gemeinsame Datenlader liefert µV/100, weshalb der REVE-Adapter nochmals durch 10 teilt. Die Vorverarbeitung ist dadurch ausdrücklich dokumentiert, nicht vollständig identisch mit CBraMod.
- REVE verwendet native Patches von 200 Samples mit Schrittweite 180. Von 600 Eingabesamples werden die ersten 560 direkt von den drei Patches erfasst; die letzten 0,2 Sekunden sind nicht direkt enthalten. Durch die vorherige Offline-Filterung kann der Fensterrand trotzdem Einfluss haben. Es wird kein zukünftiger Abschnitt angehängt.

## Modell und Training

REVE-base hat 69.189.632 Parameter. Die ersten 21 Transformer-Blöcke bleiben eingefroren; ihre pro Fenster berechneten Merkmale werden zwischengespeichert. Der Cache wurde numerisch gegen einen vollständigen Modellvorlauf geprüft. Es werden dabei keine über Fenster geschätzten Statistiken angepasst.

Der Klassifikationskopf mittelt zeitlich pro Kanal, verwendet LayerNorm ohne trainierbare affine Parameter und eine lineare Schicht auf den acht verketteten Kanalrepräsentationen. Das entspricht dem Kopfprinzip des CBraMod-Piloten. Der offizielle REVE-Downstream-Code verwendet auch andere Pooling-Varianten; dieser Pilot reproduziert nicht dessen vollständiges veröffentlichtes Trainingsrezept.

- Eingefrorene Variante: 8.194 trainierbare Kopfparameter.
- Finetuning: 3.148.290 trainierbare Parameter einschließlich letztem Transformer-Block.
- Seeds 11, 22, 33; höchstens 20 Epochen; AdamW, Lernraten Kopf 0,001 / letzter Block 0,00001; Weight Decay 0,01; Batchgröße 16; Gradient Clipping 1.
- Je äußerem Testblock dient ein anderer Block der inneren Validierung. Die Epoche mit minimaler Validierungs-Cross-Entropy wird gewählt. Anschließend wird frisch initialisiert und auf beiden äußeren Trainingsblöcken für diese Epochenzahl neu trainiert.
- Der äußere Testblock wird erst danach ausgewertet. Insgesamt 18 äußere neuronale Fits, zuzüglich innerer Auswahl und sechs abschließender Forschungsmodelle auf der gesamten Sitzung.
- Alle sechs abschließenden Modelle sind ausschließlich für spätere externe Tests gedacht. Ihre Trainingsleistung geht nicht in obige Tabelle ein.

## Nachvollziehbarkeit und Prüfungen

Ergebnisse: [results.json](../analysis/results/reve_P001_v1/results.json). Einzelvorhersagen: [predictions.csv](../analysis/results/reve_P001_v1/predictions.csv). Konfiguration und Prüfsummen: [config.json](../analysis/results/reve_P001_v1/config.json). Aufteilungen und Lernkurven: [folds.json](../analysis/results/reve_P001_v1/folds.json). Audit: [audit.json](../analysis/results/reve_P001_v1/audit.json).

Acht automatisierte Tests bestanden: Daten-/Paarintegrität, Resampling, Isolation der Testdaten, eingefrorene bzw. aktualisierte Gewichte und REVE-Eingabeskalierung. Zusätzlich wurden Kennzahlen aus Einzelvorhersagen erneut berechnet und Quellcode-Hashes sowie Übereinstimmung mit den bisherigen Fenster-/Folddefinitionen geprüft. Ein gespeichertes REVE-Modell wurde erfolgreich geladen und auf bekannten Fenstern ausgeführt; dieser Funktionstest auf Trainingsdaten ist keine externe Evaluation.

Der Benchmark benötigte lokal rund 10 Sekunden auf der CPU nach Download und Installation. Die eingefrorenen Merkmale werden einmal berechnet; das ist keine Laufzeitangabe für vollständiges Training aller 69 Millionen Parameter.

```bash
# Python 3.13; für eine frische Umgebung:
python3.13 -m venv ~/.venvs/eeg-reve
~/.venvs/eeg-reve/bin/python -m pip install -r analysis/requirements-reve.lock.txt
~/.venvs/eeg-reve/bin/python -m analysis.download_reve
~/.venvs/eeg-reve/bin/python -m unittest analysis.test_reve_pipeline analysis.test_ml_pipeline -v
~/.venvs/eeg-reve/bin/python -m analysis.reve_benchmark \
  ../recordings/P-001/session_20261021_194704.csv \
  --output analysis/results/reve_P001_reproduction
```

Die tatsächliche Ausführung nutzte `~/.venvs/eeg-ml/bin/python`. Transformers 4.56.2 wurde ergänzt; dessen Abhängigkeit setzt Hugging Face Hub auf 0.36.2. Der ursprüngliche CBraMod-Lockfile bleibt erhalten, der neue Umgebungsstand steht separat in `requirements-reve.lock.txt`.

Für eine neue Sitzung mit demselben Ereignisformat:

```bash
~/.venvs/eeg-ml/bin/python -m analysis.reve_predict NEW_SESSION.csv \
  --model analysis/results/reve_P001_v1/checkpoints/Kognitiv_finetune_last_block_seed11.pt \
  --output analysis/results/reve_new_session_predictions.csv
```

Dies ist ereignisgestützte Offline-Klassifikation. Kontinuierliche Erkennung von Aufgabenbeginn und -ende wurde nicht implementiert.

## Folgerung

Als nächsten Datentest CBraMod mit festgelegten Einstellungen an einem neuen Aufnahmetag prüfen; Bandpower und REVE können als unveränderte Vergleichsmodelle mitlaufen. Bei zwölf Paaren in einer Sitzung sind die bisherigen Zahlen explorativ. Bildschirmdarstellung, zeitliche Abfolge und Artefakte können die Unterscheidung beeinflussen. Eine allgemeine Erkennung von Konzentration, anderen Personen oder neuen Tagen ist damit noch nicht belegt.

## Primärquellen und eingefrorene Versionen

- [REVE-base](https://huggingface.co/brain-bzh/reve-base/tree/dc2a075c287bb2f6c04ee5875bd79535a0f7dba6), Revision `dc2a075c287bb2f6c04ee5875bd79535a0f7dba6`.
- [REVE Position Bank](https://huggingface.co/brain-bzh/reve-positions/tree/befa5b57a455b77cf302daf610c2e9ed8140bace), Revision `befa5b57a455b77cf302daf610c2e9ed8140bace`.
- [Offizielle Skalierung für Mental Arithmetic](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/configs/task/stress.yaml), [Datenlader](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/downstream_tasks/dataloaders.py) und [Vorverarbeitung in µV](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/preprocessing/preprocessing_stress.py).

Die Modellquellen wurden gelesen; geladen werden ausschließlich lokale, per SHA256 geprüfte Snapshots. Gewichte liegen im Hugging-Face-Cache, Modelle und große Checkpoints sind vom Git-Tracking ausgeschlossen. Es wurden keine EEG-Daten hochgeladen.
