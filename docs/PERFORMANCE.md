# ⚡ Geschwindigkeit und Größe

Stand: 19.11.2026 (PR #216). Alle Zahlen sind gemessen. Die Quelle steht bei jeder Zahl.

## 🖥️ Gepacktes Programm in der CI

Gemessen wird das **fertig gebaute Windows-Programm**, nicht der Quellcode.
Quelle ist der Abnahmeschritt „Offline CV import + cover letter acceptance“ in `windows-smoke.yml`
(`scripts/ci_cv_import_exe_offline_e2e.py`), Lauf vom 16.11.2026.

**Rechner:** GitHub-Runner `windows-latest`, 4 logische und **2 physische Kerne**, AVX2. Modell: Qwen3.5-4B Q4_K_M.

| Schritt | Gesamt | Prompt lesen | Schreiben | Rest (Laden, Prüfen) |
|---|---:|---:|---:|---:|
| 🚀 Start bis bereit | 6,8 s | – | – | – |
| 📄 Lebenslauf DE, erster Import | 109,5 s | 69,0 s (1.905 Token, 27,6 Token/s) | 32,7 s (332 Token, 10,2 Token/s) | 7,9 s |
| 📄 Lebenslauf EN, Folge-Import | 46,2 s | 14,8 s (369 Token) | 24,0 s (254 Token) | 7,4 s |
| 🔁 Neustart mit Profil | 3,8 s | – | – | – |
| ✍️ Anschreiben | 90,5 s | 36,3 s (1.024 Token) | 25,9 s (277 Token) | 28,2 s |

**Zweite Messung, 22.11.2026 (schwächste Maschine):** Seit das Repository privat ist, stellt GitHub für
Windows nur noch einen Runner mit **2 logischen und 1 physischen Kern**. Dieselbe Arbeit (gleiche Tokenzahlen) dauert
dort: Start 6,2 s, Import DE 400 s, Import EN 170 s, Anschreiben 325 s. Lesen 7,9 statt 27,6 Token/s, Schreiben
2,4 statt 10,2 Token/s. Das ist eine Untergrenze; ein Laptop mit 4 oder mehr Kernen liegt deutlich darüber.
Das Anschreiben brauchte dabei **genau einen** Modellaufruf (`llm_totals`: 1 Aufruf, Laden 3,8 s): Der „Rest“ von
28 s am 16.11. war also kein zweiter Aufruf, sondern Laden und Prüfen außerhalb des Modells.

**Was man daran sieht:**

- **Prompt-Cache:** Beim Folge-Import liest das Modell nur 369 statt rund 1.900 Token. Die festen Anweisungen
  kommen als gespeicherter Modellzustand von der Platte (`core/llm_prompt_cache.py`).
- **Lesen ist teurer als Schreiben:** Auf 2 Kernen kostet das Lesen des Prompts mehr Zeit als die Antwort.
  Deshalb bekommt das Anschreiben jeden Fakt nur noch einmal (−17 bis −26 % Prompt).
- **„Rest“ beim Anschreiben:** Die Abnahme schreibt jeden Modellaufruf mit (`llm_totals`: Anzahl, Laden, Lesen,
  Schreiben). Ergebnis: ein einziger Aufruf; der Rest ist Laden des Modells und die Prüfung des Briefs.

## 💻 Optimierungen, gemessen auf dem Entwicklungsrechner

Jeweils dieselben Daten vorher und nachher, gleicher Build bis auf die Änderung.

| Änderung | Vorher | Nachher | Commit |
|---|---:|---:|---|
| Hauptfenster ohne holidays, requests, KI-Dienst, pydantic beim Start | 2,9 s | ≈ 1,3 s | `4116458f`, `83eb7d24` |
| Extraktionsantwort einzeilig (4B, 12 Lebensläufe) | 999 s | 815 s | `93e2435a` |
| Extraktionsantwort einzeilig (8B, 6 Lebensläufe) | 885 s | 762 s | `93e2435a` |
| JSON-Gerüst gebündelt (8B, ein Lebenslauf) | 189 s | 169 s | `32bd5c97` |
| Anschreiben endet mit dem Brieftext (4B) | 127 s | 91 s | `5ab1fe76` |
| Anschreiben im ersten Anlauf (4B) | 231–289 s, ohne Brief | 127 s, mit Brief | `4110af91` |
| Jeder Fakt nur einmal im Anschreiben-Prompt | 629 / 988 Token | 463 / 816 Token | `9659d801` |
| Postleitzahl-Tabellen laden (5 Länder) | 440 ms | 280 ms | `4116458f` |

## 📦 Paketgröße

| Paket | Vorher | Nachher | Wie |
|---|---:|---:|---|
| Windows-Setup | 145 MB | 96 MB | stärkste LZMA2-Stufe (`5c7f538d`) |
| Windows-Programmordner | 402 MB | 290 MB | ungenutzte Qt-Teile, doppelte llama-Bibliotheken, numpy-Teile, Pillow-AVIF, Kommandozeilen-Werkzeuge entfernt |
| Linux-Programmordner | – | −40,6 MB | Qt Quick/QML/PDF, doppelte llama-Bibliotheken (`efb7dcf5`) |
| Laufzeit ohne pandas/pgeocode | – | −17 MB | eigene Postleitzahl-Suche (`f9f3fa35`) |

Seit dem 19.11. schreibt jeder Paket-Lauf `package-size.json` mit den 40 größten Ordnern und Dateien
(`scripts/package_size_report.py`) und gibt sie im Job-Log aus.

**Windows-Programmordner in der CI (22.11.2026): 283,6 MiB** in 1.845 Dateien; davon Playwright 102,7 MiB (36 %),
PySide6 45,3 MiB, numpy.libs 20,2 MiB.

### Wohin der Platz geht (Linux-Paket, CI-Lauf vom 22.11.2026)

**439 MiB** in 1.311 Dateien, unkomprimiert (das `.tar.gz` ist rund die Hälfte).

| Ordner | Größe | Anteil | Bemerkung |
|---|---:|---:|---|
| `playwright` | 134,2 MiB | 31 % | Browser-Automatisierung (Treiber); **größter Hebel** |
| `PySide6` | 91,3 MiB | 21 % | Qt-Oberfläche, bereits um Quick/QML/PDF gekürzt |
| `_internal` (Einzeldateien) | 51,6 MiB | 12 % | u. a. llama.cpp-Bibliotheken, Python-Archiv |
| `numpy.libs` + `numpy` | 36,7 MiB | 8 % | OpenBLAS; nur llama-cpp-python braucht numpy |
| `python3.12` | 15,2 MiB | 3 % | Standardbibliothek |
| `primp` | 14,7 MiB | 3 % | HTTP-Client der Websuche |
| `cryptography` | 13,8 MiB | 3 % | TLS, Token-Verschlüsselung |
| Rest | 81,5 MiB | 19 % | rapidfuzz, lxml, pypdfium2, Pillow, … |

**Nächster Schritt:** Den Playwright-Treiber erst bei der ersten Browser-Automatisierung herunterladen, so wie
Chromium schon heute. Das würde das Paket um knapp ein Drittel verkleinern.

## 🔁 Selbst nachmessen

| Was | Befehl |
|---|---|
| Paketgröße | `python scripts/package_size_report.py --package dist/Karrierekrake` |
| Import und Anschreiben im Paket | `python scripts/ci_cv_import_exe_offline_e2e.py --help` |
| Start und Importzeiten (älteres Audit) | [`PERFORMANCE_AUDIT.md`](PERFORMANCE_AUDIT.md) |
