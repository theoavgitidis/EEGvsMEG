# CBraMod-Pilot: ausgeführter Vergleich vom 22.10.2026

**Der erste Transfer-Learning-Vergleich ist vollständig ausgeführt.** CBraMod liefert in dieser Sitzung für Kopfrechnen gegen Erholung höhere deskriptive Werte als die Bandpower-Pipelines. Motorik und Imagery profitieren in dieser Konfiguration nicht. Ein belastbarer Vorteil des Fine-Tunings gegenüber dem eingefrorenen Encoder ist nicht nachgewiesen.

## Ergebnisse auf zurückgehaltenen Blöcken

Balanced Accuracy, also mittlere Trefferquote über die Klassen. CBraMod-Werte sind Mittelwerte über drei festgelegte Trainingsseeds 11, 22, 33. Diese Seeds verwenden dieselben Testtrials und stellen **keine drei unabhängigen Stichproben** dar.

| Aufgabe | Zufall | Bisherige Bandpower | Bandpower mit CBraMod-Vorverarbeitung | CBraMod eingefroren | Letzter Encoderblock fine-getunt |
|---|---:|---:|---:|---:|---:|
| Arme / Beine / Blinzeln, 60 Trials | 33,3 % | 66,7 % | 66,7 % | 55,0 % | 56,7 % |
| Arm- / Beinvorstellung, 40 Trials | 50,0 % | 47,5 % | 62,5 % | 54,2 % | 51,7 % |
| Kopfrechnen / spätes Rest, 12 Trial-Paare | 50,0 % | 58,3 % | 62,5 % | 76,4 % | 77,8 % |

### Schwankung über Trainingsseeds

| Aufgabe | Eingefroren: Minimum–Maximum | Fine-Tuning: Minimum–Maximum |
|---|---:|---:|
| Motorik | 45,0–63,3 % | 53,3–58,3 % |
| Imagery | 50,0–57,5 % | 47,5–57,5 % |
| Kopfrechnen / Rest | 75,0–79,2 % | 70,8–83,3 % |

Diese Bereiche sind keine Konfidenzintervalle. Es wurden keine neuen Signifikanztests für diese Modellvergleiche gerechnet. Alle getesteten Seeds und alle festgelegten Varianten werden berichtet, nicht nur der beste Lauf.

## Bedeutung

- **Kopfrechnen ist der vielversprechendste Transfer-Befund.** Die 24 Fenster stammen allerdings aus nur zwölf Aufgaben-/Ruhepaaren. Es kann sich um aufgabenbezogene Aktivität, unterschiedliche visuelle Anzeige, zeitliche Reihenfolge innerhalb der Paare oder andere Störfaktoren handeln. Das Modell misst keine allgemeine Konzentrationsfähigkeit.
- **Fine-Tuning ist hier nicht klar besser:** Der Mittelwertvorsprung von 1,4 Prozentpunkten gegenüber dem eingefrorenen Encoder ist klein bei dieser Stichprobe und Seed-Streuung.
- **Für Imagery hilft bereits die Vorverarbeitung der klassischen Pipeline.** CAR, Filteränderung und Resampling wurden gemeinsam verändert. Welcher Bestandteil den Unterschied verursacht, wurde nicht getrennt untersucht. 62,5 % sind ein explorativer Wert, kein validierter Nachweis stabiler Imagery-Erkennung.
- **Bei Motorik bleibt die einfache Bandpower-Pipeline stärker.** Die zuvor ermittelten 96,7 % mit Bewegungssensoren allein bleiben ein wichtiger Kontrollbefund. Dieser neue Vergleich nutzt ausschließlich EEG.
- Die Resultate gelten für eine Person und eine Sitzung. Die bestehende Sitzung wurde bereits zur Methodenentwicklung betrachtet; eine neue Sitzung ist für eine Bestätigung erforderlich.

## Daten und Vorverarbeitung

Verwendet: `../recordings/P-001/session_20261021_194704.csv` samt Events und Metadaten. Alle 112 Aufgaben-Trials waren vollständig; keine Attempts wurden ausgeschlossen. Zusätzlich zwölf späte Ruhefenster aus dem Rechenlauf, insgesamt 124 Fenster.

