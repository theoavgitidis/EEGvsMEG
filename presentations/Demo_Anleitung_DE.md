# Eigenständige Demo: Build, Start und EEG-Aufnahme

## 1. Voraussetzungen unter Windows

Windows 64 Bit, Visual Studio 2022 oder Build Tools mit „Desktopentwicklung mit C++“ und Windows SDK sowie CMake installieren. Das Projekt muss inklusive `gtec_Clib/lib/Unicorn.dll` und `Unicorn.lib` lokal vorliegen. Headset einschalten und über Windows oder Unicorn Suite koppeln. Unicorn Recorder und andere Programme, die das Headset benutzen, vor der CLI-Demo schließen.

Die Anwendung mit der Hersteller-DLL läuft unter Windows, nicht direkt unter macOS. Die Demo zeigt manuell ausgelöste Szenariowechsel und ist kein vollständiger Studienlauf.

## 2. Bauen und starten in PowerShell

Den Beispielpfad in der ersten Zeile an den eigenen Windows-Projektordner anpassen. Alle folgenden Build-Befehle laufen aus diesem Ordner. Der neue Build-Ordner `build-demo` vermeidet Konflikte mit vorhandenen Build-Konfigurationen.

```powershell
cd "C:\Projekte\EEGvsMEG"
cmake -S gtec_Clib/terminal -B gtec_Clib/terminal/build-demo -G "Visual Studio 17 2022" -A x64
cmake --build gtec_Clib/terminal/build-demo --config Release
& .\gtec_Clib\terminal\build-demo\Release\unicorn_terminal.exe
```

CMake kopiert die Hersteller-DLL automatisch neben die EXE. Bei erneutem Bauen eine laufende CLI zuerst mit `quit` beenden. Bei späteren Starts genügt die letzte Zeile.

## 3. Befehle in der gestarteten CLI

Jeden Befehl einzeln eingeben und die Ausgabe prüfen. `scan paired` liefert die Seriennummer. In der Zeile `open DEINE_SERIENNUMMER` den Platzhalter durch diese Ausgabe ersetzen. Einen neuen Versuchsordnernamen wählen, falls `Demo_01` bereits existiert, oder mit `GoToExp "Demo_01"` den vorhandenen Ordner auswählen. Eine neue CSV-Datei verwenden, wenn `VP01_demo.csv` schon existiert.

```text
NewExp "Demo_01"
Where
version
bluetooth
scan paired
open DEINE_SERIENNUMMER
info
config
channels
cue open
record 0 "VP01_demo.csv" real
mark baseline
```

Jetzt etwa 5 Sekunden ruhig auf das Fixationskreuz schauen. Danach die folgende Reihenfolge manuell durchführen. Die Angaben zu Wartezeiten sind Anweisungen für den Vorführenden und keine CLI-Befehle.

1. `mark hands_up` eingeben. Beide Unterarme kurz anheben und wieder ablegen, nach etwa 4 Sekunden fortfahren.
2. `mark rest` eingeben. Etwa 7 Sekunden ruhig sitzen.
3. `mark legs_up` eingeben. Beide Füße kurz anheben und wieder absetzen, nach etwa 4 Sekunden fortfahren.
4. `mark rest` eingeben. Etwa 7 Sekunden ruhig sitzen.
5. `cue imagery_arms | Stelle dir vor, beide Unterarme anzuheben.` eingeben. Etwa 4 Sekunden nur vorstellen, ohne Bewegung.
6. `mark rest` eingeben. Etwa 7 Sekunden ruhig sitzen.
7. `mark subtract 7 from 347` eingeben. Etwa 10 Sekunden still fortlaufend 7 abziehen.
8. `mark rest` eingeben. Etwa 5 Sekunden ruhig sitzen.

Die Befehlsfolge im Überblick, ohne Warteanweisungen:

```text
mark hands_up
mark rest
mark legs_up
mark rest
cue imagery_arms | Stelle dir vor, beide Unterarme anzuheben.
mark rest
mark subtract 7 from 347
mark rest
status
stop
status
cue close
close
quit
```

`cue LABEL | TEXT` gehört vollständig in die CLI, nicht in PowerShell. Das Zeichen `|` trennt dort Marker und Anzeigetext. Das Teilnehmerfenster kann nach `cue open` mit F11 in den Vollbildmodus wechseln. Zum Eingeben weiterer Befehle wieder die CLI fokussieren.

`record 0` läuft bis zum manuellen Stoppen. Die Anweisung aktualisiert sich automatisch, sobald der Versuchsleiter einen passenden `mark`- oder `cue`-Befehl auslöst. Die Wartezeiten werden nicht automatisch gesteuert. Die Rechenanweisung bleibt in dieser kurzen Demo während des Rechnens sichtbar. Im Studienprotokoll ist dagegen eine separate Instruktionsphase mit anschließendem Fixationskreuz vorgesehen.

## 4. Ergebnis prüfen

`Where` nennt den tatsächlichen Aufnahmeordner. CMake legt ihn als `recordings` neben dem Projektordner fest. Beim obigen Beispiel liegen die Dateien unter:

```text
C:\Projekte\recordings\Demo_01\VP01_demo.csv
C:\Projekte\recordings\Demo_01\VP01_demo.csv.events.csv
```

Die erste Datei enthält die Kanalwerte und Zeitinformationen, die zweite die Aufgabenmarker. Markerpositionen sind zeitliche Näherungen und keine präzise Hardware-Synchronisation.

## 5. Optional: Aufnahme in Python ansehen

In einer Python-Umgebung mit MNE, NumPy und Matplotlib aus dem Projektordner ausführen. Die EEG-Einheit vorher der Ausgabe von `config` entnehmen. Das folgende Beispiel gilt nur, wenn dort für EEG tatsächlich `uV` steht:

```powershell
python analysis/view_eeg.py "..\recordings\Demo_01\VP01_demo.csv" --unit uV
```

Für eine gefilterte Anzeigekopie oder das Frequenzspektrum:

```powershell
python analysis/view_eeg.py "..\recordings\Demo_01\VP01_demo.csv" --unit uV --filtered
python analysis/view_eeg.py "..\recordings\Demo_01\VP01_demo.csv" --unit uV --psd
```

Die Anzeige verändert die gespeicherte CSV nicht.
