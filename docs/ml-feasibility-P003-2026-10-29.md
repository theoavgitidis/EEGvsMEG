# P003: explorativer ML-Test nach Anbringen der Ground-Elektroden

Untersuchung vom 29.10.2026, Sitzung `session_20261029_153043`, Protokoll `eeg-session-2.0`. **Die OSCAR-Baseline erreicht bei linker/rechter Handvorstellung 75 % Balanced Accuracy. Das ist ein Entwicklungshinweis aus einer einzelnen Sitzung, kein validierter Nachweis einer zuverlässigen Imagery-Erkennung.**

## Daten und Ausschluss

Eingaben sind die zusammengehörigen Dateien unter `../recordings/P-003/`. Die gespeicherte Teilnehmerkennung lautet `P003`; sie wurde beibehalten und nicht automatisch in das neue ID-Schema umbenannt. Laut Nutzer fehlten die Ground-Elektroden bis zum manuellen Marker. Der tatsächliche Text ist **`ground placed`**, nicht `placed ground`.

- Marker bei Rohsample **234736**, entsprechend **938,944 s / 15:38,944 min** auf der Sample-Zeitachse, während der Vorbereitung zu Motorik-Trial 58, Block 4. Die Eventfelder haben unterschiedliche Zeitursprünge: `elapsed_s=947,692862`, `actual_session_elapsed_s=938,040462`. Für den Ausschluss wird ausschließlich `samples_received` verwendet.
- Vor Berechnung der Testwerte festgelegte zusätzliche Wartezeit: **10 s**. Cutoff bei Sample **237236 / 948,944 s**. Dies ist eine konservative Ausschlussregel, keine gemessene Geräte-/OSCAR-Erholungszeit. Die Daten erlauben keine unabhängige Bestätigung, wann der Elektrodenkontakt stabil wurde.
- Ganze Trials mit Aufgaben-Cue vor dem Cutoff werden ausgeschlossen, auch wenn ihr Analysefenster erst danach beginnt. Keine Kürzung, Verschiebung, Überschreibung oder Neubereinigung der Originaldateien; keine zusätzliche Marker-Verschiebung um die OSCAR-Verzögerung.
- **58 von 168 Trials ausgeschlossen.** Es bleiben sechs Motorik-Trials aus nur einem Block und **alle 104 Trials des mentalen Laufs aus vier Blöcken**. Motorik wird wegen fehlender unabhängiger Testblöcke nicht bewertet; beim Handseitenkontrast fehlt außerdem eine Klasse. Die sechs verbleibenden Motorik-Trials werden im Bericht erhalten, aber nicht zum Trainieren der Imagery-Modelle genutzt.

Die Sitzung ist laut Metadaten `completed`, ohne Invalidierungen, Wiederholungen oder Counter-Unterbrechungen. Rohdaten: **676428 Samples**; OSCAR: **676337 Samples**, jeweils **250 Hz**, acht EEG-Kanäle in µV. OSCAR-Verarbeitung `complete`, gemeldete Verzögerung **83 Samples**, Rohsample-Index bereits ausgerichtet. Versionen: g.Pype 4.1.0, gtec-oscar 1.3.2, gtec-unicorn 1.0.0 und gtec-licensing 2.4.0. Die Verarbeitungsmetadaten melden `noncommercial_mark=true`; ein möglicher Einfluss dieser Herstellerkennzeichnung auf das EEG wurde nicht unabhängig geprüft.

## Durchgeführte Pipeline

Bestehende `analysis.ml_feasibility`-Baseline, ergänzt um expliziten Marker-Ausschluss und die begründete Auslassung nicht testbarer Kontraste. Festes Ridge-Modell, Penalty 10, keine Hyperparameter- oder Modellsuche. **OSCAR ist die primär betrachtete Variante**, die Rohdaten sind eine separat berichtete Sensitivitätsanalyse; die primäre Variante wird nicht nach der höheren Genauigkeit gewählt.

Ein einziges 3-s-Fenster pro Trial, 0,5–3,5 s nach Cue, keine überlappenden Ausschnitte. Bandpass 1–40 Hz, Butterworth vierter Ordnung mit `sosfiltfilt`, separat je Epoche; logarithmische Welch-Bandpower bei 8–13 und 13–30 Hz, insgesamt 16 EEG-Merkmale. Keine zusätzliche Referenzierung, Amplitudenverwerfung oder nachträgliche Auswahl günstiger Kanäle. Die Offline-Filterung ist keine geprüfte Echtzeitpipeline.

