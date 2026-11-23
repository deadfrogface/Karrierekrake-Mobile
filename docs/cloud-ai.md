# ☁️ Cloud-Modelle mit eigenem API-Schlüssel

Karrierekrake liest Lebensläufe und schreibt Anschreiben **standardmäßig mit der lokalen KI**. Wer möchte, kann
dafür ein Cloud-Modell nutzen – mit dem **eigenen** API-Schlüssel des Anbieters. Abgerechnet wird direkt zwischen
Nutzer und Anbieter.

## Anbieter

| Anbieter | API-Adresse (fest) | Anbindung |
|---|---|---|
| Grok (xAI) | `https://api.x.ai/v1` | Chat-Completions-Format (OpenAI-kompatibel) |
| ChatGPT (OpenAI) | `https://api.openai.com/v1` | Chat-Completions |
| Claude (Anthropic) | `https://api.anthropic.com` | offizielles Anthropic-SDK (`anthropic`), bei unterstützten Modellen mit serverseitigem Ausweichmodell, falls eine Anfrage abgelehnt wird |
| Kimi (Moonshot AI) | `https://api.moonshot.ai/v1` | Chat-Completions-Format (OpenAI-kompatibel) |

Die Modellliste kommt live vom Anbieter („Verbindung testen“). So stehen keine veralteten Modellnamen im Programm.

## Einrichten

Einstellungen → Lokale KI → **KI-Anbieter wählen …**

1. Anbieter wählen und API-Schlüssel einfügen (Link zur Anbieter-Konsole steht im Dialog).
2. **Verbindung testen** – lädt die Modelle, die der Schlüssel nutzen darf.
3. Modell wählen und ankreuzen, wofür: *Lebenslauf einlesen*, *Anschreiben schreiben*.
4. Den Hinweis lesen, **was an wen** gesendet wird, und zustimmen. Erst dann wird gespeichert.

## Was gesendet wird

| Aufgabe | Daten an den Anbieter |
|---|---|
| Lebenslauf einlesen | Text des Lebenslaufs und die Anweisungen mit dem Antwortschema |
| Anschreiben schreiben | Name und bestätigte Profilangaben (Stationen, Aufgaben, Kenntnisse, Sprachen), ein geprüfter Grundentwurf, Stellenanzeige, Anweisungen |

Nicht gesendet werden die Datenbank, Mails, Kalender, Zugangsdaten oder die Datei des Lebenslaufs selbst.

## Sicherheit und Datenschutz

- **Aus, bis alles stimmt:** Ein Cloud-Modell wird nur benutzt, wenn Anbieter, Modell, Schlüssel, Aufgabe und
  Zustimmung (`CONSENT_VERSION`) vorliegen. Sonst arbeitet die lokale KI (`core/cloud_ai.py`, `active_settings`).
- **Feste Adressen:** Jede Anfrage geht an die feste HTTPS-Adresse des Anbieters; eine eigene Adresse lässt sich
  nicht eintragen.
- **Schlüssel:** nur im Schlüsselbund des Betriebssystems, nie in einer Datei, nie im Log, nie wieder angezeigt.
- **Prüfung bleibt lokal:** Die Abgleiche nach dem Modell (Import gegen das Dokument, Anschreiben gegen Profil und
  Anzeige, Streichen erfundener Angaben) laufen bei Cloud-Antworten genauso wie bei der lokalen KI.
- **Fehler sind klar:** Abgelehnter Schlüssel, aufgebrauchtes Guthaben, Pause wegen zu vieler Anfragen,
  Netzwerk oder unbekanntes Modell erscheinen als verständliche Meldung; es wird nichts heimlich lokal wiederholt.
- **Löschen:** „Nur lokal“ stoppt alle Anfragen; *Schlüssel löschen* entfernt den Schlüssel; *Alle Daten löschen*
  entfernt alle Anbieter-Schlüssel und die Auswahl.
- **Verzeichnisse:** Datenklasse `cloud_ai` in `core/privacy/inventory.py`, Hosts in
  `docs/privacy/NETWORK_TARGETS_PR144.json`.

## Vor dem Verkauf zu klären

Rolle der Anbieter als Empfänger und Übermittlung in Drittländer (Datenschutzhinweis, P32).
