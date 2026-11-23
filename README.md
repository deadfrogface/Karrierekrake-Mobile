# 📱 Karrierekrake Mobile (Android + iOS)

Kopie von [Karrierekrake](https://github.com/deadfrogface/Karrierekrake), umgebaut zur Handy-App mit
[BeeWare](https://beeware.org): **Briefcase** baut die App, **Toga** zeichnet echte Android- und iOS-Bedienelemente.
Die Python-Logik (`core/`, `search/`, `integrations/`, `guenther/`) ist dieselbe wie am Desktop.

## Was die App kann

| Reiter | Inhalt |
|---|---|
| 🏠 Start | Überblick über aktive und markierte Bewerbungen, kurze Anleitung |
| 🔎 Jobs | Suche bei der Bundesagentur für Arbeit, Passung im Klartext, geprüftes Anschreiben, „als beworben speichern“ |
| 📋 Bewerbungen | Liste mit Archiv und ★-Filter, gespeicherte Stellenanzeige, markieren, archivieren, zurückziehen per Mail, CSV-Übersicht |
| 👤 Profil | Kontakt, Wunschberufe, Kenntnisse, Sprachen; Import aus dem LinkedIn-Datenexport |
| ⚙️ Einstellungen | Cloud-KI mit eigenem Schlüssel, Pop-ups, Archiv-Frist, Einstellungen/Profil übertragen |

**Pop-up**, wenn eine Firma antwortet (Einladung, Absage, Angebot, angeforderte Unterlagen).

## KI auf dem Handy

Nur **Cloud-Modelle mit eigenem Schlüssel** (Grok, ChatGPT, Claude, Kimi). Die Prüfung auf erfundene Angaben läuft
immer auf dem Handy. Ohne Schlüssel funktioniert alles außer dem KI-Feinschliff; das geprüfte Anschreiben aus dem
Profil gibt es trotzdem. Der Schlüssel liegt im privaten App-Speicher, den andere Apps nicht lesen können.

## Entwickeln

```bash
python -m pip install briefcase
briefcase dev                                   # am Computer ausprobieren
briefcase create android && briefcase build android && briefcase run android
briefcase create iOS && briefcase build iOS && briefcase run iOS     # braucht einen Mac mit Xcode
```

Tests (ohne Handy, mit Togas Test-Backend):

```bash
python -m pip install "toga-core~=0.5.0" "toga-dummy~=0.5.0" pytest keyring httpx pyyaml python-dotenv pypdf beautifulsoup4
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests_mobile -c /dev/null --rootdir tests_mobile
```

## Build in GitHub Actions

Workflow **Mobile app**: Tests und Android-APK (Debug) bei jedem Push/PR; iOS-Simulator-Build nur von Hand
(„Run workflow“ → iOS anhaken), weil macOS-Runner etwa das Zehnfache kosten.

## Noch offen

- Signierte Release-Builds (Play Store / App Store): Entwicklerkonten und Signierschlüssel des Inhabers.
- Lebenslauf-Import auf dem Handy (PDF → Cloud-KI), Postfach-Anbindung für automatische Antworterkennung.
- Gerätetests auf echten Handys.

Die ursprüngliche Desktop-Dokumentation: [`docs/DESKTOP_README.md`](docs/DESKTOP_README.md).

Lizenz: proprietär, alle Rechte vorbehalten (siehe `LICENSE`).
