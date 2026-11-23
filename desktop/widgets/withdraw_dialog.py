"""Withdraw an application: a checked draft the user sends from their own mail program (never sent by the app)."""
from __future__ import annotations

from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from desktop.i18n import tr
from desktop.widgets.confirm_dialog import label_button_box
from integrations.reply_draft import ReplyAction, build_action_draft


def withdraw_draft(*, case: dict, company: str, position: str, applicant_name: str):
    """Company and position come from the user's own application record; contact only from the stored case."""
    facts = {"id": case.get("id") or "withdraw", "company": company, "position": position,
             "contact_name": case.get("contact_name") or "", "contact_email": case.get("contact_email") or ""}
    return build_action_draft(ReplyAction.WITHDRAW, facts, applicant_name=applicant_name)


def mailto_url(to: str, subject: str, body: str) -> str:
    recipient = to if to and "@" in to and not any(c in to for c in "?&\r\n ") else ""
    return f"mailto:{quote(recipient)}?subject={quote(subject)}&body={quote(body)}"


class WithdrawDialog(QDialog):
    def __init__(self, *, case: dict, company: str, position: str, applicant_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("withdraw.title"))
        self.resize(620, 520)
        draft = withdraw_draft(case=case, company=company, position=position, applicant_name=applicant_name)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("withdraw.hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.to = QLineEdit(draft.to_address or (case.get("contact_email") or ""))
        self.to.setPlaceholderText(tr("withdraw.to_placeholder"))
        self.subject = QLineEdit(draft.subject)
        form.addRow(tr("withdraw.to"), self.to)
        form.addRow(tr("withdraw.subject"), self.subject)
        layout.addLayout(form)
        self.body = QPlainTextEdit(draft.body)
        layout.addWidget(self.body, 1)
        self.mark = QCheckBox(tr("withdraw.mark"))
        self.mark.setChecked(True)
        layout.addWidget(self.mark)
        buttons = label_button_box(QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel))
        self.copy_btn = QPushButton(tr("withdraw.copy"))
        self.copy_btn.clicked.connect(self._copy)
        buttons.addButton(self.copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self.mail_btn = buttons.addButton(tr("withdraw.open_mail"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._open_mail)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.handed_over = False

    def _copy(self) -> None:
        QApplication.clipboard().setText(f"{self.subject.text()}\n\n{self.body.toPlainText()}")
        self.handed_over = True
        self.copy_btn.setText(tr("withdraw.copied"))

    def _open_mail(self) -> None:
        if not QDesktopServices.openUrl(QUrl(mailto_url(self.to.text().strip(), self.subject.text(),
                                                        self.body.toPlainText()))):
            QMessageBox.warning(self, tr("withdraw.title"), tr("withdraw.no_mail_program"))
            return
        self.handed_over = True
        self.accept()

    def should_mark(self) -> bool:
        return self.handed_over and self.mark.isChecked()
