# Versuchsprotokoll: lateralisierte Motorik und MEG-Vergleich

Stand: 28.10.2026. Protokoll: `eeg-session-2.0`. **Softwareseitig implementiert und hardwarefrei geprüft; Windows-/Headset-Abnahme und wissenschaftliche Pilotvalidierung stehen aus.** Dieses Dokument ist die zentrale wissenschaftliche Spezifikation für die neue Sitzung mit 45:04 Minuten.

Die CLI startet nach aktuellem Release-Build mit `start session` den neuen Ablauf; Bedienung und Hinweise zu Bestandsaufnahmen stehen in der [Sitzungsanleitung](../gtec_Clib/terminal/SESSION_ANLEITUNG.md). Technischer Stand und Dateiverträge: [Sitzungsspezifikation](session-automation-plan.md). Einrichtung der Aufnahme: [OSCAR-Anleitung](../acquisition/README.md).

## 1. Studienziel und Umfang

Die acht gewünschten Bedingungen bilden den Schwerpunkt: linke/rechte Faust und linker/rechter Fuß, jeweils ausgeführt und vorgestellt. Dazu kommen vier kleine Vergleichsbedingungen aus dem MEG-Paradigma: beide Hände vorstellen, beide Füße vorstellen, Wortgenerierung und Subtraktion. Die geplante Aufnahme dauert **45:04 Minuten**, einschließlich Baselines und geplanter Pausen; Aufbau, Übung und ungeplante Wiederholungen kommen hinzu.

Ziel der Studienarbeit:

> Untersuchen, welche motorischen und kognitiven Aufgaben eines MEG-inspirierten BCI-Paradigmas mit einem praktischen Achtkanal-EEG unterscheidbar sind, wie sich ausgeführte und vorgestellte Bewegungen unterscheiden und welche Grenzen bei der Übertragung auf weitere Sitzungen auftreten.

Das Studienziel umfasst weiterhin die Untersuchung motorischer **und kognitiver** Aufgaben mit einem praktischen EEG sowie den Bezug zum MEG-Paradigma. Die Links-/Rechts-Unterscheidung erweitert sie. Würden Wortgenerierung und Rechnen vollständig entfallen, bliebe nur der sensomotorische Teil des ursprünglichen Ziels erhalten. Diese Einschränkung darf nicht durch eine unveränderte Zielbeschreibung verdeckt werden.

Die verfügbare Zeit erlaubt keine gleich starke Untersuchung aller Fragen. Der Vorschlag priorisiert die gewünschten Bewegungsbedingungen; der MEG-Vergleich und insbesondere die kognitiven Aufgaben bleiben explorativ. Eine gleichrangige Bestätigungsstudie aller Fragestellungen erfordert zusätzliche Sitzungen oder weniger Bedingungen.

## 2. Was der MEG-Vergleich tatsächlich erlaubt

