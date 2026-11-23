# 📚 Dokumentation

Der Einstieg in alle Dokumente von Karrierekrake. Oben steht, was heute gilt; unten der Projektverlauf.

## 🚀 Zuerst lesen

| | Dokument | Inhalt |
|---|---|---|
| 🏠 | [`../README.md`](../README.md) | Überblick, Installation, Messwerte |
| 🖥️ | [`desktop-platforms.md`](desktop-platforms.md) | Windows, macOS, Linux: Pakete, Datenordner, Grenzen |
| 🧠 | [`device-model-setup.md`](device-model-setup.md) | Wie der Assistent das passende KI-Modell wählt |
| ☁️ | [`cloud-ai.md`](cloud-ai.md) | Optionale Cloud-Modelle (Grok, ChatGPT, Claude, Kimi) mit eigenem Schlüssel |
| ⚡ | [`PERFORMANCE.md`](PERFORMANCE.md) | Gemessene Zeiten und Paketgrößen |

## 🏗️ Architektur und Produkt

| | Dokument | Inhalt |
|---|---|---|
| 🧭 | [`architecture/canonical-product-decisions.md`](architecture/canonical-product-decisions.md) | Verbindliche Produktentscheidungen |
| 🗺️ | [`architecture/local_first_google_calendar_and_geo.md`](architecture/local_first_google_calendar_and_geo.md) | Local-first: Kalender und Geodaten |
| 🔎 | [`search-intent.md`](search-intent.md), [`search-intent-filtering.md`](search-intent-filtering.md) | Suchwunsch und wie Stellen gefiltert werden |
| 🌍 | [`dach-cross-border.md`](dach-cross-border.md) | Suche über Grenzen in Deutschland, Österreich, Schweiz |
| 📬 | [`email-case-association.md`](email-case-association.md) | Wie Mails der richtigen Bewerbung zugeordnet werden |
| 📅 | [`calendar-scheduling.md`](calendar-scheduling.md) | Terminvorschläge und Kalender |
| 🔁 | [`post-application-lifecycle-final-report.md`](post-application-lifecycle-final-report.md) | Was nach dem Absenden passiert |
| 🎨 | [`desktop-design-system.md`](desktop-design-system.md) | Farben, Abstände, Komponenten |
| ♿ | [`accessibility/bfsg-engineering-report.md`](accessibility/bfsg-engineering-report.md) | Barrierefreiheit (BFSG) |
| 🧩 | [`adr/`](adr/) | Architekturentscheidungen |

## 🔒 Sicherheit

| | Dokument | Inhalt |
|---|---|---|
| ✅ | [`security/SECURITY_REVIEW_2026-11-19.md`](security/SECURITY_REVIEW_2026-11-19.md) | **Letzte Sicherheitsprüfung** und CI-Schranken |
| 📮 | [`../SECURITY.md`](../SECURITY.md) | Lücken melden, Reaktionszeiten, unterstützte Versionen |
| 🧱 | [`security/local-data-threat-model.md`](security/local-data-threat-model.md) | Bedrohungsmodell für lokale Daten |
| 🚧 | [`security/untrusted-content-boundaries.md`](security/untrusted-content-boundaries.md) | Grenzen für fremde Inhalte (Lebensläufe, Mails, Webseiten) |
| 📦 | [`security/runtime-sbom.md`](security/runtime-sbom.md) | Software-Stückliste |
| ⚠️ | [`security/dependency-exceptions.md`](security/dependency-exceptions.md) | Begründete Ausnahmen bei Abhängigkeiten |
| 🧾 | [`security/T06_VERIFICATION_AND_CRA_HANDOFF.md`](security/T06_VERIFICATION_AND_CRA_HANDOFF.md) | Nachweise für den Cyber Resilience Act |
| 🚨 | [`operations/SUPPORT_BACKUP_INCIDENT.md`](operations/SUPPORT_BACKUP_INCIDENT.md) | Support, Sicherung, Vorfallablauf |

