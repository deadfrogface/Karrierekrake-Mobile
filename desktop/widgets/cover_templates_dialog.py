"""Manage cover-letter templates: choose one, save the text as a template, or make one from an own letter."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from core import cover_templates as ct
from core.cover_letter import resolve_cover_letter_template
from desktop.i18n import i18n, tr
from desktop.widgets.confirm_dialog import label_button_box

_STANDARD = ""


class FromLetterDialog(QDialog):
    """Paste an own letter; company, position and name become placeholders."""

    def __init__(self, full_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("templates.from_letter"))
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("templates.from_letter_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.letter = QPlainTextEdit()
        layout.addWidget(self.letter, 1)
        form = QFormLayout()
        self.company = QLineEdit()
        self.position = QLineEdit()
        self.full_name = QLineEdit(full_name)
        form.addRow(tr("templates.company_in_letter"), self.company)
        form.addRow(tr("templates.position_in_letter"), self.position)
        form.addRow(tr("templates.name_in_letter"), self.full_name)
        layout.addLayout(form)
        buttons = label_button_box(QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_template(self) -> tuple[str, list[str]]:
        return ct.template_from_letter(self.letter.toPlainText(), company=self.company.text(),
                                       position=self.position.text(), full_name=self.full_name.text())


class CoverTemplatesDialog(QDialog):
    def __init__(self, config_service, parent=None) -> None:
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle(tr("templates.title"))
        self.resize(720, 640)
        layout = QVBoxLayout(self)
        intro = QLabel(tr("templates.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.choice = QComboBox()
        self.choice.currentIndexChanged.connect(self._show_selected)
        row.addWidget(self.choice, 1)
        self.delete_btn = QPushButton(tr("templates.delete"))
        self.delete_btn.setObjectName("SecondaryButton")
        self.delete_btn.clicked.connect(self._delete)
        row.addWidget(self.delete_btn)
        layout.addLayout(row)
        self.editor = QPlainTextEdit()
        layout.addWidget(self.editor, 1)
        self.placeholders = QLabel(tr("templates.placeholders") + " "
                                   + ct.placeholder_help(english=(i18n.language or "de").startswith("en")))
        self.placeholders.setWordWrap(True)
        self.placeholders.setObjectName("PageSubtitle")
        layout.addWidget(self.placeholders)
        save_row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("templates.name"))
        save_row.addWidget(self.name, 1)
        self.from_letter_btn = QPushButton(tr("templates.from_letter") + " …")
        self.from_letter_btn.setObjectName("SecondaryButton")
        self.from_letter_btn.clicked.connect(self._from_letter)
        save_row.addWidget(self.from_letter_btn)
        self.generate_btn = QPushButton(tr("templates.generate") + " …")
        self.generate_btn.setObjectName("SecondaryButton")
        self.generate_btn.clicked.connect(self._generate)
        save_row.addWidget(self.generate_btn)
        self.save_btn = QPushButton(tr("templates.save"))
        self.save_btn.setObjectName("SecondaryButton")
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        layout.addLayout(save_row)
        buttons = label_button_box(QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel))
        self.use_btn = buttons.addButton(tr("templates.use"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._use)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        current = self.config_service.load().settings.cover_letter_template
        self._reload(select=current if ct.is_user_template(current) else _STANDARD)

    def _reload(self, *, select: str) -> None:
        self.choice.blockSignals(True)
        self.choice.clear()
        self.choice.addItem(tr("templates.standard"), _STANDARD)
        for template in ct.list_templates():
            self.choice.addItem(template.name, str(template.path))
        index = max(0, self.choice.findData(select))
        self.choice.setCurrentIndex(index)
        self.choice.blockSignals(False)
        self._show_selected()

    def _show_selected(self) -> None:
        path = self.choice.currentData() or ""
        standard = not path
        if standard:
            cfg = self.config_service.load()
            cfg.settings.cover_letter_template = ct.DEFAULT_SETTING
            found = resolve_cover_letter_template(cfg)
            text = found.read_text(encoding="utf-8") if found else ""
        else:
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except OSError:
                text = ""
        self._shown_text = text.strip()
        self.editor.setPlainText(text)
        self.name.setText("" if standard else self.choice.currentText())
        self.delete_btn.setEnabled(not standard)

    def _from_letter(self) -> None:
        name = (self.config_service.load().application.full_name or "").strip()
        dialog = FromLetterDialog(name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        template, used = dialog.result_template()
        if not template.strip():
            return
        self.editor.setPlainText(template)
        if not self.name.text().strip() or not self.choice.currentData():
            self.name.setText(tr("templates.default_name"))
        if "company" not in used:
            QMessageBox.information(self, tr("templates.title"), tr("templates.company_not_found"))

    def _generate(self) -> None:
        english = (i18n.language or "de").startswith("en")
        keys = list(ct.STYLES)
        labels = [ct.STYLES[k]["en_label" if english else "de_label"] for k in keys]
        label, ok = QInputDialog.getItem(self, tr("templates.generate"), tr("templates.generate_prompt"), labels, 0, False)
        if not ok:
            return
        name, text = ct.generate_template(keys[labels.index(label)], english=english)
        self.editor.setPlainText(text)
        self.name.setText(name)

    def _save(self) -> str:
        try:
            path = ct.save_template(self.name.text(), self.editor.toPlainText())
        except ValueError as error:
            QMessageBox.warning(self, tr("templates.title"), tr(f"templates.error_{error}"))
            return ""
        except OSError:
            QMessageBox.warning(self, tr("templates.title"), tr("apps.export_failed"))
            return ""
        self._reload(select=str(path))
        return str(path)

    def _delete(self) -> None:
        path = self.choice.currentData() or ""
        if not path:
            return
        ct.delete_template(path)
        cfg = self.config_service.load()
        if cfg.settings.cover_letter_template == path:
            cfg.settings.cover_letter_template = ct.DEFAULT_SETTING
            self.config_service.save(cfg)
        self._reload(select=_STANDARD)

    def _use(self) -> None:
        path = self.choice.currentData() or ""
        if self.editor.toPlainText().strip() != self._shown_text:  # edited text is never lost
            if not path and not self.name.text().strip():
                self.name.setText(tr("templates.default_name"))
            path = self._save()
            if not path:
                return
        cfg = self.config_service.load()
        cfg.settings.cover_letter_template = path or ct.DEFAULT_SETTING
        self.config_service.save(cfg)
        self.accept()
