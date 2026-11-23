"""Withdrawing an application: a checked draft, sent from the user's own mail program, then marked."""
from urllib.parse import unquote

from desktop.widgets.withdraw_dialog import WithdrawDialog, mailto_url, withdraw_draft


def test_draft_names_role_company_contact_and_sender():
    draft = withdraw_draft(case={"id": "c1", "contact_name": "Frau Helene Beispiel", "contact_email": "hb@example.org"},
                           company="Muster GmbH", position="Bürokraft", applicant_name="Kim Test")
    assert draft.subject == "Rücknahme der Bewerbung" and draft.requires_explicit_review and not draft.auto_send
    assert draft.body.startswith("Sehr geehrte Frau Beispiel,")
    assert "Bewerbung als Bürokraft bei Muster GmbH zurück" in draft.body and draft.body.rstrip().endswith("Kim Test")


def test_without_contact_the_greeting_stays_neutral():
    draft = withdraw_draft(case={}, company="Muster GmbH", position="Bürokraft", applicant_name="")
    assert draft.body.startswith("Guten Tag,")


def test_mailto_is_encoded_and_rejects_header_injection():
    url = mailto_url("hb@example.org", "Rücknahme & Co", "Zeile 1\nZeile 2")
    assert url.startswith("mailto:hb%40example.org?subject=") and "&body=" in url
    assert unquote(url.split("body=")[1]) == "Zeile 1\nZeile 2"
    assert mailto_url("a@example.org?cc=evil@example.com", "s", "b").startswith("mailto:?subject=")


def test_dialog_marks_only_after_handing_over(qtbot, monkeypatch):
    from desktop.widgets import withdraw_dialog

    dialog = WithdrawDialog(case={}, company="Muster GmbH", position="Bürokraft", applicant_name="Kim Test")
    qtbot.addWidget(dialog)
    assert not dialog.should_mark()
    opened = []
    monkeypatch.setattr(withdraw_dialog.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    dialog._open_mail()
    assert opened and opened[0].startswith("mailto:") and dialog.should_mark()


def test_page_withdraw_marks_the_application(tmp_path, qtbot, monkeypatch):
    from core.database import Database
    from core.lifecycle import ApplicationCase
    from core.models import ApplicationRecord, Job
    from desktop.pages.applications import ApplicationsPage
    from desktop.widgets import withdraw_dialog

    db = Database(tmp_path / "jobs.db")
    db.upsert_job(Job(id="j1", title="Bürokraft", company="Muster GmbH", url="https://example.org/1"))
    db.save_application(ApplicationRecord(job_id="j1", company="Muster GmbH", position="Bürokraft", status="applied"))
    case = db.upsert_case(ApplicationCase(id="c1", job_id="j1", company="Muster GmbH", position="Bürokraft"))

    class _Cfg:
        db_path = str(tmp_path / "jobs.db")
        settings = type("S", (), {"archive_after_days": 0, "language": "de"})()
        application = type("A", (), {"full_name": "Kim Test"})()

    monkeypatch.setattr(withdraw_dialog.WithdrawDialog, "exec", lambda self: 1)
    monkeypatch.setattr(withdraw_dialog.WithdrawDialog, "should_mark", lambda self: True)
    page = ApplicationsPage(type("Svc", (), {"load": lambda self: _Cfg()})())
    qtbot.addWidget(page)
    page.refresh()
    page.table.selectRow(0)
    page._open_detail()
    page._withdraw()
    assert db.list_applications()[0].result.startswith("Zurückgezogen am")
    assert any(e.event_type == "WITHDRAWN" for e in db.list_lifecycle_events(case.id))
