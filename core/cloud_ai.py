"""Optional cloud models – Grok, ChatGPT, Claude, Kimi – with the user's own API key.

Off by default: the local model does the work. A cloud model is used only when the user has
chosen a provider and a model, stored an API key, ticked the task (CV import, cover letter) and
confirmed what leaves the computer (``CONSENT_VERSION``). The checks after the model – the import's
source-bound repairs, the cover letter guard – run locally either way.

- Each provider has one fixed HTTPS endpoint; there is no user-editable address.
- The key lives in the operating system's credential store (``integrations.secure_tokens``),
  never in a file and never in a log line.
- Grok (xAI), ChatGPT (OpenAI) and Kimi (Moonshot) speak the OpenAI chat-completions format;
  Claude is called through the official Anthropic SDK.
- Model names come from the provider's own model list, so no outdated name is built in.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Task = Literal["import", "cover"]
CONSENT_VERSION = 1  # raise when the data that leaves the computer changes; the user confirms again
SETTINGS_FILE = "cloud_ai.json"
REQUEST_TIMEOUT_S = 180.0


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    api_style: Literal["openai", "anthropic"]
    base_url: str
    key_page: str  # the provider's developer console, where the user creates an API key
    suggested_model: str = ""  # preselected when the provider lists it


PROVIDERS: dict[str, Provider] = {
    "xai": Provider("xai", "Grok (xAI)", "openai", "https://api.x.ai/v1", "https://console.x.ai/"),
    "openai": Provider("openai", "ChatGPT (OpenAI)", "openai", "https://api.openai.com/v1",
                       "https://platform.openai.com/"),
    "anthropic": Provider("anthropic", "Claude (Anthropic)", "anthropic", "https://api.anthropic.com",
                          "https://platform.claude.com/", suggested_model="claude-opus-5-5"),
    "moonshot": Provider("moonshot", "Kimi (Moonshot AI)", "openai", "https://api.moonshot.ai/v1",
                         "https://platform.moonshot.ai/"),
}
# Claude models that accept the server-side refusal fallback (a declined request is re-run on another model).
_ANTHROPIC_FALLBACK_MODELS = frozenset({"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5",
                                        "claude-opus-5", "claude-sonnet-5-5"})


class CloudAiError(RuntimeError):
    """A cloud call that did not give an answer; ``code`` is stable, ``message`` is for the user."""

    MESSAGES = {
        "not_configured": "Kein Cloud-Modell eingerichtet.",
        "no_key": "Für diesen Anbieter ist kein API-Schlüssel gespeichert.",
        "auth": "Der Anbieter hat den API-Schlüssel abgelehnt. Bitte den Schlüssel prüfen.",
        "quota": "Beim Anbieter ist kein Guthaben mehr frei oder das Limit erreicht.",
        "rate_limit": "Der Anbieter bittet um eine Pause (zu viele Anfragen). Bitte gleich noch einmal versuchen.",
        "network": "Der Anbieter ist gerade nicht erreichbar. Bitte die Internetverbindung prüfen.",
        "refused": "Das Modell hat diese Anfrage abgelehnt.",
        "truncated": "Die Antwort des Modells wurde abgeschnitten.",
        "bad_response": "Die Antwort des Anbieters war nicht verwertbar.",
        "model": "Das gewählte Modell gibt es beim Anbieter nicht (mehr). Bitte ein anderes wählen.",
    }

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(self.MESSAGES.get(code, f"Cloud-Modell: Fehler ({code})."))


@dataclass
class CloudAiSettings:
    provider: str = ""  # empty: local model only
    model: str = ""
    use_for_import: bool = False
    use_for_cover: bool = False
    consent_version: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def uses(self, task: Task) -> bool:
        return self.use_for_import if task == "import" else self.use_for_cover


def _data_dir() -> Path:
    from core.platform_paths import user_data_dir

    return user_data_dir()


def settings_path() -> Path:
    return _data_dir() / SETTINGS_FILE


def load_settings() -> CloudAiSettings:
    try:
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return CloudAiSettings()
    if not isinstance(raw, dict):
        return CloudAiSettings()
    settings = CloudAiSettings(
        provider=str(raw.get("provider") or ""),
        model=str(raw.get("model") or ""),
        use_for_import=raw.get("use_for_import") is True,
        use_for_cover=raw.get("use_for_cover") is True,
        consent_version=_as_int(raw.get("consent_version")),
    )
    if settings.provider not in PROVIDERS:
        settings.provider = ""
    return settings


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def save_settings(settings: CloudAiSettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(settings)
    data.pop("extra", None)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _account(provider_id: str) -> str:
    return f"cloud_ai_{provider_id}"


def store_api_key(provider_id: str, key: str) -> None:
    from integrations.secure_tokens import store_token

    if provider_id not in PROVIDERS:
        raise ValueError("unknown_provider")
    key = key.strip()
    if not key or any(ch.isspace() for ch in key):
        raise ValueError("invalid_key")
    store_token(_account(provider_id), {"api_key": key}, fallback_dir=_data_dir())


def load_api_key(provider_id: str) -> str:
    from integrations.secure_tokens import SecureStorageError, load_token

    try:
        payload = load_token(_account(provider_id), fallback_dir=_data_dir())
    except SecureStorageError:
        return ""
    return str((payload or {}).get("api_key") or "")


def delete_api_key(provider_id: str) -> None:
    from integrations.secure_tokens import delete_token

    delete_token(_account(provider_id), fallback_dir=_data_dir())


def active_settings(task: Task) -> CloudAiSettings | None:
    """The cloud settings to use for ``task``, or ``None`` when the local model does it."""
    settings = load_settings()
    if not (settings.provider and settings.model and settings.uses(task)):
        return None
    if settings.consent_version < CONSENT_VERSION:
        return None
    if not load_api_key(settings.provider):
        return None
    return settings


# --- HTTP (OpenAI chat-completions format) ---------------------------------------------------------------


def _openai_error(status: int, body: str) -> CloudAiError:
    text = body.lower()
    if status in (401, 403):
        return CloudAiError("auth", f"http_{status}")
    if status == 402 or "insufficient_quota" in text or ("credit" in text and status == 429):
        return CloudAiError("quota", f"http_{status}")
    if status == 429:
        return CloudAiError("rate_limit", "http_429")
    if status == 404 or "model_not_found" in text or "does not exist" in text:
        return CloudAiError("model", f"http_{status}")
    return CloudAiError("bad_response", f"http_{status}")


def _openai_request(provider: Provider, key: str, method: str, path: str, payload: dict | None = None,
                    timeout: float = REQUEST_TIMEOUT_S) -> dict:
    import httpx

    url = provider.base_url + path
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise CloudAiError("network", "timeout") from exc
    except httpx.HTTPError as exc:
        raise CloudAiError("network", type(exc).__name__) from exc
    if response.status_code >= 400:
        raise _openai_error(response.status_code, response.text[:2000])
    try:
        data = response.json()
    except ValueError as exc:
        raise CloudAiError("bad_response", "not_json") from exc
    if not isinstance(data, dict):
        raise CloudAiError("bad_response", "not_object")
    return data


def _openai_chat(provider: Provider, key: str, model: str, messages: list[dict[str, str]],
                 *, json_output: bool, timeout: float) -> str:
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if json_output:
        payload["response_format"] = {"type": "json_object"}
    data = _openai_request(provider, key, "POST", "/chat/completions", payload, timeout=timeout)
    try:
        choice = data["choices"][0]
        text = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CloudAiError("bad_response", "no_choice") from exc
    if choice.get("finish_reason") == "length":
        raise CloudAiError("truncated", "length")
    if choice.get("finish_reason") == "content_filter" or not isinstance(text, str) or not text.strip():
        raise CloudAiError("refused" if choice.get("finish_reason") == "content_filter" else "bad_response",
                           str(choice.get("finish_reason")))
    return text


# --- Claude (official Anthropic SDK) ---------------------------------------------------------------------


def _anthropic_client(key: str, timeout: float):
    import anthropic

    return anthropic.Anthropic(api_key=key, timeout=timeout, max_retries=2)


def _anthropic_errors(call):
    import anthropic

    try:
        return call()
    except anthropic.AuthenticationError as exc:
        raise CloudAiError("auth", "401") from exc
    except anthropic.PermissionDeniedError as exc:
        raise CloudAiError("auth", "403") from exc
    except anthropic.NotFoundError as exc:
        raise CloudAiError("model", "404") from exc
    except anthropic.RateLimitError as exc:
        raise CloudAiError("rate_limit", "429") from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code == 402:
            raise CloudAiError("quota", "402") from exc
        raise CloudAiError("bad_response", f"http_{exc.status_code}") from exc
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
        raise CloudAiError("network", type(exc).__name__) from exc


def _anthropic_chat(key: str, model: str, messages: list[dict[str, str]], *, timeout: float) -> str:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    turns = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") in ("user", "assistant")]
    client = _anthropic_client(key, timeout)
    kwargs: dict[str, Any] = {"model": model, "max_tokens": 16000, "messages": turns}
    if system:
        kwargs["system"] = system
    if model in _ANTHROPIC_FALLBACK_MODELS:
        # A request the model declines is re-run server-side on a model that can answer it.
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        response = _anthropic_errors(lambda: client.beta.messages.create(**kwargs))
    else:
        response = _anthropic_errors(lambda: client.messages.create(**kwargs))
    if response.stop_reason == "refusal":
        raise CloudAiError("refused", str(getattr(getattr(response, "stop_details", None), "category", "") or ""))
    if response.stop_reason == "max_tokens":
        raise CloudAiError("truncated", "max_tokens")
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    if not text.strip():
        raise CloudAiError("bad_response", "empty")
    return text


# --- public calls ----------------------------------------------------------------------------------------


def list_models(provider_id: str, key: str, *, timeout: float = 30.0) -> list[str]:
    """Model names the key can use, from the provider itself (also proves that the key works)."""
    provider = PROVIDERS[provider_id]
    if provider.api_style == "anthropic":
        client = _anthropic_client(key, timeout)
        ids = _anthropic_errors(lambda: [model.id for model in client.models.list()])
    else:
        data = _openai_request(provider, key, "GET", "/models", timeout=timeout)
        ids = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
    if not ids:
        raise CloudAiError("bad_response", "no_models")
    return sorted(dict.fromkeys(ids))


def chat(messages: list[dict[str, str]], *, task: Task, json_output: bool,
         settings: CloudAiSettings | None = None, timeout: float = REQUEST_TIMEOUT_S) -> str:
    """Send ``messages`` to the configured cloud model for ``task``; returns the model's text."""
    settings = settings or active_settings(task)
    if settings is None:
        raise CloudAiError("not_configured")
    key = load_api_key(settings.provider)
    if not key:
        raise CloudAiError("no_key")
    provider = PROVIDERS[settings.provider]
    logger.info("cloud_ai_request provider=%s task=%s json=%s", provider.id, task, int(json_output))
    if provider.api_style == "anthropic":
        text = _anthropic_chat(key, settings.model, messages, timeout=timeout)
    else:
        text = _openai_chat(provider, key, settings.model, messages, json_output=json_output, timeout=timeout)
    logger.info("cloud_ai_answer provider=%s task=%s chars=%s", provider.id, task, len(text))
    return text
