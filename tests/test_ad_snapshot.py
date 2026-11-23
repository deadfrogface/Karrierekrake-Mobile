"""The job ad is saved with the application and stays readable when the live ad changes or disappears."""
from core.application_export import ad_snapshot_html
from core.database import Database
from core.models import ApplicationRecord, Job


def _db(tmp_path, description="Wir suchen Unterstützung im Büro.\nVollzeit."):
    db = Database(tmp_path / "jobs.db")
    db.upsert_job(Job(id="j1", title="Bürokraft", company="Muster GmbH", city="Berlin", postal_code="10115",
                      description=description, url="https://example.org/ad"))
    return db


def test_snapshot_is_taken_when_the_application_is_saved(tmp_path):
    db = _db(tmp_path)
    app_id = db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH", position="Bürokraft"))
    db.upsert_job(Job(id="j1", title="Bürokraft", company="Muster GmbH", description="Anzeige geändert",
                      url="https://example.org/ad"))
    snap = db.application_ad_snapshot(app_id)
    assert snap["description"].startswith("Wir suchen") and snap["location"] == "10115, Berlin"
    assert snap["url"] == "https://example.org/ad" and snap["captured_at"]


def test_older_application_gets_a_snapshot_from_the_stored_job(tmp_path):
    db = _db(tmp_path)
    app_id = db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH", position="Bürokraft"))
    with db.connection() as conn:
        conn.execute("UPDATE applications SET ad_snapshot = '' WHERE id = ?", (app_id,))
    assert db.application_ad_snapshot(app_id)["title"] == "Bürokraft"
    assert db.list_applications()[0].ad_snapshot  # stored now


def test_unknown_application_and_missing_job(tmp_path):
    db = _db(tmp_path)
    assert db.application_ad_snapshot("nope") == {}
    assert "keine Stellenanzeige" in ad_snapshot_html({})


def test_ad_markup_is_shown_as_text_never_rendered(tmp_path):
    db = _db(tmp_path, description="<img src='https://tracker.example/x.png'><script>alert(1)</script>")
    app_id = db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH", position="Bürokraft"))
    html = ad_snapshot_html(db.application_ad_snapshot(app_id))
    assert "<img" not in html and "<script" not in html and "&lt;script&gt;" in html


def test_dialog_and_pdf(tmp_path, qtbot):
    from desktop.services.application_export import write_html_pdf
    from desktop.widgets.ad_snapshot_dialog import AdSnapshotDialog

    db = _db(tmp_path)
    snap = db.application_ad_snapshot(db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH")))
    dialog = AdSnapshotDialog(snap)
    qtbot.addWidget(dialog)
    assert "Wir suchen" in dialog.view.toPlainText() and dialog.pdf_btn.isEnabled()
    out = write_html_pdf(ad_snapshot_html(snap), tmp_path / "ad.pdf", title="Anzeige")
    assert out.read_bytes()[:4] == b"%PDF"


class _Resp:
    def __init__(self, body, url="https://jobs.example.org/ad/1", ctype="text/html; charset=utf-8"):
        self._body, self.url, self.headers = body, url, {"Content-Type": ctype}

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self._body


class _Session:
    def __init__(self, response):
        self.response, self.calls = response, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.response


PAGE = ("<html><body><nav>Menü Login</nav><main><h1>Bürokraft (m/w/d)</h1><p>Ihre Aufgaben: "
        + "Termine koordinieren, Post bearbeiten. " * 10 + "</p><script>track()</script></main>"
        "<footer>Impressum</footer></body></html>").encode()


def test_capture_reads_the_main_text_only():
    from search.job_detail import capture_ad_page

    text = capture_ad_page("https://jobs.example.org/ad/1", session=_Session(_Resp(PAGE)))
    assert text.startswith("Bürokraft (m/w/d)") and "Ihre Aufgaben" in text
    assert "Menü" not in text and "track()" not in text and "Impressum" not in text


def test_capture_refuses_unsafe_or_unsuitable_pages():
    from search.job_detail import MAX_PAGE_BYTES, capture_ad_page

    assert capture_ad_page("http://jobs.example.org/ad", session=_Session(_Resp(PAGE))) == ""
    assert capture_ad_page("https://www.linkedin.com/jobs/view/1", session=_Session(_Resp(PAGE))) == ""
    assert capture_ad_page("https://a.example.org/x", session=_Session(_Resp(PAGE, url="http://a.example.org/x"))) == ""
    assert capture_ad_page("https://a.example.org/x", session=_Session(_Resp(b"%PDF", ctype="application/pdf"))) == ""
    assert capture_ad_page("https://a.example.org/x", session=_Session(_Resp(b"x" * (MAX_PAGE_BYTES + 1)))) == ""


def test_page_text_is_stored_once_and_shown(tmp_path):
    db = _db(tmp_path)
    app_id = db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH", position="Bürokraft"))
    assert db.applications_without_ad_page() == [(app_id, "https://example.org/ad")]
    db.set_ad_page_text(app_id, "Vollständiger Anzeigentext " * 20)
    assert db.applications_without_ad_page() == []
    html = ad_snapshot_html(db.application_ad_snapshot(app_id))
    assert "Vollständige Anzeige von der Website" in html and "Vollständiger Anzeigentext" in html


def test_snapshot_has_every_field(tmp_path):
    db = Database(tmp_path / "jobs.db")
    db.upsert_job(Job(id="j2", title="Bürokraft", company="Muster GmbH", city="Berlin", address="Musterweg 1",
                      remote_type="hybrid", employment_type="Teilzeit", salary_min=30000, salary_max=36000,
                      url="https://example.org/ad", application_url="https://example.org/apply", description="x"))
    snap = db.application_ad_snapshot(db.save_application(ApplicationRecord(job_id="j2", company="Muster GmbH")))
    assert snap["work_model"] == "Hybrid" and snap["salary"] == "30.000 € – 36.000 €"
    assert snap["application_url"] == "https://example.org/apply" and snap["address"] == "Musterweg 1"
