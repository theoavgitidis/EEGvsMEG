# Machbarkeit der Aufgabenerkennung mit den vorhandenen Daten

Historischer Ergebnisbericht zu den bisherigen Aufgaben von Protokoll 1.0. Datenumfang und Resultate beziehen sich auf den damaligen Versuch; sie validieren nicht das neue [Versuchsprotokoll 2.0](experiment-protocol.md).

Untersuchung vom 22.10.2026. **Ja: Ein personenspezifischer ML-Prototyp lässt sich trainieren. Ein zuverlässig generalisierendes Modell oder ein Vorteil durch Fine-Tuning ist mit den vorhandenen Daten noch nicht belegt.**

Ergänzung: Die [erneute Prüfung verfügbarer Modelle und Trainingswege](ml-options-review-2026-10-22.md) erweitert die Kandidaten um unter anderem CBraMod, REVE und aufgabenbezogenes Vortraining. Sie empfiehlt Transfer Learning jetzt als gleichwertigen Entwicklungsweg; die unten dokumentierten Baseline-Ergebnisse bleiben unverändert.

## Tatsächlich verfügbare Daten

Untersucht wurde `../recordings/P-001/session_20261021_194704.csv` mit Eventdatei, Phasenplan und Sitzungsmetadaten. Im lokalen Aufnahmeordner liegt genau eine Sitzung einer Personenkennung vor. Die Datei `test_session01.csv` im Repository enthält lediglich Baseline-Marker und wurde nicht als gelabelter Aufgabendatensatz verwendet.

- 574.425 Samples bei 250 Hz; 38:17,7 Minuten Aufnahme, acht EEG-Kanäle in µV sowie Accelerometer/Gyroskop.
- 60 Motorik-Trials: je 20 Arme, Beine und Blinzeln; vier Blöcke.
- 40 Imagery-Trials: je 20 Arm- und Beinvorstellung; vier Blöcke.
- 12 Kopfrechen-Trials; drei Blöcke. Pro Trial wurde zusätzlich ein spätes Ruhefenster aus derselben Erholung extrahiert, somit 24 Fenster aus 12 Trial-Paaren.
- Alle 112 Trials vollständig, keine invalidierten Attempts, keine übersprungenen Trials im Skript. Sampleindex lückenlos; keine nichtendlichen EEG-Werte; Validation Indicator durchgängig 1. Laut Sitzungsmetadaten keine Counter-Unterbrechungen. Das ersetzt keine Signalqualitäts- oder Kontaktprüfung.
- Aufgabenmarker liefern beobachtete Dauern zwischen 3,9 und 10,1 s. Softwaremarker/Samplezähler sind keine unabhängig gemessenen Display-Onsets.

Die vielen Samples sind keine ebenso vielen unabhängigen Trainingsbeispiele. Für Imagery existieren hier nur 40 Aufgabenwiederholungen und nur eine Person an einem Termin.

## Durchgeführter Klassifikationstest

Reproduzierbares Skript: `analysis/ml_feasibility.py`; vollständige Werte und Konfusionsmatrizen: `analysis/results/ml_feasibility_P001.json`.

Ein festgelegter linearer Ridge-Klassifikator (Penalty 10, keine Hyperparametersuche) erhält 40 Merkmale: logarithmische Bandpower in 1–4, 4–8, 8–13, 13–30 und 30–40 Hz für acht Kanäle. Pro Aufgabe wird ein 3-s-Fenster von 0,5 bis 3,5 s nach dem Cue verwendet. Ruhe beim Rechnen: die letzten 3,5 bis 0,5 s vor Ende der Erholung. Einheitliche Fenster verhindern, dass Aufgaben allein anhand ihrer Fensterlänge erkannt werden.

Bandpass 1–40 Hz separat je Epoche; keine gemeinsame Filterung über Trainings-/Testgrenzen. Standardisierung ausschließlich mit Trainingsdaten. Jeweils ein ganzer Block bleibt für den Test zurück; bei Kopfrechnen bleiben Aufgabe und Ruhe desselben Trials zusammen. Keine überlappenden Fenster. Die bidirektionale Filterung ist eine Offline-Auswertung, noch keine geprüfte Echtzeitpipeline.

