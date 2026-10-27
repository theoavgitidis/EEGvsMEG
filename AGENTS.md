# Arbeitsregeln für Agents

Diese Regeln gelten für das gesamte Repository. Explizite Anweisungen des Nutzers haben Vorrang.

## Git und Zusammenarbeit

- Falls nicht anders beauftragt, direkt auf `main` arbeiten und die abgeschlossene eigene Arbeit committen. Keine zusätzlichen Branches, Worktrees oder Pull Requests ohne entsprechenden Auftrag anlegen.
- Pushes führt der Nutzer manuell aus. Agents führen keinen `git push` aus, außer der Nutzer beauftragt dies ausdrücklich.
- Vor Änderungen Branch und Arbeitsverzeichnis prüfen. Falls ein anderer Branch ausgecheckt ist, nicht blind wechseln und vorhandene Änderungen gefährden; die Abweichung klären.
- Bestehende Änderungen anderer Arbeit weder verwerfen noch ungefragt in den eigenen Commit aufnehmen. Dateien beziehungsweise Hunks gezielt stagen; kein pauschales `git add .` bei gemischtem Arbeitsstand.
- Zusammenhängende Änderungen mit einer kurzen, aussagekräftigen Commit-Nachricht committen. Keine History-Umschreibung oder destruktiven Git-Operationen ohne Auftrag.
- Zum Abschluss Änderungen, tatsächlich ausgeführte Prüfungen, verbleibende Einschränkungen und Commit-ID knapp nennen. Darauf hinweisen, dass der Push noch manuell erfolgt.

## Projekt und Orientierung

- Kommunikation und nutzerseitige Anleitungen standardmäßig auf Deutsch verfassen. Bestehende englische Codebezeichner und Dateikonventionen beibehalten.
- Vor fachlichen Änderungen die relevanten Anleitungen lesen: `README.md`, `docs/experiment-protocol.md`, `docs/session-automation-plan.md`, `docs/participant-ids.md` und die passende Anleitung unter `gtec_Clib/terminal/`.
- Die Windows-C++-CLI unter `gtec_Clib/terminal/` übernimmt Unicorn-Aufnahme und Sitzungssteuerung. `view_eeg.py` und `analysis/` enthalten Python/MNE-Viewer und Auswertungen. Änderungen an gemeinsamem Verhalten müssen beide Viewer-Einstiegspunkte berücksichtigen.
- Implementierten Stand, geplante Experimente und explorative ML-Piloten klar unterscheiden. Dokumentation nicht als Beleg für bereits validierte Funktionen behandeln.
- Änderungen auf den Auftrag begrenzen und bestehende Architektur bevorzugen. Keine unabhängigen Refactorings, neuen Frameworks oder zusätzlichen Abhängigkeiten ohne konkreten Nutzen.

## Aufnahme und wissenschaftliche Datenintegrität

- Originalaufnahmen unverändert erhalten. Filter, Zentrierung, Referenzierung und Artefaktbehandlung auf Kopien beziehungsweise als klar gekennzeichnete Verarbeitung ausführen. Exporte dürfen Quelldateien nicht überschreiben.
- Einheiten, Samplingrate, Kanalnamen und Kanalreihenfolge explizit prüfen. Insbesondere µV und V nicht stillschweigend verwechseln; fehlende Metadaten nicht durch unbelegte Annahmen ersetzen.
- EEG-, Event-, Phasenplan- und Metadatendateien als zusammengehörige Sitzung behandeln. Änderungen an Formaten, Markern oder Timing über Aufnahme, Import, Annotationen und Dokumentation hinweg konsistent umsetzen.
- Trial, Attempt und Invalidierung erhalten. Nachträglich ungültige Attempts dürfen in der Auswertung nicht als gültige Trials auftauchen. Pausen und Wiederholungen gemäß Sitzungsspezifikation behandeln; EEG-Aufnahme und Aufgabenablauf sind getrennte Zustände.
- Protokollparameter wie Trialzahlen, Aufgabenreihenfolge, Dauern und Randomisierung nur im Rahmen des Auftrags verändern. Bei Änderungen Spezifikation, Bedienanleitung und betroffene Tests mitziehen.
- Teilnehmer-IDs nach `docs/participant-ids.md` verwenden. Keine Klarnamen, Zuordnungsschlüssel oder personenbezogenen Rohdaten in das Repository, Logs oder Beispieldateien aufnehmen. Für Tests synthetische Daten bevorzugen.

## Visualisierung und ML

- Verarbeitung und Skalen sichtbar machen: Filter, Einheiten, Amplitudenbereiche, Zentrierung, PSD-/Bandpower-Fenster und Zeitbezug dürfen nicht irreführend verborgen bleiben. Eine reine Anzeigeoptimierung darf Messwerte und Marker nicht verändern.
- Frequenzbänder oder auffällige Kurven allein nicht als Nachweis eines mentalen Zustands interpretieren. Ergebnisse aus Pilotdaten entsprechend vorsichtig beschreiben.
- Bei ML-Auswertungen Datenleckage vermeiden: zusammengehörige Fenster beziehungsweise Trials nicht unkontrolliert auf Training und Test verteilen. Behauptete Generalisierung muss zur Trennung nach Sitzung oder Person passen.
- Datenumfang, Ausschlüsse, Vorverarbeitung, Split, Seed, Modellversion und Metriken nachvollziehbar dokumentieren. Kleine Pilotstichproben und fehlende unabhängige Validierung ausdrücklich benennen.
- Bestehende Lock-Dateien und Modell-Pins beachten. Modellgewichte, Caches, virtuelle Umgebungen und große generierte Zwischenstände nicht committen. Kleine Ergebnisberichte nur mit nachvollziehbarer Herkunft und im Rahmen des Auftrags aufnehmen.

## Validierung und Dokumentation

- Prüfungen nach der betroffenen Funktion auswählen. Fehlerkorrekturen und Änderungen an Datenverarbeitung, Timing oder Markern mit passenden Regressionstests absichern; für reine Textänderungen genügt die Prüfung von Inhalt, Links und Diff.
- Hardwarefreie C++-Prüfungen: `python gtec_Clib/terminal/test_recorder.py` und `python gtec_Clib/terminal/test_session.py`.
- Python-Prüfungen gezielt mit `python -m unittest analysis.test_<modul>` ausführen. Die konkrete Modulübersicht und weitere Testbefehle stehen in `README.md`; für ML auch `analysis.test_ml_pipeline` beziehungsweise `analysis.test_reve_pipeline` berücksichtigen.
- Die vorhandene passende Python-Umgebung nutzen. Abhängigkeiten nicht unnötig global installieren. Browserprüfungen nur bei verfügbarer Browserumgebung ausführen; sichtbare UI-Änderungen nach Möglichkeit zusätzlich visuell prüfen.
- Ein erfolgreicher Test auf macOS ersetzt keinen Windows-Build und keinen Echtzeitlauf mit Vendor-DLL und Unicorn-Headset. Nur tatsächlich durchgeführte Prüfungen als bestanden melden; fehlende Hardware oder Laufzeitumgebung konkret angeben.
- Bei geändertem Bedienverhalten die betroffenen README- und Bedienanleitungen im selben Commit aktualisieren. Beispiele müssen zu den tatsächlichen CLI-Optionen und Dateiformaten passen.
- Vor dem Commit den eigenen Diff auf unbeabsichtigte Änderungen, Daten, Geheimnisse und generierte Dateien prüfen.
