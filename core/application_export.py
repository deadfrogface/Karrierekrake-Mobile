"""Overview of the user's applications for their own records or the employment agency.

Jobcenter and Agentur für Arbeit often ask for proof of one's own efforts ("Nachweis der Eigenbemühungen"):
date, employer, position, how and where one applied, and the outcome. This module turns the stored
applications into exactly that table. Nothing is sent anywhere; the user saves the file.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable

COLUMNS_DE = ("Datum", "Arbeitgeber", "Stelle", "Ort", "Beworben über", "Status", "Ergebnis / Notiz", "Link zur Anzeige")
COLUMNS_EN = ("Date", "Employer", "Position", "Location", "Applied via", "Status", "Result / note", "Link to the ad")

_SOURCES = {
    "bundesagentur": "Bundesagentur für Arbeit", "arbeitsagentur": "Bundesagentur für Arbeit",
    "indeed": "Indeed", "linkedin": "LinkedIn", "stepstone": "StepStone", "xing": "XING",
    "company_site": "Karriereseite des Arbeitgebers", "company_web": "Karriereseite des Arbeitgebers",
    "manual": "selbst eingetragen", "demo": "Demo",
}


@dataclass(frozen=True)
class ExportRow:
    applied_on: str  # ISO date YYYY-MM-DD, "" when unknown
    employer: str
    position: str
    location: str
    via: str
    status: str
    result: str
    url: str

    def cells(self, *, german: bool = True) -> list[str]:
        day = _display_date(self.applied_on, german=german)
        return [day, self.employer, self.position, self.location, self.via, self.status, self.result, self.url]


def _iso_day(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 and text[4] == "-" else ""


def _display_date(iso: str, *, german: bool) -> str:
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    return day.strftime("%d.%m.%Y") if german else iso


def source_label(source: str) -> str:
    key = (source or "").strip().lower()
    return _SOURCES.get(key, source or "")


def build_rows(db, *, status_label: Callable[[str], str] = lambda s: s,
               since: date | None = None, until: date | None = None) -> list[ExportRow]:
    """One row per stored application, oldest first, optionally limited to a date range (inclusive)."""
    rows: list[ExportRow] = []
    for record in db.list_applications(limit=100000):
        job = db.get_job(record.job_id) if record.job_id else None
        applied_on = _iso_day(record.application_date)
        if applied_on and (since or until):
            day = date.fromisoformat(applied_on)
            if (since and day < since) or (until and day > until):
                continue
        rows.append(ExportRow(
            applied_on=applied_on,
            employer=record.company or (job.company if job else ""),
            position=record.position or (job.title if job else ""),
            location=(job.city if job else "") or "",
            via=source_label(record.platform or (job.source if job else "")),
            status=status_label(record.status),
            result=(record.result or "").strip(),
            url=((job.application_url or job.url) if job else "") or "",
        ))
    rows.sort(key=lambda r: (r.applied_on or "9999", r.employer.lower()))
    return rows


def write_csv(rows: Iterable[ExportRow], path: Path, *, german: bool = True) -> Path:
    """CSV that opens correctly in Excel: UTF-8 with BOM, semicolons in German, commas in English."""
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";" if german else ",")
        writer.writerow(COLUMNS_DE if german else COLUMNS_EN)
        for row in rows:
            writer.writerow([_safe_cell(cell) for cell in row.cells(german=german)])
    return path


def _safe_cell(value: str) -> str:
    """Spreadsheets run a cell that starts with = + - @ as a formula; such text is shown as plain text."""
    text = str(value or "")
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def overview_html(rows: list[ExportRow], *, applicant: str, german: bool = True, today: date | None = None) -> str:
    """The same table as a printable page (the desktop app renders it to PDF)."""
    from html import escape

    today = today or date.today()
    title = "Nachweis der Eigenbemühungen – Bewerbungsübersicht" if german else "Overview of applications"
    stamp = (f"Erstellt am {today.strftime('%d.%m.%Y')} mit Karrierekrake · {len(rows)} Bewerbungen"
             if german else f"Created on {today.isoformat()} with Karrierekrake · {len(rows)} applications")
    columns = COLUMNS_DE if german else COLUMNS_EN
    head = "".join(f"<th>{escape(c)}</th>" for c in columns[:-1])
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row.cells(german=german)[:-1]) + "</tr>"
        for row in rows
    ) or f'<tr><td colspan="{len(columns) - 1}">{"Keine Bewerbungen." if german else "No applications."}</td></tr>'
    name = f"<p><b>{escape(applicant)}</b></p>" if applicant.strip() else ""
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:sans-serif;font-size:10pt;color:#1d2733}"
        "h1{font-size:14pt;color:#132238;margin:0 0 4pt}"
        "p{margin:2pt 0}.meta{color:#5b6b7b}"
        "table{border-collapse:collapse;width:100%;margin-top:8pt}"
        "th{background:#132238;color:#fff;text-align:left;padding:4pt}"
        "td{border-bottom:1px solid #dfe5ea;padding:4pt;vertical-align:top}"
        "</style></head><body>"
        f"<h1>{escape(title)}</h1>{name}<p class='meta'>{escape(stamp)}</p>"
        f"<table width='100%' cellpadding='5' cellspacing='0'><tr>{head}</tr>{body}</table></body></html>"
    )


def ad_snapshot_html(snapshot: dict, *, german: bool = True) -> str:
    """The saved job ad as a readable page. Plain text only: the ad's own markup is never rendered."""
    from html import escape

    if not snapshot:
        return "<p>" + ("Für diese Bewerbung ist keine Stellenanzeige gespeichert." if german
                        else "No job ad is saved for this application.") + "</p>"
    labels = (("location", "Ort", "Location"), ("address", "Adresse", "Address"), ("country", "Land", "Country"),
              ("work_model", "Arbeitsmodell", "Work model"), ("employment_type", "Arbeitszeit", "Working time"),
              ("salary", "Gehalt", "Salary"), ("published_at", "Veröffentlicht", "Published"),
              ("source", "Quelle", "Source"), ("url", "Link zur Anzeige", "Link to the ad"),
              ("application_url", "Bewerbungslink", "Application link"))
    facts = "".join(
        f"<tr><td><b>{escape(de if german else en)}</b></td><td>{escape(str(snapshot.get(key) or ''))}</td></tr>"
        for key, de, en in labels if snapshot.get(key)
    )
    saved = _display_date(_iso_day(str(snapshot.get("captured_at") or "")), german=german)
    note = (f"Gespeichert am {saved} – so stand die Anzeige, als du dich beworben hast." if german
            else f"Saved on {saved} – the ad as it was when you applied.")
    body = escape(str(snapshot.get("description") or "")).replace("\n", "<br>") or "–"
    page = str(snapshot.get("page_text") or "").strip()
    page_html = ""
    if page and page != str(snapshot.get("description") or "").strip():
        when = _display_date(_iso_day(str(snapshot.get("page_captured_at") or "")), german=german)
        heading = (f"Vollständige Anzeige von der Website (gespeichert am {when})" if german
                   else f"Full ad from the website (saved on {when})")
        page_html = f"<hr><h3>{escape(heading)}</h3><p>{escape(page).replace(chr(10), '<br>')}</p>"
    return (
        "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;font-size:10pt;color:#1d2733}"
        "h1{font-size:15pt;color:#132238;margin:0}h2{font-size:11pt;color:#5b6b7b;margin:2pt 0 8pt}"
        ".meta{color:#5b6b7b}td{padding:2pt 10pt 2pt 0;vertical-align:top}</style></head><body>"
        f"<h1>{escape(str(snapshot.get('title') or ''))}</h1><h2>{escape(str(snapshot.get('company') or ''))}</h2>"
        f"<p class='meta'>{escape(note)}</p><table>{facts}</table><hr><p>{body}</p>{page_html}</body></html>"
    )