| Ziel | Unabhängige Aufgaben-Trials | EEG: Balanced Accuracy | Zufallsniveau | Bewegungssensoren allein |
|---|---:|---:|---:|---:|
| Arme / Beine / Blinzeln | 60 | **66,7 %** | 33,3 % | **96,7 %** |
| Arm- / Beinvorstellung | 40 | **47,5 %** | 50 % | 52,5 % |
| Kopfrechnen / spätes Rest | 12 Paare | **58,3 %** | 50 % | 45,8 % |

Balanced Accuracy ist der Mittelwert der Trefferquote je Klasse. Der EEG-Motorikwert schwankt zwischen 46,7 und 93,3 % über die vier Testblöcke; für Imagery zwischen 20 und 70 %. Eine kleine Stichprobe und zeitliche Veränderungen begrenzen die Aussagekraft deutlich.

199 Label-Permutationen, innerhalb der Blöcke beziehungsweise beim Rechnen durch Vertauschen innerhalb der Trial-Paare, dienen als explorative Zufallskontrolle. Motorik-EEG: p=0,005, Imagery-EEG: p=0,615. Die Tests sind nicht für Mehrfachvergleiche korrigiert; p=0,005 ist die kleinste mit 199 Permutationen auflösbare Stufe. Kein unabhängiger Bestätigungsdatensatz. Ein zusätzlicher linearer Klassifikator mit ausschließlich Aufnahmezeit erreicht jeweils nur Zufallsniveau; dies schließt komplexere zeitliche Störfaktoren nicht aus.

Die Bewegungssensoren zeigen, dass die Motorikbedingungen stark über körperliche Signale unterscheidbar sind. Das beweist nicht, dass das EEG-Modell dieselben Merkmale nutzt. Augen-, Muskel- und Elektrodenbewegungsartefakte bleiben jedoch naheliegende Erklärungen. Blinzeln ist ausdrücklich eine Augensignalbedingung. Die EEG-Trefferquote ist daher kein Nachweis reiner neuronaler Aufgabenerkennung.

## Training, Modellentwurf und Fine-Tuning

**Klassische Modelle jetzt:** sinnvoll und direkt ausführbar. Der getestete Bandpower-Klassifikator ist eine erste Baseline. Als nächste festgelegte Vergleichspipelines bieten sich CSP plus regularisierte LDA für Imagery und Kovarianzmerkmale mit Riemannscher Klassifikation an. Modellwahl und Parameter müssen innerhalb der Trainingsblöcke erfolgen; nachträgliches Optimieren auf den hier veröffentlichten Testwerten benötigt neue Bestätigungsdaten.

