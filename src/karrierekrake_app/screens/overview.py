"""Start tab: what is going on, and what the app can and cannot do."""
from __future__ import annotations

import toga

from karrierekrake_app import ui
from karrierekrake_app.ui import t


class OverviewScreen:
    def __init__(self, app, services) -> None:
        self.app = app
        self.services = services
        self.stack = ui.PageStack()
        self.summary = ui.text("")
        self.stack.show(ui.column(
            ui.title("Karrierekrake"),
            ui.text(t("Finde. Bewirb. Behalte den Überblick.", "Find. Apply. Stay on top."), muted=True),
            self.summary,
            ui.heading(t("So geht's", "How it works")),
            ui.text(t("1. Profil ausfüllen oder von LinkedIn übernehmen\n2. Jobs suchen und Passung ansehen\n"
                      "3. Geprüftes Anschreiben erstellen und selbst absenden\n4. Bewerbungen im Blick behalten",
                      "1. Fill in your profile or import it from LinkedIn\n2. Search jobs and see the fit\n"
                      "3. Create a checked cover letter and send it yourself\n4. Keep track of applications")),
            ui.warning(t("Karrierekrake erfindet nichts: Jedes Anschreiben wird gegen dein Profil geprüft. "
                         "Eine Zusage kann keine App versprechen.",
                         "Karrierekrake invents nothing: every letter is checked against your profile. "
                         "No app can promise a job offer.")),
            ui.button(t("Aktualisieren", "Refresh"), self.refresh)), root=True)
        self.refresh()

    @property
    def widget(self) -> toga.Widget:
        return self.stack.container

    def refresh(self, _widget=None) -> None:
        active = self.services.applications()
        starred = sum(1 for r in active if r.starred)
        self.summary.text = t(f"{len(active)} aktive Bewerbungen · {starred} markiert",
                              f"{len(active)} active applications · {starred} starred")