Vier Folds: jeweils drei ganze Blöcke zum Training, der übrige Block zum Test. Standardisierung nur aus Trainingsdaten. Keine zufällige Aufteilung von Fenstern desselben Trials. Kontrollen: sechs IMU-Kanäle mit Standardabweichung und Spannweite, außerdem ein separater Klassifikator nur mit der Aufnahmezeit. Diese Kontrollen werden nicht mit EEG-Merkmalen kombiniert.

199 Label-Permutationen innerhalb der Blöcke, Seed **20261022**, bei festem Klassifikator. Sitzungsgenerator-Seed **4188517853**. Laufzeitumgebung `~/.venvs/eeg-ml`: NumPy 2.5.4, SciPy 1.18.1, pandas 3.1.0. Kein Download neuer Gewichte, kein Deep-Learning-Training. Die Ergebnisdateien enthalten Eingabe-SHA-256, Ausschlussliste, verbleibende Fenster samt ursprünglichen Trial-/Attempt-/Block-IDs, Klassenzahlen, Fold-Werte und Konfusionsmatrizen.

## Ergebnisse

Alle Genauigkeiten sind **Balanced Accuracy**; bei den ausgeglichenen Klassen entspricht dies hier der normalen Trefferquote. Die Kontraste überlappen teilweise und liefern keine unabhängigen zusätzlichen Trials.

| Vergleich | Trials / je Klasse | Zufall | OSCAR-EEG | Roh-EEG | Nur IMU | Nur Zeit | p OSCAR / roh, unbereinigt |
|---|---:|---:|---:|---:|---:|---:|---:|
| Linke / rechte Handvorstellung | 32 / 16 | 50 % | **75,0 %** | 62,5 % | 25,0 % | 50 % | 0,025 / 0,165 |
| Linke / rechte Fußvorstellung | 32 / 16 | 50 % | 37,5 % | 46,9 % | 50,0 % | 50 % | 0,905 / 0,700 |
| Vier unilaterale MI-Klassen | 64 / 16 | 25 % | 28,1 % | **39,1 %** | 21,9 % | 25 % | 0,335 / 0,020 |
| Beidseitige Hand- / Fußvorstellung | 24 / 12 | 50 % | 45,8 % | 58,3 % | 58,3 % | 50 % | 0,705 / 0,330 |
| Wortgenerierung / Subtraktion | 16 / 8 | 50 % | 56,3 % | 62,5 % | 62,5 % | 50 % | 0,290 / 0,225 |

Beim OSCAR-Handseitenkontrast sind **24 von 32 Trials korrekt**, zwölf je Klasse. Alle vier Testblöcke erreichen **75 %**, jeweils sechs von acht Trials. Die entsprechende Rohdaten-Baseline erreicht in jedem Block 62,5 %. Das macht den Handseitenkontrast zum konkreten Kandidaten für eine vorab festgelegte Prüfung an einer neuen Sitzung.

**Keine der EEG-Auswertungen ist nach Holm-Korrektur innerhalb der fünf EEG-Kontraste je Signalvariante bei 5 % abgesichert.** Der kleinste korrigierte OSCAR-p-Wert beträgt 0,125, der kleinste Rohdaten-p-Wert 0,100. Die JSON-Berichte enthalten die unbereinigten explorativen p-Werte; Kontrollen und der zweite Signalweg vergrößern die gesamte Explorationsfamilie zusätzlich. Für den priorisierten MEG-Anker, beidseitige Hand-/Fußvorstellung, zeigt diese Pipeline keinen belastbaren Erfolg. Ein EEG–MEG-Leistungsvergleich wurde nicht durchgeführt.

## Signalprüfungen und Grenzen

Beide Sampleindizes sind lückenlos; Rohsample-Zeit `nominal_time_s` entspricht exakt `sample_index / 250`. Alle neun Hilfskanäle der OSCAR-Datei stimmen über deren gesamte Länge exakt mit den entsprechenden Rohsamples überein. Der Rohdaten-Counter steigt durchgängig um eins. In beiden Dateien ist der Validation Indicator immer 1; keine nichtendlichen EEG-Werte. Das bestätigt Dateikonsistenz, aber keine korrekte Elektrodenplatzierung oder gute Kontaktqualität.

