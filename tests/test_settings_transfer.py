"""Settings file: only harmless app settings travel; paths, accounts and safety switches never do."""
import json

import pytest

from core.config import SettingsConfig
from core.settings_transfer import (GUARDED_FIELDS, PRIVATE_FIELDS, SettingsImportError, export_settings,
                                    import_settings)


def test_round_trip_moves_preferences(tmp_path):
    source = SettingsConfig(theme="dark", language="en", archive_after_days=30, jobs_per_search=60,
                            enabled_sources=["bundesagentur"])
    path = export_settings(source, tmp_path / "s.json", app_version="1.2.3")
    new, applied, skipped = import_settings(SettingsConfig(), path)
    assert (new.theme, new.language, new.archive_after_days, new.jobs_per_search) == ("dark", "en", 30, 60)
    assert new.enabled_sources == ["bundesagentur"]
    assert {"theme", "language", "archive_after_days"} <= set(applied) and set(skipped) <= GUARDED_FIELDS


def test_private_fields_are_never_written(tmp_path):
    source = SettingsConfig(local_calendar_feed_url="https://cal.example/secret.ics", imap_username="person@example.org",
                            browser_automation_profile="D:/Automation/profile")
    data = json.loads(export_settings(source, tmp_path / "s.json").read_text(encoding="utf-8"))["settings"]
    assert not (PRIVATE_FIELDS & data.keys())
    assert "secret.ics" not in json.dumps(data) and "example.org" not in json.dumps(data)


def test_safety_switches_and_unknown_or_wrong_types_are_skipped(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"format": "karrierekrake-settings", "version": 1, "settings": {
        "automatic_submission": True, "dry_run": False, "allow_employer_email_send": True,
        "database_path": "/etc/passwd", "evil": 1, "jobs_per_search": "lots", "theme": "light"}}), encoding="utf-8")
    current = SettingsConfig(theme="dark")
    new, applied, skipped = import_settings(current, path)
    assert applied == ["theme"]
    assert set(skipped) == {"automatic_submission", "dry_run", "allow_employer_email_send", "database_path",
                            "evil", "jobs_per_search"}
    assert new.automatic_submission is False and new.dry_run is True and new.database_path == current.database_path
    assert current.theme == "dark"  # the input is not changed


@pytest.mark.parametrize("content,code", [
    ("not json", "not_json"), ('{"format": "other", "settings": {}}', "wrong_format"),
    ('{"format": "karrierekrake-settings", "version": 99, "settings": {}}', "newer_version"),
])
def test_bad_files_are_refused(tmp_path, content, code):
    path = tmp_path / "s.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SettingsImportError) as err:
        import_settings(SettingsConfig(), path)
    assert str(err.value) == code


def test_guarded_fields_exist():
    from dataclasses import fields
    names = {f.name for f in fields(SettingsConfig)}
    assert GUARDED_FIELDS <= names and PRIVATE_FIELDS <= names


def test_settings_page_export_then_import(tmp_path, monkeypatch, qtbot):
    from desktop import paths as paths_mod
    from desktop.i18n import i18n

    def fake_dirs():
        root = tmp_path / "Karrierekrake"
        dirs = {n: root / n for n in ("config", "data", "logs", "browser_profile", "browsers", "cvs", "cache",
                                       "cover_letters")}
        dirs["root"] = root
        for p in dirs.values():
            p.mkdir(parents=True, exist_ok=True)
        return dirs

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(paths_mod, "ensure_app_dirs", fake_dirs)
    monkeypatch.setattr("desktop.services.ensure_app_dirs", fake_dirs)
    monkeypatch.setattr("desktop.services.schedule_service.ScheduleService.sync_from_config", lambda self: (True, "ok"))
    messages = []
    monkeypatch.setattr("desktop.pages.settings.QMessageBox.information", lambda *a, **k: messages.append(a[-1]))
    monkeypatch.setattr("desktop.pages.settings.QMessageBox.warning", lambda *a, **k: messages.append("WARN " + a[-1]))
    from desktop.pages import settings
    from desktop.services import ConfigService

    i18n.set_language("de")
    service = ConfigService()
    cfg = service.load()
    cfg.settings.archive_after_days = 30
    service.save(cfg)
    monkeypatch.setattr(settings, "confirm_action", lambda *a, **k: True)
    page = settings.SettingsPage(service)
    qtbot.addWidget(page)
    page.load_from_config()
    out = tmp_path / "export.json"
    monkeypatch.setattr(settings.QFileDialog, "getSaveFileName", lambda *a: (str(out), ""))
    page._export_settings_file()
    assert out.is_file() and messages[-1].startswith("Einstellungen gespeichert")

    cfg = service.load()
    cfg.settings.archive_after_days = 5
    service.save(cfg)
    monkeypatch.setattr(settings.QFileDialog, "getOpenFileName", lambda *a: (str(out), ""))
    page._import_settings_file()
    assert service.load().settings.archive_after_days == 30
    assert page.archive_after_days.value() == 30
    assert "übernommen" in messages[-1]
    page.model_setup.shutdown()
    qtbot.waitUntil(lambda: not page.model_setup.busy, timeout=10000)


def test_profile_skills_and_applicant_travel_but_paths_do_not(tmp_path):
    from core.config import empty_app_config
    from core.settings_transfer import export_all, import_all

    old = empty_app_config(root=tmp_path)
    old.profile.jobs.desired_titles = ["Sachbearbeitung"]
    old.profile.qualifications.skills = ["SAP", "Buchhaltung"]
    old.profile.employment.weekly_hours_min, old.profile.employment.weekly_hours_max = 20, 30
    old.application.first_name, old.application.city = "Kim", "Berlin"
    old.application.cv_path = "D:/Old/cv.pdf"
    old.settings.theme = "dark"
    path = export_all(old, tmp_path / "all.json")
    assert "D:/Old" not in path.read_text(encoding="utf-8")

    new_laptop = empty_app_config(root=tmp_path)
    new_laptop.application.cv_path = "E:/New/cv.pdf"
    new, applied, skipped, included = import_all(new_laptop, path)
    assert included and new.settings.theme == "dark"
    assert "Sachbearbeitung" in new.profile.jobs.desired_titles
    assert [s.value if hasattr(s, "value") else s for s in new.profile.qualifications.skills] == ["SAP", "Buchhaltung"]
    assert (new.profile.employment.weekly_hours_min, new.profile.employment.weekly_hours_max) == (20, 30)
    assert (new.application.first_name, new.application.city) == ("Kim", "Berlin")
    assert new.application.cv_path == "E:/New/cv.pdf"  # this computer's file stays


def test_old_settings_only_file_still_imports(tmp_path):
    from core.config import empty_app_config
    from core.settings_transfer import import_all

    path = tmp_path / "v1.json"
    path.write_text(json.dumps({"format": "karrierekrake-settings", "version": 1, "settings": {"theme": "dark"}}),
                    encoding="utf-8")
    cfg = empty_app_config(root=tmp_path)
    cfg.profile.jobs.desired_titles = ["Bleibt"]
    new, _, _, included = import_all(cfg, path)
    assert not included and new.settings.theme == "dark" and new.profile.jobs.desired_titles == ["Bleibt"]
