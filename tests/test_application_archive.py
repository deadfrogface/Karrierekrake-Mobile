"""Applications without activity leave the active list after the configured days; history stays."""
from datetime import datetime, timedelta, timezone

from core.database import Database
from core.models import ApplicationRecord, Job

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def _db(tmp_path):
    db = Database(tmp_path / "jobs.db")
    db.upsert_job(Job(id="j1", title="Sachbearbeitung", company="Muster GmbH", url="https://example.org/1"))
    return db


def _app(db, days_ago, status="applied", job_id="j1"):
    when = (NOW - timedelta(days=days_ago)).replace(microsecond=0).isoformat()
    return db.save_application(ApplicationRecord(job_id=job_id, company="Muster GmbH", position="Sachbearbeitung",
                                                 application_date=when, status=status))


def test_old_quiet_applications_are_archived_and_others_stay(tmp_path):
    db = _db(tmp_path)
    old = _app(db, 20)
    fresh = _app(db, 3)
    waiting = _app(db, 30, status="needs_review")

    assert db.archive_inactive_applications(14, now=NOW) == 1
    active = {r.id for r in db.list_applications(archived=False)}
    assert active == {fresh, waiting}
    assert [r.id for r in db.list_applications(archived=True)] == [old]
    assert len(db.list_applications()) == 3  # export and statistics still see everything
    assert db.archive_inactive_applications(14, now=NOW) == 0  # idempotent


def test_zero_days_turns_it_off(tmp_path):
    db = _db(tmp_path)
    _app(db, 400)
    assert db.archive_inactive_applications(0, now=NOW) == 0
    assert db.list_applications(archived=True) == []


def test_recent_case_activity_keeps_it_active(tmp_path):
    db = _db(tmp_path)
    _app(db, 30)
    with db.connection() as conn:
        conn.execute("INSERT INTO application_cases (id, job_id, company, position) VALUES ('c1', 'j1', 'M', 'S')")
        conn.execute("INSERT INTO lifecycle_events (id, case_id, event_type, occurred_at, recorded_at) "
                     "VALUES ('e1', 'c1', 'INTERVIEW_SCHEDULED', ?, ?)",
                     ((NOW - timedelta(days=2)).isoformat(), NOW.isoformat()))
    assert db.archive_inactive_applications(14, now=NOW) == 0


def test_manual_archive_and_restore(tmp_path):
    db = _db(tmp_path)
    app_id = _app(db, 1)
    db.set_application_archived(app_id, True)
    assert db.list_applications(archived=False) == []
    db.set_application_archived(app_id, False)
    assert [r.id for r in db.list_applications(archived=False)] == [app_id]


def test_old_database_gets_the_column(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE applications (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, company TEXT, position TEXT,"
                     " application_date TEXT, platform TEXT, status TEXT, cv_used TEXT, cover_letter_used TEXT,"
                     " result TEXT, error_message TEXT)")
        conn.execute("INSERT INTO applications (id, job_id, status, application_date) VALUES ('a', '', 'applied', '2026-01-01')")
    db = Database(path)
    assert db.list_applications(archived=False)[0].archived_at == ""


def test_star_survives_and_filters(tmp_path):
    db = _db(tmp_path)
    starred = _app(db, 1)
    _app(db, 2)
    db.set_application_starred(starred, True)
    assert [r.id for r in db.list_applications(starred_only=True)] == [starred]
    assert db.list_applications(starred_only=True)[0].starred is True
    db.set_application_starred(starred, False)
    assert db.list_applications(starred_only=True) == []


def test_applications_page_star_and_archive_controls(tmp_path, qtbot):
    from desktop.pages.applications import ApplicationsPage

    db = _db(tmp_path)
    app_id = _app(db, 1)

    class _Cfg:
        db_path = str(tmp_path / "jobs.db")
        settings = type("S", (), {"archive_after_days": 14, "language": "de"})()

    service = type("Svc", (), {"load": lambda self: _Cfg()})()
    page = ApplicationsPage(service)
    qtbot.addWidget(page)
    page.refresh()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    page._open_detail()
    page._toggle_starred()
    assert page.table.item(0, 0).text().startswith("★ ")
    page.starred_only.setChecked(True)
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    page._open_detail()
    page._toggle_archived()
    assert page.table.rowCount() == 0  # archived and hidden
    page.show_archive.setChecked(True)
    assert page.table.rowCount() == 1 and "archiviert" in page.table.item(0, 1).text()
    assert db.list_applications(archived=True)[0].id == app_id


def _case(db, case_id="c1", job_id="j1"):
    from core.lifecycle import ApplicationCase
    return db.upsert_case(ApplicationCase(id=case_id, job_id=job_id, company="Muster GmbH", position="Sachbearbeitung"))


def test_a_reply_brings_the_application_back(tmp_path):
    from core.lifecycle import LifecycleEvent

    db = _db(tmp_path)
    app_id = _app(db, 30)
    case = _case(db)
    assert db.archive_inactive_applications(14, now=NOW) == 1
    db.append_lifecycle_event(LifecycleEvent(event_type="FOLLOWUP_SENT", case_id=case.id))
    assert db.list_applications(archived=False) == []  # own follow-up is not a reply
    db.append_lifecycle_event(LifecycleEvent(event_type="INTERVIEW_REQUESTED", case_id=case.id))
    assert [r.id for r in db.list_applications(archived=False)] == [app_id]


def test_a_linked_mail_brings_it_back_and_counts_as_activity(tmp_path):
    db = _db(tmp_path)
    app_id = _app(db, 30)
    case = _case(db)
    db.archive_inactive_applications(14, now=NOW)
    db.save_email_message({"gmail_id": "m1", "subject": "Ihre Bewerbung", "case_id": case.id,
                           "association_status": "linked", "received_at": NOW.isoformat()})
    assert [r.id for r in db.list_applications(archived=False)] == [app_id]
    assert db.archive_inactive_applications(14, now=NOW) == 0  # the recent mail keeps it active