MEGBCI2020 enthält beidseitige Hand-/Fußvorstellung sowie Wortgenerierung und Subtraktion, jedoch keine entsprechenden Links-/Rechts- oder Ausführungsbedingungen. Dokumentiert sind 17 Personen, zwei Termine und 50 Trials je Klasse und Termin. Das ursprüngliche Timing ist 2 s Vorbereitung, 5 s Aufgabe mit sichtbarem Cue und 1,5–2 s Intervall. [Rathee et al. (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8085139/)

Deshalb werden echte beidseitige Imagery-Trials erhoben. Das Zusammenlegen von linker und rechter Vorstellung erzeugt keine beidseitige Vorstellung. Auch ein rechnerischer Mittelwert ihrer EEG-Muster ist kein Ersatz für diese Bedingung.

Eine spätere MEG-Auswertung beschreibt für die Hände Greifvorstellung und für die Füße beidseitige Dorsalflexion. Das unterstützt die inhaltliche Anbindung unserer Bewegungswahl. Sie analysiert 18 Personen; ihre Kohorte und Ergebnisse dürfen nicht ungeprüft mit der veröffentlichten 17-Personen-Datenbasis gleichgesetzt werden. [Originalstudie zur MEG-Auswertung](https://onlinelibrary.wiley.com/doi/full/10.1002/hbm.26284)

| Vergleich | Aussage und Grenze |
|---|---|
| Beidseitige Hand- gegen Fußvorstellung in EEG und MEG | Inhaltlich ähnlichste gemeinsame Aufgabe; angepasster Ablauf und verschiedene Kohorten bleiben Störfaktoren. |
| Wortgenerierung gegen Subtraktion | Erhält den kognitiven Vergleich; wenige EEG-Trials und gegebenenfalls andere Sprache begrenzen ihn. |
| Unilaterale Aufgaben im EEG | Neue Erweiterung; in diesem MEG-Datensatz fehlt das direkte Gegenstück. |
| Ausführung gegen Vorstellung im EEG | Eigene Vergleichsfrage; tatsächliche Bewegung kann Artefakte und sensorische Rückmeldungen enthalten. |
| EEG- gegen MEG-Klassifikationsleistung | Vergleich zweier Messkonfigurationen und Datensätze; kein isolierter kausaler Nachweis eines Modalitätsvorteils. |

Die längere EEG-Erholung von 6–8 s, andere Klassenmischung, kleinere Trialzahlen und gegebenenfalls deutsche Wortgenerierung sind bewusste Anpassungen. Gleiche Aufgabenbezeichnungen machen daraus keine exakte Replikation. Ein simultaner EEG–MEG-Vergleich ist nicht vorgesehen; hierfür werden keine gemeinsamen Echtzeittrigger behauptet.

## 3. Konkrete Bewegungen

### Hände: lockere Faust schließen und öffnen

Unterarme vollständig abstützen, Handgelenke möglichst neutral, Schultern und Kiefer entspannen. Nur die angewiesene Hand langsam zu einer lockeren Faust schließen und wieder öffnen. Kein kräftiges Pressen, kein Handgelenkbeugen und kein Anheben des Arms.

Im viersekündigen Fenster ungefähr zwei gleichmäßige Schließ-/Öffnungszyklen, jeder etwa 2 s. Diese langsame Bewegung vorher üben; während der Messung kein Metronom und kein Zählen verlangen. Zwei Zyklen sind eine eigene Standardisierungsentscheidung, kein belegtes Optimum. Nicht maximal öffnen oder die Finger abrupt strecken. Bis zum Aufgabenende wieder in der Ausgangsposition sein.

Bei Imagery dieselbe Bewegung aus der eigenen Körperperspektive **fühlen**, ohne sie auszuführen: Fingerbeugung, leichte Spannung und Lösen vorstellen. Kein Betrachten eines inneren Films aus Zuschauerperspektive als Standardstrategie.

### Beine: Dorsalflexion im Sprunggelenk

Die Bedingung wird präzise als **linker/rechter Fuß: Dorsalflexion** bezeichnet. Sie untersucht keine Bewegung des ganzen Beins.

- Bequem sitzen, Rücken und Oberschenkel abstützen; Knie ungefähr rechtwinklig, beide Fersen auf einer stabilen Unterlage.
- Den Vorfuß der angewiesenen Seite samt Zehen in Richtung Schienbein anheben und kontrolliert absenken. Die Ferse bleibt aufliegen. Die Bewegung kommt aus dem Sprunggelenk; reines Zehenstrecken genügt nicht.
- Kleine, schmerzfreie Auslenkung; etwa 10–15° als zu prüfender Übungsrichtwert, nicht als erzwungene Zielvorgabe. Vor Studienbeginn eine reproduzierbare bequeme Ausführung festlegen und dokumentieren.
- Ungefähr zwei Hebe-/Senkzyklen in 4 s. Keine Hüftbeugung, kein Knieheben, kein Abheben des ganzen Beins und kein kräftiges Stampfen. Die Gegenseite bleibt entspannt.
- In Imagery dieselbe Empfindung von Vorfußheben und Absenken vorstellen; beide Füße bleiben tatsächlich ruhig.

Diese Wahl soll Rumpf- und Kopfmitbewegungen gegenüber dem bisherigen Beinheben verringern und eine klar instruierbare Vorstellung ermöglichen. Das ist eine zu prüfende Designannahme; eine bessere EEG-Klassifikation wird nicht vorausgesetzt.

Für links-/rechtsseitige Dorsalflexionsvorstellung gibt es eine EEG-Originalstudie mit neun Personen. Sie beschreibt zugleich die schwierige Trennung der nahe beieinanderliegenden kortikalen Fußrepräsentationen und verwendete 19 Elektroden. Ihre Befunde begründen die Untersuchung, garantieren aber keine erfolgreiche Unterscheidung mit acht Kanälen. [Tariq et al. (2020)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0230184)

Links und rechts erhalten **dieselbe gespiegelte Bewegung**. Links den Fuß heben und rechts nach unten drücken würde Seite und Bewegungsart vermischen. Größere Bewegungen nur zur Steigerung der Trefferquote würden außerdem eine Artefakterkennung begünstigen.

### Vier zusätzliche Vergleichsbedingungen

1. **Beide Hände vorstellen:** beidseitiges, gleichzeitiges lockeres Faustschließen und Öffnen, 5 s. Langsam und kontinuierlich vorstellen; keine tatsächliche Bewegung.
2. **Beide Füße vorstellen:** beidseitiges, gleichzeitiges Vorfußheben und Absenken, 5 s; keine tatsächliche Bewegung.
3. **Wortgenerierung:** zu einem zentral angezeigten Buchstaben still ein passendes Wort finden. Nicht sprechen oder die Lippen bewegen. Im Pilot prüfen, ob die Aufgabe zu früh endet; Strategie vor der Hauptstudie festlegen. Implementierter Standard: deutsches Wort. Das ist eine dokumentierte Sprachadaption gegenüber englischen Wörtern im MEG-Versuch. Für einen engeren Sprachvergleich wäre Englisch mit vorab geprüfter Sprachkompetenz erforderlich.
4. **Subtraktion:** eine zweistellige Zahl von einer zwei- oder dreistelligen Zahl still subtrahieren, z. B. `83 − 27`. Fünf Sekunden Aufgabenzeit; nach Lösung das Ergebnis still prüfen. Dies ersetzt hier das bisherige zehnsekündige fortlaufende Subtrahieren von 7. Es ist keine äquivalente Fortsetzung der alten Rechenbedingung. Individuelle Lösungsdauer und anschließendes Prüfen können das Signal mitbestimmen.

Implementierte Parameter: acht unterschiedliche Buchstaben aus `BDFGHKLMNRST`; acht unterschiedliche Subtraktionspaare mit Minuend 60–199 und Subtrahend 12–59. Auswahl vorab mit dem gespeicherten Sitzungsseed, durchgehend positives Ergebnis. Diese Bereiche sind feste Pilotentscheidungen und keine validierte Schwierigkeitskalibrierung.

Für die kognitiven Aufgaben Buchstaben/Zahlen vorab festlegen, Schwierigkeit in der Übung prüfen und nicht während der Messung adaptiv verändern. Keine Antwortbewegung während des Aufgabenfensters. Verständnis und Durchführung in den ohnehin geplanten Blockpausen kurz abfragen; zusätzliche Antwortzeit verlängert die Sitzung.

Faustöffnen/-schließen als tatsächliche und vorgestellte Links-/Rechts-Aufgabe bietet zusätzlich einen Bezug zum [PhysioNet EEG Motor Movement/Imagery Dataset](https://physionet.org/content/eegmmidb/1.0.0/). Dieser Datensatz bietet keinen identischen links-/rechtsseitigen Fußvergleich. Sein Labelmapping hängt vom jeweiligen Lauf ab.

## 4. Bedingungen, Wiederholungen und Blockaufbau

### Lauf M: Motorische Ausführung

Vier Blöcke mit jeweils 16 Trials: vier Trials je Bedingung. Über den Lauf entstehen 16 Trials je Bedingung und 64 insgesamt.

| Vorgeschlagenes Label | Bedingung | Trials pro Sitzung |
|---|---|---:|
| `me_hand_left` | Linke Faust schließen/öffnen | 16 |
| `me_hand_right` | Rechte Faust schließen/öffnen | 16 |
| `me_foot_left` | Linker Vorfuß heben/senken | 16 |
| `me_foot_right` | Rechter Vorfuß heben/senken | 16 |

### Lauf I: Imagery und mentale Vergleichsaufgaben

Vier Blöcke mit jeweils 26 Trials. Jeder Block enthält alle acht Bedingungen dieses Laufs; die Vergleichsaufgaben liegen dadurch über die Sitzung verteilt und nicht ausschließlich am Anfang oder Ende.

| Vorgeschlagenes Label | Bedingung | Pro Block | Pro Sitzung |
|---|---|---:|---:|
| `mi_hand_left` | Linke Faust vorstellen | 4 | 16 |
| `mi_hand_right` | Rechte Faust vorstellen | 4 | 16 |
| `mi_foot_left` | Linken Vorfuß vorstellen | 4 | 16 |
| `mi_foot_right` | Rechten Vorfuß vorstellen | 4 | 16 |
| `mi_hands_bilateral` | Beide Hände gleichzeitig vorstellen | 3 | 12 |
| `mi_feet_bilateral` | Beide Füße gleichzeitig vorstellen | 3 | 12 |
| `word_generation` | Stille Wortgenerierung | 2 | 8 |
| `mental_subtraction_single` | Einzelne stille Subtraktion | 2 | 8 |
| **Summe** | | **26** | **104** |

Gesamt: **168 geplante Aufgaben-Trials in zwölf Bedingungen**. Die acht gewünschten Bedingungen erhalten jeweils 16 Trials. Die vier ergänzenden Bedingungen sichern den inhaltlichen MEG-Bezug, sind aber keine ausreichend gepowerte Vierklassenstudie.

## 5. Timing und überprüfbare Gesamtdauer

| Trialfamilie | Vorbereitung | Aufgabe | Erholung | Mittelwert |
|---|---:|---:|---:|---:|
| Acht unilaterale Bedingungen | 2 s | 4 s | 6/7/8 s | 13 s |
| Vier MEG-bezogene Vergleichsbedingungen | 2 s | 5 s | 6/7/8 s | 14 s |

Zunächst Kreuz; dann zentraler Aufgabenhinweis während der gesamten Aufgabe; danach wieder Kreuz als Aufgabenende. Keine seitlich versetzten Pfeile und kein zusätzliches STOPP. Bei Imagery/Ausführung identische Hinweise für dasselbe Körperteil; der Modus wird vor dem Block erläutert. Damit wird die Modusklassifikation allerdings nicht von der Blockzeit entkoppelt.

Exakte Erholungskontingente, innerhalb der Kontingente zufällig zugeordnet:

- Je unilateraler Bedingung und Block: einmal 6, zweimal 7, einmal 8 s; über den Lauf 4/8/4.
- Je beidseitiger Imagery-Bedingung und Block: einmal 6, einmal 7, einmal 8 s; über den Lauf 4/4/4.
- Je kognitiver Bedingung: zwei Blöcke mit 6 und 8 s, zwei Blöcke mit zweimal 7 s; über den Lauf 2/4/2. Welche Blöcke welches Paar erhalten, wird unabhängig vom Inhalt ausgelost.

Jeder Motorikblock dauert damit exakt 208 s = 3:28, jeder gemischte Imageryblock exakt 348 s = 5:48. Die Reihenfolge innerhalb des Blocks verändert diese Summen nicht.

| Abschnitt | Rechnung | Dauer |
|---|---|---:|
| Anfangsbaseline | 60 s, Augen offen | 1:00 |
| Motorische Trials | 64 × 13 s im Mittel | 13:52 |
| Motorische Blockpausen | 3 × 45 s | 2:15 |
| Laufwechsel | 90 s | 1:30 |
| Unilaterale Imagery-Trials | 64 × 13 s im Mittel | 13:52 |
| Beidseitige Imagery-Trials | 24 × 14 s im Mittel | 5:36 |
| Kognitive Vergleichstrials | 16 × 14 s im Mittel | 3:44 |
| Blockpausen im gemischten Lauf | 3 × 45 s | 2:15 |
| Endbaseline | 60 s, Augen offen | 1:00 |
| **Gesamt** | **2704 s** | **45:04** |

**Rest ist die angeleitete Erholung zwischen Aufgaben; es gibt keine zusätzlichen Rest-Trials.** Während des Kreuzes still sitzen, die vorherige Aufgabe beenden und keine neue Bewegung oder bewusste Vorstellung beginnen. Augen bleiben offen; Erholung bedeutet keine garantierte mentale Inaktivität.

Die viersekündigen unilateralen und fünfsekündigen Vergleichsaufgaben sind getrennte Trialfamilien. Für Vergleiche zwischen ihnen ausschließlich gleich lange Auswertungsfenster verwenden; die Dauer darf kein Klassifikationsmerkmal werden.

Sechs bis acht Sekunden Erholung sind ein zu prüfender Ausgangspunkt, keine gesicherte vollständige Rückkehr zur Baseline. Insbesondere nach wiederholten Bewegungen und Kopfrechnen den Zeitverlauf im Pilot prüfen. Frühe Erholung nicht als neutrale Ruhe labeln. Müssen Pausen länger sein, die Gesamtdauer ehrlich neu berechnen.

**Zeitannahme:** 45 Minuten beziehen sich auf die Aufnahme. Ist stattdessen der gesamte Termin auf 45 Minuten begrenzt, muss nach Messung der tatsächlichen Aufbau-/Übungszeit ein kürzerer Plan entstehen; ein Headset-Aufbau passt nicht zusätzlich in diese Rechnung.

## 6. Reihenfolge, Anzeige und Kontrollen

- Übung und Einweisung von den Hauptdaten getrennt kennzeichnen. Jede Person übt vorab alle tatsächlichen Bewegungen und die zugehörige kinästhetische Vorstellung, unabhängig davon, welcher Lauf zuerst kommt.
- Laufreihenfolge M→I und I→M zwischen Personen möglichst gleich verteilen. Bei zwei Terminen dieselbe Person möglichst in umgekehrter Reihenfolge messen. Reihenfolgegruppe separat von der stabilen [Teilnehmer-ID](participant-ids.md) dokumentieren.
- Alle Bedingungen eines Blocks unter den Kontingenten zufällig mischen; höchstens zwei gleiche Bedingungen hintereinander, auch über Blockgrenzen. Seed, Liste und alle Dauern vorab speichern. Den Generator auf Machbarkeit und Häufigkeiten prüfen.
- Schriftposition, Größe und Helligkeit möglichst vergleichbar; Aufgaben stets zentral anzeigen. Ein identischer räumlicher Cue verhindert keine inhaltsabhängigen visuellen Unterschiede.
- Kein EEG-Klassifikationsfeedback während der Hauptmessung. Natürliche Blinzler erlauben, vorzugsweise in Erholung; kein erzwungenes langes Offenhalten der Augen.
- In Blockpausen kurz Ausführung, unerwünschte Mitbewegungen, Imagery-Strategie und subjektive Schwierigkeit erfassen. Selbstauskunft misst keine objektiv erfolgreiche Imagery.
- Keine spontanen Aufgabenwechsel bei schlechten Zwischenergebnissen. Ein Pilot darf zur Änderung des Protokolls führen; danach neue Version und separate Bestätigungsdaten.

Für Blick-/Cue-Einflüsse zentrale Sensoren als vorab definierte Sensitivitätsanalyse verwenden. Eine erfolgreiche Klassifikation nach Ausschluss der ersten 0,5 s beweist nicht, dass visuelle Einflüsse verschwunden sind. Ein separater passiver Cue-Kontrollversuch wäre methodisch stärker, benötigt aber zusätzliche Zeit und gehört nicht zu den errechneten 45:04.

## 7. EEG, Bewegungskontrolle und Verarbeitung

Vor Aufnahme Kanalreihenfolge und reale Positionen verifizieren. Die im Projekt hinterlegte Unicorn-Anordnung enthält Fz, C3, Cz, C4, Pz, PO7, Oz und PO8; generische CSV-Namen allein bestätigen diese Zuordnung nicht. C3/Cz/C4 sind für die vorab geplanten sensomotorischen Analysen besonders relevant. Referenz, Kontaktqualität, Abtastrate und Einheiten ausdrücklich dokumentieren.

Die schon ausgewertete lokale Pilotsitzung lieferte für Bewegungssensoren allein hohe Motorik-Unterscheidbarkeit und für die einfache Imagery-Baseline kein überzufälliges Ergebnis. Das motiviert bessere Bewegungskontrolle, belegt aber weder die Nutzlosigkeit von Imagery noch den Erfolg des neuen Plans. [Lokaler Pilotbericht](ml-feasibility-2026-10-22.md)

Die vorhandene IMU am Kopf kann die Bewegungslosigkeit von Fingern oder Füßen nicht zuverlässig bestätigen. Wenn verfügbar, synchronisiertes bilaterales EMG für Unterarm und Tibialis anterior oder geeignete Fuß-/Handsensoren ergänzen. Diese sind Kontrollsignale, keine Eingaben des primären EEG-Modells. Ohne EMG sichtbare Bewegungen protokollieren und ausdrücklich festhalten, dass unterschwellige Muskelaktivität nicht ausgeschlossen ist. Neue Kontrollhardware wird hier nicht als vorhanden angenommen.

Rohdaten unverändert sichern. OSCAR-Ausgabe getrennt erhalten und eine vorab festgelegte Auswertung der Rohdatenkopie mit transparenter Verarbeitung gegen die OSCAR-Variante vergleichen. Nicht die Variante mit der besseren Testleistung nachträglich zur primären erklären. Artefaktbereinigung kann auch aufgabenrelevante Aktivität verändern; hohe Motoriktrefferquoten nach Bereinigung sind kein automatischer Nachweis neuronaler Erkennung.

## 8. Auswertung mit klarer Rangfolge

Vor Bestätigungsdaten die primäre Fragestellung, Pipeline, Fenster und Ausschlussregeln festschreiben. Vorgeschlagene Rangfolge:

1. **Primärer EEG–MEG-Anker:** beidseitige Hand- gegen beidseitige Fußvorstellung. Für beide Datensätze denselben inhaltlichen Kontrast auswerten.
2. **Zentrale EEG-Erweiterung:** linke gegen rechte Handvorstellung; dieselbe Seitenunterscheidung bei Ausführung als Referenz. Gleiche Klassen und Trialzahlen vergleichen.
3. **Anspruchsvolle sekundäre Frage:** linke gegen rechte Fußvorstellung sowie ausgeführte Dorsalflexion. Ein schwaches Ergebnis ist eine relevante Grenze des Setups.
4. **Weitere explorative Fragen:** vier unilaterale Körperteil-/Seitenklassen getrennt für ME und MI, Wortgenerierung gegen Subtraktion, Transfer eines ME-Körperteilmodells auf MI und umgekehrt.

Ein gemeinsamer Acht- oder Zwölfklassenwert ist kein geeigneter Hauptendpunkt. Ausführung und mentale Aufgaben liegen in getrennten Läufen; ein direkter ME/MI-Klassifikator könnte Laufzeit, Drift oder Ermüdung erkennen. Unterschiedliche Klassenanzahlen und Trainingsmengen dürfen nicht als Beweis interpretiert werden, dass eine Aufgabenfamilie leichter ist.

### Pipeline und Splits

- Ein gleich langes Fenster, vorgeschlagen 0,5–3,5 s nach Aufgaben-Cue, für die erste Offline-Klassifikation. Es liegt vollständig in beiden Aufgabenfenstern. Eine spätere Rebound-Analyse separat als zeitlich andere Fragestellung behandeln.
- Zunächst feste, einfache Pipeline: logarithmische Bandpower in 8–13 und 13–30 Hz mit regularisiertem linearem Klassifikator. CSP/FBCSP als begrenzte zweite Analyse; mit wenigen Trainings-Trials keine große Modellsuche. Individualisierte Bänder nur aus Trainingsdaten wählen.
- Innerhalb der Sitzung jeweils einen vollständigen Block zurückhalten. Alle Ausschnitte und Attempts desselben geplanten Trials zusammenhalten; invalidierte/unvollständige Attempts ausschließen. Vorverarbeitung und Parameterschätzung dürfen keine Testdaten zum Lernen verwenden.
- Für Sitzungsübertragung denselben Personen mindestens zwei Termine anbieten: Termin 1 Training/Modellwahl, Termin 2 unangetasteter Test. Anschließend erfolgte Optimierung benötigt weitere Bestätigungsdaten. Für neue Personen ganze Personen zurückhalten.
- Balanced Accuracy, Konfusionsmatrix, gültige Trials je Klasse, Ausschlussquoten und Unsicherheit auf Personenebene berichten. Permutationen respektieren Block-/Sitzungsstruktur; Explorationsfamilien und Mehrfachtests kennzeichnen. Eine einzelne Person liefert keine Populationsunsicherheit.
- Nur gleiche Kontraste, Fenster und vergleichbare Trainingsmengen für motorisch/imaginiert beziehungsweise motorisch/kognitiv gegenüberstellen. Für ungleiche Mengen vorab wiederholte Trainings-Subsamples oder Lernkurven festlegen, ohne Testdaten zur Auswahl zu verwenden.

### Konkreter MEG-Vergleich

Die [Originaldaten und Referenzskripte](https://github.com/sagihaider/MEGBCI2020) separat auditieren und den Hand-/Fuß-Kontrast neu auswerten, statt eine publizierte Gesamtgenauigkeit neben unseren Pilotwert zu stellen. Dabei Sensorarten, Einheiten, Sampling und Artefaktregeln je Modalität berücksichtigen. Magnetometer und Gradiometer nicht ungeprüft als gleich skalierte Kanäle behandeln. Acht MEG-Sensoren simulieren kein Achtkanal-EEG.

Zwei Ansichten vorsehen: eine transparente Auswertung mit der jeweils verfügbaren Sensormenge und eine Sensitivitätsanalyse mit angeglichenen Trainings-Trialzahlen. Personen und Sitzungen innerhalb jedes Datensatzes korrekt trennen. EEG- und MEG-Personen sind ungepaart; kein gepaarter Personentest. Leistungsunterschiede bleiben durch Gerät, Kohorte, Sensorlayout und Paradigma mitbedingt. Ein direkter Transfer von EEG-Rohkanälen auf MEG-Rohkanäle ist kein vorgesehener Hauptversuch.

## 9. Datenumfang und wissenschaftliche Tragfähigkeit

16 unilaterale, 12 beidseitige und acht kognitive Trials je Bedingung sind ein **Zeitbudget für einen Pilot**, kein Powernachweis. Mit vier Blöcken bleiben pro kognitiver Klasse nur sechs Trainings- und zwei Testtrials je Fold; einzelne Fehler verändern den Wert stark. Auch der primäre Hand-/Fuß-Anker bleibt klein. Keine robuste Vierklassen- oder Deep-Learning-Leistung versprechen.

Empfehlung: zuerst einen technischen vollständigen Probelauf und danach einen Entwicklungspilot mit mehreren Personen. Daraus verwertbare Trialquoten, Ermüdung, Lernkurven und Streuung bestimmen. Anschließend Teilnehmer-/Terminzahl anhand des primären Endpunkts und gewünschter Präzision planen. Viele EEG-Fenster ersetzen keine unabhängigen Personen. Für die beabsichtigte Prüfung neuer Sitzungen sind zwei Termine pro Person methodisch wertvoller als bloßes Aufteilen einer Aufnahme; auch zwei Termine garantieren noch keine Langzeitstabilität.

Wenn gleich starke Aussagen zum kognitiven Teil verlangt werden, muss dafür mehr Datenzeit eingeplant werden. Die volle ursprüngliche Fragestellung lässt sich inhaltlich in 45 Minuten erhalten, ihre belastbare Beantwortung jedoch nicht allein durch diesen Ablauf garantieren.

## 10. Pilotentscheidung und ausstehende Abnahme

Vor Bestätigungsdaten prüfen:

- Sind Hand- und Fußbewegung ohne sichtbare Kopf-/Rumpfmitbewegung komfortabel und wiederholbar?
- Können Personen Seiten und Modus zuverlässig unterscheiden? Funktionieren die gemischten mentalen Blöcke ohne häufige Instruktionsfehler?
- Wie viele Trials bleiben je Klasse nach vorab definierten Qualitätsregeln übrig? Sind späte Ruheabschnitte hinreichend erholt?
- Sind die kognitiven Aufgaben mit 5 s sinnvoll und inhaltlich nachvollziehbar ausführbar? Wortfindung, Rechenschwierigkeit und Sprache dokumentieren.
- Bleibt die Aufnahme einschließlich echter Wechselzeiten nahe 45 Minuten? Ungeplante Pausen und Wiederholungen separat ausweisen.

Die Umsetzung verwendet eine eigene Protokollversion gemäß [Sitzungsspezifikation](session-automation-plan.md). Vor Erhebungen nach dem neuen Protokoll Windows-Build, Anzeige und einen vollständigen Headset-Lauf prüfen sowie Einwilligung und institutionelle Studienunterlagen auf die geänderten Aufgaben abstimmen.

Der Plan wurde anhand der genannten Originalquellen erarbeitet. Plan- und Laufzeitregressionen prüfen die softwareseitige Umsetzung einschließlich einer vollständigen beschleunigten Sitzung. Das belegt keine Hardware- oder wissenschaftliche Validierung. Für diese Implementierung wurden keine MEG-Daten heruntergeladen und keine neuen Studienmodelle auf Teilnehmerdaten trainiert.
