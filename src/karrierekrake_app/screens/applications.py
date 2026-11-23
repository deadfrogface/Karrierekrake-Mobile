"""Applications tab: list (active / archive / starred), details with the saved job ad, star, archive, withdraw."""
from __future__ import annotations

import webbrowser
from datetime import date

import toga
from toga.style import Pack

from karrierekrake_app import ui
from karrierekrake_app.ui import t

STATUS = {"applied": ("Beworben", "Applied"), "needs_review": ("Prüfen", "Check"), "failed": ("Fehlgeschlagen", "Failed"),
          "closed": ("Abgeschlossen", "Closed"), "applying": ("In Arbeit", "In progress")}


def status_text(status: str) -> str:
    return t(*STATUS.get(status, (status or "–", status or "–")))


def ad_text(snapshot: dict) -> str:
    if not snapshot:
        return t("Keine Anzeige gespeichert.", "No ad saved.")
    facts = [snapshot.get(k) for k in ("title", "company", "location", "employment_type", "salary", "url")]
    page = snapshot.get("page_text") or ""
    body = snapshot.get("description") or ""
    return "\n".join(str(f) for f in facts if f) + "\n\n" + body + (("\n\n— " + t("Seite", "Page") + " —\n" + page)
                                                                    if page and page != body else "")


class ApplicationsScreen:
    def __init__(self, app, services) -> None:
        self.app = app
        self.services = services
        self.stack = ui.PageStack()
        self.show_archive = ui.switch(t("Archiv anzeigen", "Show archive"), on_change=self.refresh)
        self.starred_only = ui.switch(t("Nur markierte ★", "Starred only ★"), on_change=self.refresh)
        self.list_box = toga.Box(style=Pack(direction="column", gap=6))
        self.count = ui.text("", muted=True)
        self.stack.show(ui.column(ui.title(t("Bewerbungen", "Applications")), self.show_archive, self.starred_only,
                                  self.count, self.list_box,
                                  ui.button(t("Übersicht speichern (CSV)", "Save overview (CSV)"),
                                            self.export)), root=True)
        self.records: list = []
        self.refresh()

    @property
    def widget(self) -> toga.Widget:
        return self.stack.container

    def refresh(self, _widget=None) -> None:
        self.records = self.services.applications(archived=bool(self.show_archive.value),
                                                  starred_only=bool(self.starred_only.value))
        for child in list(self.list_box.children):
            self.list_box.remove(child)
        for index, rec in enumerate(self.records):
            star = "★ " if rec.starred else ""
            archived = t(" · archiviert", " · archived") if rec.archived_at else ""
            self.list_box.add(ui.card(f"{star}{rec.company}", f"{rec.position} · {status_text(rec.status)}{archived}",
                                      lambda w, i=index: self.open(i)))
        self.count.text = t(f"{len(self.records)} Bewerbungen", f"{len(self.records)} applications")

    def open(self, index: int) -> None:
        rec = self.records[index]
        db = self.services.db
        snapshot = db.application_ad_snapshot(rec.id)

        def toggle_star(_w):
            db.set_application_starred(rec.id, not rec.starred)
            self.refresh()
            self.stack.back()

        def toggle_archive(_w):
            db.set_application_archived(rec.id, not rec.archived_at)
            self.refresh()
            self.stack.back()

        async def withdraw(_w):
            from integrations.reply_draft import ReplyAction, build_action_draft
            from urllib.parse import quote

            config = self.services.load_config()
            draft = build_action_draft(ReplyAction.WITHDRAW, {"id": rec.id, "company": rec.company,
                                                              "position": rec.position},
                                       applicant_name=config.application.full_name)
            webbrowser.open(f"mailto:?subject={quote(draft.subject)}&body={quote(draft.body)}")
            db.set_application_result(rec.id, t(f"Zurückgezogen am {date.today():%d.%m.%Y}",
                                                f"Withdrawn on {date.today():%Y-%m-%d}"))
            self.refresh()

        page = ui.column(
            ui.title(rec.position or "–"), ui.text(rec.company or "–"),
            ui.text(status_text(rec.status) + (f" · {rec.result}" if rec.result else ""), muted=True),
            ui.heading(t("Gespeicherte Stellenanzeige", "Saved job ad")),
            toga.MultilineTextInput(value=ad_text(snapshot), readonly=True, style=Pack(height=260)),
            ui.button(t("☆ Markierung entfernen", "☆ Remove star") if rec.starred else t("★ Markieren", "★ Star"),
                      toggle_star),
            ui.button(t("Wieder aktivieren", "Make active again") if rec.archived_at else t("Archivieren", "Archive"),
                      toggle_archive),
            ui.button(t("Bewerbung zurückziehen (Mail)", "Withdraw application (mail)"), withdraw),
            ui.button(t("Zurück", "Back"), self.stack.back))
        self.stack.show(page)

    async def export(self, _widget=None) -> None:
        target = self.services.data_dir / f"Bewerbungen_{date.today().isoformat()}.csv"
        count = self.services.export_overview_csv(target)
        await self.app.main_window.dialog(toga.InfoDialog(
            t("Gespeichert", "Saved"), t(f"{count} Bewerbungen gespeichert:\n{target}", f"{count} applications saved:\n{target}")))
