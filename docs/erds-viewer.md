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

Sitzungsmetadaten werden als UTF-8 (auch mit BOM) gelesen. Ältere Windows-Aufnahmen
können `.session.json` in Windows-1252 enthalten. In diesem Fall wird die Datei
mit einem ausdrücklichen Hinweis in dieser Kodierung gelesen; Originaldatei,
Umlaute und µV-Einheiten bleiben erhalten. Fehlerhaftes JSON oder nicht dekodierbare
Bytes werden nicht durch Zeichenersetzung repariert.
Die nachgewiesene alte Mischkodierung der Einheit `ÂµV` wird ausdrücklich mit
Warnung als µV interpretiert. `recorded_channel_units` und die Hinweise im
ERD/ERS-Bericht bewahren die Originalschreibweise; unbekannte Einheiten werden
weiterhin zurückgewiesen.

## Bedienung und Bedeutung

- Zwei drehbare Köpfe vergleichen linke und rechte Hand. Ausführung/Vorstellung,
  Frequenzband und Messgröße gelten gemeinsam. Kameras sind gekoppelt; feste
  Ansichten zeigen oben, vorn sowie beide Seiten. L/R bezeichnet die Person.
- **Alle Trials · Mittelwert** ist die Startansicht: alle akzeptierten Wiederholungen
  der gewählten Bedingung über alle Blöcke. Anzahl und Aufgabe stehen oberhalb
  der Köpfe. **Einzeltrials** zeigt links und rechts unabhängig ausgewählte Trials;
  die Auswahl nennt Block, Trial, Attempt und Cue-Zeitpunkt innerhalb der Aufnahme.
  Vor/Zurück wechselt die Wiederholung je Seite. Diese Auswahl stellt keine
  zeitgleiche oder statistisch gepaarte Messung beider Hände dar.
- **Trialübersichten und Bandkurven** zeigen fest **C3 links und C4 rechts**
  nebeneinander; auf schmalen Bildschirmen stehen sie untereinander. Jede Elektrode
  zeigt beide Handbedingungen: in der Trialübersicht als zwei Karten (linke Hand
  oben, rechte Hand unten), in der Bandkurve als zwei Kurven. Eine Kartenzeile
  entspricht einer akzeptierten Wiederholung. Beide Elektroden verwenden dieselben
  Farbgrenzen beziehungsweise automatisch denselben numerischen Y-Bereich, auch
  bei absoluter Bandpower. Ein Klick auf eine Kartenzeile öffnet den betreffenden
  Einzeltrial und wählt dessen Elektrode für EEG-Spannung, Referenzanzeige und
  Zeit-Frequenz-Karten. Die festen C3-/C4-Vergleiche bleiben beim Kanalwechsel erhalten.
  Im Gesamtmittel lassen sich zusätzlich alle Einzelkurven in beiden Diagrammen
  einblenden. Darunter lassen sich **einzelne Trial-Kurven ein-/ausblenden**:
  getrennte Listen für linke/rechte Hand nennen Block, Trial, Attempt und Aufnahmezeit.
  Ein Häkchen gilt gleichzeitig für C3 und C4; je Hand gibt es außerdem
  **Alle einblenden/ausblenden**. Die Auswahl bleibt bei Band-, Kanal-, Aufgaben-
  und Ansichtswechsel erhalten, solange der Viewer geöffnet ist. Der Hauptschalter
  blendet die gewählten Einzelkurven gemeinsam ein oder aus, ohne die Häkchen
  zurückzusetzen. In der Einzeltrial-Ansicht ist diese Hintergrundauswahl deaktiviert.
  **Dies ist nur eine Anzeigeauswahl:** Gesamtmittel, Kopfwerte, Tabelle und
  Trialkarten behalten sämtliche akzeptierten Trials. Für einen wissenschaftlichen
  Ausschluss die dokumentierte QC-Datei verwenden. In der Einzelansicht folgen beide Bandkurven derselben linken/rechten
  Trialauswahl; das Gesamtmittel wird zum Vergleich gepunktet dargestellt.
  Kopf, Tabelle, Zeit-Frequenz-Karte und ungefilterte EEG-Spannung zeigen ebenfalls
  diese Trialauswahl. „Ungefiltert“ bedeutet
  ohne zusätzliche Viewer-Filter; bei OSCAR ist es weiterhin das OSCAR-Signal.