- Aufgaben: 0,5 bis 3,5 s nach `cue_onset`.
- Rechen-Rest: letzte 3,5 bis 0,5 s vor Ende der zugehörigen Erholung.
- Fenster werden gegen die tatsächlichen Phasengrenzen geprüft; keine Auffüllung unvollständiger Aufgaben.
- Alle acht EEG-Kanäle laut Metadaten aktiviert und in µV; zusammenhängender Sampleindex und gültige Samples geprüft.
- Für CBraMod: gemeinsame Durchschnittsreferenz über acht Kanäle, pro Epoche unabhängig Butterworth 5. Ordnung 0,3–40 Hz vorwärts/rückwärts, Polyphasen-Resampling 250→200 Hz, Amplituden geteilt durch 100. Modellform: `(124, 8, 3, 200)`.
- Die Skalierung µV/100 entspricht dem veröffentlichten BCIC-IV-2a-Datenloader der Autoren. Die epochweise bidirektionale Filterung ist unsere festgelegte Offline-Variante; sie reproduziert nicht exakt deren kausale Filterung längerer Trials.
- Bisherige Bandpower-Baseline unverändert mit ursprünglicher Vorverarbeitung neu berechnet. Zweite Bandpower-Pipeline verwendet dieselben verarbeiteten Signale wie CBraMod und trennt damit den Modellvergleich vom Vorverarbeitungswechsel.
- Die Reihenfolge Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 folgt der Projektkonfiguration. Die physische Montage wurde nicht unabhängig nachgemessen; die CSV selbst nennt EEG 1–8.
- Keine automatische Amplitudenausschlussregel, ICA oder neue manuelle Artefaktbewertung. Nach der CBraMod-Vorverarbeitung lag das 99. Perzentil der absoluten Amplitude bei ca. 42 µV, das Maximum bei ca. 1.340 µV. Die Daten sind daher nicht als durchgehend artefaktfrei zu verstehen.

## Modell und tatsächliches Fine-Tuning

