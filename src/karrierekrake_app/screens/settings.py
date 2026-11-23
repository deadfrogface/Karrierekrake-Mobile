"""Settings tab: cloud AI with the user's own key, pop-ups, archive, move settings and profile between devices."""
from __future__ import annotations

import toga
from toga.style import Pack

from core import cloud_ai
from karrierekrake_app import ui
from karrierekrake_app.ui import t


class SettingsScreen:
    def __init__(self, app, services) -> None:
        self.app = app
        self.services = services
        self.stack = ui.PageStack()
        names = [p.label for p in cloud_ai.PROVIDERS.values()]
        self._ids = list(cloud_ai.PROVIDERS)
        self.provider = toga.Selection(items=[t("Keiner (ohne KI)", "None (no AI)")] + names, style=Pack(height=ui.TOUCH))
        self.key = toga.PasswordInput(placeholder=t("API-Schlüssel", "API key"), style=Pack(height=ui.TOUCH))
        self.model = toga.Selection(items=[], style=Pack(height=ui.TOUCH))
        self.use_cover = toga.Switch(t("Für Anschreiben nutzen", "Use for cover letters"))
        self.use_import = toga.Switch(t("Zum Einlesen des Lebenslaufs nutzen", "Use to read the CV"))
        self.consent = toga.Switch(t("Ich bin einverstanden, dass dafür Daten an den Anbieter gehen.",
                                     "I agree that data goes to the provider for this."))
        self.popups = toga.Switch(t("Pop-up, wenn eine Firma antwortet", "Pop-up when a company replies"))
        self.archive_days = toga.NumberInput(min=0, max=365, step=1, style=Pack(height=ui.TOUCH, width=120))
        self.status = ui.text("", muted=True)
        self.stack.show(ui.column(
            ui.title(t("Einstellungen", "Settings")),
            ui.heading(t("KI-Anbieter", "AI provider")),
            ui.warning(t("Auf dem Handy arbeitet Karrierekrake mit Cloud-KI und deinem eigenen Schlüssel. Dafür gehen "
                         "dein Lebenslauf-Text bzw. Profil und die Anzeige an Server dieser Firma, meist im Ausland. "
                         "Die Prüfung auf erfundene Angaben läuft trotzdem hier auf dem Handy.",
                         "On the phone Karrierekrake uses cloud AI with your own key. Your CV text or profile and the "
                         "ad go to that company's servers, usually abroad. The check for invented claims still runs "
                         "here on the phone.")),
            self.provider, self.key, ui.button(t("Modelle laden", "Load models"), self.load_models), self.model,
            self.use_cover, self.use_import, self.consent,
            ui.button(t("KI-Einstellungen speichern", "Save AI settings"), self.save_ai, primary=True),
            ui.heading(t("Bewerbungen", "Applications")), self.popups,
            ui.text(t("Ohne Aktivität archivieren nach (Tagen, 0 = nie)", "Archive without activity after (days, 0 = never)"),
                    muted=True), self.archive_days,
            ui.button(t("Speichern", "Save"), self.save_general),
            ui.heading(t("Gerät wechseln", "Change device")),
            ui.button(t("Einstellungen und Profil exportieren", "Export settings and profile"), self.export_all),
            ui.button(t("Einstellungen und Profil importieren …", "Import settings and profile …"), self.import_all),
            self.status), root=True)
        self.load()

    @property
    def widget(self) -> toga.Widget:
        return self.stack.container

    def load(self) -> None:
        settings = cloud_ai.load_settings()
        if settings.provider in self._ids:
            self.provider.value = cloud_ai.PROVIDERS[settings.provider].label
            if settings.model:
                self.model.items = [settings.model]
                self.model.value = settings.model
        self.use_cover.value, self.use_import.value = settings.use_for_cover, settings.use_for_import
        self.consent.value = settings.consent_version >= cloud_ai.CONSENT_VERSION
        config = self.services.load_config()
        self.popups.value = bool(getattr(config.settings, "reply_popups", True))
        self.archive_days.value = int(getattr(config.settings, "archive_after_days", 14))

    def _provider_id(self) -> str:
        labels = [cloud_ai.PROVIDERS[i].label for i in self._ids]
        return self._ids[labels.index(self.provider.value)] if self.provider.value in labels else ""

    async def load_models(self, _widget=None) -> None:
        provider, key = self._provider_id(), (self.key.value or "").strip() or cloud_ai.load_api_key(self._provider_id())
        if not provider or not key:
            self.status.text = t("Bitte Anbieter wählen und Schlüssel eingeben.", "Please choose a provider and enter the key.")
            return
        try:
            models = await ui.in_background(cloud_ai.list_models, provider, key)
        except cloud_ai.CloudAiError as error:
            self.status.text = str(error)
            return
        self.model.items = models
        self.status.text = t(f"{len(models)} Modelle gefunden.", f"{len(models)} models found.")

    def save_ai(self, _widget=None) -> None:
        provider = self._provider_id()
        try:
            if provider and (self.key.value or "").strip():
                cloud_ai.store_api_key(provider, self.key.value)
                self.key.value = ""
        except ValueError:
            self.status.text = t("Der Schlüssel sieht nicht gültig aus.", "The key does not look valid.")
            return
        cloud_ai.save_settings(cloud_ai.CloudAiSettings(
            provider=provider, model=str(self.model.value or "") if provider else "",
            use_for_cover=bool(self.use_cover.value), use_for_import=bool(self.use_import.value),
            consent_version=cloud_ai.CONSENT_VERSION if self.consent.value else 0))
        self.status.text = t("Gespeichert ✓", "Saved ✓")

    def save_general(self, _widget=None) -> None:
        config = self.services.load_config()
        config.settings.reply_popups = bool(self.popups.value)
        config.settings.archive_after_days = int(self.archive_days.value or 0)
        self.services.save_config(config)
        self.status.text = t("Gespeichert ✓", "Saved ✓")

    def export_all(self, _widget=None) -> None:
        from core.settings_transfer import export_all

        target = self.services.data_dir / "Karrierekrake_Einstellungen.json"
        export_all(self.services.load_config(), target)
        self.status.text = t(f"Gespeichert: {target}", f"Saved: {target}")

    async def import_all(self, _widget=None) -> None:
        from core.settings_transfer import SettingsImportError, import_all

        path = await self.app.main_window.dialog(toga.OpenFileDialog(t("Datei wählen", "Choose file"), file_types=["json"]))
        if not path:
            return
        try:
            config, applied, skipped, _ = import_all(self.services.load_config(), path)
        except (OSError, ValueError, SettingsImportError):
            self.status.text = t("Diese Datei kann nicht übernommen werden.", "This file cannot be imported.")
            return
        self.services.save_config(config)
        self.load()
        self.status.text = t("Profil und Einstellungen übernommen ✓", "Profile and settings imported ✓")
