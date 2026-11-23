"""Shows the job ad saved with an application; can save it as a PDF."""
from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout

from core.application_export import ad_snapshot_html
from desktop.i18n import i18n, tr
from desktop.widgets.confirm_dialog import label_button_box


class AdSnapshotDialog(QDialog):
    def __init__(self, snapshot: dict, parent=None) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self._german = not (i18n.language or "de").startswith("en")
        self.setWindowTitle(tr("apps.ad_title"))
        self.resize(760, 640)
        layout = QVBoxLayout(self)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)  # text only; nothing from the ad is opened or loaded
        self.view.setHtml(ad_snapshot_html(snapshot, german=self._german))
        layout.addWidget(self.view, 1)
        buttons = label_button_box(QDialogButtonBox(QDialogButtonBox.StandardButton.Close))
        self.pdf_btn = QPushButton(tr("apps.ad_save_pdf"))
        self.pdf_btn.setEnabled(bool(snapshot))
        self.pdf_btn.clicked.connect(self._save_pdf)
        buttons.addButton(self.pdf_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_pdf(self) -> None:
        from desktop.services.application_export import write_html_pdf

        company = "".join(c for c in str(self.snapshot.get("company") or "") if c.isalnum() or c in " -_").strip()
        suggested = f"Stellenanzeige_{company or 'Job'}_{date.today().isoformat()}.pdf".replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, tr("apps.ad_save_pdf"), suggested, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            write_html_pdf(ad_snapshot_html(self.snapshot, german=self._german), path, title=tr("apps.ad_title"))
        except OSError:
            QMessageBox.warning(self, tr("apps.ad_title"), tr("apps.export_failed"))
