"""Karrierekrake for Android and iOS (BeeWare/Toga). The same core as the desktop app, a phone-made UI."""
from __future__ import annotations

import asyncio
import os

import toga

from karrierekrake_app import ui
from karrierekrake_app.services import AppServices

REPLY_CHECK_SECONDS = 60


class Karrierekrake(toga.App):
    def startup(self) -> None:
        # Tests and the desktop preview can point the app at another folder; on the phone it is the app's own one.
        self.services = AppServices(os.environ.get("KARRIEREKRAKE_APP_DATA") or self.paths.data)
        config = self.services.load_config()
        ui.set_language(getattr(config.settings, "language", "de") or "de")
        from karrierekrake_app.screens.applications import ApplicationsScreen
        from karrierekrake_app.screens.jobs import JobsScreen
        from karrierekrake_app.screens.overview import OverviewScreen
        from karrierekrake_app.screens.profile import ProfileScreen
        from karrierekrake_app.screens.settings import SettingsScreen

        self.pages = {
            "overview": OverviewScreen(self, self.services),
            "jobs": JobsScreen(self, self.services),
            "applications": ApplicationsScreen(self, self.services),
            "profile": ProfileScreen(self, self.services),
            "settings": SettingsScreen(self, self.services),
        }
        t = ui.t
        self.tabs = toga.OptionContainer(content=[
            (t("Start", "Home"), self.pages["overview"].widget),
            (t("Jobs", "Jobs"), self.pages["jobs"].widget),
            (t("Bewerbungen", "Applications"), self.pages["applications"].widget),
            (t("Profil", "Profile"), self.pages["profile"].widget),
            (t("Einstellungen", "Settings"), self.pages["settings"].widget),
        ], on_select=self.on_tab)
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.tabs
        self.main_window.show()
        self._reply_task = asyncio.ensure_future(self.watch_replies())

    def on_tab(self, widget, **_kwargs) -> None:
        current = widget.current_tab.text if widget.current_tab is not None else ""
        if current in (ui.t("Bewerbungen", "Applications"),):
            self.pages["applications"].refresh()
        elif current in (ui.t("Start", "Home"),):
            self.pages["overview"].refresh()

    async def watch_replies(self) -> None:
        """Pop-up when an employer answered (invitation, rejection, offer, linked mail)."""
        while True:
            await self.check_replies()
            await asyncio.sleep(REPLY_CHECK_SECONDS)

    async def check_replies(self) -> list[dict]:
        config = self.services.load_config()
        if not getattr(config.settings, "reply_popups", True):
            return []
        rows = self.services.new_replies()
        if rows:
            from core.reply_texts import describe

            await self.main_window.dialog(toga.InfoDialog(
                ui.t("Neue Antwort auf deine Bewerbung", "New reply to your application"),
                "\n".join(describe(r, english=ui.t("de", "en") == "en") for r in rows[:5])))
        return rows


def main() -> Karrierekrake:
    return Karrierekrake("Karrierekrake", "de.karrierekrake.app")
