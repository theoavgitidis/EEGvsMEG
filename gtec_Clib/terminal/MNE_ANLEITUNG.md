# Unicorn-Aufnahmen mit MNE ansehen

**OSCAR-Stand 27.10.2026:** `start session` nimmt standardmäßig mit OSCAR über Python auf; `start session raw` wählt ausdrücklich Rohdaten. Beide Varianten bleiben getrennt gespeichert. Einrichtung, Geräteübergabe, Signalwahl und noch erforderliche Windows-/Headset-Abnahme: [OSCAR-Anleitung](../../acquisition/README.md). Beide Viewer bevorzugen für neue OSCAR-Sitzungen die bereinigten Daten; `--signal raw` wählt Rohdaten. FIF-Exporte enthalten die gewählte Variante vor zusätzlichen Anzeigefiltern.

Stand: 21. Oktober 2026. Beide mitgelieferten Viewer verwenden dieselbe Zeitansicht mit getrennten EEG-Spuren, einer eigenen Marker-Zeitleiste und einem Spektrogramm auf gemeinsamer Zeitachse. Die Befehle für FIF-/PNG-Export in dieser Anleitung beziehen sich auf `view_eeg.py` im Projektstamm.

Das Skript `view_eeg.py` im Projektstamm liest die EEG-Kanäle deiner CSV und
die Labels aus der danebenliegenden `.events.csv` in MNE ein. Die Originaldateien
bleiben unverändert. Es funktioniert für neue Versuche unter `EEG/recordings`
und frühere CSV-Dateien im Projektstamm. Es zeigt abgeschlossene Aufnahmen,
keinen Live-Datenstrom.

## Ablauf und Dateiablage

1. Die Aufnahme vollständig beenden und ihren Abschlusszustand mit `status` prüfen.
2. Bei einem Rechnerwechsel den gesamten Teilnehmerordner kopieren.
3. Die Einheit der EEG-Werte anhand von `config` oder den gespeicherten Gerätemetadaten prüfen.
4. Die **EEG-CSV** mit `view_eeg.py` öffnen; die passende Ereignisdatei wird automatisch geladen.
5. Zuerst die ungefilterte Aufnahme prüfen, anschließend bei Bedarf ausdrücklich eine gefilterte Ansicht öffnen.
6. Für Amplitudenvergleiche einen gemeinsamen Bereich mit `--scale-uv` wählen; bei Bedarf FIF oder PNG exportieren.

`recordings` liegt **neben** `EEGvsMEG`, nicht darin. Beispiel für neue Teilnehmer nach dem [ID-Schema](../../docs/participant-ids.md):

```text
Projects/                         # unter Windows beispielsweise C:\EEG\
├── EEGvsMEG/                     # Repository mit view_eeg.py und analysis/
└── recordings/
    └── EVM-P001/
        ├── session_YYYYMMDD_HHMMSS.csv
        ├── session_YYYYMMDD_HHMMSS.csv.events.csv
        ├── session_YYYYMMDD_HHMMSS.csv.plan.csv
        └── session_YYYYMMDD_HHMMSS.csv.session.json
```

Die Datei ohne weiteren Zusatz, `session_YYYYMMDD_HHMMSS.csv`, ist die Eingabe des Viewers. Die `.events.csv` enthält die Marker. Plan und JSON bleiben zur Zuordnung und Auswertung daneben; der Viewer liest sie nicht automatisch ein und ermittelt daraus auch keine Einheit. Dateinamen und vorhandene Teilnehmer-IDs beim Kopieren beibehalten. `P-001` in den Mac-Beispielen ist ein vorhandener Aufnahmeordner; er muss nicht umbenannt werden.

Der Aufnahmeordner gehört nicht zum Git-Repository. Ein Git-Push ersetzt deshalb keine Sicherung der Aufnahmen. Für die Ansicht werden weder eine Headset-Verbindung noch Bluetooth oder die Windows-Unicorn-DLL benötigt. Die gesamte Projektstruktur einschließlich `analysis/` muss vorhanden sein; `view_eeg.py` allein reicht nicht.

## 1. Installation prüfen

Die Windows-Befehle dieser Anleitung gehören in PowerShell, die macOS-Befehle in Terminal. Recorder-Befehle wie `stop`, `status`, `config` und `Where` gehören dagegen in das laufende Unicorn-Terminal. Die Auswertung gespeicherter Aufnahmen funktioniert auf beiden Systemen; die Aufnahme mit der Unicorn-CLI benötigt Windows.

### Windows

```powershell
cd C:\EEG\EEGvsMEG
```

Die folgenden Beispiele verwenden die Umgebung `.venv-mne` im Repository. Falls sie noch nicht vorhanden ist, einmalig anlegen:

```powershell
python -m venv .venv-mne
& .\.venv-mne\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-mne\Scripts\python.exe -m pip install mne numpy pandas matplotlib
& .\.venv-mne\Scripts\python.exe -c "import mne, numpy, pandas, matplotlib; print('MNE-Version:', mne.__version__)"
```