- **Aufgabenmittel** verwendet nur vollständige 1-s-Fenster in der Aufgabe.
  **Nach Aufgabenende** verwendet Fenstermitten 0,5–2,5 s nach dem tatsächlichen
  `task_offset`; deren Signalunterstützung liegt 0–3 s nach dem Marker.
- **Baseline / Referenz** ist im Verlauf sichtbar: Eine graue Fläche in Bandkurven
  und EEG-Spuren markiert den Signalzeitraum der tatsächlich verwendeten
  Referenzfenster. In Zeit-Frequenz- und Trialkarten wird dieser Bereich nur
  umrandet, damit die Farben der Messwerte erhalten bleiben. Bei Mittelwerten
  beziehungsweise überlagerten Bedingungen zeigt die Markierung die Vereinigung
  der jeweiligen Trialintervalle. Die Referenzanzeige nennt zusätzlich die
  PSD-Fenstermitten und die Zahl der überlappenden Fenster je Trial.
  Nominal: Signal von −2 bis 0 s, Fenstermitten von −1,5 bis −0,5 s.
  Leicht abweichende Vorbereitungsmarker werden berücksichtigt.
- Oberhalb der Kurven stehen **Referenz-, Aufgaben- und Reboundleistung in µV²**
  für den ausgewählten Kanal und die jeweilige linke/rechte Auswahl, einschließlich
  Prozentänderung und Trialzahl. Die horizontale Strich-Punkt-Linie zeigt bei
  Prozentwerten das Referenzmittel 0 %, bei absoluter Bandpower je eine Referenz
  für links (blau) und rechts (orange). **Leistung mit Referenz (µV²)** öffnet
  diesen absoluten Vergleich; **Referenz + Verlauf zeigen** holt den Bereich
  nach einem Zoom wieder ins Bild. Einzelne Werte innerhalb der Referenz dürfen
  schwanken und werden nicht auf 0 % gesetzt.
- **Zeitverlauf** zeigt cuebezogene Fenstermitten mit einem Zeitschieber und
  optionalem Abspielen. Der Regler ist auch in **Aufgabenmittel** und **Nach
  Aufgabenende** bedienbar: Schieben oder Abspielen wechselt unmittelbar zu
  **Zeitverlauf**. Pfeiltasten sowie Pos1/Ende funktionieren bei fokussiertem Regler.
  Köpfe, Zahlenbalken, Tabelle und senkrechte Zeitmarkierungen folgen derselben
  Fenstermitte; Kurven, Zeit-Frequenz- und Trialkarten behalten ihre Daten und den
  gewählten Zoom beim Schieben. Die Grenzen der Farbskala bleiben fest.
  Abspielen ist eine verlangsamte Vorschau mit 100-ms-Schritten, keine
  Echtzeitwiedergabe. Pause und manuelles Schieben stoppen die Wiedergabe; am Ende
  hält sie an, ein erneuter Start beginnt wieder vorn. Es wird keine Zeit gestreckt.
  Unterschiedliche tatsächliche Aufgabenenden werden in den Diagrammen als
  gestrichelte Linien angezeigt.
- **Blau = negative ERD**, neutral = 0 %, **Rot = positive ERS**. Feste gemeinsame
  Farbgrenzen bleiben bei Zeit-/Bedingungswechsel erhalten; Überläufe werden
  gezählt. Die absolute Bandpower in µV² hat eine eigene sequenzielle Skala.
