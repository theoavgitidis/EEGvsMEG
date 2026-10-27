# OSCAR: Integrationsstand

Geprüft am 27.10.2026. OSCAR ist noch **nicht in der Pipeline aktiv**.

## Verifizierter Stand

- Die mitgelieferte Unicorn-C-API (`gtec_Clib/lib/unicorn.h`) stellt keine OSCAR-Funktion bereit. Der C++-Recorder speichert weiterhin die vom Treiber gelieferten Werte.
- Das offizielle Python-Paket `gtec-oscar==1.3.2` wurde lokal in `.venv-mne` unter Python 3.12 installiert. Der systemweite Python 3.15 wird von dieser Paketversion nicht unterstützt.
- Die öffentliche Laufzeitschnittstelle bietet `OscarLive(enable_oscar=True)`, `setup(fs, n_ch)` und `step(data)`.
- Bereits `OscarLive().setup(250.0, 8)` bricht mit `RuntimeError: gtec_oscar is not authenticated. Call gtec_oscar.authenticate(key) first.` ab. Installation allein aktiviert die Verarbeitung nicht.
- Es wurde kein bereinigtes Signal erzeugt. Die vorhandenen Viewer und ML-Pipelines wurden nicht auf OSCAR umgestellt.

## Nächster notwendiger Schritt

Einen von g.tec unterstützten Authentifizierungsweg für die direkte Python-Nutzung klären oder den offiziellen g.Pype-Workflow mit freigeschaltetem OSCAR einsetzen. Schlüssel nicht ins Repository oder in Chat-Nachrichten schreiben. Nach geklärtem Zugang müssen zuerst Einheiten, Array-Ausrichtung, Blockgrößen, Ausgabebedeutung sowie Anlauf- und Verzögerungsverhalten mit dem echten Paket geprüft werden.

## Geplanter erster Einbau

OSCAR zunächst optional auf einer Kopie gespeicherter Aufnahmen anwenden, bevor Anzeige-Filter laufen. Beide Viewer sollen denselben Adapter nutzen. Roh-CSV und Ereignisdatei bleiben erhalten. Korrigierte Signale müssen eindeutig als OSCAR-Ausgabe gekennzeichnet werden.

Die Verzögerung muss aus der tatsächlichen Konfiguration stammen: Die g.Pype-Dokumentation nennt bei 250 Hz beispielhaft 83 Samples und warnt ausdrücklich davor, `K` als Verzögerung zu interpretieren. Ereignisse, Anlaufbereich und Aufnahmeende müssen entsprechend geprüft werden; keine pauschale Verschiebung ohne verifiziertes Ausgabetiming. Erst danach die Verarbeitung in Merkmalsberechnung oder Klassifikation übernehmen und Rohdaten gegen korrigierte Daten vergleichen.

## Herstellerquellen

- [Offizielles Paket](https://pypi.org/project/gtec-oscar/)
- [g.Pype: OSCAR und Authentifizierungs-/Installationsumgebung](https://gpype.gtec.at/content/5_faq/index.html)
- [HybridBlack mit enable_oscar](https://gpype.gtec.at/content/7_sdk_reference/backend_sources/hybrid_black.html)
- [AmplifierSource: tatsächliche OSCAR-Verzögerung](https://github.com/gtec-medical-engineering/gpype/blob/main/gpype/backend/sources/base/amplifier_source.py)

## Lokale Reproduktion der aktuellen Blockade

```sh
.venv-mne/bin/python -c 'from gtec_oscar import OscarLive; print(OscarLive().setup(250.0, 8))'
```

Erwartetes Ergebnis ohne Hersteller-Authentifizierung: die oben genannte Fehlermeldung. Dies ist kein Nachweis einer funktionierenden Artefaktkorrektur.
