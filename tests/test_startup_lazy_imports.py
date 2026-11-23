"""Opening the main window loads none of the libraries only later work needs.

Each of these held the window back by a third of a second to a second: the holidays package builds every country on
import (the Settings provider probe pulled it in through the calendar), ``requests`` came with the update panel, and
the start page's model check loaded the whole local-AI service with its pydantic contracts, and reading the search
intent from the configuration loaded pydantic itself (about 0.6 s; ``core.search_intent`` is a plain class now).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent("""
    import sys, time
    sys.path.insert(0, sys.argv[1])
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from desktop.services import ConfigService
    from desktop.main_window import MainWindow
    service = ConfigService()
    service.load()
    window = MainWindow(service)
    window.show()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:  # let the startup workers (provider probe, geo preload) run
        app.processEvents()
        time.sleep(0.02)
    print("LOADED=" + ",".join(m for m in ("holidays", "requests", "guenther.service", "pydantic") if m in sys.modules))
""")


def test_the_main_window_opens_without_the_late_libraries(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", KARRIEREKRAKE_DATA_DIR=str(tmp_path / "data"))
    out = subprocess.run([sys.executable, "-c", _SCRIPT, str(ROOT)], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=180)
    lines = [line for line in out.stdout.splitlines() if line.startswith("LOADED=")]
    assert lines, out.stdout + out.stderr
    assert lines[-1] == "LOADED=", lines[-1]


def test_the_lazy_entry_points_still_reach_the_libraries():
    import core.app_updates as updates
    import guenther
    from integrations import calendar_availability

    assert updates.requests.get is __import__("requests").get
    assert guenther.get_guenther_service is __import__("guenther.service", fromlist=["x"]).get_guenther_service
    assert date_in(calendar_availability.load_holiday_dates(country="DE", years=[2026], enabled=True))


def date_in(dates) -> bool:
    from datetime import date

    return date(2026, 12, 25) in dates
