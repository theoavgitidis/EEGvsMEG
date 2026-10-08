# Unicorn-Aufnahmen mit MNE ansehen

Das Skript `view_eeg.py` im Projektstamm liest die EEG-Kanäle deiner CSV und
die Labels aus der danebenliegenden `.events.csv` in MNE ein. Die Originaldateien
bleiben unverändert. Es funktioniert für neue Versuche unter `EEG/recordings`
und frühere CSV-Dateien im Projektstamm. Es zeigt abgeschlossene Aufnahmen,
keinen Live-Datenstrom.

## 1. Installation prüfen

Alle Befehle dieser Anleitung gehören in PowerShell. Nur `stop`, `status` und
`config` gehören in das laufende Unicorn-Terminal.

```powershell
cd C:\Users\DHBWQ\Desktop\EEG\EEGvsMEG
& .\.venv-mne\Scripts\python.exe -c "import mne, pandas; print('MNE-Version:', mne.__version__)"
```

Die Umgebung ist auf diesem Rechner bereits eingerichtet. Bei einer neuen
Installation einmalig:

```powershell
python -m venv .venv-mne
& .\.venv-mne\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-mne\Scripts\python.exe -m pip install mne pandas matplotlib
```

Eine Aktivierung mit `Activate.ps1` ist nicht nötig. Rufe immer den Interpreter
in `.venv-mne` auf, damit Installation und Ausführung dieselben Pakete verwenden.

## 2. Aufnahme beenden und Einheit prüfen

Im Unicorn-Terminal:

```text
stop
status
config
```

Prüfe bei verbundenem Headset die Einheit der EEG-Kanäle in `config`.
Die CSV enthält keine Einheit; MNE erwartet Volt. Deshalb verlangt das Skript
die ausdrückliche Angabe `--unit`. Die Beispiele nehmen Mikrovolt an; das ist
eine Annahme, keine aus der CSV verifizierte Einheit.

| Anzeige in `config` | Argument | Umrechnung zu Volt |
|---|---|---|
| `µV`, `μV`, `uV` | `--unit uV` | Wert × 0,000001 |
| `mV` | `--unit mV` | Wert × 0,001 |
| `V` | `--unit V` | Wert unverändert |

## 3. Deine aktuelle Aufnahme öffnen

Für die vorhandene Aufnahme `Test01/test01.csv`:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV
```

Es öffnet sich ein interaktives MNE-Fenster. PowerShell bleibt beschäftigt,
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

Die EEG-Kanäle stehen untereinander, die Zeitachse zeigt Sekunden.
Das Skript wählt nur Spalten wie `EEG 1` bis `EEG 8`; Batterie, Counter,
Beschleunigung und Gyroskop werden nicht als EEG importiert. Die Abtastrate
ist entsprechend der CLI fest auf 250 Hz eingestellt.

| Bedienung | Funktion |
|---|---|
| Pfeil links/rechts | Zeitfenster verschieben |
| Shift + Pfeil links/rechts | Um ein ganzes Zeitfenster springen |
| `+` / `-` | Amplitudenanzeige vergrößern/verkleinern |
| `a` | Annotationsmodus |
| Klick auf Kanalnamen | Kanal als schlecht markieren bzw. Markierung entfernen |

Standardmäßig nutzt die Anzeige automatische Skalierung und entfernt für die
Ansicht den Mittelwert der Kanäle. Das verändert die Originaldaten nicht.
Für Vergleiche eine feste Skalierung verwenden:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 25 --duration 20 --scale-uv 100
```

Die Ansicht beginnt bei Sekunde 25 und zeigt 20 Sekunden. `--scale-uv` ist
immer in Mikrovolt angegeben, unabhängig von der Einheit der ursprünglichen CSV.
Interaktive Änderungen werden beim Schließen nicht automatisch gespeichert.

## 5. Labels und Cue-Zeitpunkte

Zur Datei `test01.csv` sucht das Skript automatisch `test01.csv.events.csv`.
Es übernimmt Labels aus `mark LABEL` und `cue LABEL | TEXT`. Vorschauen mit
`cue text` oder `cue rest` erzeugen keine Labels.

Die Markerposition wird aus `samples_received / 250` berechnet. In deiner
Test01-Aufnahme liegen die Labels ungefähr bei:

| Label | Empfangene Samples | Position in MNE |
|---|---:|---:|
| `rest` | 7000 | 28,0 s |
| `hands_up` | 10375 | 41,5 s |
| `hands_down` | 16925 | 67,7 s |
| `imagine hands` | 21200 | 84,8 s |
| `rest` | 23825 | 95,3 s |

Das Skript übernimmt Labels wortgetreu. `imagine hands` und `imagine_hands`
sind verschiedene Labels. In der Cue-CLI ist nur `imagine_hands` eine
vordefinierte Anweisung; das andere Label wird als Text angezeigt.

Die Positionen sind Näherungen: Die empfangene Samplezahl beschreibt den
Verarbeitungsstand bei Eingabe, keinen gemessenen physikalischen Cue-Beginn.
Bluetooth-Puffer und blockweises Lesen erzeugen Unsicherheit. `elapsed_s`
beschreibt dagegen verstrichene Host-Zeit; beide Zeitachsen können auseinanderliegen.
Marker außerhalb der Sample-Zeitachse werden mit einem Hinweis ausgelassen.
Für präzise EEG–MEG-Synchronisation sind validierte gemeinsame Trigger erforderlich.

