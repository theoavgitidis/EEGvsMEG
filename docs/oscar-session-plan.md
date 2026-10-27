# Umsetzung: OSCAR bei start session

Entscheidungen vom 27.10.2026:
- `start session` verwendet OSCAR; `start session raw` wählt ausdrücklich den bisherigen C-API-Rohdatenrecorder.
- C++ behält Sitzung, Anzeige, Pausen, Trial/Attempt und Marker. Ein Python-Prozess übernimmt die OSCAR-Aufnahme exklusiv.
- Rohdaten bleiben unter dem bisherigen CSV-Namen, bereinigte Daten liegen separat unter `<CSV>.oscar.csv`. Importer bevorzugen bei entsprechend gekennzeichneten Sitzungen OSCAR; `--signal raw` wählt Rohdaten.
- Keine automatische Rückfallaufnahme. Initialisierungsfehler verhindern Aufgabenstart; Verarbeitungsfehler beenden die Sitzung als fehlgeschlagen.
- Nutzer übernimmt den Windows-/Headset-Abnahmetest.

Arbeitsschritte:
1. Python-Worker mit g.Pype, Rohdatenabgriff vor OSCAR, bereinigtem Ausgang, expliziter Zeitzuordnung, begrenzten Puffern und Abschlussprüfung.
2. Prozessadapter für C++, READY-/Status-/Fehlerprotokoll, exklusiver Geräteübergabe und geordnetem Stop.
3. Sitzung, Status und Metadaten erweitern, Startfreigabe erst nach ersten gültigen bereinigten Samples.
4. Gemeinsame Dateiauswahl für Viewer und ML, unveränderte Marker auf der geprüften Rohsample-Zeitachse; Herkunft sichtbar machen.
5. Hardwarefreie Regressionstests, Herstellerpaket-Test mit synthetischer Quelle, Windows-Bauanleitung und Hardware-Abnahme dokumentieren.

Zeitvertrag: OSCAR-Ausgabeverzögerung aus dem laufenden Modell lesen. Anlaufsamples verwerfen und jedes bereinigte Sample anhand des unveränderten, verzögerten Geräte-Counters gegen das zugehörige Rohsample prüfen. Bei unpassender Verzögerung, Reordering oder fehlenden Samples abbrechen statt Marker zu verschieben oder Lücken zu verstecken. Beim Stop weitere reale Samples einlesen, bis die bereinigte Ausgabe den beim Stop erfassten Rohsample-Stand abdeckt. Keine künstlichen EEG-Samples zum Auffüllen.

## Implementierter und geprüfter Stand

Alle fünf Arbeitsschritte sind umgesetzt. C++ bleibt für den Ablauf zuständig; `acquisition/oscar_worker.py` und `worker_process.h` bilden Aufnahme und Prozesskommunikation ab. `analysis/recording_files.py` stellt die gemeinsame Datenwahl bereit.

Ausgeführt unter macOS:
- `test_recorder.py`: manuelle/timed/continuous Aufnahme, Marker, Pfade und Fehler bestanden.
- `test_session.py`: 250 Seeds, alle Laufreihenfolgen, vollständige beschleunigte 112-Trial-Sitzung, Pausen/Repeats, Timing- und I/O-Fehler bestanden.
- `test_oscar_session.py`: synthetischer Prozesspartner; READY, Stop, Start-/Laufzeitfehler, unbestätigtes EOF, nicht erfolgreicher Exitcode und exklusiver Geräteübergang und Statusstillstand bestanden.
- Viewer-/Datenregressionen: 46 Tests ausgeführt, 44 bestanden und zwei optionale Herstellerpaket-Tests in dieser Umgebung übersprungen. Der gemeinsame Import einschließlich ML-Dateiauswahl wurde geprüft.
- Separat in einer Umgebung mit gepinnten Herstellerpaketen: alle zehn OSCAR-Tests bestanden, einschließlich der beiden optionalen Tests mit echtem Modell und synthetischem Treiber (Delay-Zuordnung sowie READY/Stop/Nachlauf/Metadaten).
- Diff und Python-Syntax geprüft. Vollständige Modelltrainingstests wegen fehlendem torch in der Viewer-Umgebung nicht ausführbar; das Modelltraining wurde nicht verändert.

Ausstehend bleibt die in `acquisition/README.md` beschriebene Windows-/Headset-Abnahme durch den Nutzer. Das umfasst auch echten Lizenzzugang und einen vollständigen Echtzeitlauf; die hardwarefreien Tests ersetzen diese Prüfung nicht.
