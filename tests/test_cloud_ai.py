"""Cloud models (own API key): settings, consent gate, OpenAI-format and Claude calls, error mapping.

No real key and no network: HTTP goes through an httpx mock transport, Claude through a fake client.
"""
import json
from types import SimpleNamespace

import httpx
import pytest

from core import cloud_ai

_REAL_CLIENT = httpx.Client


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path))
    keys: dict[str, str] = {}
    monkeypatch.setattr(cloud_ai, "load_api_key", lambda provider: keys.get(provider, ""))
    return keys


def _mock_http(monkeypatch, handler):
    real = _REAL_CLIENT
    seen = []

    def factory(*args, **kwargs):
        def record(request):
            seen.append(request)
            return handler(request)
        kwargs["transport"] = httpx.MockTransport(record)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)
    return seen


def _configure(provider="xai", model="grok-test", *, import_=True, cover=True, consent=cloud_ai.CONSENT_VERSION):
    cloud_ai.save_settings(cloud_ai.CloudAiSettings(provider=provider, model=model, use_for_import=import_,
                                                    use_for_cover=cover, consent_version=consent))


def test_default_is_local_only(data_dir):
    assert cloud_ai.load_settings() == cloud_ai.CloudAiSettings()
    assert cloud_ai.active_settings("import") is None
    with pytest.raises(cloud_ai.CloudAiError) as err:
        cloud_ai.chat([{"role": "user", "content": "x"}], task="cover", json_output=False)
    assert err.value.code == "not_configured"


@pytest.mark.parametrize("change", ["no_consent", "old_consent", "no_key", "task_off", "no_model"])
def test_nothing_is_sent_without_every_condition(data_dir, change):
    data_dir["xai"] = "key-123"
    _configure(consent=0 if change == "no_consent" else cloud_ai.CONSENT_VERSION - (change == "old_consent"),
               import_=change != "task_off", model="" if change == "no_model" else "grok-test")
    if change == "no_key":
        data_dir.clear()
    assert cloud_ai.active_settings("import") is None


def test_settings_survive_a_restart_and_unknown_providers_are_dropped(data_dir):
    _configure(provider="moonshot", model="kimi-x", import_=False, cover=True)
    loaded = cloud_ai.load_settings()
    assert (loaded.provider, loaded.model, loaded.use_for_import, loaded.use_for_cover) == ("moonshot", "kimi-x", False, True)
    cloud_ai.settings_path().write_text(json.dumps({"provider": "evil.example", "model": "m"}), encoding="utf-8")
    assert cloud_ai.load_settings().provider == ""


def test_openai_format_call_uses_fixed_endpoint_key_and_json_mode(data_dir, monkeypatch):
    data_dir["xai"] = "key-123"
    _configure()
    seen = _mock_http(monkeypatch, lambda request: httpx.Response(200, json={
        "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}))

    text = cloud_ai.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "U JSON"}],
                         task="import", json_output=True)

    assert text == '{"ok": true}'
    request = seen[0]
    assert str(request.url) == "https://api.x.ai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer key-123"
    body = json.loads(request.content)
    assert body["model"] == "grok-test" and body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "S"}


@pytest.mark.parametrize("status,body,code", [
    (401, "{}", "auth"), (403, "{}", "auth"), (429, "{}", "rate_limit"),
    (429, '{"error": {"code": "insufficient_quota"}}', "quota"), (402, "{}", "quota"),
    (404, '{"error": {"code": "model_not_found"}}', "model"), (500, "{}", "bad_response"),
])
def test_openai_format_errors_become_clear_codes(data_dir, monkeypatch, status, body, code):
    data_dir["openai"] = "key"
    _configure(provider="openai", model="gpt-test")
    _mock_http(monkeypatch, lambda request: httpx.Response(status, text=body))
    with pytest.raises(cloud_ai.CloudAiError) as err:
        cloud_ai.chat([{"role": "user", "content": "x"}], task="cover", json_output=False)
    assert err.value.code == code
    assert "key" not in str(err.value) and err.value.args[0]  # a German message, never the key


