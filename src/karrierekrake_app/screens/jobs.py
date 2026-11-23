"""Jobs tab: search the Bundesagentur, see why a job fits, draft a checked letter, record the application."""
from __future__ import annotations

import webbrowser

import toga
from toga.style import Pack

from karrierekrake_app import ui
from karrierekrake_app.ui import t


class JobsScreen:
    def __init__(self, app, services) -> None:
        self.app = app
        self.services = services
        self.stack = ui.PageStack()
        self.jobs: list = []
        config = services.load_config()
        titles = list(config.profile.jobs.desired_titles or [])
        self.keyword_label, self.keyword = ui.field(t("Was suchst du?", "What are you looking for?"),
                                                    titles[0] if titles else "", t("z. B. Bürokauffrau", "e.g. office clerk"))
        home = config.profile.location
        self.place_label, self.place = ui.field(t("Wo? (Ort oder PLZ)", "Where? (town or postcode)"),
                                                home.postal_code or home.city or "")
        self.radius = toga.Selection(items=["10 km", "25 km", "50 km", "100 km"], style=Pack(height=ui.TOUCH))
        self.radius.value = "25 km"
        self.status = ui.text("", muted=True)
        self.results = toga.Box(style=Pack(direction="column", gap=6))
        self.search_btn = ui.button(t("Jobs suchen", "Search jobs"), self.search, primary=True)
        self.stack.show(ui.column(ui.title(t("Jobs", "Jobs")), self.keyword_label, self.keyword, self.place_label,
                                  self.place, self.radius, self.search_btn, self.status, self.results), root=True)

    @property
    def widget(self) -> toga.Widget:
        return self.stack.container

    async def search(self, _widget=None) -> None:
        self.search_btn.enabled = False
        self.status.text = t("Suche läuft …", "Searching …")
        radius = int(str(self.radius.value or "25").split()[0])
        outcome = await ui.in_background(self.services.search_jobs, self.keyword.value, self.place.value, radius)
        self.search_btn.enabled = True
        if outcome.error == "keyword_missing":
            self.status.text = t("Bitte gib einen Beruf oder ein Stichwort ein.", "Please enter a job title or keyword.")
            return
        if outcome.error.startswith("network"):
            self.status.text = t("Keine Verbindung zur Jobsuche. Bitte später erneut versuchen.",
                                 "No connection to the job search. Please try again later.")
            return
        self.jobs = outcome.jobs
        self.status.text = t(f"{len(self.jobs)} Treffer", f"{len(self.jobs)} results")
        self._render_results()

    def _render_results(self) -> None:
        for child in list(self.results.children):
            self.results.remove(child)
        for index, job in enumerate(self.jobs[:40]):
            place = job.city or job.postal_code or ""
            label = f"{job.title}\n{job.company}{' · ' + place if place else ''}"
            self.results.add(toga.Button(label, on_press=lambda w, i=index: self.open_job(i),
                                         style=Pack(height=ui.TOUCH + 16, flex=1)))

    def open_job(self, index: int) -> None:
        job = self.jobs[index]
        good, check = self.services.fit_lines(job)
        parts = [ui.title(job.title), ui.text(job.company), ui.text(job.city or job.address or "", muted=True)]
        if good:
            parts.append(ui.heading(t("Warum es passt", "Why it fits")))
            parts += [ui.text("✓ " + line) for line in good]
        if check:
            parts.append(ui.heading(t("Bitte prüfen", "Please check")))
            parts += [ui.text("⚠ " + line) for line in check]
        parts.append(ui.heading(t("Anzeige", "Ad")))
        parts.append(toga.MultilineTextInput(value=job.description or "–", readonly=True, style=Pack(height=220)))
        letter = toga.MultilineTextInput(placeholder=t("Hier erscheint dein geprüftes Anschreiben.",
                                                       "Your checked cover letter appears here."), style=Pack(height=260))
        note = ui.text("", muted=True)

        async def draft(_w):
            note.text = t("Anschreiben wird erstellt …", "Writing the cover letter …")
            text, problem = await ui.in_background(self.services.draft_cover_letter, job)
            letter.value = text
            note.text = (t("Geprüft: nichts erfunden. Lies es vor dem Absenden selbst.",
                           "Checked: nothing invented. Read it yourself before sending.") if text
                         else t(f"Kein Anschreiben möglich ({problem}). Ergänze dein Profil.",
                                f"No cover letter possible ({problem}). Complete your profile."))

        async def applied(_w):
            self.services.record_application(job, letter=letter.value or "")
            await self.app.main_window.dialog(toga.InfoDialog(
                t("Gespeichert", "Saved"), t("Die Bewerbung steht jetzt unter „Bewerbungen“.",
                                             "The application is now under “Applications”.")))

        url = job.application_url or job.url
        parts += [ui.heading(t("Anschreiben", "Cover letter")), letter, note,
                  ui.button(t("Anschreiben erstellen", "Write cover letter"), draft, primary=True),
                  ui.button(t("Als beworben speichern", "Save as applied"), applied),
                  ui.button(t("Anzeige im Browser öffnen", "Open ad in browser"),
                            lambda w: webbrowser.open(url) if url.startswith("https://") else None),
                  ui.button(t("Zurück", "Back"), self.stack.back)]
        self.stack.show(ui.column(*parts))
