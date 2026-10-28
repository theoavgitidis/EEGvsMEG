# Kodierung von Teilnehmern und Sitzungen

Stand: 28. Oktober 2026. Schema-Version: 1; das ID-Schema bleibt beim Aufgabenwechsel unverändert.

## Teilnehmer-ID

Für neue Teilnehmende wird dieses Schema verwendet:

```text
EVM-P001
│   │└── dreistellige, zentral vergebene Nummer: 001–999
│   └─── P = Participant / teilnehmende Person
└─────── EVM = EEGvsMEG-Projekt
```

| Beispiel | Bedeutung |
|---|---|
| `EVM-P001` | Erste unter diesem Schema registrierte Person |
| `EVM-P002` | Zweite registrierte Person |
| `EVM-P027` | Person mit der Nummer 027 |

Der Code besteht aus Großbuchstaben, Ziffern und einem Bindestrich. Immer drei Ziffern verwenden: `EVM-P007`, nicht `EVM-P7`. `EVM-P000` wird nicht vergeben. Die Nummer ist eine Registrierungsnummer; sie bezeichnet weder die Reihenfolge der Messungen noch eine Bedingung.

Eine Person behält ihre ID über sämtliche Termine, Experimente, erneute Aufnahmen und verwendeten Laptops. Eine zweite Sitzung derselben Person erhält daher keinen neuen Teilnehmercode.

Name, Initialen, Geburtsdatum, Alter, Geschlecht, Händigkeit, Messdatum und Aufgabenreihenfolge sind keine Bestandteile der Teilnehmer-ID. Benötigte Merkmale werden als separate Angaben erhoben. Eine gegebenenfalls notwendige Zuordnung zwischen Person und Code wird getrennt von Git und den EEG-Dateien aufbewahrt.

## Vergabe ohne Doppelbelegung

1. Vor der ersten Messung eine freie Nummer aus einer zentralen Vergabeliste reservieren.
2. Den vollständigen Code im Versuchsprotokoll festhalten.
3. Auf jedem Messrechner exakt denselben Code verwenden; die lokale Ordnerliste allein bestimmt nicht, ob eine ID frei ist.
4. Bei weiteren Terminen die vorhandene ID erneut auswählen.
5. Eine vergebene Nummer nicht einer anderen Person zuweisen, auch wenn eine Messung ausfällt, abgebrochen wird oder Daten nicht ausgewertet werden.

Lücken in der Nummerierung sind erlaubt. Die Beispieltabelle oben reserviert noch keine echten Personen. Mehrere Versuchsführer oder Laptops müssen dieselbe Vergabeliste verwenden.

## Nutzung in der bestehenden CLI

Die Beispiele starten nach aktuellem Release-Build den [Zweilaufplan 2.0](experiment-protocol.md). Bestehende Protokoll-1.0-Aufnahmen behalten ihre ursprüngliche Version und Zuordnung.

### Erster Termin auf einem Messrechner

Im Unicorn-Terminal, bei gestoppter Aufnahme:

```text
NewExp "EVM-P001"
Where
```

Nach Verbindung und Konfiguration des Headsets:

```text
cue open
```

Fenster auf den Teilnehmermonitor verschieben, Terminal erneut fokussieren und starten:

```text
start session
```

Die CLI speichert den Ordnernamen `EVM-P001` als `participant_id` in den Session-Metadaten. Die Vergabe des Codes erfolgt derzeit durch den Versuchsführer; die CLI prüft die Zulässigkeit des Ordnernamens, aber nicht dessen Übereinstimmung mit diesem Teilnehmer-Schema.

### Weiterer Termin oder neue Aufnahme derselben Person

Falls der Ordner auf diesem Rechner bereits existiert:

```text
GoToExp "EVM-P001"
Where
cue open
```

Nach Vorbereitung und Positionierung des Fensters erneut `start session` ausführen. Die neue Aufnahme erhält automatisch einen neuen Dateinamensstamm. Einen laufenden Versuch zuvor abschließen oder kontrolliert abbrechen; Ordnerwechsel während einer Aufnahme sind gesperrt.

Auf einem anderen Laptop, auf dem der Ordner noch nicht existiert, erneut `NewExp "EVM-P001"` verwenden. Dadurch wird dieselbe Teilnehmer-ID lokal angelegt; es wird keine neue Person registriert. Beim Zusammenführen vorhandene Dateien nicht überschreiben.

## Teilnehmer-ID und Sitzungs-ID getrennt halten