Eine Aktivierung mit `Activate.ps1` ist nicht nötig. Rufe immer den Interpreter
in `.venv-mne` auf, damit Installation und Ausführung dieselben Pakete verwenden.

### macOS

Eine Windows-Umgebung mit `Scripts/python.exe` funktioniert auf dem Mac nicht. Auf dem Mac einmalig eine eigene Umgebung außerhalb des Repositorys anlegen:

```bash
cd /Users/theoa/Desktop/Projects/EEGvsMEG
python3 -m venv ~/.venvs/eeg-mne
~/.venvs/eeg-mne/bin/python -m pip install mne numpy pandas matplotlib
~/.venvs/eeg-mne/bin/python -c "import mne, numpy, pandas, matplotlib; print('MNE-Version:', mne.__version__)"
mkdir -p /Users/theoa/Desktop/Projects/recordings
open /Users/theoa/Desktop/Projects/recordings
```

Der letzte Befehl öffnet den Zielordner im Finder. Den gesamten Teilnehmerordner vom Windows-Laptop dorthin kopieren. EEG-CSV, passende `.csv.events.csv`, `.csv.plan.csv` und `.csv.session.json` zusammenlassen. Beispiel für eine vorhandene Aufnahme bei bestätigter Einheit `uV`:

```bash
cd /Users/theoa/Desktop/Projects/EEGvsMEG
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" --unit uV
```

Den Dateipfad durch die tatsächlich kopierte Aufnahme ersetzen. Installation und Anlegen der Umgebung sind nur einmal nötig; zum erneuten Öffnen reichen `cd` und der Viewer-Befehl. In den folgenden PowerShell-Beispielen lässt sich `& .\.venv-mne\Scripts\python.exe .\view_eeg.py` auf dem Mac durch `~/.venvs/eeg-mne/bin/python view_eeg.py` ersetzen; Pfade dort mit `/` schreiben.

## 2. Aufnahme beenden und Einheit prüfen

Eine automatische Sitzung regulär bis zum Abschluss laufen lassen und im Unicorn-Terminal mit `status` prüfen. `stop` während einer laufenden automatischen Sitzung **bricht sie ab**. Eine noch laufende manuelle Aufnahme vor dem Öffnen beenden:

```text
stop
status
config
```

Prüfe bei verbundenem Headset die Einheit der EEG-Kanäle in `config`. Bei einer bereits kopierten automatischen Sitzung lässt sie sich außerdem in der zugehörigen `.csv.session.json` unter `device.channels` für die EEG-Kanäle nachsehen.
Die CSV enthält keine Einheit; MNE erwartet Volt. Deshalb verlangt das Skript
die ausdrückliche Angabe `--unit`. Die Beispiele nehmen Mikrovolt an; das ist
eine Annahme, keine aus der CSV verifizierte Einheit.

| Anzeige in `config` | Argument | Umrechnung zu Volt |
|---|---|---|
| `µV`, `μV`, `uV` | `--unit uV` | Wert × 0,000001 |
| `mV` | `--unit mV` | Wert × 0,001 |
| `V` | `--unit V` | Wert unverändert |

## 3. Aufnahme auswählen und öffnen

Für eine automatische Sitzung zeigt das Unicorn-Terminal den vollständigen Dateipfad an; `Where` nennt den Experimentordner. Den tatsächlichen Namensstamm aus dieser Ausgabe übernehmen. Beispiel für `EVM-P001` (bei bestätigter EEG-Einheit `uV`; Datum und Uhrzeit durch den vorhandenen Dateinamen ersetzen):

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\EVM-P001\session_20261021_194704.csv" --unit uV
```

Die danebenliegende `.csv.events.csv` wird automatisch mit eingelesen. Aufgabenart, Trial und Attempt erscheinen bei automatischen Ereignissen in den Annotationen; siehe Abschnitt 5. Plan-CSV und Session-JSON bleiben separate Begleitdateien. FIF-Export ohne interaktives Fenster:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\EVM-P001\session_20261021_194704.csv" --unit uV --no-show --save-fif "..\recordings\EVM-P001\session_20261021_194704_raw.fif"
```

Die folgenden Beispiele beziehen sich auf ältere Testaufnahmen. Für `Test01/test01.csv`:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV
```

Es öffnet sich die interaktive EEG-Ansicht auf Basis der importierten MNE-Daten. PowerShell bleibt beschäftigt,
bis du das Fenster schließt. Für die frühere Aufnahme:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py .\test_session01.csv --unit uV
```

