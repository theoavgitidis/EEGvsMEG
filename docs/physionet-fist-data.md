# Öffentliche EEG-Daten: ausgeführte linke/rechte Faustbewegung

Stand: 29.10.2026. Dieser Schritt umfasst Auswahl, Originaldownload und technische Labelprüfung. Kein Training, keine Artefaktbereinigung und keine validierte Übertragung auf das Unicorn-Headset.

## Auswahl und Herkunft

Verwendet wird das [PhysioNet EEG Motor Movement/Imagery Dataset, Version 1.0.0](https://physionet.org/content/eegmmidb/1.0.0/), DOI [10.13026/C28G6P](https://doi.org/10.13026/C28G6P). Die [MNE-Laufübersicht](https://mne.tools/stable/generated/mne.datasets.eegbci.load_data.html) bestätigt die Auswahl:

| Läufe | Inhalt | Download dieses Schritts |
|---|---|---|
| **3, 7, 11** | **Tatsächliches Öffnen/Schließen der linken oder rechten Faust** | **Ja, alle 109 öffentlichen Personenkennungen** |
| 4, 8, 12 | Linke/rechte Faust vorstellen | Nein; mögliche spätere, getrennte Erweiterung |
| 5, 9, 13 | Beide Fäuste gegen beide Füße, ausgeführt | Nein |
| 6, 10, 14 | Beide Fäuste gegen beide Füße, vorgestellt | Nein |
| 1, 2 | Baselines mit offenen/geschlossenen Augen | Nein |

Die Wahl passt zur Handbewegung aus unserem Protokoll 2.0. Cue-Anordnung, Gerät, Referenzierung, Bewegungstempo und Erholung sind dadurch noch nicht identisch. Die Quellen definieren keine unabhängige Trainingsklasse für unsere links-/rechtsseitigen Fußbewegungen.

Nur für die gewählten Läufe gilt:

| Originalcode | Bedeutung | Projektlabel |
|---|---|---|
| `T0` | Erholung zwischen Aufgaben | `rest` |
| `T1` | Linke Faust öffnen/schließen | `me_hand_left` |
| `T2` | Rechte Faust öffnen/schließen | `me_hand_right` |

Das Audit weist andere Läufe und unbekannte Codes zurück. Es liest Ereignisse aus EDF+; die originalen WFDB-Dateien `.edf.event` werden zusätzlich erhalten und per Prüfsumme geprüft, aber nicht unabhängig dekodiert. Laut PhysioNet enthalten beide dieselben Annotationen. Die Prüfung bestätigt Dateikonsistenz und die dokumentierte Bedeutung der Codes, nicht die tatsächliche Ausführung oder fehlerfreie Links-/Rechtsannotation jeder einzelnen Person.

Lizenz: [Open Data Commons Attribution License v1.0](https://physionet.org/content/eegmmidb/view-license/1.0.0/). Bei Verwendung den Datensatz und die BCI2000-Originalpublikation zitieren: Schalk et al. (2004), *BCI2000: A General-Purpose Brain-Computer Interface (BCI) System*, IEEE TBME 51(6), 1034–1043, DOI [10.1109/TBME.2004.827072](https://doi.org/10.1109/TBME.2004.827072). Weitere Zitierhinweise stehen auf der Datensatzseite.

## Ablage und reproduzierbarer Download

Standardablage außerhalb des Desktop-/iCloud-Checkouts:

```text
~/.cache/eegvsmeg/physionet-eegmmidb-1.0.0/
    source/SHA256SUMS.txt
    source/RECORDS
    source/ANNOTATORS
    source/wfdbcal
    source/S001/S001R03.edf
    source/S001/S001R03.edf.event
    ...
    download-manifest.json
    audit/audit.json
    audit/summary.json
    audit/annotations.csv
```

Öffentliche Kennungen bleiben im Namensraum `physionet:S001` bis `physionet:S109`. Sie erhalten keine lokalen `EVM-P...`-IDs. Originalaufnahmen, Ereignisdateien und vollständige lokale Berichte werden nicht ins Repository aufgenommen.

Im Repository-Stamm mit der vorhandenen MNE-Umgebung:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.download_physionet
~/.venvs/eeg-mne/bin/python -m analysis.audit_physionet
```

Der Downloader lädt **327 EDF-Dateien und 327 Ereignisdateien**, dazu drei kleine Begleitdateien sowie die offizielle SHA-256-Liste. Die Liste ist mit SHA-256 `7f5d16957d8ee7bce86cc7ccba0e5994f63f33781607eb3f838392d49311a208` gepinnt. Jede Quelldatei wird dagegen geprüft. Vier gleichzeitige Downloads sind Standard; `--workers 1` reduziert die Parallelität.

Vorhandene korrekte Dateien werden wiederverwendet. Neue Dateien werden erst nach erfolgreicher Prüfsumme atomar veröffentlicht. Vorhandene Dateien mit abweichender Prüfsumme werden nicht überschrieben; der Befehl bricht mit dem konkreten Dateipfad ab. Ein abgebrochener Download kann durch denselben Aufruf fortgesetzt werden; dabei werden fehlende Dateien neu geladen. Die Zwischenstände eines hart abgebrochenen Prozesses können als `.part` verbleiben und zählen nicht als Originaldateien.

Nur lokal erneut prüfen, ohne Netzwerkzugriff:

```bash
~/.venvs/eeg-mne/bin/python -m analysis.download_physionet --verify-only
~/.venvs/eeg-mne/bin/python -m analysis.audit_physionet
```

Ein kleiner Einstieg ist mit `--subjects 1 2 3` **bei beiden Befehlen** möglich. `--root /PFAD/AUSSERHALB/DER/CLOUD` ändert die Ablage; unter Windows beispielsweise `--root 'D:\EEG-data\physionet-eegmmidb-1.0.0'` mit dem dort vorhandenen Python-Interpreter. Das Downloadmanifest beschreibt jeweils den letzten angeforderten Umfang; andere bereits geladene Dateien bleiben erhalten. Der Auditumfang folgt ausdrücklich `--subjects`, standardmäßig allen 109 Personen, und nicht einer Verzeichnis-Auflistung.

## Prüfungen und Bedeutung der Berichte

Das Audit prüft jede angeforderte Aufnahme einschließlich ihrer Eventdatei erneut gegen die offizielle Prüfsumme. Zusätzlich werden EDF-Dimensionen und vollständige Dateigröße, 64 eindeutige EEG-Kanalnamen, physische Einheiten `uV`, 160 Hz auf allen EEG-Kanälen, Kalibrierbereiche, endliche Signalwerte, vollständig konstante Kanäle und EDF-Lesewarnungen geprüft. Die Datei wird vollständig lokal gelesen; ein erfolgreicher Download allein ersetzt diesen Schritt nicht.

Für die vorgesehene Unicorn-Montage wird die Reihenfolge **Fz, C3, Cz, C4, Pz, PO7, Oz, PO8** über die EDF-Kanalnamen ermittelt. Groß-/Kleinschreibung und abschließende EDF-Punkte werden nur beim Namensvergleich vereinheitlicht. Es wird weder die Originalreihenfolge geändert noch die lokale Verkabelung als bestätigt angenommen. MNE liest physisch skalierte Werte in **Volt**; die Amplitudendiagnose wird ausdrücklich in µV berichtet. EDF-Vorfilterangaben werden mitgeführt. Es erfolgen keine zusätzlichen Filter, kein Resampling, keine Referenzierung und keine Signalexporte.

`annotations.csv` erhält jeden gelesenen EDF-Marker mit öffentlicher Personenkennung, Lauf, Aufnahme, eindeutiger Annotation-/Trialkennung, Originalcode, Aufgabenlabel, Onset und Dauer. Für Handaufgaben wird ausschließlich die strukturelle Verfügbarkeit des vorgesehenen **0,5–3,5-s-Fensters nach Cue** geprüft. Aufgaben unter 3,5 s werden ausgeschlossen. Widersprüchliche Metadaten, Lesefehler, beschädigte Dateien oder problematische Annotationgrenzen sperren die Aufnahme vollständig. Fehlende oder nicht lesbare Aufnahmen bleiben im Bericht sichtbar; ihre unbekannten Trialzahlen werden nicht erfunden.

T0-Annotationen und unbeschriftete Dateiende bleiben erhalten beziehungsweise werden als fehlende Annotation dokumentiert. Sie erzeugen **keine ausgewählten Ruhefenster**. Insbesondere ist PhysioNet-Erholung kein automatisch gleichwertiger Ersatz für die späten Erholungsfenster unseres Bewegungsklassifikators.

`audit.json` enthält die vollständigen Dateibefunde einschließlich Prüfsummen und Ausschlüssen. `summary.json` enthält den kompakten Befund und auffällige Aufnahmen. `eligible_task_window` bedeutet lediglich, dass Metadaten und Zeitgrenzen die Prüfung bestehen. Artefakte, Cue-/Augenbewegungseinflüsse, eine möglicherweise vertauschte Seitenannotation und tatsächliche Bewegungsausführung sind damit nicht validiert. Die strukturell verfügbaren Aufgabenfenster sind noch kein freigegebener Trainingssplit. Es werden weder Personen umetikettiert noch abweichende Samplingraten stillschweigend korrigiert.

Vor späterem Training müssen Qualitätsregeln, Referenzierung, Einheiten, Samplingrate und Kanalwahl festgelegt werden. Für personenübergreifende Tests ganze Personen zurückhalten; alle Fenster desselben Trials zusammenhalten. Die öffentliche Datenquelle bleibt vom lokalen Protokoll und den lokalen Testdaten unterscheidbar. Der vorhandene Bewegungsklassifikator akzeptiert diese EDF-Dateien noch nicht als Eingabe.

## Tatsächlich ausgeführter Download und Befund am 29.10.2026

Beide vollständigen Standardbefehle wurden mit der bestehenden Umgebung `~/.venvs/eeg-mne` ausgeführt. Alle 327 EDF-Dateien und 327 Eventdateien sowie die Begleitdateien wurden erfolgreich heruntergeladen und gegen die offizielle SHA-256-Liste geprüft. Das Downloadmanifest zählt **835.495.308 Byte** ohne die Prüfsummenliste. Alle 327 EDF-Dateien wurden vollständig lokal eingelesen. MNE-Version **1.13.2**, NumPy **2.5.4**; keine neuen Pakete installiert.

| Befund | Ergebnis |
|---|---:|
| Öffentliche Personen / ausgewählte Aufnahmen | 109 / 327 |
| Gesamte Aufnahmedauer einschließlich Erholung | 11,23 Stunden |
| EDF-Ereignisse insgesamt | 9.854 |
| Handaufgaben vor strukturellem Ausschluss | 4.927 |
| Strukturell verfügbare 3-s-Handfenster | **4.725 aus 315 Aufnahmen / 105 Personen** |
| Davon linke / rechte Faust | **2.369 / 2.356** |
| Ausgeschlossene Handaufgaben | 202 |

Alle Aufnahmen enthalten 64 EEG-Kanäle mit `uV` im EDF-Header und alle acht vorgesehenen Kopfpositionen. Deren nullbasierte Quellindizes in der Zielreihenfolge sind **33, 8, 10, 12, 50, 55, 61, 59**. Es gab keine EDF-Lesewarnungen, keine nichtendlichen Signalwerte und keine über die ganze Aufnahme konstanten Kanäle. Das schließt Signalabschnitte mit Artefakten nicht aus.

Es wurden **zwölf Aufnahmen aus vier Personenkennungen vorläufig vollständig ausgeschlossen**:

| Kennungen | Betroffene Läufe | Konkreter Befund |
|---|---|---|
| `S088`, `S092`, `S100` | Je 3, 7, 11 | Jeweils **128 Hz statt 160 Hz** im Header; zusätzlich Lücken/Überlappungen zwischen Annotationen von 25–75 ms. |
| `S089` | 3, 7, 11 | 160 Hz, aber Lücken/Überlappungen zwischen Annotationen von 50 ms. |

Die Differenzen wurden aus gespeichertem Onset minus Ende der vorherigen Annotation berechnet; das Audit toleriert höchstens ein Sample. Alle betroffenen Dateien stimmen mit den offiziellen Prüfsummen überein: Es handelt sich um Befunde der Quelle, nicht um nachgewiesene Downloadfehler. Die Dateien bleiben unverändert erhalten. Eine spätere Freigabe oder Korrektur benötigt eine gesonderte Prüfung; das Audit nimmt weder Resampling noch Timingreparaturen vor.

Die verbleibenden Aufgaben dauern laut Annotation 4,0 oder 4,1 s und enthalten das vollständige 0,5–3,5-s-Fenster. Die Ausschlüsse sind technische, konservative Regeln und keine nach Modellleistung ausgewählte Personenmenge. Insbesondere beweisen die verbleibenden 105 Personen keine durchgängig korrekten Seitenlabels oder ausreichende Signalqualität.

Der kleine [Ergebnissnapshot](../analysis/results/physionet_fists_audit_2026-10-29.json) ist eine unveränderte Kopie der lokal erzeugten `audit/summary.json`. Er enthält Version, Quellen-Hash, Softwareversionen, Umfang und konkrete Ausschlüsse. Der vollständige Bericht und die Labeltabelle bleiben außerhalb des Repositorys. Nach einem erneuten Audit lässt sich der Snapshot so aktualisieren:

```bash
cp ~/.cache/eegvsmeg/physionet-eegmmidb-1.0.0/audit/summary.json \
  analysis/results/physionet_fists_audit_2026-10-29.json
```

## Regressionstests

```bash
~/.venvs/eeg-mne/bin/python -m unittest analysis.test_physionet
```

Die Tests verwenden ausschließlich synthetisches EEG und simulierte Downloads. Sie prüfen unter anderem den laufabhängigen Labelvertrag, Prüfsummen und unveränderte Originale, einen echten synthetischen EDF+-Lesevorgang, Einheiten-/Samplingfehler, konstante Signale, kurze Aufgaben und falsche Annotationgrenzen. Es werden keine weiteren Abhängigkeiten installiert und keine Hardwaretests behauptet.
