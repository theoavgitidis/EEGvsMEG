# Handbewegungen: ERD/ERS und 3D-Kopfansicht

Die Offline-Ansicht wertet **Protokoll 2.0** aus: linke/rechte Faustbewegung und
linke/rechte kinästhetische Vorstellung, getrennt nach Bedingung. Beidseitige
Vorstellung, Fuß- und kognitive Aufgaben sowie die alten Armaufgaben aus 1.0
werden nicht in diese Handbedingungen umgedeutet. Auch eine unvollständige Sitzung
kann vollständige gültige Trials enthalten; die Aufnahme wird dadurch nicht als
abgeschlossen oder wissenschaftlich validiert erklärt.

## Starten

Die bestehende Viewer-Umgebung mit MNE, NumPy, SciPy, pandas und Plotly verwenden.
Die Kopfansicht benötigt die in **MNE 1.13** vorhandene Montage `fsaverage_1005`
und die mitgelieferte fsaverage-Kopfoberfläche. Getestet mit MNE 1.13.2 und
Plotly 6.9.0; kein PyVista, VTK, Qt, individuelles MRT oder fsaverage-Download nötig.
Plotly ist dieselbe optionale Abhängigkeit wie für die Wasserfallansicht
(`python -m pip install 'plotly>=6,<7'`). Bei fehlender Montage/Geometrie die
Version der verwendeten Umgebung prüfen; keine Koordinaten anderer Modelle mischen.

macOS, bei anhand der Metadaten bestätigten Mikrovolt:

```bash
~/.venvs/eeg-mne/bin/python view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds
```

Windows PowerShell, mit der vorhandenen Viewer-Umgebung:

```powershell
& .\.venv-mne\Scripts\python.exe .\view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds
```

**OSCAR ist hier Standard**, auch bei `--signal auto`. Fehlende, unvollständige
oder nicht bestätigte OSCAR-Ausgaben erzeugen einen Fehler. Nur mit ausdrücklichem
Parameter werden Rohdaten verwendet:

```bash
python view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds --signal raw
python analysis/view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds
python -m analysis.view_eeg PFAD_ZUR_SESSION.csv --unit uV --view erds
```

Alle drei Einstiege verwenden dieselbe Berechnung. EEG-, Event- und Sessiondatei
müssen zusammen vorliegen, bei OSCAR zusätzlich Rohdaten, bereinigte Daten und
bestätigte `.processing.json`. Samplingrate und aktivierte Kanal-Einheiten werden
aus den Metadaten geprüft. Der Browser und Plotly werden ausschließlich lokal
bereitgestellt; Beenden mit **Strg+C** im Terminal. Es werden keine Messdaten
an externe Server geschickt. Die bisherigen Zeitkurven-/Wasserfall-Modi behalten
ihre bestehende Signalwahl.

## Bedienung und Bedeutung

- Zwei drehbare Köpfe vergleichen linke und rechte Hand. Ausführung/Vorstellung,
  Frequenzband und Messgröße gelten gemeinsam. Kameras sind gekoppelt; feste
  Ansichten zeigen oben, vorn sowie beide Seiten. L/R bezeichnet die Person.
- **Aufgabenmittel** verwendet nur vollständige 1-s-Fenster in der Aufgabe.
  **Nach Aufgabenende** verwendet Fenstermitten 0,5–2,5 s nach dem tatsächlichen
  `task_offset`; deren Signalunterstützung liegt 0–3 s nach dem Marker.
- **Zeitverlauf** zeigt cuebezogene Fenstermitten mit einem Zeitschieber und
  optionalem Abspielen. Es wird keine Zeit gestreckt. Unterschiedliche tatsächliche
  Aufgabenenden werden in den Diagrammen als gestrichelte Linien angezeigt.
- **Blau = negative ERD**, neutral = 0 %, **Rot = positive ERS**. Feste gemeinsame
  Farbgrenzen bleiben bei Zeit-/Bedingungswechsel erhalten; Überläufe werden
  gezählt. Die absolute Bandpower in µV² hat eine eigene sequenzielle Skala.
- Ein Klick auf einen Messpunkt oder eine Tabellenzeile wählt den Kanal für
  Zeitkurven und Zeit-Frequenz-Karten. Tooltip und Tabelle zeigen Referenz,
  Leistung, Änderung und gültige Trialzahl. Grau/× bedeutet ausgeschlossen oder
  nicht verfügbar, **nicht 0 %**. Die Zeit-Frequenz-Karten bleiben bei Prozentwerten
  und verwenden eine gemeinsame separate Skala von −100 bis +100 %.
