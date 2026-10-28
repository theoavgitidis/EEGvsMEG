# OSCAR aktivieren: recherchierter Integrationsweg

Recherche vom 27.10.2026; Dokumentation abgeglichen am 28.10.2026. **Der OSCAR-Aufnahmeweg ist implementiert und Standard bei `start session`; Windows-/Headset-Abnahme steht aus.** Bedienung, technischer Zeitvertrag und bisheriger Prüfstand stehen in der [Aufnahmeanleitung](../acquisition/README.md). Die folgenden Abschnitte dokumentieren Lizenzaktivierung und Herstellerquellen. Lizenzaktivierung und Headset-Lauf wurden nicht ausgeführt.

## Ergebnis und Korrektur der bisherigen Einschätzung

Die offizielle g.Pype-FAQ nennt für `HybridBlack` eine aktive **Unicorn Python Hybrid Black**-Lizenz. Dieselbe FAQ dokumentiert OSCAR als integrierte Funktion der Verstärkerknoten: `enable_oscar=True`. Eine separate OSCAR-Kauflizenz wird für diesen Weg dort nicht gefordert. g.Pype ist für private und Bildungsnutzung innerhalb einer IDE kostenlos; kommerzielle Bereitstellung hat eigene Lizenzbedingungen.

Damit ist unsere frühere Annahme, zunächst einen eigenen OSCAR-Schlüssel beschaffen zu müssen, nicht begründet. Der beobachtete Fehler beim direkten `OscarLive().setup(...)` zeigt nur, dass die isolierte Nutzung von `gtec_oscar` noch nicht authentifiziert war. Er beweist keinen fehlenden Kaufanspruch. Der Unicorn-Lizenzschlüssel sollte nicht auf Verdacht an `gtec_oscar.authenticate` übergeben werden: Der dokumentierte Einstieg ist die g.Pype-Pipeline.