Originalimplementierung: [wjq-learning/CBraMod](https://github.com/wjq-learning/CBraMod), Commit `b9e961003214326972c567eff390e75b0287e32a`. Zwei Modelldateien sind unter `analysis/vendor/cbramod/` samt MIT-Lizenz abgelegt. Ein Import wurde auf paketrelativ geändert.

Autoren-Checkpoint: [weighting666/CBraMod](https://huggingface.co/weighting666/CBraMod), Revision `500543c7e30bda1b22bfd51a49301b238dee21fd`, Datei `pretrained_weights.pth`. SHA256: `0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178`. Laden mit `weights_only=True`, Hashprüfung und `strict=True`; keine fehlenden oder unerwarteten Parameter. Das Originalmodell enthält 4.924.000 Parameter einschließlich Rekonstruktionsausgang.

Der Rekonstruktionsausgang wird für Klassifikation nicht verwendet. Die ersten elf Encoderblöcke und das Patch-Embedding bleiben eingefroren im Evaluationsmodus. Ihre Ausgabe wird pro Fenster zwischengespeichert; kein Training oder datensatzübergreifendes Normalisieren beim Caching. Der Cache wurde numerisch gegen den vollständigen Encoder geprüft.

Der Klassifikationskopf mittelt über die drei Zeitsegmente, erhält die acht Kanäle getrennt, normalisiert jedes Beispiel mit parameterfreier LayerNorm und verwendet eine lineare Schicht. Beide CBraMod-Varianten verwenden denselben Kopf.

- Eingefroren: nur Kopf trainiert, 4.803 Parameter für Motorik beziehungsweise 3.202 für binäre Aufgaben.
- Fine-Tuning: letzter Encoderblock plus Kopf, 407.403 beziehungsweise 405.802 trainierbare Parameter.
- Parameteränderungen der letzten Schicht wurden geprüft: exakt null bei der eingefrorenen Variante, positiv bei jedem Fine-Tuning-Fold. Das ursprüngliche Checkpointmodell bleibt unverändert.
- AdamW, Kopf-Lernrate 0,001, Encoder-Lernrate 0,00001, Weight Decay 0,01, Batchgröße 16, Gradient Clipping 1, maximal 20 Epochen.

Die Konfiguration ist ein erster begrenzter Versuch. Teilweise wurde das Maximum von 20 Epochen gewählt; es fand anschließend keine Suche nach besseren Testwerten statt. Andere Köpfe, Lernraten und weitere trainierbare Schichten wurden nicht getestet.

## Datenaufteilung

Für jeden Hauptlauf bleibt jeweils ein vollständiger Block außen für den Test zurück: vier äußere Folds für Motorik und Imagery, drei für Rechnen.

Innerhalb der übrigen Blöcke wird der zyklisch nächste Block als Validierung verwendet. Die Trainingsdauer wird anhand der kleinsten Validierungs-Kreuzentropie gewählt. Danach startet das Modell erneut vom ursprünglichen Checkpoint und trainiert für diese Dauer auf **allen äußeren Trainingsblöcken**. Erst anschließend folgt die Testvorhersage.

Aufgaben- und Ruhefenster eines Rechen-Trials bleiben immer zusammen. Die innere Validierung ist eine einzelne Blockaufteilung, keine vollständige innere Kreuzvalidierung. Insbesondere beim Rechnen bleibt innen nur ein Block für das Training, was die Auswahl instabil machen kann. Keine Testlabels oder Testwerte bestimmen die Trainingsdauer.

## Gespeicherte Ergebnisse und Modelle

Unter [analysis/results/cbramod_P001_v1](../analysis/results/cbramod_P001_v1):

- `results.json`: alle aggregierten Werte, Testblockwerte und Konfusionsmatrizen.
- `predictions.csv`: einzelne Out-of-fold-Vorhersagen mit Seed und Variante.
- `epochs.csv`: Fenster, Trial/Attempt, Block und Samplegrenzen.
- `folds.json`: konkrete Trainings-/Validierungs-/Testindizes, Trainingsverläufe, gewählte Epochen und Gewichtsänderungen.
- `config.json`: Daten-/Codehashes, Checkpointidentität, Paketversionen und vorab festgelegte Konfiguration.
- `completion.json`: Abschluss und gemessene Laufzeit.
- `checkpoints/`: 18 zusätzliche Forschungsmodelle, nach der Auswertung auf allen Fenstern des jeweiligen Hauptlaufs trainiert; drei Seeds × zwei Varianten × drei Hauptläufe. Diese sind nicht die Quelle der berichteten Testwerte und benötigen eine neue Sitzung für eine externe Bewertung. Für sie wurde die mediane innen gewählte Trainingsdauer verwendet. Binärdateien sind von Git ausgeschlossen.

Vollständiger Benchmark nach Installation und Download: ca. **23 Sekunden CPU-Laufzeit** auf dem lokalen Apple M3. Installation, Recherche, Codeentwicklung und Download sind darin nicht enthalten. Einmaliges Caching der unveränderten elf Blöcke reduziert den wiederholten Rechenaufwand stark. PyTorch erkennt MPS, aber dieser reproduzierbare Pilot verwendet CPU und vier Threads.

## Reproduktion

Python 3.13 verwenden. Die erste Einrichtung mit dem systemweiten Python 3.15 scheiterte an fehlenden PyTorch-Wheels; die abgeschlossene Umgebung nutzt 3.13.

```bash
python3.13 -m venv ~/.venvs/eeg-ml
~/.venvs/eeg-ml/bin/python -m pip install -r analysis/requirements-ml.lock.txt
~/.venvs/eeg-ml/bin/python -m analysis.download_cbramod
~/.venvs/eeg-ml/bin/python -m unittest analysis.test_ml_pipeline -v
~/.venvs/eeg-ml/bin/python -m analysis.cbramod_benchmark \
  ../recordings/P-001/session_20261021_194704.csv \
  --output analysis/results/cbramod_P001_repeat
```

Das Ausgabeverzeichnis muss neu sein, damit bestehende Ergebnisse erhalten bleiben. Der Lockfile hält die hier verwendeten Paketversionen fest; andere Plattformen benötigen passende Wheels.

Auf eine spätere vollständige Sitzung anwenden, nach Ersetzen von `NEUE_SITZUNG.csv`:

```bash
~/.venvs/eeg-ml/bin/python -m analysis.cbramod_predict \
  NEUE_SITZUNG.csv \
  --model analysis/results/cbramod_P001_v1/checkpoints/Kognitiv_frozen_encoder_seed11.pt \
  --output analysis/results/new_session_predictions.csv
```

Das Beispiel verwendet einen fest gewählten Seed und ist keine Empfehlung aufgrund seines Testwertes. Die Inferenz verwendet weiterhin bekannte Aufgabenmarker. Softmax-Ausgaben sind nicht kalibriert. Eine Anwendung auf dieselbe Trainingssitzung ist nur ein Funktionstest, kein neuer Leistungsnachweis.

## Prüfung und nächste Entscheidung

Sechs automatisierte Tests bestanden: Invalidierung/unvollständige Trials, Ausschluss zu kurzer Phasen, zusammengehaltene Trial-Paare, disjunkte Datenaufteilungen, Erhaltung von Dauer/Frequenz beim Resampling, tatsächliches Einfrieren/Anpassen und Unabhängigkeit der Modellanpassung von nicht verwendeten Testeingaben. Der vollständige Benchmark schloss ohne Fehler ab.

Als nächste fachliche Schritte bieten sich ein REVE-Vergleich für Rechnen, die unabhängige Prüfung der neuen Imagery-Bandpower-Pipeline sowie ein neuer Messtermin an. Für eine größere Aussage über neuronale Aufgabenerkennung bleiben Artefakt- und Anzeige-Kontrollen nötig. Die aktuelle Evidenz rechtfertigt keine Behauptung einer generell überlegenen Fine-Tuning-Methode.
