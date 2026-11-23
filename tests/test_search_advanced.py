"""Extended search: preferred skills, industries, companies and ad age are edited on the search page."""


def test_advanced_fields_round_trip(tmp_path, monkeypatch, qtbot):
    from desktop import paths as paths_mod

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
    from desktop.pages import search
    from desktop.services import ConfigService

    monkeypatch.setattr(search.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(search.QMessageBox, "warning", lambda *a, **k: None)
    service = ConfigService()
    page = search.SearchPage(service)
    qtbot.addWidget(page)
    page.load_from_config()
    page.target_roles.set_items(["Sachbearbeitung"])
    page.preferred_skills.set_items(["SAP"])
    page.preferred_industries.set_items(["Gesundheit"])
    page.excluded_industries.set_items(["Glücksspiel"])
    page.preferred_companies.set_items(["Muster GmbH"])
    page.excluded_companies.set_items(["Zeitarbeit AG"])
    page.published_within.setValue(7)
    page.save()

    cfg = service.load()
    intent = cfg.profile.search_intent
    assert intent.preferred_skills == ["SAP"] and intent.preferred_industries == ["Gesundheit"]
    assert intent.excluded_industries == ["Glücksspiel"] and cfg.profile.jobs.excluded_industries == ["Glücksspiel"]
    assert cfg.profile.filters.preferred_companies == ["Muster GmbH"]
    assert cfg.profile.filters.excluded_companies == ["Zeitarbeit AG"]
    assert cfg.settings.published_within_days == 7

    again = search.SearchPage(service)
    qtbot.addWidget(again)
    again.load_from_config()
    assert again.preferred_skills.get_items() == ["SAP"] and again.published_within.value() == 7
    assert again.excluded_companies.get_items() == ["Zeitarbeit AG"]