Quellen: [g.Pype-FAQ](https://gpype.gtec.at/content/5_faq/index.html), [HybridBlack-Referenz](https://gpype.gtec.at/content/7_sdk_reference/backend_sources/hybrid_black.html).

## 1. Installation auf dem Messrechner

Python 3.12 verwenden; g.Pype 4.1.0 unterstützt Python 3.10–3.14. Eine neue Umgebung außerhalb des synchronisierten Checkouts anlegen. Beispiel für macOS mit installiertem `python3.12`:

```sh
python3.12 -m venv "$HOME/.venvs/eeg-oscar"
source "$HOME/.venvs/eeg-oscar/bin/activate"
python -m pip install 'gpype[gui,devices]==4.1.0' 'gtec-oscar==1.3.2' 'gtec-licensing==2.4.0' 'gtec-unicorn==1.0.0'
```

Windows PowerShell, mit installiertem Python 3.12:

```powershell
py -3.12 -m venv "$env:LOCALAPPDATA\EEGvsMEG\venvs\oscar"
& "$env:LOCALAPPDATA\EEGvsMEG\venvs\oscar\Scripts\Activate.ps1"
python -m pip install 'gpype[gui,devices]==4.1.0' 'gtec-oscar==1.3.2' 'gtec-licensing==2.4.0' 'gtec-unicorn==1.0.0'
```

`gui` liefert das Fenster, `devices` unter anderem den aktuellen `gtec_unicorn`-Treiber. Das alte `UnicornPy`-Modul aus dem lokal ergänzten Windows-SDK ist für diesen Weg nicht erforderlich. Die genannten Versionen wurden als offizielle Wheels heruntergeladen und ihre öffentlichen Python-Schnittstellen geprüft; die vollständige Installation dieser Kombination wurde hier nicht ausgeführt.

Quellen: [Installation und unterstützte Python-Versionen](https://gpype.gtec.at/), [Treiberpaket](https://pypi.org/project/gtec-unicorn/), [g.Pype-Changelog](https://gpype.gtec.at/content/8_appendix/index.html).

## 2. Vorhandene Unicorn-Python-Lizenz prüfen und aktivieren

Auf dem Rechner und unter dem Benutzerkonto ausführen, die später die Aufnahme durchführen:

```sh
python -c 'from gtec_licensing import api; print(api.check_license("Unicorn Python Hybrid Black").name)'
```

`SUCCESS` bestätigt die lokale Lizenzprüfung. Der Produktname stammt aus der g.Pype-Dokumentation; nennt ein tatsächlicher `gtec_unicorn.LicenseError` einen anderen Produktnamen, diesen mit den Kaufunterlagen abgleichen.

Unter Windows ist die Aktivierung über Unicorn Suite → **Licensing** der offiziell beschriebene Weg. Dort den vorhandenen Python-API-Lizenzschlüssel eingeben. Anschließend die obige Prüfung im verwendeten Python-Interpreter wiederholen. Eine aktive Lizenz auf einem anderen Rechner bestätigt keine Aktivierung auf dem Messrechner.

Alternativ bietet die öffentliche API des offiziellen Pakets `gtec-licensing==2.4.0` eine Aktivierung mit Schlüssel, Produktname und Kauf-E-Mail. Diesen Code lokal in einem Terminal ausführen; er fragt den Schlüssel verdeckt ab und gibt nur den Statusnamen aus:

```python
from getpass import getpass
from gtec_licensing import api

product = "Unicorn Python Hybrid Black"
status = api.check_license(product)
print("Lizenzstatus:", status.name)
if status != api.ErrorCode.SUCCESS:
    email = input("Lizenz-E-Mail: ").strip()
    key = getpass("Unicorn-Python-Lizenzschlüssel: ")
    status = api.activate(key, product, email)
    del key
    print("Aktivierung:", status.name)
```

Dieser Aufruf wurde anhand von `gtec_licensing/api.py` des offiziellen PyPI-Wheels geprüft, aber nicht mit einem Kundenschlüssel ausgeführt. Keine Schlüssel in Code, Git oder Kommandozeilenargumenten speichern. Bei `NO_ACTIVATIONS_LEFT` oder einem Produktkonflikt die bestehende Aktivierung beziehungsweise g.tec-Support klären; keine automatische Deaktivierung vornehmen. Ob der vorhandene individuelle Schlüssel akzeptiert wird, entscheidet erst dieser Lizenztest.

Quellen: [Unicorn-FAQ zur Aktivierung und Rechnerbindung](https://www.gtec.at/unicorn-faq/), [offizielles Licensing-Paket](https://pypi.org/project/gtec-licensing/).

## 3. Headset vorbereiten

- Unter Windows das Unicorn zuerst per Bluetooth mit dem Messrechner koppeln. Den bestehenden C++-Recorder und andere Programme schließen, die das Headset geöffnet halten.
- Unter macOS benötigt der aktuelle Treiber Apple Silicon und macOS 14 oder neuer. Der App, die Python startet, Bluetooth-Zugriff geben. Der Hauptthread muss eine Ereignisschleife ausführen; `MainApp.run()` übernimmt dies. Ein bloßes `time.sleep()` im Hauptthread genügt nicht.

Quellen: [g.Pype-FAQ](https://gpype.gtec.at/content/5_faq/index.html), [Plattformhinweise](https://gpype.gtec.at/content/4_advanced_topics/platform_notes.html).

## 4. OSCAR in der Pipeline einschalten

Das ist der entscheidende Schalter:

```python
source = gp.HybridBlack(enable_oscar=True)
```

Vollständiges Minimalbeispiel für einen separaten Live-Test, etwa als lokale Datei `oscar_live_test.py` speichern und aus der IDE mit der obigen Umgebung starten:

```python
import gpype as gp

app = gp.MainApp(caption="Unicorn – OSCAR Live-Test")
pipeline = gp.Pipeline()
source = gp.HybridBlack(
    channel_count=8,
    frame_size=4,
    enable_oscar=True,
)
scope = gp.TimeSeriesScope(name="OSCAR-Ausgabe", time_window=10)
pipeline.connect(source, scope)
app.add_widget(scope)

try:
    pipeline.start()
    # setup() erfolgt erst mit dem ersten Datenblock; der Produktionsworker
    # wartet deshalb auf erste ausgerichtete Samples, bevor er READY meldet.
    app.run()
finally:
    pipeline.close()
```

Das Beispiel wurde gegen die öffentlichen Konstruktoren und Methoden im offiziellen g.Pype-4.1.0-Wheel geprüft. Kein Hardwarelauf durchgeführt. Es ersetzt weder unseren Sitzungsrecorder noch die bestehende Markersteuerung und speichert keine Aufnahme. `pipeline.start()` muss ohne Lizenz-/Authentifizierungsfehler durchlaufen; sichtbare Signalblöcke und die nach den ersten Blöcken verfügbare `oscar_delay_samples` dienen als erste Funktionsprüfung. Die Wirksamkeit der Korrektur ist damit noch nicht wissenschaftlich validiert.

Die tatsächliche Verzögerung nach dem Start auslesen; `K` ist nicht die Verzögerung. Der Hersteller nennt bei 250 Hz beispielhaft 83 Samples. Zusätzlich setzt g.Pype bei aktivem OSCAR seinen Event-Margin auf null. Ereignistiming muss deshalb neu geprüft werden.

Quellen: [HybridBlack](https://gpype.gtec.at/content/7_sdk_reference/backend_sources/hybrid_black.html), [öffentlicher Pipeline-Quelltext](https://gpype.gtec.at/_modules/gpype/backend/pipeline.html), [AmplifierSource-Quelltext](https://github.com/gtec-medical-engineering/gpype/blob/main/gpype/backend/sources/base/amplifier_source.py), [OSCAR-FAQ](https://gpype.gtec.at/content/5_faq/index.html).

## Bedeutung für unser Projekt

Der C++-Recorder besitzt in der mitgelieferten C-API keinen OSCAR-Schalter. Der oben beschriebene Live-Weg verwendet eine separate Python-Aufnahmequelle. Die implementierte C++-Anbindung an diesen Python-Aufnahmeweg ist in der Aufnahmeanleitung beschrieben.

Die Integration mit getrennter Roh-/OSCAR-Ausgabe und beiden Viewer-Einstiegspunkten ist vorhanden. Ihre Windows-/Headset-Abnahme gemäß Aufnahmeanleitung steht aus; dabei Kanalreihenfolge, Einheiten, Verzögerung und Ereignisse prüfen. Die Blinzelbedingung des bisherigen Protokolls 1.0 erfasst bewusst auch das Augensignal; ihre Auswertung darf nicht unbemerkt durch Artefaktkorrektur verändert werden. Im neuen [Zielprotokoll 2.0](experiment-protocol.md) ist Blinzeln keine Aufgabenklasse mehr.

Die alternative Hersteller-App Unicorn Recorder bietet ebenfalls OSCAR sowie LSL/UDP. Die Produktseite belegt jedoch nicht eindeutig, ob deren exportierter Stream jeweils die korrigierten Daten oder Rohdaten führt. Dies vor einer LSL-Integration praktisch prüfen: [Unicorn Suite](https://www.gtec.at/product/unicorn-suite/).

Die lokal ergänzte alte API unter `gtec_PythonAPI/Unicorn Python/` enthält Acquisition-Beispiele und Windows-DLLs, aber keine Implementierung des importierten `UnicornPy`-Moduls und keine dokumentierte OSCAR-Konfiguration. Diese Unvollständigkeit blockiert den aktuellen g.Pype-Weg nicht.
