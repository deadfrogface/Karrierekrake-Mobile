"""Application overview for one's own records or the employment agency (CSV and PDF)."""
import csv
from datetime import date

from core.application_export import ExportRow, build_rows, overview_html, write_csv
from core.database import Database
from core.models import ApplicationRecord
from desktop.demo_data import seed_demo_database


def _db(tmp_path):
    path = tmp_path / "jobs.db"
    seed_demo_database(path)
    return Database(path)


def test_rows_come_from_the_stored_applications_with_job_details(tmp_path):
    rows = build_rows(_db(tmp_path))
    assert {r.employer for r in rows} == {"Spree Klinikverbund", "Kiefer Digital UG"}
    klinik = next(r for r in rows if r.employer == "Spree Klinikverbund")
    assert klinik.position == "Empfangs- und Büromanagement"
    assert klinik.location == "Berlin" and klinik.via == "Indeed"
    assert klinik.url.startswith("https://example.com/")
    assert klinik.applied_on == date.today().isoformat()


def test_csv_opens_in_german_excel(tmp_path):
    out = write_csv(build_rows(_db(tmp_path)), tmp_path / "x.csv")
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM: Excel reads umlauts correctly
    lines = list(csv.reader(out.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    assert lines[0][:3] == ["Datum", "Arbeitgeber", "Stelle"]
    assert len(lines) == 3
    assert lines[1][0].count(".") == 2  # 22.11.2026


def test_cells_that_look_like_formulas_stay_text(tmp_path):
    row = ExportRow("2026-11-01", "=HYPERLINK(\"http://evil\")", "+Chef", "-", "@x", "Beworben", "", "")
    out = write_csv([row], tmp_path / "f.csv")
    data = list(csv.reader(out.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))[1]
    assert data[1].startswith("'=") and data[2] == "'+Chef" and data[3] == "'-" and data[4] == "'@x"


def test_date_range_filter(tmp_path):
    db = _db(tmp_path)
    db.save_application(ApplicationRecord(id="old", job_id="demo-1", company="Alt GmbH", position="Assistenz",
                                          application_date="2025-01-10T09:00:00+00:00", status="applied"))
    rows = build_rows(db, since=date(2025, 1, 1), until=date(2025, 1, 31))
    assert [r.employer for r in rows] == ["Alt GmbH"]


def test_printable_page_escapes_text_and_names_the_applicant():
    rows = [ExportRow("2026-11-01", "<b>Firma</b>", "Stelle", "Ort", "Indeed", "Beworben", "", "")]
    page = overview_html(rows, applicant="Alex Muster", today=date(2026, 11, 22))
    assert "&lt;b&gt;Firma&lt;/b&gt;" in page and "<b>Firma</b>" not in page
    assert "Alex Muster" in page and "22.11.2026" in page and "Nachweis der Eigenbemühungen" in page


def test_pdf_and_csv_files_are_written(tmp_path, qapp):
    from desktop.services.application_export import export_overview

    db = _db(tmp_path)
    assert export_overview(db, tmp_path / "u.pdf", applicant="Alex Muster") == 2
    assert (tmp_path / "u.pdf").read_bytes().startswith(b"%PDF")
    assert export_overview(db, tmp_path / "u.csv") == 2
