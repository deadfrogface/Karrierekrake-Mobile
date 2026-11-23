"""The provider dialog: local stays the default, saving needs key, model and consent, the key goes to the store."""
import pytest

from core import cloud_ai
from desktop.i18n import i18n


@pytest.fixture()
def keys(tmp_path, monkeypatch):
    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path))
    store: dict[str, str] = {}
    monkeypatch.setattr(cloud_ai, "load_api_key", lambda pid: store.get(pid, ""))
    monkeypatch.setattr(cloud_ai, "store_api_key", lambda pid, key: store.__setitem__(pid, key.strip()))
    monkeypatch.setattr(cloud_ai, "delete_api_key", lambda pid: store.pop(pid, None))
    i18n.set_language("de")
    return store


def _dialog(qtbot):
    from desktop.widgets.cloud_ai_dialog import CloudAiDialog

    dialog = CloudAiDialog(None)
    qtbot.addWidget(dialog)
    return dialog


def test_local_is_the_default_and_saves_nothing_to_send(qtbot, keys):
    dialog = _dialog(qtbot)
    assert dialog.provider_id() == ""
    assert not dialog.use_import.isEnabled() and not dialog.consent.isEnabled()
    dialog._save()
    assert cloud_ai.load_settings() == cloud_ai.CloudAiSettings()
    assert keys == {}


def test_using_a_cloud_model_needs_key_model_and_consent(qtbot, keys):
    dialog = _dialog(qtbot)
    dialog.provider.setCurrentIndex(dialog.provider.findData("anthropic"))
    dialog.use_cover.setChecked(True)
    assert not dialog.save_btn.isEnabled()  # no key, no model, no consent

    dialog.key.setText("  sk-test-key  ")
    dialog._models_loaded("anthropic", ["claude-haiku-5-5", "claude-opus-5-5"])
    assert dialog.model.currentText() == "claude-opus-5-5"  # the provider's suggested model is preselected
    assert not dialog.save_btn.isEnabled()  # still no consent

    dialog.consent.setChecked(True)
    assert dialog.save_btn.isEnabled()
    dialog._save()

    saved = cloud_ai.load_settings()
    assert (saved.provider, saved.model, saved.use_for_cover, saved.use_for_import) == (
        "anthropic", "claude-opus-5-5", True, False)
    assert saved.consent_version == cloud_ai.CONSENT_VERSION
    assert keys == {"anthropic": "sk-test-key"}
    assert cloud_ai.active_settings("cover") is not None and cloud_ai.active_settings("import") is None


def test_consent_names_the_provider_and_the_data(qtbot, keys):
    dialog = _dialog(qtbot)
    dialog.provider.setCurrentIndex(dialog.provider.findData("xai"))
    text = dialog.consent_text.text()
    assert "Grok (xAI)" in text and "Lebenslauf" in text and "Stellenanzeige" in text
    assert "https://" in dialog.key_page.text()


def test_switching_back_to_local_turns_the_cloud_off(qtbot, keys):
    keys["openai"] = "k"
    cloud_ai.save_settings(cloud_ai.CloudAiSettings(provider="openai", model="m", use_for_import=True,
                                                    consent_version=cloud_ai.CONSENT_VERSION))
    dialog = _dialog(qtbot)
    assert dialog.provider_id() == "openai" and dialog.use_import.isChecked()
    dialog.provider.setCurrentIndex(0)
    dialog._save()
    assert cloud_ai.active_settings("import") is None


def test_settings_page_summary(keys):
    from desktop.widgets.cloud_ai_dialog import cloud_ai_summary

    assert "lokal" in cloud_ai_summary()
    keys["moonshot"] = "k"
    cloud_ai.save_settings(cloud_ai.CloudAiSettings(provider="moonshot", model="kimi-k", use_for_import=True,
                                                    consent_version=cloud_ai.CONSENT_VERSION))
    assert cloud_ai_summary() == "KI: Kimi (Moonshot AI) (kimi-k) für Lebenslauf einlesen."