Für einen anderen Versuch einfach den Pfad ersetzen:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Mein Versuch\session01.csv" --unit uV
```

Pfadnamen mit Leerzeichen in Anführungszeichen setzen. Relative Pfade gelten
für den aktuellen PowerShell-Ordner; deshalb oben zuerst `cd` ausführen.
Alternativ ist ein vollständiger Windows-Pfad möglich.

## 4. Anzeige bedienen

Jeder EEG-Kanal hat eine eigene Achse. Kurven werden innerhalb dieser Achse begrenzt und können dadurch nicht in benachbarte Kanäle hineinlaufen. Die Zeitachse zeigt Sekunden. Das Skript importiert nur Spalten wie `EEG 1` bis `EEG 8`; Batterie, Counter, Beschleunigung und Gyroskop werden nicht als EEG importiert. Die Abtastrate ist entsprechend der CLI fest auf 250 Hz eingestellt.

Die automatische Anzeige zentriert jeden Kanal um den Median des gerade sichtbaren Ausschnitts und passt seinen Bereich beim Wechsel des Ausschnitts neu an. Ohne zusätzliche Vergrößerung berücksichtigt die Anpassung alle Samples des Ausschnitts einschließlich großer Ausschläge. Bereich und abgezogener Offset stehen an jeder Spur in µV. Die Skalen können sich pro Kanal unterscheiden; gleiche Kurvenhöhe bedeutet deshalb nicht automatisch gleiche Amplitude. Die Zentrierung betrifft ausschließlich die Darstellung, nicht die CSV oder den FIF-Export. Ohne Filter werden auch die ersten Samples einschließlich Einschwingvorgängen und Drift angezeigt.

Aufgabenmarker stehen in einer eigenen Zeitleiste über den EEG-Spuren. Ihre vollständigen Beschreibungen werden nicht mehr über die Kurven geschrieben. Zeitgleiche Marker werden an einer Position zusammengefasst; kurze Beschriftungen werden nur gesetzt, wenn sie Platz haben. Die ausführlichen Angaben des ausgewählten Markers stehen rechts. Dort bleiben Aufgabenart, Trial, Attempt und Status lesbar. Auch Marker ohne Kurzbeschriftung sind auswählbar.

Unter den EEG-Spuren zeigt ein Spektrogramm die Leistungsdichte des ausgewählten Kanals über Zeit und Frequenz. Marker, Spuren und Spektrogramm bleiben beim Blättern und Ändern der Fensterdauer auf derselben Zeitachse. Eine EEG-Spur anklicken oder die Kanal-Schaltflächen rechts verwenden, um einen anderen Kanal auszuwählen. Die Auswahl mittelt keine Kanäle und verändert keine EEG-Werte.

### Die Anzeigen lesen

| Bereich | Bedeutung |
|---|---|
| Kopfzeile, z. B. `01:00.000 – 01:20.000 / 38:17.700` | Sichtbarer Ausschnitt und Gesamtdauer aus der Samplezahl der CSV. Diese Dauer kann von den geplanten 38:16 Minuten abweichen und umfasst auch aufgezeichnete Pausen. |
| `Unfiltered` beziehungsweise Filterfrequenzen | Aktive Filter der Anzeigekopie. Standardmäßig ist kein Filter aktiv. |
| `Auto / channel` | Jeder Kanal erhält einen eigenen Bereich für das sichtbare Zeitfenster. |
| `EEG 1 · ±46.4 µV`, darunter `DC -0.4 µV` | Sichtbarer Bereich und abgezogener Median dieses Kanals. Die y-Achse zeigt Abweichungen von diesem Median in µV. |
| `CLIPPED: …%` | Anteil sichtbarer Samples außerhalb des gewählten Bereichs. Die Begrenzung betrifft nur die Zeichnung. |
| Spektrogramm und Farbskala | Leistungsdichte des ausgewählten Kanals in dB bezogen auf 1 µV²/Hz. Standardmäßig entspricht der feste Farbbereich −20 bis 40 dB. |
| Delta, Theta, Alpha, Beta, Gamma | Frequenzbänder mit Grenzen bei 0,5, 4, 8, 13, 30 und 100 Hz; nur der sichtbare Frequenzbereich wird beschriftet. |
| Schraffierte Frequenzbereiche | Bereich außerhalb der nominalen Anzeigefiltergrenzen. Geringe Leistung dort kann durch den Filter entstehen. |
| Linie bei 50 Hz | Orientierung für mögliche Netzstörungen; sie entfernt keine Signalanteile. |
| `Raise legs #1 (+3)` | Kurzer Anzeigename für Trial 1 und drei weitere Marker am selben Zeitpunkt. Die vollständigen Beschreibungen bleiben erhalten. |
| Orange Markerlinie und `MARKER DETAILS` | Ausgewählter Ereigniszeitpunkt und Details eines einzelnen Markers. Die Auswahl kann beim Blättern außerhalb des sichtbaren Ausschnitts liegen; ihre Zeit steht weiterhin rechts. |
| Aufnahmeübersicht unter dem Spektrogramm | Alle Markerpositionen und blau hervorgehobenes sichtbares Zeitfenster. Übersicht und Kopfzeile folgen der aufgezeichneten Zeit, nicht dem Live-Countdown des Experiments. |

Die Darstellung passt sich beim Vergrößern oder Verkleinern des Fensters an. Wenn für Kurzbeschriftungen nicht genug Platz bleibt, werden weniger davon gezeichnet; die Marker selbst und ihre Details bleiben verfügbar. Bei langen Zeitfenstern erhält die reduzierte Linienzeichnung die Minima und Maxima der zusammengefassten Samples, damit schmale Ausschläge sichtbar bleiben.

