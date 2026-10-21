# EEGvsMEG

EEG-Aufnahme und Pilotversuche mit dem Unicorn-Headset. Die Windows-CLI führt Motorik, Motor Imagery und stilles Kopfrechnen automatisch durch. Aufnahmen und Aufgabenmarker können anschließend mit Python/MNE angezeigt und als FIF exportiert werden.

Stand: 19. Oktober 2026. Sitzungsprotokoll: `eeg-session-1.0`.

## Dokumentation

| Thema | Anleitung |
|---|---|
| Automatische Sitzung und Bedienung im Versuch | [SESSION_ANLEITUNG.md](gtec_Clib/terminal/SESSION_ANLEITUNG.md) |
| Windows-Build und technische Übersicht | [Terminal-README](gtec_Clib/terminal/README.md) |
| Alle CLI-Befehle und manuelle Aufnahme | [VERWENDUNG.md](gtec_Clib/terminal/VERWENDUNG.md) |
| EEG und Marker ansehen, filtern und exportieren | [MNE_ANLEITUNG.md](gtec_Clib/terminal/MNE_ANLEITUNG.md) |
| Aufgaben, Trialzahlen und wissenschaftlicher Pilotplan | [Versuchsprotokoll](docs/experiment-protocol.md) |
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
NewExp "VP01"
scan paired
open DEINE_SERIENNUMMER
config
cue open
```

Alle acht EEG-Kanäle müssen aktiviert sein. Bei mehreren Monitoren das Teilnehmerfenster vor dem Start auf den vorgesehenen Bildschirm verschieben. Dann:

```text
start session
```

Für einen vorhandenen Versuch `GoToExp "VP01"` anstelle von `NewExp` verwenden. Seriennummer durch die Ausgabe von `scan paired` ersetzen. Neue Sitzungen erhalten automatisch eigene Dateinamen.

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

Beide MNE-Viewer erhalten Aufgabenart, Trial und Wiederholungsversuch in den Annotationen. Eine spätere Invalidierung kennzeichnet auch frühere Marker desselben Attempts als ungültig. Der Viewer im Projektstamm unterstützt FIF-/PNG-Export; der Viewer unter `analysis/` bietet zusätzlich eine Spektrumsansicht. Installation und Einheitenprüfung: [MNE-Anleitung](gtec_Clib/terminal/MNE_ANLEITUNG.md).

## Tests und Prüfstand

Aus dem Repository-Stamm:

```sh
python gtec_Clib/terminal/test_recorder.py
python gtec_Clib/terminal/test_session.py
python -m unittest analysis.test_event_annotations
```

C++-Tests benötigen Clang++ oder MSVC `cl`; Annotationstests benötigen MNE, NumPy und pandas. Die hardwarefreien Tests umfassen 250 Zufallsseeds, alle sechs Laufreihenfolgen, einen vollständigen beschleunigten Sitzungsdurchlauf, Unterbrechungen, Fehler und die im Review korrigierten Timingfälle. Beide Viewer wurden mit einem echten FIF-Speicher-/Ladetest geprüft. Die C++-Plan- und Laufzeittests bestanden außerdem mit Address-/UndefinedBehavior-Sanitizer auf macOS.

Die aktuelle Windows-Anzeige, interaktive Terminalbedienung, Vendor-DLL und ein Echtzeitlauf mit Headset sind noch auf dem Messrechner zu validieren. Automatische Artefaktbereinigung, Klassifikation und eine validierte EEG–MEG-Synchronisation gehören noch nicht zum implementierten Funktionsumfang.
