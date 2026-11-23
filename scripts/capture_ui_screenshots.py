#!/usr/bin/env python3
"""Capture real UI screenshots into docs/assets/screenshots/ (Qt offscreen or xvfb).

Uses fictional demo data only. Never touches a real user AppData profile unless
LOCALAPPDATA is left at the process default (CI / media scripts must override).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "assets" / "screenshots"
# Pages by their navigation key, so a new page in the sidebar does not shift the pictures.
NAMES = [
    ("01-dashboard.png", "nav.overview"),
    ("02-jobs.png", "nav.jobs"),
    ("03-applications.png", "nav.applications"),
    ("04-settings.png", "nav.settings"),
    ("05-logs.png", "nav.logs"),
    ("06-profile.png", "nav.profile"),
    ("08-search.png", "nav.search"),
    ("09-inbox.png", "nav.inbox"),
]


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    tmp = tempfile.mkdtemp(prefix="karrierekrake-shots-")
    os.environ["LOCALAPPDATA"] = tmp

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from desktop.demo_data import DEMO_PROFILE, seed_demo_database
    from desktop.i18n import i18n
    from desktop.main_window import MainWindow
    from desktop.services import ConfigService
    from desktop.theme import stylesheet_for

    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    svc = ConfigService()
    cfg = svc.load()
    cfg = svc.apply_safe_defaults(cfg)
    cfg.application.first_name = DEMO_PROFILE["first_name"]
    cfg.application.last_name = DEMO_PROFILE["last_name"]
    cfg.application.email = DEMO_PROFILE["email"]
    cfg.application.phone = DEMO_PROFILE["phone"]
    cfg.profile.location.home_address = f"{DEMO_PROFILE['city']}, Deutschland"
    cfg.profile.jobs.desired_titles = list(DEMO_PROFILE["titles"])
    cfg.settings.theme = "light"
    cfg.settings.language = "de"
    cfg.settings.dry_run = True
    svc.save(cfg)
    svc.mark_first_run_done()
    seed_demo_database(cfg.db_path)

    i18n.set_language("de")
    app.setStyleSheet(stylesheet_for("light"))
    window = MainWindow(svc)
    window.resize(1180, 760)
    window.show()
    # Force profile/jobs pages to load demo config
    window.profile.load_from_config()
    window.jobs.refresh()
    window.applications.refresh()
    window.dashboard.refresh()
    window.logs.refresh()

    def capture() -> None:
        for name, key in NAMES:
            window._navigate(window._page_index[key])
            app.processEvents()
            window.stack.currentWidget()
            # Grab the whole window for consistent chrome (sidebar + content)
            pix = window.grab()
            target = OUT / name
            pix.save(str(target), "PNG")
            print(f"wrote {target.relative_to(ROOT)} ({pix.width()}x{pix.height()})")
        # also grab detail-oriented jobs after selecting first row
        window._navigate(window._page_index["nav.jobs"])
        app.processEvents()
        if window.jobs.table.rowCount() > 0:
            window.jobs.table.selectRow(0)
            app.processEvents()
            pix = window.grab()
            pix.save(str(OUT / "02-jobs.png"), "PNG")
            print("updated 02-jobs.png with selection")
        window.close()
        app.quit()

    QTimer.singleShot(200, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