| Bedienung | Funktion |
|---|---|
| Pfeil links/rechts | Um ein halbes Zeitfenster zurück/weiter |
| Shift + Pfeil links/rechts | Um ein ganzes Zeitfenster zurück/weiter |
| Schaltflächen `< Window` / `Window >` | Um ein ganzes Zeitfenster zurück/weiter |
| Home / End | Ersten/letzten Ausschnitt anzeigen |
| `+` / `-` | Amplitudenanzeige vergrößern/verkleinern |
| `a` oder Schaltfläche `Auto` | Vergrößerung und feste Skalierung zurücksetzen; wieder automatisch pro Kanal anpassen |
| Klick in eine EEG-Spur oder Kanal-Schaltflächen rechts | Kanal für das Spektrogramm wählen |
| `Fit colors` | Farbgrenzen aus dem 5. und 99. Perzentil der gültigen sichtbaren Leistungsdichte bestimmen und für folgende Ansichten festhalten |
| `Reset colors` | Spektrogramm-Farbgrenzen auf −20 bis 40 dB zurücksetzen |
| Frequenzskalen-Schaltfläche rechts | Zwischen logarithmischer und linearer Frequenzachse wechseln |
| Klick in die Marker-Zeitleiste | Marker bei dieser Position auswählen |
| Schaltflächen `< Event` / `Event >` | Zum vorherigen/nächsten einzelnen Marker wechseln, auch bei identischen Zeitpunkten |
| Klick in die Aufnahmeübersicht oder Zeitschieber | Zu einer anderen Stelle der Aufnahme wechseln |
| Eingabefeld `Window (s)` | Anzahl sichtbarer Sekunden ändern und mit Enter bestätigen |
| Scrollen über den Markerdetails | Längere Beschreibungen durchsehen |

Die Tastaturbefehle gelten bei fokussiertem Viewer. Nach Eingaben in `Window (s)` außerhalb des Textfelds klicken, um wieder per Pfeiltaste zu navigieren. Beim Erreichen des Aufnahmeendes wird das Fenster auf den letzten vollständigen Ausschnitt begrenzt. Ist die ganze Aufnahme kürzer als die Fensterdauer, wird die gesamte Aufnahme gezeigt.

Klicks zur Navigation und Markerauswahl ändern keine Annotationen. Die Pan-/Zoom-Funktionen der allgemeinen Matplotlib-Werkzeugleiste sind in dieser Ansicht deaktiviert; verwende die oben genannten Bedienelemente. Die Speicherfunktion der Werkzeugleiste bleibt verfügbar. Die eigenen MNE-Browserfunktionen zum Bearbeiten von Annotationen oder Markieren schlechter Kanäle gehören nicht zu dieser Ansicht. Solche Auswertungsschritte lassen sich gesondert an den importierten MNE-Daten durchführen.

Für einen einheitlichen Amplitudenbereich über alle Kanäle eine feste Skalierung verwenden:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 25 --duration 20 --scale-uv 100
```

Die Ansicht beginnt bei Sekunde 25 und zeigt 20 Sekunden. `--scale-uv 100` setzt den sichtbaren Bereich auf ±100 µV um den jeweiligen Kanalmedian. `--scale-uv` ist immer in Mikrovolt angegeben, unabhängig von der Einheit der ursprünglichen CSV. Werte außerhalb des Bereichs bleiben innerhalb ihrer Kanalachse abgeschnitten; `CLIPPED` mit dem Anteil betroffener Samples weist darauf hin. Auch eine interaktive Vergrößerung mit `+` kann Werte abschneiden. Mit `a` zur automatischen Anpassung zurückkehren. Interaktive Änderungen werden beim Schließen nicht automatisch gespeichert.

### Frequenzbänder über die Zeit lesen

Die Frequenzachse beginnt bei 0,5 Hz und ist standardmäßig logarithmisch, damit auch Delta und Theta neben den breiteren höheren Bändern lesbar bleiben. Die Achsenwerte sind tatsächliche Hz-Werte. `--frequency-scale linear` wählt gleiche Abstände pro Hz. Die Obergrenze ist standardmäßig 100 Hz; `--spectrogram-max HZ` ändert sie, begrenzt durch die Nyquist-Frequenz von 125 Hz bei 250 Hz Abtastrate.

| Band | Beschrifteter Bereich |
|---|---:|
| Delta (δ) | 0,5–4 Hz |
| Theta (θ) | 4–8 Hz |
| Alpha (α) | 8–13 Hz |
| Beta (β) | 13–30 Hz |
| Gamma (γ) | 30–100 Hz |

Die Bandgrenzen sind gebräuchliche Konventionen und können in einer späteren Auswertung anders festgelegt werden. Beschriftungen enden an der gewählten Obergrenze; ein abgeschnittener Gamma-Bereich ist kein vollständiges Gamma-Band.

Die Berechnung verwendet 2-s-Hann-Fenster mit 0,5-Hz-Frequenzabstand. Der Zielabstand zwischen Fenstern beträgt 0,25 s und wird auf ganze Samples gerundet; bei 250 Hz sind das 62 Samples beziehungsweise 0,248 s. Die Berechnung bleibt an der Aufnahme ausgerichtet, sodass Blättern bereits betrachtete Zeitpunkte nicht anders berechnet. Auch längere Ansichten behalten diesen Zeitabstand bei.

Jede Zeitspalte beschreibt ein ganzes 2-s-Fenster um ihren Mittelpunkt. Übergänge erscheinen dadurch ungefähr eine Sekunde vor und nach dem tatsächlichen Wechsel geglättet. Es werden nur vollständige Fenster verwendet: an Anfang und Ende der Aufnahme bleiben Bereiche grau. Eine Aufnahme unter 2 s erhält einen Hinweis auf zu wenige Daten. Ein kurzer sichtbarer Ausschnitt kann trotzdem Spektralwerte aus vollständigen Fenstern mit Daten außerhalb des Ausschnitts zeigen.

Die Farbgrenzen bleiben beim Blättern, Wechseln des Kanals und Ändern der Amplitudenskalierung gleich. Dadurch sind Farben zwischen Ansichten vergleichbar. Mit `Fit colors` lässt sich der Kontrast an den sichtbaren Ausschnitt anpassen; danach gilt der neue Farbbereich weiter, bis er erneut angepasst oder mit `Reset colors` zurückgesetzt wird. Die Farbskala nennt die jeweils gültigen Grenzen. Farben an den Skalenenden können auch stärkere oder schwächere Werte enthalten.

Das Spektrogramm nutzt dieselbe gefilterte oder ungefilterte Anzeigekopie wie die Spuren. Schraffierung außerhalb der nominalen Filtergrenzen kennzeichnet gedämpfte Bereiche; die Übergänge realer Filter sind nicht scharf. Beispielsweise reduziert ein 1–40-Hz-Filter Delta unter 1 Hz und große Teile von Gamma. Die 50-Hz-Linie hilft, Netzstörungen zu erkennen. Bewegung und Muskelaktivität können vor allem höhere Frequenzen, Blinzeln und Augenbewegungen vor allem niedrige Frequenzen mitbestimmen. Die Ansicht bereinigt diese Artefakte nicht; ein Band belegt keinen bestimmten mentalen Zustand.

Beispiel mit EEG 3, linearer Frequenzachse und einer Obergrenze von 60 Hz:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --spectrogram-channel "EEG 3" --frequency-scale linear --spectrogram-max 60
```

