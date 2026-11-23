"""The phone app with Toga's test backend: every tab builds, profile/applications/settings work offline."""
import asyncio
import sys

import pytest

from core.models import Job


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from karrierekrake_app.app import Karrierekrake

    monkeypatch.setattr(Karrierekrake, "watch_replies", lambda self: asyncio.sleep(0))
    monkeypatch.setenv("KARRIEREKRAKE_APP_DATA", str(tmp_path / "data"))
    application = Karrierekrake("Karrierekrake", "de.karrierekrake.app")
    yield application


def test_all_tabs_build(app):
    assert len(app.tabs.content) == 5
    assert {"overview", "jobs", "applications", "profile", "settings"} == set(app.pages)


def test_profile_round_trip(app):
    profile = app.pages["profile"]
    profile.first.value, profile.last.value, profile.city.value = "Kim", "Test", "Berlin"
    profile.titles.value = "Bürokraft\nSachbearbeitung"
    profile.skills.value = "SAP, Excel"
    profile.languages.value = "Englisch | B2"
    profile.save()
    config = app.services.load_config()
    assert config.application.full_name == "Kim Test" and config.profile.location.city == "Berlin"
    assert config.profile.jobs.desired_titles == ["Bürokraft", "Sachbearbeitung"]
    assert config.profile.qualifications.skill_values() == ["SAP", "Excel"]
    assert config.profile.qualifications.languages[0].level == "B2"


def test_search_scores_and_stores_jobs(app, monkeypatch):
    from search import bundesagentur

    jobs = [Job(id="j1", source="bundesagentur", title="Bürokraft", company="Muster GmbH", city="Berlin",
                description="Wir suchen eine Bürokraft mit Excel.", url="https://example.org/1")]
    monkeypatch.setattr(bundesagentur.BundesagenturSource, "search", lambda self, queries: list(jobs))
    outcome = app.services.search_jobs("Bürokraft", "Berlin", 25)
    assert [j.id for j in outcome.jobs] == ["j1"] and app.services.db.get_job("j1") is not None
    assert app.services.search_jobs("", "", 25).error == "keyword_missing"


def test_application_list_star_and_archive(app):
    services = app.services
    job = Job(id="j1", source="bundesagentur", title="Bürokraft", company="Muster GmbH", url="https://example.org/1",
              description="Anzeigentext")
    services.db.upsert_job(job)
    app_id = services.record_application(job)
    screen = app.pages["applications"]
    screen.refresh()
    assert len(screen.records) == 1
    services.db.set_application_starred(app_id, True)
    screen.starred_only.value = True
    screen.refresh()
    assert len(screen.records) == 1 and screen.records[0].starred
    assert services.db.application_ad_snapshot(app_id)["description"] == "Anzeigentext"


def test_cloud_settings_and_key_stay_in_the_app_folder(app):
    from core import cloud_ai

    settings = app.pages["settings"]
    settings.provider.value = cloud_ai.PROVIDERS["openai"].label
    settings.key.value = "sk-test-123"
    settings.model.items = ["gpt-test"]
    settings.model.value = "gpt-test"
    settings.use_cover.value, settings.consent.value = True, True
    settings.save_ai()
    assert cloud_ai.load_api_key("openai") == "sk-test-123"
    assert cloud_ai.active_settings("cover") is not None
    keys = (app.services.data_dir / "keys.json").read_text(encoding="utf-8")
    assert "sk-test-123" in keys and "sk-test-123" not in cloud_ai.settings_path().read_text(encoding="utf-8")


def test_reply_popup_reports_once(app):
    from core.lifecycle import ApplicationCase, LifecycleEvent

    db = app.services.db
    db.upsert_job(Job(id="j1", title="Bürokraft", company="Muster GmbH", url="https://example.org/1"))
    db.upsert_case(ApplicationCase(id="c1", job_id="j1", company="Muster GmbH", position="Bürokraft"))
    assert app.services.new_replies() == []  # first look only sets the start point
    db.append_lifecycle_event(LifecycleEvent(event_type="INTERVIEW_REQUESTED", case_id="c1"))
    rows = app.services.new_replies()
    assert len(rows) == 1 and app.services.new_replies() == []


def test_no_desktop_ui_or_local_model_is_loaded(app):
    loaded = {name.split(".")[0] for name in sys.modules}
    assert not loaded & {"PySide6", "shiboken6", "llama_cpp", "playwright"}


def test_claude_works_without_the_sdk(monkeypatch, tmp_path):
    import json

    import httpx

    from core import cloud_ai

    monkeypatch.setattr(cloud_ai, "_sdk_available", lambda: False)
    real = httpx.Client
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "claude-b"}, {"id": "claude-a"}]})
        return httpx.Response(200, json={"stop_reason": "end_turn", "content": [{"type": "text", "text": "Brief"}]})

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real(*a, transport=httpx.MockTransport(handler), **k))
    assert cloud_ai.list_models("anthropic", "key") == ["claude-a", "claude-b"]
    assert cloud_ai._anthropic_chat("key", "claude-a", [{"role": "system", "content": "S"},
                                                         {"role": "user", "content": "U"}], timeout=5) == "Brief"
    body = json.loads(seen[-1].content)
    assert seen[-1].headers["x-api-key"] == "key" and body["system"] == "S" and str(seen[-1].url).startswith("https://api.anthropic.com/")
