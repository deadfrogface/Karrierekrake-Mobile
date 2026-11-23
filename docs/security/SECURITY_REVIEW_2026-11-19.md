# 🔐 Sicherheitsprüfung 19.11.2026

Geprüfter Stand: Branch `cursor/lean-fast-commercial-d85b` (PR #216) gegen `main`.

## ✅ Ergebnis auf einen Blick

| Prüfung | Werkzeug | Ergebnis |
|---|---|---|
| Manuelle Prüfung der Änderungen aus PR #216 | Code-Review (Sicherheitsfokus) | **keine Befunde** (hoch/mittel) |
| Statische Codeanalyse | Bandit, alle Ordner mit Programmcode | **0 Befunde ab „mittel“** (vorher 42, davon 1 echter, jetzt behoben) |
| Abhängigkeiten mit bekannten Lücken | pip-audit, OSV-Scanner | ✅ keine offenen; 2 dokumentierte Ausnahmen (siehe unten) |
| Geheimnisse im Repo | Gitleaks | ✅ keine |
| Personenbezogene Daten im Repo | `scripts/privacy_scan.py` | ✅ keine |
| Sicherheitstests (Injection, beschädigte Dateien) | pytest | ✅ grün |

Alle automatischen Prüfungen laufen bei jedem Push im CI-Job **`security`** (`.github/workflows/ci.yml`).
Seit dieser Prüfung bricht die CI schon bei einem **mittleren** Bandit-Befund ab (vorher nur bei hohen).

## 🛠️ Behoben

### Modell aus einem gemeinsamen Temp-Ordner (mittel)

`core/cv_llm_runtime.py` suchte das KI-Modell zuletzt auch unter `/tmp/karrierekrake-models` und
`/var/tmp/karrierekrake-models`. Auf Linux und macOS kann dort **jedes andere Konto** des Rechners eine
präparierte Modelldatei ablegen, die das Programm dann geladen hätte (Angriffsfläche: GGUF-Parser in llama.cpp).

- **Jetzt:** Es werden nur noch Ordner des angemeldeten Nutzers durchsucht.
- **Test:** `tests/test_model_lookup_no_shared_temp.py` (scheitert am alten Code).

### URLs nur noch als Web-Adressen (Härtung)

`urllib.request.urlopen` öffnet auch `file:`-, `ftp:`- und `data:`-URLs. Alle Aufrufe im Programm laufen jetzt über
`core/security/url_open.py`, das vor dem Verbindungsaufbau nur `https` zulässt
(`http` nur dort, wo ein lokaler Dienst angesprochen wird: Ollama, BRouter).

- Betroffen: Geodaten-Download, BRouter, Modell-Download, Ollama, Microsoft-OAuth, Verbindungstest.
- **Test:** `tests/test_url_open.py`.

## 📋 Geprüfte und begründete Bandit-Hinweise

Jeder akzeptierte Hinweis steht mit Begründung direkt an der Codezeile (`# nosec <Regel>  # <Grund>`).
So fällt jeder **neue** Befund sofort auf.

| Regel | Wo | Warum unbedenklich |
|---|---|---|
| B506 `yaml.load` | `core/config.py` | Lädt mit `SafeLoader` (C-Variante, wenn vorhanden) |
| B608 SQL-String | `core/database.py`, `core/privacy/lifecycle.py` | Nur feste Tabellen-/Spaltennamen oder `?`-Platzhalter; alle Werte als Parameter |
| B310 `urlopen` | Google-OAuth-Widerruf, Firmen-Jobseiten | Feste HTTPS-Endpunkte |
| B310/B108/B302/B314/B615 | `scripts/` | Build-, CI- und Messskripte; feste HTTPS-Quellen mit SHA-256-Prüfung, eigene CI-Dateien, lokale Entwickler-Pfade. Nicht Teil des ausgelieferten Programms |

## ⚠️ Bekannte, dokumentierte Ausnahmen

Details und Begründung: [`dependency-exceptions.md`](dependency-exceptions.md).

| Kennung | Paket | Einordnung |
|---|---|---|
| PYSEC-2026-2447 | diskcache 5.6.3 (über llama-cpp-python) | Kein Upstream-Fix. Pickle-Zugriff wird vor jedem LLM-Import abgeschaltet (`core/security/diskcache_guard.py`, getestet). |
| PYSEC-2026-1604 | markdownify 0.13 (über python-jobspy) | Niedrig (lokaler DoS); Fix durch Pin von jobspy blockiert. |

## 🔎 Was manuell geprüft wurde (PR #216)

| Bereich | Befund |
|---|---|
| Prompt-Cache (`core/llm_prompt_cache.py`) | Dateinamen aus eigenem Modellordner + Hash; Löschen nur `*.state` im festen Cache-Ordner, ohne Rekursion; Symlinks werden nur als Link entfernt |
| Modellwechsel (`guenther/setup_models.py`, `model_manager.py`) | Zu löschende Ordner aus festem Katalog; Symlinks werden übersprungen; unter Modell-Sperre |
| Postleitzahlen (`core/geo_postal_index.py`) | Nur mitgelieferte CSV, kein Netz, keine Deserialisierung |
| Updates (`core/app_updates.py`) | Nur späterer Import; TLS- und Hash-/Manifestprüfung unverändert |
| Suchprofil ohne pydantic (`core/search_intent.py`) | Weiter strikt: unbekannte Felder abgelehnt, Enums geprüft |
| Termin-Erkennung aus Mails (`integrations/proposal_parse.py`) | Nur Regex und Datumsrechnung; bei Mehrdeutigkeit Abbruch |
| LLM-Ausgabe (`cover_guard`, `cover_quality`, `llm_lookahead`, `llm_fast_json`) | Nur Textvergleiche; native Puffer vom Modell bemessen; Grammatik konstant |
| Logs | Nur Zähler und Modell-IDs, keine personenbezogenen Daten |

## 📚 Weiterführend

- Meldeweg für Lücken: [`SECURITY.md`](../../SECURITY.md)
- Bedrohungsmodell lokale Daten: [`local-data-threat-model.md`](local-data-threat-model.md)
- Grenzen für nicht vertrauenswürdige Inhalte: [`untrusted-content-boundaries.md`](untrusted-content-boundaries.md)
- Software-Stückliste: [`runtime-sbom.md`](runtime-sbom.md)