## 5. Labels und Cue-Zeitpunkte

Zur Datei `test01.csv` sucht das Skript automatisch `test01.csv.events.csv`.
Es übernimmt Labels aus `mark LABEL` und `cue LABEL | TEXT`. Vorschauen mit
`cue text` oder `cue rest` erzeugen keine Labels.

Die Markerposition wird aus `samples_received / 250` berechnet. In einer früheren
Test01-Aufnahme lagen die Labels beispielsweise bei:

| Label | Empfangene Samples | Position in MNE |
|---|---:|---:|
| `rest` | 7000 | 28,0 s |
| `hands_up` | 10375 | 41,5 s |
| `hands_down` | 16925 | 67,7 s |
| `imagine hands` | 21200 | 84,8 s |
| `rest` | 23825 | 95,3 s |

Manuelle Labels und Labels älterer Aufnahmen werden wortgetreu übernommen. `imagine hands` und `imagine_hands` sind verschiedene Labels. In der aktuellen manuellen Cue-CLI besitzen beide keine eigene Zuordnung und erscheinen als freier Text. Die automatische Sitzung verwendet dagegen `imagine_arms` beziehungsweise `imagine_legs` als Bedingungen und zeigt `ARME VORSTELLEN` beziehungsweise `BEINE VORSTELLEN`.

Die Positionen sind Näherungen: Die empfangene Samplezahl beschreibt den
Verarbeitungsstand bei Eingabe, keinen gemessenen physikalischen Cue-Beginn.
Bluetooth-Puffer und blockweises Lesen erzeugen Unsicherheit. `elapsed_s`
beschreibt dagegen verstrichene Host-Zeit; beide Zeitachsen können auseinanderliegen.
Marker außerhalb der Sample-Zeitachse werden mit einem Hinweis ausgelassen.
Für präzise EEG–MEG-Synchronisation sind validierte gemeinsame Trigger erforderlich.

Bei Aufnahmen aus `start session` enthält die Annotationsbeschreibung außerdem die Aufgabenart, Trial- und Attempt-ID, Block, Phase und gegebenenfalls Rechenzahlen. Beispiel:

```text
task_onset | run=Motorik | condition=arms | block=1 | trial=1 | attempt=2 | phase=task | status=completed
```

`status=invalid` markiert einen später invalidierten Versuch, `status=completed` einen Versuch mit Abschlussmarker ohne Invalidierung und `status=incomplete` einen Versuch ohne dokumentierten Abschluss. Eine Invalidierung gilt für alle Marker desselben Attempts, auch wenn sie erst später in der Ereignisdatei steht. Diese Angaben bleiben im FIF-Export erhalten. Die Auswahl gültiger Trials erfolgt weiterhin ausdrücklich in der Auswertung; die Punktannotationen schließen Daten nicht automatisch aus. Manuelle Labels und ältere Ereignisdateien werden weiterhin wortgetreu übernommen.