Zusätzliche Signalkontrolle an allen 104 mentalen Analysefenstern, separat mit demselben 1–40-Hz-Filter: Die mediane Kanal-/Epochen-Spannweite beträgt in Rohdaten **60,1 µV**, nach OSCAR **53,2 µV**. Die maximale gefilterte Spannweite liegt roh bei **3902,1 µV** in EEG 2, nach OSCAR bei **131,3 µV**. Rohdaten enthalten auch nach dem Cutoff sehr große DC-Offsets: Median der absoluten EEG-Werte über alle Kanäle und Samples ab Cutoff etwa **191879 µV**. Die Bandpassauswertung entfernt den Gleichanteil; der starke Rohdaten-Transient bleibt eine Qualitätsauffälligkeit. Aus der geringeren OSCAR-Amplitude folgt kein unabhängiger Wirksamkeitsnachweis und kein Nachweis neuronaler Herkunft der Klassifikation.

Die Angabe zu fehlenden Ground-Elektroden stammt vom Nutzer. Der Marker belegt keine automatisch gemessene Kontaktverbesserung. OSCAR lief bereits während des fehlerhaften Anfangsabschnitts; ein möglicher länger anhaltender Verarbeitungseinfluss wurde nicht quantifiziert. Die zehn Sekunden Wartezeit ändern an den ausgewerteten mentalen Trials nichts, da dieser Lauf erst später beginnt. Eine abweichende kurze Wartezeit wäre deshalb keine unabhängige Replikation des Imagery-Ergebnisses.

Die Zuordnung generischer EEG-Namen zu realen Kopfpositionen wurde nicht unabhängig verifiziert. Die Kopf-IMU schließt subtile Finger-/Fußbewegungen oder EMG-Einflüsse nicht aus. Auch visuelle Cue-Unterschiede, Drift und andere Artefakte bleiben mögliche Erklärungen. Nur eine Person an einem Termin, kleine Klassenumfänge, keine unabhängigen Sitzungs-/Personentests und kein EEG–MEG-Test. Kein trainiertes Modell für einen Produktiveinsatz gespeichert.

## Reproduktion und Prüfungen

Aus dem Repository-Stamm, jeweils einen **neuen** Ausgabepfad verwenden; vorhandene Berichte werden geschützt:

```bash
~/.venvs/eeg-ml/bin/python -m analysis.ml_feasibility \
  ../recordings/P-003/session_20261029_153043.csv \
  --signal oscar --after-marker "ground placed" --settle-seconds 10 \
  --output analysis/results/ml_feasibility_P003_oscar_post_ground_REPRO.json

~/.venvs/eeg-ml/bin/python -m analysis.ml_feasibility \
  ../recordings/P-003/session_20261029_153043.csv \
  --signal raw --after-marker "ground placed" --settle-seconds 10 \
  --output analysis/results/ml_feasibility_P003_raw_post_ground_REPRO.json

~/.venvs/eeg-ml/bin/python -m unittest \
  analysis.test_ml_feasibility analysis.test_ml_pipeline \
  analysis.test_session_protocol analysis.test_reve_pipeline
```

Beide vollständigen Auswertungen wurden erfolgreich ausgeführt. **20 Tests bestanden**, darunter Marker-Grenzen, zusätzliche Wartezeit, Ausschluss kompletter Aufgaben-/Restpaare, fehlende/mehrdeutige Marker, synthetischer CLI-Durchlauf mit nur einem verbleibenden Motorikblock, Protokolltrennung und Modelltraining auf synthetischen Eingaben. Zusätzliche oben genannte Zeit-/Counter-/Hilfskanal- und Amplitudenprüfungen wurden direkt auf den Originaldateien ausgeführt. Kein erneuter Windows-Build oder Headset-Lauf im Rahmen dieser Offline-Auswertung.

Vollständige Ergebnisse: [OSCAR](../analysis/results/ml_feasibility_P003_oscar_post_ground.json), [Rohdaten](../analysis/results/ml_feasibility_P003_raw_post_ground.json). Die Ausschlussoptionen gelten nur für `analysis.ml_feasibility`; CBraMod-/REVE-CLIs und Viewer übernehmen sie nicht automatisch.
