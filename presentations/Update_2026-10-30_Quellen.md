# Projektupdate für den 30.10.2026

Präsentation: `EEGvsMEG_Update_2026-10-30.pptx`, 18 Folien.
Inhaltlicher Stand: 29.10.2026, Repository-Commit `f6b0aab`.
Vergleichsbasis: `Presentation1_Update_2026-10-22.pptx` und die seitdem dokumentierten Implementierungen.

Auf Wunsch des Nutzers konzentriert sich die Endfassung auf Versuchsprotokoll und Viewer. ML-Verfahren und ML-Ergebnisse wurden entfernt. OSCAR und der zweite RAW-Versuch bleiben als technischer Kontext enthalten.

## Quellen und Abgrenzung

- OSCAR: `acquisition/README.md`, `docs/oscar-integration.md`, `docs/oscar-hardwareless-handoff-2026-10-28.md` und die Änderungen bis `f6b0aab`. Der Fehlerbericht vom 28.10. wird durch die neueren Prozessstart-/Importkorrekturen vom 29.10. ergänzt. Daraus wird kein erfolgreicher vollständiger Headset-Lauf abgeleitet.
- Protokoll: `docs/experiment-protocol.md`, `docs/session-automation-plan.md`, `gtec_Clib/terminal/SESSION_ANLEITUNG.md` und `gtec_Clib/terminal/session_plan.h`.
- Viewer: `gtec_Clib/terminal/MNE_ANLEITUNG.md`, `analysis/eeg_browser.py`, `analysis/time_frequency.py`, `analysis/waterfall_browser.py`, `analysis/waterfall_data.py`, `analysis/waterfall_view.html`.
- Organisation: `docs/participant-ids.md`, `docs/participant-record-template.md` und `README.md`.

Die Sprechernotizen enthalten pro Folie die relevanten Quellen und zusätzliche fachliche Einschränkungen. Protokoll 2.0 ist implementiert und hardwarefrei geprüft, wissenschaftliche Validierung und vollständige Hardware-Abnahme bleiben offen.

Der zweite Versuch ohne OSCAR ist auf Wunsch des Nutzers als eigener Punkt enthalten. Dafür wurden keine Aufnahmedateien ausgewertet und keine Ergebniszahlen oder Aussagen über Vollständigkeit und Signalqualität ergänzt.

## Screenshots

Die vier Screenshots zeigen die tatsächlichen implementierten Viewer mit synthetischen Beispieldaten, ausdrücklich auf den Folien gekennzeichnet. Sie enthalten keine Teilnehmermessdaten. Verwendet wurden acht Kanäle bei 250 Hz über 60 s, Seed `20261030`, ein modulierter Sinus um 9–12,15 Hz, eine 20-Hz-Komponente und Rauschen. Die Marker dienen nur der Bedienungsdemonstration. Die Darstellung ist ungefiltert, für die Amplitudenansichten wurde ein gemeinsamer Bereich von ±50 µV gewählt. Keine Aussagen über echte aufgabenbezogene Muster werden aus diesen Bildern abgeleitet.

## Prüfung dieses Artefakts

Alle 18 Folien wurden im Präsentationsrenderer einzeln visuell geprüft. Tabellen und Text sind editierbar, Screenshots eingebettet. Folienzahl, PPTX-Paketstruktur, Geometrie, Schrift und Quellenabdeckung wurden geprüft. PowerPoint unter Windows und die Aufnahmehardware wurden für diesen Präsentationsauftrag nicht ausgeführt. Die auf den Folien genannten Softwaretests sind dokumentierte frühere Prüfungen und keine in diesem Auftrag neu ausgeführten Regressionen.