Start- und Endlabels werden als einzelne Marker importiert, nicht automatisch
als zusammenhängende Phasen. Die Dauer der Annotationspunkte ist null. Die Zusammenfassung zeitgleicher Marker und gekürzte Beschriftungen betreffen nur die Anzeige: Alle ursprünglichen Annotationsbeschreibungen bleiben in den MNE-Daten und im FIF-Export erhalten. Mit `< Event` / `Event >` lassen sich auch zeitgleiche Einträge einzeln lesen. Wiederholte Klicks auf dieselbe Markerposition wechseln ebenfalls zwischen den dortigen Einträgen.

## 6. Gefilterte Ansicht

Die Ansicht startet standardmäßig ungefiltert bei Sekunde 0. Große Einschwingvorgänge direkt nach Aufnahmebeginn können den automatischen Amplitudenbereich stark vergrößern. Zum Prüfen eines späteren Ausschnitts mit ausdrücklich gewähltem 1–40-Hz-Bandpass:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 60 --duration 20 --highpass 1 --lowpass 40
```

Sie zeigt die Sekunden 60–80 mit automatischer Skalierung und einem Bandpass
von 1–40 Hz. Die langsame Drift wird unterdrückt; schnellere Schwankungen und
die Labels sind dadurch besser sichtbar. Die Einheit `uV` weiterhin mit dem
Unicorn-Befehl `config` bestätigen.

Für die vorhandene Aufnahme auf dem Mac lautet derselbe Befehl vollständig:

```bash
cd /Users/theoa/Desktop/Projects/EEGvsMEG
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" \
  --unit uV --start 60 --duration 20 --highpass 1 --lowpass 40
```

Ohne `--highpass 1 --lowpass 40` wird derselbe Ausschnitt ungefiltert angezeigt. Für einen direkten Amplitudenvergleich kann bei beiden Aufrufen zusätzlich `--scale-uv 100` gewählt werden; danach auf `CLIPPED` achten. Filter und Skalierung werden nicht in der Sitzung gespeichert und müssen beim nächsten Aufruf erneut angegeben werden.

### Drift, große Ausschläge und feste Skalierung

Ein großer Gleichspannungsanteil wird für die Anzeige durch die Medianzentrierung entfernt; eine Änderung des Offsets im sichtbaren Zeitfenster bleibt als Drift sichtbar. Die automatische Anpassung zeigt pro Kanal dessen eigenen Wertebereich. Bei fester Skalierung wie `--scale-uv 100` können starke Schwankungen über ±100 µV hinausgehen und werden an der Grenze des zugehörigen Kanals abgeschnitten. Das wird sichtbar angezeigt; die Originaldaten werden nicht abgeschnitten.

Zum Prüfen der ungefilterten Drift die feste Skalierung weglassen:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 60 --duration 20
```

Für eine Ansicht mit unterdrückter langsamer Drift anschließend den obigen Befehl mit `--highpass 1 --lowpass 40` verwenden. Eine gut lesbare gefilterte Kurve bestätigt allein keine gute Signalqualität; die Ursache der Drift wird dadurch nicht bestimmt. Originaldaten und EEG-Einheit gesondert prüfen.

`--start` bestimmt nur den anfänglichen Ausschnitt. Beim Weiterblättern ändern sich die angezeigten Sekunden; maßgeblich ist die Zeitachse. Automatische Skalierung wird dabei für den neuen Ausschnitt neu berechnet.

### Weitere Aufnahmen

Zuerst ungefilterte Daten prüfen. Eine optionale Ansicht mit 1–40 Hz:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --highpass 1 --lowpass 40
```

Die Filterung erfolgt an einer Kopie für die Ansicht. Sie verändert weder CSV
noch die ungefilterten Daten beim FIF-Export. 1–40 Hz ist ein Beispiel für die
Sichtprüfung; Auswertungsfilter richten sich nach der wissenschaftlichen Fragestellung.

## 7. MNE-Datei und Bild speichern

EEG und Labels als FIF-Datei importieren, ohne Fenster:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --no-show --save-fif "..\recordings\Test01\test01_raw.fif"
```

Bild eines Ausschnitts speichern:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 25 --duration 20 --snapshot "..\recordings\Test01\test01_preview.png" --no-show
```

Vorhandene Ausgabedateien werden abgelehnt. Wähle dann einen neuen Namen.
Der Zielordner muss existieren. FIF enthält EEG und Labels, keine anderen
Gerätekanäle und keine Elektrodenpositionen. Die ursprüngliche CSV bleibt erhalten.

`--snapshot` speichert den **anfänglichen** Ausschnitt aus `--start` und `--duration` einschließlich Spektrogramm des gewählten Startkanals, bevor das interaktive Fenster geöffnet wird. Zum Speichern nach interaktivem Blättern, Kanalwechsel oder Anpassung der Farbgrenzen die Speicherfunktion der Matplotlib-Werkzeugleiste verwenden. Mit `--no-show` wird kein Fenster geöffnet; ohne Exportoption entstehen keine Ausgabedateien. Das Spektrogramm und seine Anzeigeeinstellungen werden nicht als EEG-Daten im FIF gespeichert.

PNG und FIF können in einem Aufruf erzeugt werden. Beispiel auf dem Mac: gefiltertes Vorschaubild, aber **ungefilterte** EEG-Werte und vollständige Marker im FIF:

```bash
cd /Users/theoa/Desktop/Projects/EEGvsMEG
~/.venvs/eeg-mne/bin/python view_eeg.py \
  "../recordings/P-001/session_20261021_194704.csv" \
  --unit uV --start 60 --duration 20 --highpass 1 --lowpass 40 \
  --snapshot "../recordings/P-001/session_20261021_194704_preview.png" \
  --save-fif "../recordings/P-001/session_20261021_194704_raw.fif" \
  --no-show