def test_truncated_and_network_errors(data_dir, monkeypatch):
    data_dir["moonshot"] = "key"
    _configure(provider="moonshot", model="kimi")
    _mock_http(monkeypatch, lambda request: httpx.Response(200, json={
        "choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}))
    with pytest.raises(cloud_ai.CloudAiError) as err:
        cloud_ai.chat([{"role": "user", "content": "x"}], task="import", json_output=True)
    assert err.value.code == "truncated"

    def offline(request):
        raise httpx.ConnectError("down", request=request)

    _mock_http(monkeypatch, offline)
    with pytest.raises(cloud_ai.CloudAiError) as err:
        cloud_ai.chat([{"role": "user", "content": "x"}], task="import", json_output=True)
    assert err.value.code == "network"


def test_model_list_comes_from_the_provider(monkeypatch):
    seen = _mock_http(monkeypatch, lambda request: httpx.Response(200, json={
        "data": [{"id": "b-model"}, {"id": "a-model"}, {"id": "b-model"}]}))
    assert cloud_ai.list_models("openai", "key") == ["a-model", "b-model"]
    assert str(seen[0].url) == "https://api.openai.com/v1/models"


class _FakeClaude:
    def __init__(self, response):
        self.calls = []
        create = lambda **kwargs: self.calls.append(kwargs) or response  # noqa: E731
        self.messages = SimpleNamespace(create=create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))
        self.models = SimpleNamespace(list=lambda: [SimpleNamespace(id="claude-opus-5-5"), SimpleNamespace(id="claude-haiku-5-5")])


def _claude_response(text="Brief", stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, stop_details=None,
                           content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])


def test_claude_call_uses_system_prompt_and_refusal_fallback(data_dir, monkeypatch):
    data_dir["anthropic"] = "key"
    _configure(provider="anthropic", model="claude-opus-5-5")
    fake = _FakeClaude(_claude_response("Sehr geehrte"))
    monkeypatch.setattr(cloud_ai, "_anthropic_client", lambda key, timeout: fake)

    text = cloud_ai.chat([{"role": "system", "content": "Regeln"}, {"role": "user", "content": "Profil"}],
                         task="cover", json_output=False)

    assert text == "Sehr geehrte"
    call = fake.calls[0]
    assert call["system"] == "Regeln" and call["messages"] == [{"role": "user", "content": "Profil"}]
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_refusal_and_truncation_are_errors(data_dir, monkeypatch):
    data_dir["anthropic"] = "key"
    _configure(provider="anthropic", model="claude-haiku-5-5")
    for stop, code in (("refusal", "refused"), ("max_tokens", "truncated")):
        fake = _FakeClaude(_claude_response(stop=stop))
        monkeypatch.setattr(cloud_ai, "_anthropic_client", lambda key, timeout, fake=fake: fake)
        with pytest.raises(cloud_ai.CloudAiError) as err:
            cloud_ai.chat([{"role": "user", "content": "x"}], task="cover", json_output=False)
        assert err.value.code == code
        assert "fallbacks" not in fake.calls[0]  # only models that support it get the fallback


def test_claude_models_listed(monkeypatch):
    monkeypatch.setattr(cloud_ai, "_anthropic_client", lambda key, timeout: _FakeClaude(_claude_response()))
    assert cloud_ai.list_models("anthropic", "key") == ["claude-haiku-5-5", "claude-opus-5-5"]


def test_every_provider_endpoint_is_fixed_https():
    for provider in cloud_ai.PROVIDERS.values():
        assert provider.base_url.startswith("https://") and provider.key_page.startswith("https://")


def test_key_validation_rejects_blank_and_whitespace(monkeypatch, tmp_path):
    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path))
    for bad in ("", "  ", "abc def"):
        with pytest.raises(ValueError):
            cloud_ai.store_api_key("xai", bad)
    with pytest.raises(ValueError):
        cloud_ai.store_api_key("unknown", "key")
