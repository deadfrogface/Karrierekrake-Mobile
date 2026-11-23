"""Pop-up when an employer answers: invitation, rejection, offer, requested documents or a linked mail.

Checks the local database every minute (mail sync and the case timeline write there). Nothing is fetched for
this. The window shows a pop-up; when the app sits in the tray, the tray shows a short message instead.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from core.database import Database
from core.models import utc_now_iso
from desktop.i18n import de_en, tr
from desktop.widgets.confirm_dialog import label_button_box

_EVENT_TEXT = {
    "APPLICATION_RECEIVED": ("Eingangsbestätigung", "Confirmation of receipt"),
    "UNDER_REVIEW": ("Bewerbung wird geprüft", "Application under review"),
    "DOCUMENT_REQUESTED": ("Unterlagen angefordert", "Documents requested"),
    "ASSESSMENT_RECEIVED": ("Test oder Aufgabe erhalten", "Assessment received"),
    "INTERVIEW_REQUESTED": ("Einladung zum Gespräch", "Interview invitation"),
    "INTERVIEW_SCHEDULED": ("Gesprächstermin steht", "Interview scheduled"),
    "INTERVIEW_RESCHEDULED": ("Termin verschoben", "Interview rescheduled"),
    "INTERVIEW_CANCELLED": ("Termin abgesagt", "Interview cancelled"),
    "INTERVIEW_COMPLETED": ("Gespräch abgeschlossen", "Interview completed"),
    "OFFER_RECEIVED": ("Angebot erhalten 🎉", "Offer received 🎉"),
    "REJECTION_RECEIVED": ("Absage", "Rejection"),
}
SEEN_KEY = "replies_seen_at"
SEEN_IDS_KEY = "replies_seen_ids"


def describe(row: dict) -> str:
    who = row.get("company") or de_en("Eine Firma", "A company")
    if row.get("kind") == "mail":
        what = de_en("Neue Mail", "New mail") + (f": {row['detail']}" if row.get("detail") else "")
    else:
        what = de_en(*_EVENT_TEXT.get(str(row.get("detail")), ("Neue Antwort", "New reply")))
    return f"{who} – {what}"


class ReplyNoticeDialog(QDialog):
    open_applications = Signal()

    def __init__(self, rows: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("replies.title"))
        layout = QVBoxLayout(self)
        intro = QLabel(tr("replies.intro", n=str(len(rows))))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.items = QLabel("<ul>" + "".join(f"<li>{escape(describe(r))}</li>" for r in rows[:8]) + "</ul>")
        self.items.setWordWrap(True)
        layout.addWidget(self.items)
        buttons = label_button_box(QDialogButtonBox(QDialogButtonBox.StandardButton.Close))
        self.open_btn = buttons.addButton(tr("replies.open"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._open)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open(self) -> None:
        self.open_applications.emit()
        self.accept()


class ReplyWatcher(QObject):
    """Finds new employer replies and shows them once."""

    replies_found = Signal(list)
    INTERVAL_MS = 60_000

    def __init__(self, config_service, parent=None) -> None:
        super().__init__(parent)
        self.config_service = config_service
        self.timer = QTimer(self)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.check)

    def start(self) -> None:
        meta = self.config_service.load_meta()
        if not meta.get(SEEN_KEY):  # first start: only replies from now on
            meta[SEEN_KEY] = utc_now_iso()
            self.config_service.save_meta(meta)
        self.timer.start()
        QTimer.singleShot(5000, self.check)

    def check(self) -> list[dict]:
        cfg = self.config_service.load()
        if not getattr(cfg.settings, "reply_popups", True):
            return []
        meta = self.config_service.load_meta()
        since = str(meta.get(SEEN_KEY) or utc_now_iso())
        seen = list(meta.get(SEEN_IDS_KEY) or [])
        try:
            rows = Database(cfg.db_path).employer_replies_since(since)
        except Exception:  # noqa: BLE001 - a busy or missing database is checked again next minute
            return []
        rows = [r for r in rows if f"{r['kind']}:{r['id']}" not in seen]
        if rows:
            meta[SEEN_KEY] = max(str(r.get("at") or since) for r in rows)
            meta[SEEN_IDS_KEY] = (seen + [f"{r['kind']}:{r['id']}" for r in rows])[-200:]
            self.config_service.save_meta(meta)
            self.replies_found.emit(rows)
        return rows