- **Farbbereich anpassen** bestimmt gemeinsame Grenzen aus den aktuellen
  Elektrodenwerten beider Köpfe, mit 5 % Rand und neutralem Nullpunkt. Die Grenzen
  bleiben anschließend auch beim Trial- oder Zeitwechsel fest; erneutes Anpassen
  erfolgt ausdrücklich per Knopfdruck. Manuelle Grenzen und **Standardskala** sind
  ebenfalls verfügbar. Es gibt keine separate automatische Skalierung je Kopf
  oder Elektrode. Unter jedem Kopf stehen Zahlenbalken, Wertebereich und C3−C4-
  Differenz (in Prozentpunkten beziehungsweise µV²). Ähnliche Werte dürfen ähnlich
  aussehen: Eine engere Skala oder Farbänderung erzeugt keinen räumlichen Effekt.
  Beide Balkendiagramme verwenden dieselben Zahlenachsen und zeigen auch Werte
  außerhalb der Farbgrenzen. Prozent-Zeitkurven haben automatisch mindestens
  einen Prozentpunkt Achsenspanne, damit Rundungsrauschen um 0 nicht vergrößert
  wird; die Messwerte bleiben erhalten und die Diagramme sind weiterhin zoombar.
- Ein Klick auf einen Messpunkt oder eine Tabellenzeile wählt den Kanal für
  EEG-Spannung, Referenzanzeige und Zeit-Frequenz-Karten; die Bandkurven und
  Trialübersichten bleiben fest bei C3/C4. Tooltip und Tabelle zeigen Referenz,
  Leistung, Änderung und gültige Trialzahl. Grau/× bedeutet ausgeschlossen oder
  nicht verfügbar, **nicht 0 %**. Die Zeit-Frequenz-Karten bleiben bei Prozentwerten
  und verwenden eine gemeinsame separate Skala von −100 bis +100 %.
  Auch ein Klick auf einen Zahlenbalken wechselt den Kanal.
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

## Baseline als eigene Ansicht

Unter **Ansicht → Baseline** stehen zwei Arten zur Verfügung:

- **Ruhebaseline · Anfang / Ende:** vollständig markierte 60-s-Abschnitte aus
  `baseline_start`/`baseline_end`. Abschnitt und Attempt stehen in der Auswahl.
  Invalidierte, unvollständige, mehrdeutige oder von Pausen überlappte Attempts
  werden ausgeschlossen. Fehlende Ruhebaselines erzeugen einen sichtbaren Hinweis;
  Vorbereitung und Pausen werden nicht als Ersatzruhe angenommen.
- **Trial-Vorbereitung:** die tatsächlich verwendeten Referenzfenster jedes
  akzeptierten Hand-Trials mit Block, Trial, Attempt und Aufnahmezeitpunkt.
  Invalidierte oder ausgeschlossene Trials erscheinen auch hier nicht erneut.

**Untersuchter Abschnitt** und **Referenzabschnitt** sind getrennt auswählbar.
Standard: **Eigenes Abschnittsmittel**. Dann beschreibt 0 % das mittlere
Leistungsniveau dieses Abschnitts, und der Verlauf darf davon abweichen. Eine
andere Referenz, etwa die Anfangsbaseline für die Endbaseline, wird ausschließlich
ausdrücklich gewählt. Für jedes eingeschlossene EEG und Frequenzband gilt:

```text
Änderung (%) = 100 × (Fensterleistung / mittlere gültige Leistung des Referenzabschnitts − 1)
```

