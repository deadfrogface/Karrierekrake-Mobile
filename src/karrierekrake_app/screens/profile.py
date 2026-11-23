"""Profile tab: contact data, wished jobs, place, skills, languages; import from LinkedIn's data export."""
from __future__ import annotations

import toga
from toga.style import Pack

from core.config import LanguageEntry, SourcedText
from karrierekrake_app import ui
from karrierekrake_app.ui import t


def _lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").replace(",", "\n").splitlines() if line.strip()]


class ProfileScreen:
    def __init__(self, app, services) -> None:
        self.app = app
        self.services = services
        self.stack = ui.PageStack()
        self.first = toga.TextInput(placeholder=t("Vorname", "First name"), style=Pack(height=ui.TOUCH))
        self.last = toga.TextInput(placeholder=t("Nachname", "Last name"), style=Pack(height=ui.TOUCH))
        self.email = toga.TextInput(placeholder=t("E-Mail", "Email"), style=Pack(height=ui.TOUCH))
        self.phone = toga.TextInput(placeholder=t("Telefon", "Phone"), style=Pack(height=ui.TOUCH))
        self.street = toga.TextInput(placeholder=t("Straße und Hausnummer", "Street and number"), style=Pack(height=ui.TOUCH))
        self.postal = toga.TextInput(placeholder=t("PLZ", "Postcode"), style=Pack(height=ui.TOUCH, width=110))
        self.city = toga.TextInput(placeholder=t("Ort", "Town"), style=Pack(height=ui.TOUCH, flex=1))
        self.titles = toga.MultilineTextInput(placeholder=t("Wunschberufe, einer pro Zeile", "Wished jobs, one per line"),
                                              style=Pack(height=100))
        self.skills = toga.MultilineTextInput(placeholder=t("Kenntnisse, eine pro Zeile", "Skills, one per line"),
                                              style=Pack(height=140))
        self.languages = toga.MultilineTextInput(placeholder=t("Sprachen, z. B. Englisch | B2", "Languages, e.g. English | B2"),
                                                 style=Pack(height=90))
        self.status = ui.text("", muted=True)
        self.stack.show(ui.column(
            ui.title(t("Profil", "Profile")),
            ui.text(t("Deine Angaben bleiben auf diesem Handy.", "Your data stays on this phone."), muted=True),
            ui.heading(t("Kontakt", "Contact")), self.first, self.last, self.email, self.phone, self.street,
            ui.row(self.postal, self.city),
            ui.heading(t("Was suchst du?", "What are you looking for?")), self.titles,
            ui.heading(t("Kenntnisse", "Skills")), self.skills,
            ui.heading(t("Sprachen", "Languages")), self.languages,
            ui.button(t("Speichern", "Save"), self.save, primary=True),
            ui.button(t("Von LinkedIn importieren …", "Import from LinkedIn …"), self.import_linkedin),
            ui.text(t("LinkedIn: Einstellungen → Datenschutz → „Kopie Ihrer Daten erhalten“ → ZIP-Datei wählen.",
                      "LinkedIn: Settings → Data privacy → “Get a copy of your data” → choose the ZIP file."), muted=True),
            self.status), root=True)
        self.load()

    @property
    def widget(self) -> toga.Widget:
        return self.stack.container

    def load(self) -> None:
        config = self.services.load_config()
        a = config.application
        self.first.value, self.last.value, self.email.value, self.phone.value = a.first_name, a.last_name, a.email, a.phone
        self.street.value, self.postal.value, self.city.value = a.street, a.postal_code, a.city
        self.titles.value = "\n".join(config.profile.jobs.desired_titles or [])
        self.skills.value = "\n".join(config.profile.qualifications.skill_values())
        self.languages.value = "\n".join(config.profile.qualifications.language_labels())

    def save(self, _widget=None) -> None:
        config = self.services.load_config()
        a = config.application
        a.first_name, a.last_name = self.first.value.strip(), self.last.value.strip()
        a.email, a.phone, a.street = self.email.value.strip(), self.phone.value.strip(), self.street.value.strip()
        a.postal_code, a.city = self.postal.value.strip(), self.city.value.strip()
        location = config.profile.location
        location.postal_code, location.city = a.postal_code, a.city
        config.profile.jobs.desired_titles = _lines(self.titles.value)
        q = config.profile.qualifications
        q.skills = [SourcedText(value=s, source="manual") for s in _lines(self.skills.value)]
        languages = []
        for line in (self.languages.value or "").splitlines():
            if line.strip():
                name, _, level = line.partition("|")
                languages.append(LanguageEntry(language=name.strip(), level=level.strip(), source="manual"))
        q.languages = languages
        intent = config.profile.search_intent
        if intent is not None and hasattr(intent, "target_roles"):
            intent.target_roles = list(config.profile.jobs.desired_titles)
        self.services.save_config(config)
        self.status.text = t("Gespeichert ✓", "Saved ✓")

    async def import_linkedin(self, _widget=None) -> None:
        from core.linkedin_import import LinkedInImportError, read_linkedin_export
        from core.profile_merge import merge_qualifications

        path = await self.app.main_window.dialog(toga.OpenFileDialog(t("LinkedIn-Export wählen", "Choose LinkedIn export"),
                                                                     file_types=["zip"]))
        if not path:
            return
        try:
            data = await ui.in_background(read_linkedin_export, str(path))
        except (LinkedInImportError, OSError, UnicodeError):
            self.status.text = t("Das ist kein LinkedIn-Datenexport.", "This is not a LinkedIn data export.")
            return
        config = self.services.load_config()
        config.profile.qualifications = merge_qualifications(config.profile.qualifications, data.qualifications)
        self.services.save_config(config)
        self.load()
        counts = data.counts()
        self.status.text = t(f"Übernommen: {counts['skills']} Kenntnisse, {counts['positions']} Stationen, "
                             f"{counts['languages']} Sprachen.",
                             f"Added: {counts['skills']} skills, {counts['positions']} positions, {counts['languages']} languages.")
