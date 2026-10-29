# Öffentliche EEG-Daten: ausgeführte linke/rechte Faustbewegung

Stand: 29.10.2026. Auswahl, Originaldownload, technische Labelprüfung und ein Importer für die Bewegungspipeline sind implementiert. Der vollständige Datenimport wurde ausgeführt; echtes Modelltraining und die Übertragung auf das Unicorn-Headset sind noch nicht validiert.

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

Der unten beschriebene Import legt Referenzierung, Einheiten, Samplingrate und Kanalwahl ausdrücklich fest. Weitere Artefakt-/Qualitätsregeln müssen vor einer wissenschaftlichen Modellstudie festgelegt werden. Für personenübergreifende Tests ganze Personen zurückhalten; alle Fenster desselben Trials zusammenhalten. Die öffentliche Datenquelle bleibt vom lokalen Protokoll und den lokalen Testdaten unterscheidbar.

## Importer und Trainingsschnittstelle

Die beiden vorhandenen Umgebungen haben unterschiedliche Aufgaben: `eeg-mne` liest EDF und bereitet Daten vor; `eeg-ml` lädt die vorbereiteten Dateien und kann das bestehende Modell trainieren. Es müssen keine neuen Pakete installiert oder Umgebungen vermischt werden.

```bash
~/.venvs/eeg-mne/bin/python -m analysis.physionet_dataset \
  --output-dir ~/.cache/eegvsmeg/physionet-eegmmidb-1.0.0/prepared-fists-250hz-v1
```

Dieser Importer prüft die Originale und Marker **erneut**, statt ungeprüft eine frühere Audit-CSV als Trainingsfreigabe zu übernehmen. Die bekannten strukturellen Ausschlüsse bleiben erhalten. Fehlende, beschädigte oder nicht lesbare Eingaben brechen den Import ab; sie werden nicht als erfolgreiche Teilmenge übergangen. Ein vorhandener Ausgabeordner wird nicht überschrieben.

Der feste Eingabevertrag:

1. Nur ausgeführte unilaterale Handaufgaben aus Läufen 3/7/11. Keine Ruhe-, Fuß- oder Imagery-Fenster und keine Umdeutung ins lokale Sitzungsprotokoll.
2. Kanalauswahl **über Namen** in der Reihenfolge `Fz, C3, Cz, C4, Pz, PO7, Oz, PO8`. Generische lokale Namen `EEG 1` bis `EEG 8` werden dadurch noch nicht als korrekt verkabelt bestätigt.
3. MNE liefert physisch skalierte **Volt**; Multiplikation mit `1e6` erzeugt ausdrücklich **µV**. Die Header-Einheit muss weiterhin `uV` sein.
4. Pro Trial genau **560 Originalsamples bei 160 Hz** ab dem zum nächsten Sample gerundeten Cue: 3,5 s bis zum exklusiven Ende. Original-Onset, Dauer, Samplegrenzen und Rundungsfehler bleiben in der Fenstertabelle erhalten.
5. Resampling ausschließlich innerhalb dieser Historie mit `scipy.signal.resample_poly`: **25/16**, Kaiser-Fenster mit Parameter 5, konstante Null-Randfortsetzung. Ergebnis: **875 Samples × 8 Kanäle bei 250 Hz in µV**. Es werden keine Originalsamples vor oder nach dieser Historie verwendet. Das erhöht die Samplingrate, nicht die gemessene zeitliche Information.
6. Die vorhandene gemeinsame Merkmalsfunktion verwendet 0–0,5 s als Filtervorlauf und 0,5–3,5 s für 16 logarithmische Mu-/Beta-Bandpowermerkmale. Ihre Parameter stehen unverändert in `analysis.movement_features`. Keine zusätzliche Referenzierung oder Artefaktbereinigung; die öffentliche Aufnahmereferenz bleibt eine Transfergrenze.

Die zentrierte FIR-Interpolation verwendet innerhalb der bereits vollständigen Historie auch spätere Samples. Sie ist eine ausdrücklich dokumentierte **Offline-Vorverarbeitung**, kein validierter Streaming-Resampler. Der kausale Bandpass der nachfolgenden Merkmalsfunktion ändert diese Eigenschaft nicht. Alle benötigten Originalsamples liegen spätestens am Ende der 3,5-s-Historie vor; die Pipeline greift nicht über dieses Ende hinaus.

Ausgaben im neuen Ordner:

| Datei | Inhalt |
|---|---|
| `histories_uv.npy` | Float64-Array mit Form `Trials × 875 × 8`; verarbeitetes EEG, außerhalb Git aufbewahren |
| `features.npy` | `Trials × 16`, dieselben Merkmale wie beim Bewegungsklassifikator |
| `windows.csv` | Label, Originalcode, Person, Aufnahme, Lauf, Trialkennung, Quellgrenzen und Zeilenzuordnung |
| `manifest.json` | Exakter Import-/Merkmalsvertrag, Original- und Ausgabe-Prüfsummen, Softwareversionen, Ausschlüsse und Grenzen |

`load_prepared()` im Modul `analysis.physionet_dataset` ist die Python-Schnittstelle: Es liefert Fenstertabelle, Merkmalsmatrix und Manifest. Es benötigt kein MNE und lädt ohne Pickle. Es prüft Datei-Hashes, Form, Klassen, Zeilenreihenfolge, Personen-/Trialzuordnung und die Übereinstimmung sämtlicher gespeicherter Merkmale mit den gespeicherten Historien. Die öffentlichen Personenkennungen bleiben erhalten. Identische EDF-Dateien dürfen nicht als unabhängige Aufnahmen importiert werden.

Die CLI-Anbindung an den vorhandenen Klassifikator ist:

```bash
~/.venvs/eeg-ml/bin/python -m analysis.movement_classifier train-physionet \
  ~/.cache/eegvsmeg/physionet-eegmmidb-1.0.0/prepared-fists-250hz-v1 \
  --output-dir ~/.cache/eegvsmeg/physionet-eegmmidb-1.0.0/hand-side-model-v1
```

Dieser **optionale nächste Schritt** trainiert `hand-side` mit zwei Klassen und der bestehenden Standardisierung/logistischen Regression. Mindestens zwei Personen sind nötig. Leave-one-participant-out hält alle Läufe und Trials einer Person gemeinsam zurück; Standardisierung und Modell werden nur auf den übrigen Personen gelernt. Der Modellvertrag kennzeichnet die öffentliche Datenquelle und den Import ausdrücklich. Lokale `evaluate`-/`replay`-Aufrufe akzeptieren öffentliche Modelle nicht als bereits validierten Unicorn-Transfer. Der binäre Kontrast hat keine Ruheklasse und erzeugt keine Freigabe für die Gesten-Ereignislogik.

### Tatsächlich ausgeführter Import

Der vollständige Import nach `prepared-fists-250hz-v1` wurde ausgeführt: **4.725 Trials aus 105 Personen**, 2.369 links und 2.356 rechts; zwölf Aufnahmen beziehungsweise 202 Aufgaben bleiben ausgeschlossen. Die Originaldateien wurden erneut gegen ihre offiziellen Prüfsummen geprüft. Anschließend wurde der vollständige vorbereitete Datensatz in `eeg-ml` geladen und jede Merkmalszeile gegen ihre EEG-Historie nachgerechnet. Damit ist die Schnittstelle praktisch geprüft. Der Trainingsbefehl wurde mit synthetischen Personen end-to-end getestet; auf dem echten öffentlichen Datensatz wurde in diesem Schritt kein Modell trainiert.

Die abgeleiteten Dateien benötigen zusammen rund **266 MB**. Der maximale Cue-Rundungsfehler dieses konkreten Imports ist **0 s**; alle Onsets lagen bereits auf dem 160-Hz-Sample-Raster. Der kleine [Importsnapshot](../analysis/results/physionet_fists_import_2026-10-29.json) hält Importvertrag, Umfang, Softwareversionen und die SHA-256-Prüfsummen von Eingabemanifest und vorbereiteten Dateien fest. EEG-Arrays und Modellparameter werden nicht ins Repository aufgenommen.

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
~/.venvs/eeg-mne/bin/python -m unittest analysis.test_physionet_dataset
~/.venvs/eeg-ml/bin/python -m unittest analysis.test_movement_classifier
```

Die Tests verwenden ausschließlich synthetisches EEG und simulierte Downloads. Sie prüfen unter anderem den laufabhängigen Labelvertrag, Prüfsummen und unveränderte Originale, synthetischen EDF+-Import einschließlich absichtlich vertauschter Kanalreihenfolge, Einheiten-/Samplingfehler, konstante Signale, kurze Aufgaben und falsche Annotationgrenzen. Weitere Regressionen prüfen Resampling und physische Dauer, manipulierte Caches, binäre Wahrscheinlichkeiten gegen scikit-learn, Modellpersistenz, vollständige Personentrennung und den Trainingsbefehl. Es werden keine weiteren Abhängigkeiten installiert und keine Hardwaretests behauptet.