Dies ist eine deskriptive Leistungsänderung; ohne Aufgabenereignis ist eine
Ruhefluktuation kein nachgewiesenes ereignisbezogenes ERD/ERS. Die Wahl der Referenz
bestimmt die Interpretation und ersetzt keine Artefaktkontrolle; siehe
[MNE: Baseline correction considerations](https://mne.tools/stable/auto_tutorials/time-freq/20_sensors_time_frequency.html#baseline-correction-considerations).
Die Referenzierung der Handaufgaben bleibt unverändert.

Ein drehbarer Kopf, Zahlenbalken und Tabelle zeigen alle acht Kanalwerte. C3-/C4-
Bandkurven stehen nebeneinander mit gemeinsamen Y-Grenzen; ein ausdrücklich anderer
Referenzabschnitt erscheint orange gestrichelt, jeweils ab seinem eigenen Beginn.
Die X-Achse begrenzt sich auf den untersuchten Abschnitt. Der Kanalwähler steuert
zusätzlich EEG-Spannung und Zeit-Frequenz-Karte. Letztere bleibt ausdrücklich in %
mit eigener Skala ±100 %, auch bei absoluter Bandpower. **Abschnittsmittel** zeigt
die mittlere Leistung der gültigen Fenster; **Zeitverlauf**, Schieben oder Abspielen
zeigt die ausgewählte Fenstermitte ab Abschnittsbeginn. Es gibt keinen Aufgaben-Cue
oder Reboundmarker in dieser Ansicht. Kamerasteuerung und Farbgrenzen sind sichtbar.

Auch hier: 1-s-Hann-Fenster und 100-ms-Schritte. Kein Fenster überschreitet die
Abschnittsgrenzen. Technische Samplefehler, nicht endliche Werte und QC-Intervalle
maskieren alle betroffenen Fenster für sämtliche eingeschlossenen Elektroden.
Die Referenz verwendet dieselbe gemeinsame Menge gültiger Fenster. Fensterzahl,
Fehlstellen und Referenzzeitraum sind sichtbar; überlappende Fenster sind keine
unabhängigen Wiederholungen. Null-/numerisch unauflösbare Referenzen bleiben als
Prozentwerte fehlend, während absolute Leistung und Spannung weiterhin sichtbar sind.

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
Diese aufgabennahe Referenz ist von den separaten 60-s-Ruhebaselines der Sitzung
zu unterscheiden. In der Handaufgabenansicht werden Ruhebaselines nicht zur
Normalisierung herangezogen. Vorbereitung kann Erwartungsaktivität enthalten;
die sichtbare Markierung begründet keine physiologisch neutrale Ruhephase.
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

Für **Einzeltrials**, Trialübersichten und eingeblendete Einzelkurven gilt dagegen:

```text
Einzeltrial-ERD/ERS (%) = 100 × (Leistung dieses Trials / eigene Referenzleistung − 1)
```

Die Vorbereitung und die vollständigen Fenster werden identisch zum Gesamtmittel
ausgewählt. Das Mittel dieser Einzeltrial-Prozentwerte ist im Allgemeinen **nicht**
der oben definierte Gesamtwert. Bei n=1 gibt es keine Mittelung über Wiederholungen;
eine kurze Referenz oder ein Artefakt kann einen großen Ausschlag verursachen.
Die Einzelansicht dient der deskriptiven Kontrolle und begründet allein keine
robuste ERD/ERS oder Signifikanz. Die Spannungsansicht zeigt die gewählte
Datenvariante in µV ohne Zentrierung; fehlende Samples bleiben Lücken.

Gleichartige Farben können durch ähnliche relative Leistungsänderungen in vielen
Kanälen entstehen. Zusätzlich sind bei engen Unterschieden die Zahlen aussagekräftiger
als die begrenzte Farbabstufung. Gemeinsame Signalanteile können etwa mit Referenz,
Bewegung oder anderen Artefakten zusammenhängen; die Kopfansicht unterscheidet diese
Ursachen nicht. Sie ändert weder Filter noch Referenzierung, um Kontraste zu erzeugen.

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
`report.json` enthält zusätzlich Baseline-Abschnittsmetadaten und Baseline-Ausschlüsse.
`baselines.csv` enthält die vollständigen Bandkurven der verfügbaren Ruhe-/
Vorbereitungsabschnitte, deren eigene mittlere Referenzleistung, relative Änderung,
Aufnahmebeginn und Fensterzahl. Fehlende Fenster bleiben leer. Diese CSV verwendet
ausdrücklich die Eigenreferenz; andere interaktive Vergleiche stehen im Auswahl-JSON.
Zusätzlich enthält `trials.csv` Referenz-, Aufgaben- und Reboundwerte je gültigem
Trial/Kanal/Band mit Block-, Trial-, Attempt-ID und Aufnahmezeitpunkt.
`reference_windows` im JSON nennt pro Trial den erlaubten Referenzzeitraum,
die tatsächlich verwendeten Fenstermitten, deren Signalzeitraum und Fensterzahl.
`trials.csv` enthält Signalgrenzen und Fenstermitten ebenfalls. Alle Zeiten sind
cuebezogen; Originalmarker und Berechnungswerte bleiben erhalten.
Im Browser sind Gesamtbericht, Zusammenfassungs-CSV, aktuelle Tabelle,
**Aktuelle Auswahl (JSON)** und PNG-Abbildungen verfügbar. **C3-Kurven als PNG**
und **C4-Kurven als PNG** exportieren das jeweilige Diagramm; Beschriftung und
Dateiname nennen dessen feste Elektrode unabhängig vom Kanalwähler.
Bei eingeblendeten Einzelkurven nennt der PNG-Titel deren sichtbare Anzahl und
weist darauf hin, dass die Mittelwerte weiterhin alle akzeptierten Trials enthalten.
`curve_visibility` im Auswahl-JSON und in der Auswahlspalte der Tabellen-CSV nennt
den Hauptschalter, die sichtbaren Trial-IDs und die einzeln deaktivierten IDs der
aktuellen Aufgabenfamilie. Diese Angaben verändern die wissenschaftlichen Ausschlüsse nicht.
Der Auswahl-JSON nennt die festen Vergleichskanäle unter
`motor_comparison_channels` und enthält
beide ausgewählten Trials oder Mittelwerte, ihre Kurven und Referenzen,
Band, Zeitauswahl, Farbgrenzen und Verarbeitungsmetadaten; bei Einzeltrials auch
die EEG-Spannungen und Zeit-Frequenz-Werte des ausgewählten Kanals. Die aktuelle
Tabellen-CSV enthält diese Auswahlparameter als JSON-Spalte. Der Gesamtbericht
bleibt unabhängig vom gerade geöffneten Trial. Einzeltrial-Details werden bei
Bedarf vom lokalen Server nachgeladen; der Browser benötigt weiter den laufenden
Python-Prozess.
Abbildungen zusammen mit dem passenden Auswahl-JSON und Gesamtbericht aufbewahren:
Diese enthalten
vollständige Referenz-, Montage-, Datenvarianten- und Ausschlussinformationen.
Browserdownloads werden vom Browser verwaltet und ändern keine Quelldateien.
In der Baseline-Ansicht exportiert **Baseline-Auswahl (JSON)** den untersuchten und
den Referenzabschnitt einschließlich Kurven, Referenzwerten, EEG-Spannung und
Zeit-Frequenz-Werten des gewählten Kanals. Baseline-Tabelle und PNG-Schaltflächen
beziehen sich auf dieselbe Auswahl. Für Nachvollziehbarkeit PNG zusammen mit dem
zugehörigen Auswahl-JSON aufbewahren. Die Baseline-Tabelle dokumentiert zusätzlich
Referenz-ID/-Zeitraum, gültige Referenzfenster, Datenvariante, Band und Zeitwahl.

Numerische Tests verwenden synthetische Signale. HTTP-Tests benötigen einen
lokalen Port; optionale UI-Tests Playwright und installiertes Chrome (alternativ
`EEG_BROWSER_EXECUTABLE`). Kein Browser-/Modell-/Datendownload erfolgt in Tests.
Diese Prüfungen ersetzen keine wissenschaftliche Pilotvalidierung mit Headset.

Methodischer Bezug: [Pfurtscheller & Lopes da Silva (1999)](https://doi.org/10.1016/S1388-2457(99)00141-8),
[Neuper et al. (2005)](https://doi.org/10.1016/j.cogbrainres.2005.08.014),
[Šťastný & Sovka (2007)](https://doi.org/10.1155/2007/54925).
Die konkrete Hann-/Schrittweitenwahl ist unsere offengelegte spektrale
Ausgestaltung, keine Behauptung einer exakten Replikation dieser Experimente.