**Kleines neuronales Netz:** EEGNet lässt sich technisch auf acht Kanäle und feste Zeitfenster anpassen. Die Originalarbeit beschreibt eine kompakte Architektur für mehrere EEG-Paradigmen, aber keinen Erfolgsgaranten für diese Sitzung. Hier wäre das ein explorativer Vergleich; 20 Trials pro Imagery-Klasse bieten wenig Schutz vor Overfitting. [EEGNet, Originalarbeit](https://arxiv.org/abs/1611.08024).

**Fine-Tuning eines vortrainierten EEG-Modells:** technisch prüfbar, gegenwärtig zweite Priorität. EEGPT stellt vortrainierte Repräsentationen und Anpassungsmodule bereit. Die Kompatibilität von Elektrodenpositionen, Kanälen, Referenzierung, Einheiten, Abtastrate, Zeitfenstern und Pretraining-Aufgaben müsste ausdrücklich geprüft werden. Zunächst Encoder einfrieren und nur einen kleinen Klassifikationskopf trainieren; anschließend gegebenenfalls einzelne Schichten anpassen. Ein Checkpoint-Download oder Fine-Tuning wurde in dieser Untersuchung nicht durchgeführt. Die acht Unicorn-Kanäle und unsere beidseitige Arm-/Beinvorstellung entsprechen nicht automatisch dem Pretraining-Szenario. [EEGPT, Originalarbeit](https://proceedings.neurips.cc/paper_files/paper/2024/file/4540d267eeec4e5dbd9dae9448f0b739-Paper-Conference.pdf).

**Großes Modell von Grund auf:** technisch startbar, aber für diese Datenbasis kein sinnvoller erster Ansatz. Zusätzliche Fenster, Augmentation und mehr Epochen ersetzen keine neuen Trials, Termine oder Personen.

## Sinnvolles Ziel und nächster Versuch

1. Zunächst getrennte Ziele verfolgen: Motorik mit drei Klassen; Imagery mit zwei Klassen; Kopfrechnen gegen zugehörige Erholung. Ein gemeinsamer Sechsklassen-Klassifikator könnte hier Motorik, Imagery und Rechnen anhand der getrennten Laufzeiten, Ermüdung oder Signaldrift unterscheiden. Derselbe Durchlauf kann diesen Zusammenhang nicht auflösen.
2. EEG-only als primäres Modell; Bewegungssensoren als separate Kontrollpipeline. Für eine bewusst multimodale Gestenerkennung dürfen EEG und IMU kombiniert werden, die Aussage wäre dann eine andere.
3. Für Imagery die Sensorpositionen und Signalqualität prüfen, insbesondere zentrale Elektroden. Früh- und Spätfenster sowie neuronale Frequenzbereiche als vorab definierte Sensitivitätsanalysen vergleichen. Die erste halbe Sekunde auszuschließen beseitigt die unterschiedliche visuelle Aufgabenanzeige nicht vollständig.
4. Weitere vollständige Blöcke erheben und mindestens einen weiteren Termin derselben Person für einen unangetasteten Sitzungstest vorsehen. Eine zweite Sitzung ermöglicht erstmals einen solchen Test, belegt aber noch keine robuste Langzeitstabilität. Wenn das Modell auf neue Personen übertragen werden soll, mehrere Personen erheben und vollständige Personen zurückhalten.
5. Keine fixe angeblich ausreichende Teilnehmer-/Trialzahl aus dieser Sitzung ableiten. Datenbedarf anhand von Lernkurven, Blockstreuung, Artefaktverlusten und gewünschter Genauigkeitspräzision planen. Für Bestätigungsdaten Auswertung vorab festlegen. MOABB trennt entsprechend Evaluation innerhalb einer Sitzung, zwischen Sitzungen und zwischen Personen. [MOABB-Evaluationsbeispiele](https://moabb.neurotechx.com/docs/auto_examples/paradigm_examples/index.html).

Der bisherige Test fragt: „Welche vorgegebene Aufgabe liegt in diesem bekannten Aufgabenfenster vor?“ Eine laufende Erkennung unbekannter Aufgabenbeginne benötigt zusätzlich Rest/Unknown, Bewertung von Fehlalarmen pro Minute, Latenzen und einen kontinuierlichen Test. Das ist hier noch nicht untersucht. MEG-Daten liegen im untersuchten Aufnahmebestand nicht vor; ein EEG–MEG-Modell lässt sich damit nicht prüfen.

## Reproduktion

```bash
~/.venvs/eeg-mne/bin/python analysis/ml_feasibility.py \
  ../recordings/P-001/session_20261021_194704.csv \
  --output analysis/results/ml_feasibility_P001.json
```

Benötigt NumPy, SciPy und pandas. Originalaufnahmen werden nur gelesen. Das Skript wurde auf der vollständigen Sitzung ausgeführt; zusätzlich wurden Merkmalsform und endliche Werte sowie eine synthetisch vollständig trennbare Klassifikationsaufgabe geprüft. Kein trainiertes Produktionsmodell wird gespeichert.
