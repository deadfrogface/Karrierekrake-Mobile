"""Pop-up when an employer answers: replies are found once, own steps never trigger it."""
from core.database import Database
from core.lifecycle import ApplicationCase, LifecycleEvent
from core.models import Job


def _db(tmp_path):
    db = Database(tmp_path / "jobs.db")
    db.upsert_job(Job(id="j1", title="Bürokraft", company="Muster GmbH", url="https://example.org/1"))
    db.upsert_case(ApplicationCase(id="c1", job_id="j1", company="Muster GmbH", position="Bürokraft"))
    return db


def test_replies_since_lists_employer_steps_and_mails_only(tmp_path):
    db = _db(tmp_path)
    db.append_lifecycle_event(LifecycleEvent(event_type="FOLLOWUP_SENT", case_id="c1"))
    db.append_lifecycle_event(LifecycleEvent(event_type="INTERVIEW_REQUESTED", case_id="c1"))
    db.save_email_message({"gmail_id": "m1", "subject": "Ihre Bewerbung", "case_id": "c1",
                           "association_status": "linked"})
    db.save_email_message({"gmail_id": "m2", "subject": "Newsletter", "association_status": "unlinked"})
    rows = db.employer_replies_since("2000-01-01T00:00:00+00:00")
    kinds = sorted((r["kind"], r["detail"]) for r in rows)
    assert kinds == [("event", "INTERVIEW_REQUESTED"), ("mail", "Ihre Bewerbung")]
    assert db.employer_replies_since("2999-01-01T00:00:00+00:00") == []


class _Service:
    def __init__(self, db_path, popups=True):
        self.meta = {}
        self.cfg = type("C", (), {"db_path": str(db_path),
                                  "settings": type("S", (), {"reply_popups": popups})()})()

    def load(self):
        return self.cfg

    def load_meta(self):
        return dict(self.meta)

    def save_meta(self, meta):
        self.meta = dict(meta)


def test_watcher_reports_each_reply_once(tmp_path, qtbot):
    from desktop.widgets.reply_notice import ReplyWatcher, describe

    db = _db(tmp_path)
    service = _Service(tmp_path / "jobs.db")
    watcher = ReplyWatcher(service)
    watcher.start()
    watcher.timer.stop()
    assert watcher.check() == []  # nothing new since the first start
    db.append_lifecycle_event(LifecycleEvent(event_type="OFFER_RECEIVED", case_id="c1"))
    found = []
    watcher.replies_found.connect(found.append)
    rows = watcher.check()
    assert len(rows) == 1 and describe(rows[0]).startswith("Muster GmbH – Angebot erhalten")
    assert found == [rows] and watcher.check() == []


def test_switched_off_means_no_popup(tmp_path, qtbot):
    from desktop.widgets.reply_notice import ReplyWatcher

    db = _db(tmp_path)
    service = _Service(tmp_path / "jobs.db", popups=False)
    service.meta["replies_seen_at"] = "2000-01-01T00:00:00+00:00"
    db.append_lifecycle_event(LifecycleEvent(event_type="REJECTION_RECEIVED", case_id="c1"))
    assert ReplyWatcher(service).check() == []


def test_dialog_lists_replies_and_opens_applications(qtbot):
    from desktop.widgets.reply_notice import ReplyNoticeDialog

    dialog = ReplyNoticeDialog([{"company": "Muster <GmbH>", "kind": "event", "detail": "REJECTION_RECEIVED"}])
    qtbot.addWidget(dialog)
    assert "Muster &lt;GmbH&gt; – Absage" in dialog.items.text()
    opened = []
    dialog.open_applications.connect(lambda: opened.append(True))
    dialog._open()
    assert opened == [True]