- Die Köpfe bleiben neutral; nur die acht gleich großen Messpunkte sind gefärbt.
  Die Ansicht enthält keine Flächeninterpolation und keine Quellenlokalisation.
  Die Standardpositionen sind keine individuell vermessene Anatomie. C3 liegt
  links und ist zur rechten Hand kontralateral, C4 entsprechend zur linken Hand.

Die Zuordnung ist `EEG 1–8 → Fz, C3, Cz, C4, Pz, PO7, Oz, PO8`. Genau benannte
Positionsspalten werden ebenfalls unterstützt; doppelte Zuordnungen werden
zurückgewiesen. Fehlende Kanäle bleiben grau. Generische unbekannte Namen werden
nicht automatisch räumlich zugeordnet. Die reale Belegung am Headset muss vor
wissenschaftlicher Interpretation geprüft werden; eine Bestätigung ist optional
in der QC-Datei dokumentierbar. Die Koordinaten stammen aus `fsaverage_1005`,
Kopf und Sensoren werden in dasselbe MNE-Kopfkoordinatensystem transformiert.
Eine kleine Projektion auf die Oberfläche dient ausschließlich der Sichtbarkeit.

## Berechnung und Grenzen

Für jeden Trial und Kanal werden 250 Samples (1 s bei bestätigten 250 Hz) mit
einem periodischen Hann-Fenster und entferntem Fenstermittel analysiert. Eine
korrekt normierte einseitige PSD liefert µV²/Hz; die Integration über Frequenzbins
liefert µV². Binanteile an Bandgrenzen werden anteilig gewichtet. Hauptbänder:
Mu 8–13 Hz, Beta 13–30 Hz. Sensitivitätsbänder: 8–12 und 13–28 Hz.

Es gibt **keinen zusätzlichen Bandpass, keine neue Referenzierung und keine
Anzeigezentrierung** in dieser Berechnung. Die Eingangsdaten bleiben unverändert.
Zeitkurvenoptionen wie `--filtered`, `--highpass`, `--lowpass`, `--psd`,
`--start`, `--duration`, `--scale-uv`, `--save-fif` und `--snapshot` sind für diesen
Modus nicht vorgesehen; abweichende Einstellungen werden zurückgewiesen.

Die Referenz verwendet vollständige Fenster innerhalb der Vorbereitung vor dem
Cue, frühestens −2 s; nominal liegen deren Mittelpunkte bei −1,5 bis −0,5 s.
Aufgabenmittel entstehen aus vollständigen Aufgabenfenstern, nominal mit
Mittelpunkten 0,5–3,5 s. Zuerst wird Leistung je Trial berechnet, dann über Trials
gemittelt und schließlich normalisiert:

```text
ERD/ERS (%) = 100 × (mittlere Leistung / mittlere Referenzleistung − 1)
```

Nicht zuerst die Spannungen mitteln und nicht die Einzeltrial-Prozentwerte
mitteln. Referenz- und Aufgabenleistung der Einzeltrials stehen zur Kontrolle im
JSON-Bericht. Eine halbe Schwingungsamplitude bedeutet ein Viertel Leistung
(−75 %), doppelte Amplitude vierfache Leistung (+300 %).

100-ms-Schritte sind **keine unabhängige 100-ms-Auflösung**: Jeder Wert enthält
1 s Signal. Das Frequenzraster ist 1 Hz; die Hann-Rauschbandbreite beträgt 1,5 Hz.
Die 6–40-Hz-Karten zeigen auch explorative Komponenten außerhalb der Hauptbänder.
Referenzwerte unterhalb der relativen float64-Rechengenauigkeit (Maschinen-Epsilon
mal gesamter Referenz-PSD je Kanal) werden nicht dividiert: Solche Frequenzbins
bleiben leer, statt numerisches Rundungsrauschen als riesige ERS darzustellen.
Das ist eine numerische Grenze, keine biologische Signifikanz-/Rauschschwelle.
Software-Cues messen weder den physikalischen Bildschirm-Onset noch den
tatsächlichen Beginn/Abschluss einzelner Faustzyklen. OSCAR-Samples liegen bereits
auf der Rohsample-Zeitachse; Marker werden nicht nochmals verschoben.

Die Ausgabe ist **deskriptiv**: keine Signifikanzmaske und keine automatisch
validierte Zustands-/Bewegungserkennung. Vorbereitung kann Erwartung enthalten,
Erholung einen verbleibenden Rebound. Keine automatische Ersatzreferenz wird
aus Anfangsbaseline oder früher Erholung ausgewählt. Referenzleistungen über
Trials prüfen; andere Referenzdefinitionen benötigen eine gesonderte dokumentierte
Sensitivitätsauswertung. Ohne EMG lassen sich Muskelbeiträge nicht ausschließen.