Start- und Endlabels werden als einzelne Marker importiert, nicht automatisch
als zusammenhängende Phasen. Die Dauer der Annotationspunkte ist null.

## 6. Gefilterte Ansicht

Für deine Aufnahme `Test01/test01.csv` hat folgende Ansicht funktioniert:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 60 --duration 20 --highpass 1 --lowpass 40
```

Sie zeigt die Sekunden 60–80 mit automatischer Skalierung und einem Bandpass
von 1–40 Hz. Die langsame Drift wird unterdrückt; schnellere Schwankungen und
die Labels sind dadurch besser sichtbar. Die Einheit `uV` weiterhin mit dem
Unicorn-Befehl `config` bestätigen.

### Schräge Linien oder scheinbar leere Kanäle

Bei einer starken langsamen Drift und fester Skalierung wie `--scale-uv 100`
können die Kurven aus dem sichtbaren Bereich laufen. Dann erscheinen nur kurze
schräge Linien; das bedeutet nicht, dass die CSV leer ist. In Test01 steigt
`EEG 1` zwischen Sekunde 60 und 80 um etwa 20.000 CSV-Einheiten. Falls die
Einheit Mikrovolt stimmt, entspricht das etwa 20.000 µV.

Zum Prüfen der ungefilterten Drift die feste Skalierung weglassen:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py "..\recordings\Test01\test01.csv" --unit uV --start 60 --duration 20
```

Für die übersichtliche Ansicht danach den obigen Befehl mit `--highpass 1`
und `--lowpass 40` verwenden. Eine gut lesbare gefilterte Kurve bestätigt
allein keine gute Signalqualität; die Ursache der Drift wird dadurch nicht
bestimmt. Originaldaten und EEG-Einheit gesondert prüfen.

`--start` bestimmt nur den anfänglichen Ausschnitt. Wenn du im Browser weiter
blätterst, ändern sich die angezeigten Sekunden; maßgeblich ist die Zeitachse.

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

FIF später aus einem Python-Skript öffnen:

```python
import mne

raw = mne.io.read_raw_fif(
    r"C:\Users\DHBWQ\Desktop\EEG\recordings\Test01\test01_raw.fif",
    preload=True,
)
mne.viz.set_browser_backend("matplotlib")
raw.plot(block=True)
```

## 8. Alle Skriptoptionen

| Argument | Bedeutung |
|---|---|
| `CSV` | Pfad zur EEG-Datei, erforderlich |
| `--unit uV`, `--unit mV`, `--unit V` | Tatsächliche Einheit der CSV-Werte, erforderlich |
| `--start SEKUNDEN` | Beginn des dargestellten Ausschnitts, Standard 0 |
| `--duration SEKUNDEN` | Fensterbreite, Standard 10 |
| `--scale-uv WERT` | Feste Amplitudenskalierung; sonst automatisch |
| `--highpass HZ` | Optionaler Hochpass für die Ansicht |
| `--lowpass HZ` | Optionaler Tiefpass für die Ansicht |
| `--save-fif PFAD` | Ungefilterte EEG-Daten und Labels exportieren |
| `--snapshot PFAD` | Aktuellen Ausschnitt als PNG speichern |
| `--no-show` | Ohne interaktives Fenster importieren/exportieren |
| `--help` | Kurzreferenz |

## 9. Fehler und Grenzen

| Problem | Lösung |
|---|---|
| `No module named mne` | Python aus `.venv-mne` verwenden; dort Pakete installieren. |
| CSV nicht gefunden | Arbeitsordner und CSV-Pfad prüfen. |
| Keine Labels | Passende `.events.csv` und deren Inhalt prüfen. |
| Sehr große/kleine Werte | Einheit mit `config` prüfen; `--unit` korrigieren. |
| Nur schräge Linien oder scheinbar leere Kanäle | Feste Skalierung weglassen und ungefilterte Drift prüfen. Für eine übersichtliche Kopie `--highpass 1 --lowpass 40` verwenden; siehe Abschnitt 6. |
| Ungültige Samples | Leere Felder, NaN/Inf und unvollständige CSV prüfen. Aufnahme zuerst stoppen. |
| Nicht fortlaufender `sample_index` | CSV ist gekürzt, verändert oder unvollständig; Zeitbasis vor Import klären. |
| Counter-Unterbrechungen | Können Verluste, Rücksetzungen oder Überläufe sein; keine automatische Reparatur. |
| Kein Fenster | Ohne `--no-show` starten; auf einem Rechner mit Desktop ausführen. |
| Ausgabe existiert bereits | Neuen FIF-/PNG-Dateinamen wählen. |

Das Skript repariert keine verlorenen Samples und setzt keine Elektrodenpositionen
oder Referenz. `EEG 1` bis `EEG 8` sind keine bestätigten 10–20-Positionsnamen.
Für Kopfkarten zuerst die tatsächliche Kanalzuordnung des Headsets bestimmen.

## Quellen

- [MNE RawArray: Array-Import, Anzeige und FIF-Speicherung](https://mne.tools/1.12/generated/mne.io.RawArray.html)
- [MNE Annotations: Labels und Zeitangaben](https://mne.tools/1.12/generated/mne.Annotations.html)
- [MNE create_info: EEG-Einheiten in Volt](https://mne.tools/stable/generated/mne.create_info.html)
