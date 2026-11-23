# 📝 Feedback aus der Präsentation (22.11.2026)

Zwei Entwickler haben Karrierekrake gesehen. Unten jeder Punkt mit Einordnung, Aufwand und Reihenfolge.
Status: ✅ erledigt · 🔨 in Arbeit · 📋 geplant · 💬 Entscheidung nötig

| # | Wunsch | Was es schon gibt | Aufwand | Prio | Status |
|---|---|---|---|---|---|
| 1 | **Bewerbungsübersicht exportieren** (z. B. für Arbeitsamt/Jobcenter: Datum, Firma, Stelle, Status) | Bewerbungen → „Übersicht exportieren“: PDF (Jobcenter) oder CSV (Excel) | klein | ⭐⭐⭐ | ✅ |
| 2 | **Bewerbungen nach X Tagen als inaktiv archivieren** (Standard 14 Tage, einstellbar) | Automatisch nach 14 Tagen ohne Aktivität (Einstellungen → Kommunikation, 0 = nie); bei Antwort oder zugeordneter Mail automatisch zurück; „Archiv anzeigen“, „Wieder aktivieren“ | klein | ⭐⭐⭐ | ✅ |
| 3 | **Bewerbungen markieren (Stern)** und vor dem Absenden noch einmal prüfen | ☆/★ im Bewerbungsdetail, Filter „Nur markierte“; Vorschau vor dem Absenden existiert | klein | ⭐⭐⭐ | ✅ |
| 4 | **Einstellungen exportieren und importieren** | Einstellungen → Daten & Datenschutz → „Einstellungen und Profil exportieren/importieren“: Einstellungen, Profil, Skills, Stichwörter, Suchwünsche, Bewerberdaten (ohne Dateien, Konten, Pfade; Auto-Absenden nie importiert) | klein | ⭐⭐ | ✅ |
| 5 | **Deutlicher Hinweis: Was kann es, was nicht** (Rechner-Anforderung, lokales Modell schwächer als ChatGPT) | Roter Hinweis unter jeder Modellauswahl (Tempo hängt an der Grafikkarte, Qualität unter ChatGPT, Cloud = Daten an Firmen im Ausland); Willkommensseite und Über-Dialog: „Was Karrierekrake kann – und was nicht“ | klein | ⭐⭐⭐ | ✅ |
| 6 | **Snapshot der Stellenanzeige** – nachlesbar, auch wenn sie offline genommen wird | Beim Bewerben werden alle Angaben der Anzeige als Text gespeichert; zusätzlich wird die Anzeigenseite einmal im Hintergrund als Text gesichert (nicht LinkedIn). Bewerbungsdetail → „Stellenanzeige“ (auch als PDF) | klein–mittel | ⭐⭐⭐ | ✅ |
| 7 | **Teilzeit genau**: Stunden pro Woche, Tage, Spanne | Suche → Konditionen: Stunden pro Woche (von–bis) und Arbeitstage; Passung liest Wochenstunden und Wochenendarbeit aus der Anzeige | mittel | ⭐⭐ | ✅ |
| 8 | **Erweiterte Sucheinstellungen** | Suche → „Weitere Filter“ zusätzlich: Wunsch-Kenntnisse (Bonus), Wunsch-/Ausschluss-Branchen, Wunsch-/Ausschluss-Firmen, Anzeigenalter in Tagen | mittel | ⭐⭐ | ✅ |
| 9 | **Vorlagen**: Anschreiben als Vorlage speichern, aus eigenem Anschreiben eine Vorlage machen | Einstellungen → Allgemein → „Anschreiben-Vorlagen“: speichern, wählen, löschen, aus eigenem Anschreiben (Firma/Stelle/Name → Platzhalter) | mittel | ⭐⭐ | ✅ |
| 10 | **Unterschrift hochladen und einfügen** | Profil → Unterschrift (PNG/JPG, verkleinert, ohne Metadaten); erscheint unter der Grußformel in der Bewerbungsmappe | mittel | ⭐⭐ | ✅ |
| 11 | **Bewerbungsunterlagen exportieren und mitnehmen** (Mappe: Anschreiben + Lebenslauf) | Bewerbungsdetail → „Bewerbungsmappe (PDF)“: Anschreiben mit Briefkopf + Unterschrift, Lebenslauf, angehakte PDF-Unterlagen | mittel | ⭐⭐ | ✅ |
| 12 | **Absage-E-Mail schicken** (Bewerbung zurückziehen) | Bewerbungsdetail → „Bewerbung zurückziehen“: geprüfter Entwurf → eigenes Mailprogramm oder kopieren; danach als zurückgezogen markiert | mittel | ⭐ | ✅ |
| 13 | **LinkedIn-Profil importieren** (Skills, Keywords) → Profil → Anschreiben | Profil → „Von LinkedIn importieren“: offizieller Datenexport (ZIP) → Kenntnisse, Stationen, Ausbildung, Sprachen, Zertifikate, Stichwörter der Überschrift; Nachrichten/Kontakte werden nie gelesen | mittel | ⭐⭐ | ✅ |
| 14 | **Google Fonts / Material** (Idee, falls Icons fehlen) | – | – | – | 🗑️ verworfen |
| 15 | **Testabdeckung**: Was decken unsere Tests ab? | Analyse in `docs/project/TESTABDECKUNG.md` | klein | ⭐⭐ | ✅ |
| 16 | **Lizenzschlüssel gegen Raubkopien** | Gerätegebundene Lizenzschlüssel ohne Server (siehe unten) | mittel | ⭐⭐⭐ vor Verkauf | ✅ |
| 17 | **Benachrichtigung bei Antworten von Firmen** (Pop-up der App) | Desktop: Pop-up bei Einladung, Absage, Angebot, angeforderten Unterlagen oder zugeordneter Mail; im Infobereich eine Kurzmeldung; abschaltbar (Einstellungen → Kommunikation). Handy-App: eigenes Repo `Karrierekrake-Mobile` | mittel | ⭐⭐ | ✅ Desktop · 🔨 Handy |
| 18 | **Eigener Server mit KI** anbieten | Cloud-Modelle mit eigenem Schlüssel (#219) decken den Bedarf ohne eigenen Server | groß | ⭐ später | 💬 bewusst zurückgestellt (kein Server) |
| 19 | **Kopie vom Repo** | `python scripts/backup_repo.py <Ordner>`: komplette Sicherung (alle Branches + Historie) als geprüfte Datei; Wiederherstellen mit `git clone <Datei>` | klein | ⭐⭐ | ✅ |

## #16 Lizenzschlüssel ohne Server (umgesetzt)

1. **Einmalig:** `python scripts/issue_license_key.py keygen --out <sicherer Ort>/karrierekrake-signing.key`
   → Datei geheim halten und sichern (nie ins Repo); ausgegebene Key-ID + öffentlichen Schlüssel in
   `config/commercial_release.json` → `public_keys` eintragen.
2. **Pro Verkauf:** Käufer kopiert den **Gerätecode** (Einstellungen → Lizenz, `KK-XXXX-XXXX-XXXX-XXXX`) und schickt ihn.
   `python scripts/issue_license_key.py issue --private-key … --key-id … --device KK-… --license-id <Bestellnr.> --features ad_free,…`
   → Schlüssel `KKL1.…` an den Käufer; er fügt ihn unter „Lizenzschlüssel eingeben“ ein.
3. **Neuer Rechner:** gleiche `--license-id`, `--revision` +1, alte und neue Gerätecodes (max. 5).

Ein Schlüssel gilt nur auf den genannten Geräten, unbefristet oder bis `--expires`. Grenze ohne Server:
Sperren eines ausgegebenen Schlüssels ist nicht möglich, und wer den Programmcode verändert, kann jede Prüfung umgehen.

## Einordnung #18 (ohne eigenen Server)

- **#18 Eigener KI-Server:** zurückgestellt. Wer mehr Leistung will, nutzt die Cloud-Modelle mit eigenem Schlüssel.

## Reihenfolge

1. Schnelle, sichtbare Gewinne: 1, 2, 3, 5, 6, 4
2. Bewerbung komfortabler: 7, 9, 10, 11
3. Vor dem Verkauf: 16
4. Später / Entscheidung nötig: 13, 12, 8, 14, 15, 17, 18, 19