| Ebene | Beispiel | Bedeutung / Herkunft |
|---|---|---|
| Teilnehmer-ID | `EVM-P001` | Dauerhafte Personenkennung; gewählter Experimentordner |
| Sitzungs-ID | `session_20261021_183000` | Automatisch erzeugte einzelne Aufnahme; lokale Startzeit im Namensstamm |
| Hauptlauf | Aktuell `Motorik`, `Imagery` (M/I); früher zusätzlich `Kognitiv` | Aufgabenart innerhalb einer Aufnahme; abhängig von der Protokollversion |
| Trial | `12` | Geplanter Trial innerhalb eines Hauptlaufs |
| Attempt | `2` | Zweiter Durchführungsversuch desselben Trials nach Unterbrechung |

Beispiel bei einem Repository unter `C:\EEG\EEGvsMEG`:

```text
C:\EEG\recordings\EVM-P001\
    session_20261021_183000.csv
    session_20261021_183000.csv.events.csv
    session_20261021_183000.csv.plan.csv
    session_20261021_183000.csv.session.json

    session_20261028_170000.csv
    session_20261028_170000.csv.events.csv
    session_20261028_170000.csv.plan.csv
    session_20261028_170000.csv.session.json
```

Das sind zwei Aufnahmen derselben Person. Die Metadaten enthalten jeweils `participant_id: EVM-P001` und die jeweilige `session_id`.

Der Zeitstempel-Stamm einer Sitzung ist nicht projektweit eindeutig: Zwei Personen auf unterschiedlichen Laptops können zeitgleich starten. Für die Zuordnung einer Aufnahme deshalb immer **Teilnehmer-ID plus Sitzungs-ID** verwenden. Beim Export und bei der Datensicherung den Teilnehmerordner beziehungsweise diese Zuordnung erhalten.

Eine Pause mit `session resume` bleibt Teil derselben Sitzung und erhöht bei einem unterbrochenen Trial die Attempt-ID. Ein neuer Start nach einem Abbruch erzeugt eine neue Sitzungs-ID unter derselben Teilnehmer-ID. Besuchsnummern wie „Termin 1“ oder „Termin 2“ können im Versuchsprotokoll ergänzt werden; sie sind derzeit kein eigenes automatisch verwaltetes CLI-Feld und nicht identisch mit der Anzahl erzeugter Aufnahme-Dateien.

## Reihenfolgegruppen separat dokumentieren

Für das neue Protokoll die Reihenfolge **M→I** oder **I→M** und den Termin separat dokumentieren. Die Personenkennung bleibt dabei stabil. Die CLI nimmt `session order motorik imagery` oder `session order imagery motorik` an; Standard ist Motorik zuerst.

Die bisherigen Gruppen A–F gehören ausschließlich zu Protokoll 1.0; ihre Zuordnung steht in der [Sitzungsanleitung](../gtec_Clib/terminal/SESSION_ANLEITUNG.md). Aktuelles Beispiel für Imagery zuerst:

```text
GoToExp "EVM-P001"
session order imagery motorik
```

Die CLI speichert die konkrete Laufreihenfolge in den Sitzungsmetadaten. Gruppenbuchstaben werden nicht als eigenes Feld automatisch gespeichert. Reihenfolgen niemals allein aus Teilnehmernummer oder Besuchsnummer ableiten.

## Techniktests und bestehende Daten

Techniktests ohne Zuordnung zu einer Studienperson erhalten beschreibende Namen, beispielsweise `DEV-LAPTOP01` oder `DEV-REHEARSAL01`. Sie verwenden keine Teilnehmernummer aus der Vergabeliste und werden bei einer Teilnehmerauswertung nicht als eigene Studienpersonen gezählt. Da die CLI auch solche Ordnernamen als `participant_id` speichert, muss die Auswertung ihre Eingabedaten ausdrücklich auswählen.

Sobald Messdaten tatsächlich einer Studienperson zugeordnet werden sollen, deren feste Teilnehmer-ID verwenden — auch für zusätzliche Pilotaufnahmen derselben Person.

Bestehende Codes wie `VP01` behalten zunächst ihre Bedeutung. Bereits erhobene Daten nicht allein durch Umbenennen des Ordners migrieren: In den vorhandenen JSON-Dateien bleibt sonst die alte ID stehen. Ein Wechsel auf das neue Schema benötigt eine dokumentierte, eindeutige Zuordnung und konsistente Anpassung aller betroffenen Metadaten. Einer bereits registrierten Person nicht versehentlich eine zweite Identität geben.

## Bezug zur Auswertung

Alle Aufnahmen und Attempts derselben Person bleiben über `participant_id` zusammengehörig. Für eine personenübergreifende Evaluation darf dieselbe Person nicht mit einer anderen Sitzung im Training und im Test erscheinen. Für eine Untersuchung neuer Sitzungen derselben Personen wird dagegen ausdrücklich nach Sitzungs-ID getrennt. Weitere Regeln zur Datenaufteilung stehen im [Versuchsprotokoll](experiment-protocol.md).
