"""Choose a cloud model (Grok, ChatGPT, Claude, Kimi) with the user's own API key – or stay local.

The local model stays the default. Nothing is sent until a provider, a model and a task are chosen,
a key is stored and the user has confirmed which data goes to that provider.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import cloud_ai
from desktop.i18n import tr
from desktop.widgets.confirm_dialog import label_button_box
from desktop.widgets.dialog_geometry import fit_dialog_to_screen, wrap_dialog_body


def cloud_ai_summary() -> str:
    """One line for the settings page: which model reads CVs and writes letters."""
    settings = cloud_ai.load_settings()
    if not settings.provider or settings.consent_version < cloud_ai.CONSENT_VERSION:
        return tr("cloud_ai.summary_local")
    tasks = [tr(key) for key, on in (("cloud_ai.task_import", settings.use_for_import),
                                      ("cloud_ai.task_cover", settings.use_for_cover)) if on]
    if not tasks:
        return tr("cloud_ai.summary_local")
    return tr("cloud_ai.summary_cloud", provider=cloud_ai.PROVIDERS[settings.provider].label,
              model=settings.model, tasks=", ".join(tasks))


class CloudAiDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CloudAiDialog")
        self.setWindowTitle(tr("cloud_ai.title"))
        self._settings = cloud_ai.load_settings()
        self._worker = None
        self._thread = None

        body = QWidget()
        layout = QVBoxLayout(body)
        intro = QLabel(tr("cloud_ai.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItem(tr("cloud_ai.provider_local"), "")
        for provider in cloud_ai.PROVIDERS.values():
            self.provider.addItem(provider.label, provider.id)
        form.addRow(tr("cloud_ai.provider"), self.provider)

        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(tr("cloud_ai.key_placeholder"))
        self.key_state = QLabel()
        self.key_state.setObjectName("KkHint")
        self.key_page = QLabel()
        self.key_page.setOpenExternalLinks(True)
        self.key_page.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.delete_key_btn = QPushButton(tr("cloud_ai.key_delete"))
        self.delete_key_btn.clicked.connect(self._delete_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.delete_key_btn)
        form.addRow(tr("cloud_ai.key"), key_row)
        form.addRow("", self.key_state)
        form.addRow("", self.key_page)

        self.test_btn = QPushButton(tr("cloud_ai.test"))
        self.test_btn.clicked.connect(self._load_models)
        self.model = QComboBox()
        self.model.setMinimumContentsLength(24)
        model_row = QHBoxLayout()
        model_row.addWidget(self.model, 1)
        model_row.addWidget(self.test_btn)
        form.addRow(tr("cloud_ai.model"), model_row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("PageSubtitle")
        form.addRow("", self.status)

        self.use_import = QCheckBox(tr("cloud_ai.task_import"))
        self.use_cover = QCheckBox(tr("cloud_ai.task_cover"))
        form.addRow(tr("cloud_ai.tasks"), self.use_import)
        form.addRow("", self.use_cover)
        layout.addLayout(form)

        self.consent_text = QLabel()
        self.consent_text.setWordWrap(True)
        self.consent_text.setObjectName("KkNotice")
        self.consent = QCheckBox(tr("cloud_ai.consent_box"))
        layout.addWidget(self.consent_text)
        layout.addWidget(self.consent)

        outer = QVBoxLayout(self)
        outer.addWidget(wrap_dialog_body(body), stretch=1)
        buttons = label_button_box(QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        self.save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        outer.addWidget(buttons)

        self.provider.currentIndexChanged.connect(self._provider_changed)
        for signal in (self.consent.toggled, self.use_import.toggled, self.use_cover.toggled,
                       self.model.currentIndexChanged, self.key.textChanged):
            signal.connect(self._update_state)
        index = self.provider.findData(self._settings.provider)
        self.provider.setCurrentIndex(max(0, index))
        self.use_import.setChecked(self._settings.use_for_import)
        self.use_cover.setChecked(self._settings.use_for_cover)
        self.consent.setChecked(self._settings.consent_version >= cloud_ai.CONSENT_VERSION and bool(self._settings.provider))
        if self._settings.model:
            self.model.addItem(self._settings.model)
        self._provider_changed()
        fit_dialog_to_screen(self, preferred_width=620, preferred_height=560)

    # --- state ---------------------------------------------------------------------------------------------

    def provider_id(self) -> str:
        return str(self.provider.currentData() or "")

    def _provider_changed(self) -> None:
        pid = self.provider_id()
        cloud = bool(pid)
        for widget in (self.key, self.delete_key_btn, self.test_btn, self.model, self.use_import,
                       self.use_cover, self.consent, self.consent_text):
            widget.setEnabled(cloud)
        if pid != self._settings.provider:
            self.model.clear()
        self.key.clear()
        has_key = cloud and bool(cloud_ai.load_api_key(pid))
        self.key_state.setText(tr("cloud_ai.key_saved") if has_key else (tr("cloud_ai.key_missing") if cloud else ""))
        self.delete_key_btn.setVisible(has_key)
        if cloud:
            provider = cloud_ai.PROVIDERS[pid]
            self.key_page.setText(tr("cloud_ai.key_page", url=provider.key_page))
            self.consent_text.setText(tr("cloud_ai.consent", provider=provider.label))
        else:
            self.key_page.setText("")
            self.consent_text.setText("")
        self.status.setText("")
        self._update_state()

    def _update_state(self, *_args) -> None:
        pid = self.provider_id()
        if not pid:
            self.save_btn.setEnabled(True)
            return
        any_task = self.use_import.isChecked() or self.use_cover.isChecked()
        has_key = bool(self.key.text().strip()) or bool(cloud_ai.load_api_key(pid))
        ready = bool(self.model.currentText()) and has_key and self.consent.isChecked()
        # Choosing a provider without a task is allowed (nothing is sent); using it needs everything.
        self.save_btn.setEnabled(ready or not any_task)

    # --- actions -------------------------------------------------------------------------------------------

    def _current_key(self) -> str:
        typed = self.key.text().strip()
        return typed or cloud_ai.load_api_key(self.provider_id())

    def _load_models(self) -> None:
        pid, key = self.provider_id(), self._current_key()
        if not pid or not key:
            self.status.setText(tr("cloud_ai.key_missing"))
            return
        from desktop.workers import FunctionWorker, connect_queued, start_worker

        self.test_btn.setEnabled(False)
        self.status.setText(tr("cloud_ai.testing"))
        worker = FunctionWorker(lambda: cloud_ai.list_models(pid, key))
        connect_queued(worker.finished, lambda models, pid=pid: self._models_loaded(pid, models))
        connect_queued(worker.failed, self._models_failed)
        self._worker = worker
        self._thread = start_worker(worker)

    def _models_loaded(self, pid: str, models: list[str]) -> None:
        self.test_btn.setEnabled(True)
        if pid != self.provider_id():
            return
        previous = self.model.currentText() or self._settings.model or cloud_ai.PROVIDERS[pid].suggested_model
        self.model.clear()
        self.model.addItems(models)
        if previous in models:
            self.model.setCurrentText(previous)
        self.status.setText(tr("cloud_ai.test_ok", count=len(models)))
        self._update_state()

    def _models_failed(self, error) -> None:
        self.test_btn.setEnabled(True)
        self.status.setText(str(error) if isinstance(error, cloud_ai.CloudAiError) else tr("cloud_ai.test_failed"))

    def _delete_key(self) -> None:
        pid = self.provider_id()
        if pid:
            cloud_ai.delete_api_key(pid)
            self._provider_changed()

    def _save(self) -> None:
        pid = self.provider_id()
        try:
            if pid and self.key.text().strip():
                cloud_ai.store_api_key(pid, self.key.text())
        except ValueError:
            self.status.setText(tr("cloud_ai.key_invalid"))
            return
        except Exception:  # noqa: BLE001 - e.g. no credential store on this system
            self.status.setText(tr("cloud_ai.key_store_failed"))
            return
        if not pid:
            settings = cloud_ai.CloudAiSettings()
        else:
            settings = cloud_ai.CloudAiSettings(
                provider=pid, model=self.model.currentText().strip(),
                use_for_import=self.use_import.isChecked(), use_for_cover=self.use_cover.isChecked(),
                consent_version=cloud_ai.CONSENT_VERSION if self.consent.isChecked() else 0,
            )
        cloud_ai.save_settings(settings)
        self.accept()