## Ausschlüsse und manuelle Qualitätsprüfung

Retrospektive Invalidierung hat Vorrang vor Abschlussmarkern. Vollständige,
eindeutige `trial_start`, `cue_onset`, `task_offset` und `trial_end` sind erforderlich.
Protokoll, Lauf, Bedingung, Trial und Attempt werden geprüft. Mehrere als gültig
abgeschlossene Attempts desselben Trials werden als mehrdeutig ausgeschlossen.
Auch überlappende protokollierte Pausen schließen den Attempt aus.

Nicht endliche Werte, ungültige Validation-Samples und Counter-Unterbrechungen
werden berücksichtigt. Fehler in Referenz/Aufgabe oder den ersten 3 s Erholung
schließen den ganzen Trial für **alle eingeschlossenen Kanäle und Bänder** aus.
Ein späterer Datenfehler erzeugt Lücken im Zeitverlauf, ohne den Aufgabenmittelwert
zu verändern. Ein Zeitbin, das nicht in allen akzeptierten Trials vollständig
unterstützt ist, bleibt für die gesamte Bedingung leer. Die Trialmenge wird beim
Abspielen nicht unbemerkt geändert. Fehlende technische Hilfskanäle erscheinen
als Einschränkung im Bericht. Signalqualität zusätzlich anhand der bestehenden
EEG-Zeitkurven prüfen; OSCAR garantiert keine artefaktfreien Trials.

Eine optionale UTF-8-JSON-Datei kann bekannte schlechte Kanäle, ganze Attempts
und beobachtete Artefaktintervalle ausschließen:

```json
{
  "bad_channels": ["PO8"],
  "bad_trials": ["Motorik/1/3/1"],
  "bad_intervals_s": [[123.4, 124.8]],
  "montage_confirmed": true
}
```

`bad_trials` verwendet `Lauf/Block/Trial/Attempt` aus der Ereignisdatei;
unbekannte IDs werden zurückgewiesen. Kanalnamen sind Positionsnamen.
Intervalle sind aufnahmebezogene Sekunden, halb offen `[Start, Ende)`.
`montage_confirmed: true` erst nach tatsächlicher Prüfung setzen; es bestätigt
die Kanalbelegung, keine individuelle Vermessung. Nicht benötigte Listen können
entfallen. Die Datei verändert weder Aufnahme noch Originalmarker:

```bash
python view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds --erds-qc pruefung.json
```

## Export und Tests

```bash
python view_eeg.py PFAD_ZUR_SESSION.csv --unit uV --view erds --no-show --erds-export NEUER_ORDNER
python -m unittest analysis.test_erds analysis.test_erds_browser
```

Der Export legt ausschließlich einen neuen Ordner an: `report.json` mit allen
aggregierten Band-/Zeit-Frequenz-Werten, Einzeltrial-Zusammenfassungen,
Konfiguration, QC und Quellenprüfsummen; `summary.csv` für Aufgabe/Rebound;
`bandpower.csv` für die Zeitverläufe. Keine Originaldatei wird überschrieben.
Im Browser sind JSON, Zusammenfassungs-CSV, aktuelle Tabelle und PNG-Abbildungen
verfügbar. Abbildungen zusammen mit dem JSON-Bericht aufbewahren: Er enthält
vollständige Referenz-, Montage-, Datenvarianten- und Ausschlussinformationen.
Browserdownloads werden vom Browser verwaltet und ändern keine Quelldateien.

Numerische Tests verwenden synthetische Signale. HTTP-Tests benötigen einen
lokalen Port; optionale UI-Tests Playwright und installiertes Chrome (alternativ
`EEG_BROWSER_EXECUTABLE`). Kein Browser-/Modell-/Datendownload erfolgt in Tests.
Diese Prüfungen ersetzen keine wissenschaftliche Pilotvalidierung mit Headset.

Methodischer Bezug: [Pfurtscheller & Lopes da Silva (1999)](https://doi.org/10.1016/S1388-2457(99)00141-8),
[Neuper et al. (2005)](https://doi.org/10.1016/j.cogbrainres.2005.08.014),
[Šťastný & Sovka (2007)](https://doi.org/10.1155/2007/54925).
Die konkrete Hann-/Schrittweitenwahl ist unsere offengelegte spektrale
Ausgestaltung, keine Behauptung einer exakten Replikation dieser Experimente.