```

FIF später aus einem Python-Skript im Projektstamm mit derselben getrennten Zeitansicht öffnen:

```python
import mne
import matplotlib.pyplot as plt
from analysis.eeg_browser import create_browser

raw = mne.io.read_raw_fif(
    "../recordings/Test01/test01_raw.fif",
    preload=True,
)
browser = create_browser(raw, title="Gespeicherte Aufnahme")
plt.show(block=True)
```

Eine FIF-Datei nicht als CSV-Argument an `view_eeg.py` übergeben; dafür den obigen Python-Code verwenden. FIF-Werte sind bereits in Volt gespeichert, deshalb beim späteren Lesen nicht erneut mit `--unit` umrechnen.

## 8. Alle Skriptoptionen

| Argument | Bedeutung |
|---|---|
| `CSV` | Pfad zur EEG-Datei, erforderlich |
| `--unit uV`, `--unit mV`, `--unit V` | Tatsächliche Einheit der CSV-Werte, erforderlich |
| `--start SEKUNDEN` | Beginn des dargestellten Ausschnitts, Standard 0 |
| `--duration SEKUNDEN` | Fensterbreite, Standard 10 |
| `--scale-uv WERT` | Gemeinsamer sichtbarer Bereich ±WERT µV um den Kanalmedian; sonst automatische Anpassung je Kanal und Ausschnitt |
| `--highpass HZ` | Optionaler Hochpass für die Ansicht |
| `--lowpass HZ` | Optionaler Tiefpass für die Ansicht |
| `--spectrogram-channel NAME` | Startkanal des Spektrogramms, z. B. `"EEG 3"`; standardmäßig erster EEG-Kanal |
| `--frequency-scale {log,linear}` | Frequenzachse des Spektrogramms; Standard `log` |
| `--spectrogram-max HZ` | Obere dargestellte Frequenz; Standard 100 Hz, höchstens Nyquist-Frequenz |
| `--save-fif PFAD` | Ungefilterte EEG-Daten und Labels exportieren |
| `--snapshot PFAD` | Anfänglichen Ausschnitt aus `--start` / `--duration` als PNG speichern |
| `--no-show` | Ohne interaktives Fenster importieren/exportieren |
| `--help` | Kurzreferenz |

`--duration` und `--scale-uv` müssen endlich und größer als null sein. `--start` muss innerhalb der Aufnahme liegen. Filtergrenzen müssen zwischen 0 und 125 Hz liegen, beide Grenzen ausschließlich; bei zwei Grenzen muss der Hochpass kleiner als der Tiefpass sein.

### Zweiter Einstieg: `analysis/view_eeg.py`

Dieses Skript nutzt dieselbe getrennte Zeitansicht, hat aber einen kleineren, **anderen** Optionssatz:

| Option | Bedeutung |
|---|---|
| `CSV`, `--unit` | Wie beim Hauptviewer erforderlich |
| `--filtered` | Anzeigekopie mit 50-Hz-Notch und 0,5–30-Hz-Bandpass |
| `--psd` | Welch-Leistungsdichtespektrum statt Zeitkurven, bis 100 Hz |
| `--spectrogram-channel NAME` | Startkanal für das Spektrogramm in der Zeitansicht |
| `--frequency-scale {log,linear}` | Frequenzachse des Spektrogramms; Standard `log` |
| `--spectrogram-max HZ` | Obere dargestellte Frequenz des Spektrogramms; Standard 100 Hz, begrenzt durch Nyquist |
| `--help` | Hilfe für diesen Einstieg |

Beispiel auf dem Mac, aus dem Projektstamm:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.view_eeg \
  "../recordings/P-001/session_20261021_194704.csv" --unit uV --filtered --psd
```

