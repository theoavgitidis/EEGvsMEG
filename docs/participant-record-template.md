# Teilnehmerbogen – Vorlage

Stand: 28.10.2026. Für Motorik, Motor Imagery und kognitive Vergleichsaufgaben gemäß [Versuchsprotokoll](experiment-protocol.md). Ein Bogen je Person; den Sitzungsabschnitt für jede Aufnahme wiederholen. Neue Aufgaben sind für Protokoll 2.0 geplant; die CLI führt noch Protokoll 1.0 aus. Bei Bestandsaufnahmen nicht durchgeführte Aufgaben als `n/a` erfassen.

**Nur die leere Vorlage in Git speichern.** Ausgefüllte Bögen geschützt außerhalb des Repositorys ablegen. Keine Namen, Kontaktdaten, Geburtsdaten oder Zuordnungsschlüssel eintragen; Einwilligungen und eine gegebenenfalls notwendige Namenszuordnung separat aufbewahren. `n/a` bedeutet nicht erhoben oder unbekannt; „keine Angabe“ bedeutet bewusst nicht beantwortet.

## Welche Angaben sind sinnvoll?

- **Zuordnung und Durchführung:** Teilnehmer-ID, Sitzungs-ID, Einwilligungsstatus, Einweisung und Abweichungen sind für nachvollziehbare Datennutzung und Ausschlüsse erforderlich.
- **Stichprobenbeschreibung:** Alter in vollendeten Jahren und Händigkeit erfassen. Händigkeit und eine einfache Selbstauskunft zur Fußpräferenz beschreiben die Stichprobe bei den Links-/Rechts-Aufgaben; sie sind keine automatisch gültigen Ausschlusskriterien. Geschlecht ist für das aktuelle Auswertungsziel kein Pflichtfeld; nur bei vorab begründeter Fragestellung ergänzen und die gemeinte Variable definieren.
- **Sitzungseinflüsse und Aufgabeneinhaltung:** Schlaf, aktuelle Müdigkeit, kürzlicher Koffeinkonsum und Schwierigkeiten bei der Ausführung knapp dokumentieren. Das sind mögliche Einflussgrößen, keine diagnostischen Angaben oder automatisch gültigen Ausschlusskriterien.

Die Auswahl ist ein Projektvorschlag auf Grundlage des [Versuchsprotokolls](experiment-protocol.md). Alter und Händigkeit sind auch etablierte Teilnehmermerkmale in [BIDS](https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/data-summary-files.html). Diese Markdown-Vorlage ist kein BIDS-Export; das [EVM-ID-Schema](participant-ids.md) bleibt bestehen.

## Person – einmal ausfüllen

| Angabe | Eintrag |
|---|---|
| Teilnehmer-ID | `EVM-P___` |
| Alter bei erster Sitzung (volle Jahre) | |
| Händigkeit (Selbstauskunft) | rechts / links / beidhändig / keine Angabe |
| Bevorzugter Fuß zum Schießen eines Balls (Selbstauskunft) | rechts / links / keine klare Präferenz / keine Angabe |
| Für Wortgenerierung vorgesehene Sprache gut beherrscht? | Sprache: ___; ja / teilweise / nein / keine Angabe |
| Vorerfahrung mit Motor Imagery / EEG-Aufgaben | keine / vorhanden / keine Angabe |

## Sitzung – je Aufnahme ausfüllen

IDs exakt aus den Sitzungsmetadaten übernehmen. Teilnehmer-ID und Sitzungs-ID bilden gemeinsam die Zuordnung; auch ein Neustart nach Abbruch erhält einen eigenen Abschnitt.

| Angabe | Eintrag |
|---|---|
| Teilnehmer-ID + Sitzungs-ID | `EVM-P___` + `session_…` |
| Besuchsnummer | |
| Einwilligung für diese Erhebung dokumentiert und gültig | ja / nein / ungeklärt |
| Alle Aufgaben erklärt, geübt und verstanden | ja / nein; ggf. Schwierigkeit: |
| Protokollversion; konkrete Laufreihenfolge | tatsächliche Version: ___; Reihenfolge: ___; geplant 2.0: M→I oder I→M; bisher 1.0: drei Läufe |
| Schlaf letzte Nacht (Stunden, Selbstauskunft) | |
| Müdigkeit unmittelbar vor Beginn | 0 = keine / 1 = leicht / 2 = mittel / 3 = stark |
| Koffein in den letzten 4 Stunden | nein / ja: Getränk, ungefähre Menge und Abstand zum Start / keine Angabe |
| Aktuelle Beeinträchtigung der Aufgaben oder Wachheit | keine berichtet / vorhanden / keine Angabe; nur aufgabenrelevante Auswirkung, keine Diagnosen oder Medikamentennamen |
| Geübte Bewegungsdefinition und Auslenkung je Seite | Faustschließen/-öffnen: ___; Fuß-Dorsalflexion: ___; Abweichung oder bisherige 1.0-Bewegung: ___ |
| Verwendete Sprache und Strategie der Wort-/Rechenaufgabe | Sprache: ___; Strategie/Schwierigkeit: ___; einzelne Subtraktion oder bisheriges serielles Rechnen: ___ |
| Signalqualität und Elektrodenkontakte vor Start geprüft | ja / nein; Auffälligkeit: |
| Nachher: Imagery ohne tatsächliche Bewegung möglich? | Hände/Füße und links/rechts/beidseitig bei Bedarf getrennt; ja / teilweise / nein / unklar; Selbstbericht bzw. Beobachtung kennzeichnen |
| Nachher: Wortgenerierung gemäß Anweisung möglich? | ja / teilweise / nein / unklar / n/a; Selbstbericht, ggf. vorzeitiges Aufgabenende |
| Nachher: Rechnen gemäß Anweisung möglich? | ja / teilweise / nein / unklar / n/a; Selbstbericht, ggf. vorzeitiges Aufgabenende |
| Besonderheiten, Unterbrechungs-/Abbruchgründe | keine / kurze Notiz mit Lauf, Block, Trial und Attempt oder Ereigniszeit |

Ohne geklärte Einwilligung keine Messung beginnen. Die Fragen nach der Sitzung sind kurze Selbstauskünfte und kein objektiver Leistungsnachweis; während der Aufgaben- und Restfenster keine Antworten erheben. Auffälligkeiten während der Messung zusätzlich mit `mark` protokollieren, ohne personenbezogene Details.

## Bei der Auswertung ergänzen

- Verwendbar: ja / teilweise / nein / noch ungeprüft.
- Ausgeschlossene Läufe/Trials/Attempts und Begründung bzw. Verweis auf Ausschlussliste: ___

Abgeschlossene Trials sind nicht automatisch artefaktfrei. Ungültige und unvollständige Attempts gemäß [Versuchsprotokoll](experiment-protocol.md) ausschließen; Originaldaten erhalten. Ausschlussregeln vor der Hauptauswertung festlegen.

Datum/Startzeit, konkrete Laufreihenfolge, Seed, Samplingrate, Einheiten, Kanäle, Aufnahme-/Verarbeitungsvariante und Abschlussstatus aus den zugehörigen Metadatendateien verwenden. EEG, Events, Phasenplan und Metadaten zusammen erhalten; fehlende technische Angaben prüfen statt schätzen. Dieser Bogen ergänzt die Dateien und wird derzeit nicht automatisch von CLI oder Auswertung eingelesen.
