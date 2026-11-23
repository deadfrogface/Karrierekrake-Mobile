"""Honest expectations: what the app does, and where the local AI has limits (shown in setup and About)."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from desktop.i18n import tr


class CapabilitiesNotice(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.text = QLabel()
        self.text.setWordWrap(True)
        layout.addWidget(self.text)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.text.setText(capabilities_html())


def capabilities_html() -> str:
    def items(key: str) -> str:
        return "".join(f"<li>{line}</li>" for line in tr(key).split("\n") if line.strip())

    return (f"<b>{tr('caps.title')}</b>"
            f"<p style='margin:6px 0 2px'>✅ <b>{tr('caps.can_title')}</b></p><ul style='margin:0'>{items('caps.can')}</ul>"
            f"<p style='margin:6px 0 2px'>⚠️ <b>{tr('caps.limits_title')}</b></p><ul style='margin:0'>{items('caps.limits')}</ul>"
            f"<p style='margin:6px 0 0'>{tr('caps.tip')}</p>")