Unter Windows denselben Aufruf mit `& .\.venv-mne\Scripts\python.exe -m analysis.view_eeg` beginnen. Auch der direkte Skriptaufruf `analysis/view_eeg.py` ist möglich. Die Spektrogramm-Optionen gelten für die Zeitansicht ohne `--psd`; `--psd` öffnet stattdessen ein Spektrum ohne Zeitachse. Beide Einstiege unterstützen `--start`, `--duration`, `--scale-uv`, `--no-show` und `--view waterfall`. Die Optionen `--highpass`, `--lowpass`, `--snapshot` und `--save-fif` gehören zum **Hauptviewer** und sind bei diesem zweiten Einstieg nicht verfügbar. Für die Wasserfallansicht zusätzlich `python -m pip install "plotly>=6,<7"` in derselben Umgebung ausführen; alle Anzeigeoptionen sind in der [README](../../README.md#interaktive-wasserfallansicht) beschrieben. Für die normale Sichtprüfung und Exporte den Hauptviewer verwenden.

## 9. Fehler und Grenzen

| Problem | Lösung |
|---|---|
| `No module named mne` | Windows: Python aus `.venv-mne` verwenden. Mac: `~/.venvs/eeg-mne/bin/python` verwenden. Pakete in derselben Umgebung installieren. |
| CSV nicht gefunden | Arbeitsordner und CSV-Pfad prüfen. |
| Keine Labels | Passende `.events.csv` und deren Inhalt prüfen. |
| Sehr große/kleine Werte | Einheit mit `config` prüfen; `--unit` korrigieren. |
| Kurve ist abgeschnitten | Kennzeichnung am Kanal beachten; mit `a` automatisch anpassen oder `--scale-uv` erhöhen. Drift zuerst ungefiltert prüfen, eine gefilterte Ansicht ausdrücklich mit `--highpass 1 --lowpass 40` wählen. |
| Spektrogramm wirkt überall gleich hell/dunkel | Einheit und Farbskala prüfen; mit `Fit colors` den Kontrast für den sichtbaren Ausschnitt anpassen. |
| Grauer Bereich im Spektrogramm | Am Aufnahmeanfang/-ende fehlt ein vollständiges 2-s-Fenster; bei Aufnahmen unter 2 s sind keine Spektralwerte verfügbar. |
| Ein Frequenzband fehlt oder wirkt sehr schwach | Frequenzobergrenze und aktive Filter prüfen; schraffierte Bereiche sind außerhalb des nominalen Filterbereichs. |
| Viele Marker an derselben Stelle | Zeitleiste auswählen und mit `< Event` / `Event >` die einzelnen vollständigen Beschreibungen rechts durchgehen. |
| Ungültige Samples | Leere Felder, NaN/Inf und unvollständige CSV prüfen. Aufnahme zuerst stoppen. |
| Nicht fortlaufender `sample_index` | CSV ist gekürzt, verändert oder unvollständig; Zeitbasis vor Import klären. |
| Counter-Unterbrechungen | Können Verluste, Rücksetzungen oder Überläufe sein; keine automatische Reparatur. |
| Kein Fenster | Ohne `--no-show` starten; auf einem Rechner mit Desktop ausführen. |
| Pfeiltasten bewegen nichts | Viewer fokussieren und außerhalb von `Window (s)` klicken. Alternativ die Fenster-Schaltflächen oder den Zeitschieber verwenden. |
| Änderung am Skript scheint nicht wirksam | Alten Viewer schließen und den Befehl neu ausführen; ein bereits offenes Fenster lädt Codeänderungen nicht nach. |
| `No module named analysis` | Vollständiges Repository einschließlich `analysis/` verwenden; nicht nur die einzelne Viewer-Datei kopieren. |
| `darkdetect`-Hinweis | Hinweis zur automatischen Farbschemaerkennung. Wenn sich die Ansicht öffnet, ist das kein Fehler beim Laden der EEG-Daten. |
| Ausgabe existiert bereits | Neuen FIF-/PNG-Dateinamen wählen. |

Das Skript repariert keine verlorenen Samples und setzt keine Elektrodenpositionen
oder Referenz. `EEG 1` bis `EEG 8` sind keine bestätigten 10–20-Positionsnamen.
Für Kopfkarten zuerst die tatsächliche Kanalzuordnung des Headsets bestimmen.

## 10. Viewer-Regressionstests

Aus dem Projektstamm mit dem Python der eingerichteten MNE-Umgebung ausführen:

```bash
~/.venvs/eeg-mne/bin/python -m unittest analysis.test_event_annotations analysis.test_time_frequency analysis.test_eeg_browser analysis.test_spectrogram_browser analysis.test_view_eeg_cli
```

Unter Windows:

```powershell
& .\.venv-mne\Scripts\python.exe -m unittest analysis.test_event_annotations analysis.test_time_frequency analysis.test_eeg_browser analysis.test_spectrogram_browser analysis.test_view_eeg_cli
```

Die Tests prüfen dichte Marker und Fenstergrößenänderungen, getrennte Kanalachsen, Skalierung und Abschneidehinweise, Navigation, unveränderte Daten sowie echte PNG-Ausgabe ohne Desktop und einen ungefilterten FIF-Speicher-/Ladetest. Sie benötigen MNE, NumPy, pandas und Matplotlib. Diese Prüfungen ersetzen keine fachliche Bewertung der Signalqualität.

## Quellen

- [MNE RawArray: Array-Import, Anzeige und FIF-Speicherung](https://mne.tools/1.12/generated/mne.io.RawArray.html)
- [MNE Annotations: Labels und Zeitangaben](https://mne.tools/1.12/generated/mne.Annotations.html)
- [MNE create_info: EEG-Einheiten in Volt](https://mne.tools/stable/generated/mne.create_info.html)