Maschinenlesbare Audits (JSON) zu CPython, OpenSSL, llama.cpp, Qt und den nativen Bibliotheken liegen ebenfalls in [`security/`](security/).

## 🛡️ Datenschutz

| | Dokument | Inhalt |
|---|---|---|
| 🗂️ | [`privacy/data-inventory.md`](privacy/data-inventory.md) | Welche Daten wo liegen und wie lange |
| 📝 | [`privacy/DATENSCHUTZHINWEIS_ENTWURF.md`](privacy/DATENSCHUTZHINWEIS_ENTWURF.md) | Entwurf der Datenschutzhinweise |
| 🌐 | [`privacy/NETWORK_TARGETS_PR144.json`](privacy/NETWORK_TARGETS_PR144.json) | Jeder Host, den das Programm ansprechen darf |
| 🧠 | [`guenther-privacy.md`](guenther-privacy.md) | Datenschutz der lokalen KI |

## ⚖️ Recht und Vertrieb

| | Dokument | Inhalt |
|---|---|---|
| 📜 | [`legal/LIZENZENTSCHEIDUNGEN_PR144.md`](legal/LIZENZENTSCHEIDUNGEN_PR144.md) | Lizenzen der Komponenten, Wechsel zur eigenen Lizenz |
| 🏛️ | [`legal/EINSTUFUNG_CRA_BFSG_2026-11-13.md`](legal/EINSTUFUNG_CRA_BFSG_2026-11-13.md) | Einstufung nach CRA und BFSG |
| ✍️ | [`legal/RECHTSTEXTE_ENTWURF_2026-11-13.md`](legal/RECHTSTEXTE_ENTWURF_2026-11-13.md) | Entwürfe: Impressum, Nutzungsbedingungen, Widerruf |
| 💼 | [`commercial/README.md`](commercial/README.md) | Preise, Lizenzschlüssel, Zahlungsanbieter, Markt |

## 🧪 Qualität und Messungen

| | Dokument | Inhalt |
|---|---|---|
| 🚦 | [`review/MERGE_GATES.md`](review/MERGE_GATES.md) | Was vor einem Merge grün sein muss |
| 📄 | [`cv-corpus-acceptance.md`](cv-corpus-acceptance.md) | Lebenslauf-Korpus und Sollwerte |
| 🔁 | [`lifecycle-e2e-benchmark.md`](lifecycle-e2e-benchmark.md) | End-to-End-Benchmark der Bewerbungsabläufe |
| ✉️ | [`personaler/ABNAHME_CHECKLISTE.md`](personaler/ABNAHME_CHECKLISTE.md) | Abnahme der Anschreiben durch Personaler |
| 📊 | [`PERFORMANCE_AUDIT.md`](PERFORMANCE_AUDIT.md) | Start- und Importzeiten (Audit September) |
| 📦 | [`package-size-audit.md`](package-size-audit.md) | Paketgröße (älteres Audit) |

## 🗄️ Projektverlauf (Archiv)

Diese Dokumente halten fest, **wie** Entscheidungen entstanden sind: Messreihen, Modellvergleiche, Zwischenberichte.
Sie gelten nicht mehr als aktueller Stand, wo ein Dokument oben etwas anderes sagt.

| Ordner / Dateien | Inhalt |
|---|---|
| [`project/`](project/) | Arbeitsprotokolle, Zwischenberichte und Entscheidungsvorlagen |
| [`qa/`](qa/), [`beta/`](beta/) | Modellvergleiche, Demo- und Abnahmeprotokolle |
| `guenther-*.md` | Entwicklung der lokalen KI (Modellauswahl, Härtung, Schreibqualität) |
| `docpick`, `reuse-*`, `v1-*`, `pr19-*` | Frühere Import- und Release-Phasen |
| [`mobile/`](mobile/) | Konzept einer Begleit-App (nicht Teil des Desktop-Produkts) |
