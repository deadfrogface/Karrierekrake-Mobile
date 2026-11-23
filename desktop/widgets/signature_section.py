"""Profile section: upload or remove the scanned signature used in the application folder PDF."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from desktop.i18n import tr
from desktop.services import signature


class SignatureSection(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("Muted")
        self.preview = QLabel()
        self.preview.setMinimumHeight(60)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.upload_btn = QPushButton()
        self.upload_btn.clicked.connect(self.upload)
        self.remove_btn = QPushButton()
        self.remove_btn.setObjectName("SecondaryButton")
        self.remove_btn.clicked.connect(self.remove)
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addWidget(self.preview)
        row = QHBoxLayout()
        row.addWidget(self.upload_btn)
        row.addWidget(self.remove_btn)
        row.addStretch()
        layout.addLayout(row)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setTitle(tr("signature.title"))
        self.hint.setText(tr("signature.hint"))
        self.upload_btn.setText(tr("signature.upload"))
        self.remove_btn.setText(tr("signature.remove"))
        self.reload()

    def reload(self) -> None:
        present = signature.has_signature()
        if present:
            pix = QPixmap(str(signature.signature_path()))
            self.preview.setPixmap(pix.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.clear()
            self.preview.setText(tr("signature.none"))
        self.remove_btn.setEnabled(present)

    def upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("signature.upload"), "", tr("signature.filter"))
        if not path:
            return
        try:
            signature.store_signature(path)
        except (ValueError, OSError):
            QMessageBox.warning(self, tr("signature.title"), tr("signature.unreadable"))
            return
        self.reload()

    def remove(self) -> None:
        signature.remove_signature()
        self.reload()
