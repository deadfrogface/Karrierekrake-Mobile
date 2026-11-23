"""Move settings and profile to another computer (e.g. a new laptop) with one file.

Version 2 files carry the app settings, the search profile (skills, keywords, wished roles, filters, languages,
experience) and the applicant data, so nothing has to be typed in again. They never carry file paths, account
names or keys, CV files or applications. Switches that let the app act on the user's behalf (send applications
or mails, write to the calendar, leave test mode) are never taken from a file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import SettingsConfig

FORMAT = "karrierekrake-settings"
VERSION = 2
MAX_FILE_BYTES = 5_000_000

# Device-specific or personal: never written to the file.
PRIVATE_FIELDS = frozenset({
    "database_path", "logs_dir", "browser_profile_dir", "browser_automation_profile", "gmail_credentials_path",
    "local_calendar_path", "local_calendar_feed_url", "imap_host", "imap_username", "caldav_base_url",
    "caldav_username", "microsoft_client_id", "microsoft_redirect_uri", "oauth_privacy_policy_url",
    "oauth_homepage_url", "oauth_environment", "gmail_exclude_senders", "cover_letter_template",
})
# Let the app act for the user: exported for reference, never imported.
GUARDED_FIELDS = frozenset({
    "mode", "dry_run", "automatic_submission", "run_automatically", "allow_employer_email_send",
    "email_draft_only", "allow_calendar_write", "browser_stealth", "browser_humanized", "mail_provider",
    "calendar_provider", "gmail_sync_enabled", "calendar_freebusy_enabled", "start_with_windows",
})
_SECRET_HINTS = ("token", "secret", "password", "api_key", "credential")


def _exportable(name: str) -> bool:
    return name not in PRIVATE_FIELDS and not any(hint in name for hint in _SECRET_HINTS)


def export_settings(settings: SettingsConfig, path: str | Path, *, app_version: str = "") -> Path:
    data = {k: v for k, v in asdict(settings).items() if _exportable(k)}
    payload = {"format": FORMAT, "version": VERSION, "app_version": app_version,
               "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "settings": data}
    path = Path(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


class SettingsImportError(ValueError):
    pass


def _same_type(default: Any, value: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str) and len(value) <= 2000
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value) and len(value) <= 200
    if default is None or isinstance(default, dict):
        return value is None or isinstance(value, dict)
    return False


def import_settings(current: SettingsConfig, path: str | Path) -> tuple[SettingsConfig, list[str], list[str]]:
    """Return (new settings, applied names, skipped names). ``current`` is not changed."""
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise SettingsImportError("too_large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SettingsImportError("not_json") from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT or not isinstance(payload.get("settings"), dict):
        raise SettingsImportError("wrong_format")
    if not isinstance(payload.get("version"), int) or payload["version"] > VERSION:  # v1 = settings only
        raise SettingsImportError("newer_version")
    defaults = SettingsConfig()
    known = {f.name for f in fields(SettingsConfig)}
    values = asdict(current)
    applied, skipped = [], []
    for name, value in payload["settings"].items():
        if (name not in known or not _exportable(name) or name in GUARDED_FIELDS
                or not _same_type(getattr(defaults, name), value)):
            skipped.append(str(name))
            continue
        if values.get(name) != value:
            values[name] = value
            applied.append(name)
    return SettingsConfig(**values), sorted(applied), sorted(skipped)


def _without_paths(data: dict) -> dict:
    return {k: v for k, v in data.items() if not str(k).endswith("_path")}


def export_all(config, path: str | Path, *, app_version: str = "") -> Path:
    """Settings + profile + applicant data, serialised exactly like the app's own config files."""
    import tempfile

    from core.config import _load_yaml, save_config

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        save_config(config, profile_path=tmp_path / "p.yaml", application_path=tmp_path / "a.yaml",
                    settings_path=tmp_path / "s.yaml")
        profile = _load_yaml(tmp_path / "p.yaml")
        application = _without_paths(_load_yaml(tmp_path / "a.yaml"))
    path = export_settings(config.settings, path, app_version=app_version)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update({"profile": profile, "application": application})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def import_all(config, path: str | Path):
    """Return (new config, applied setting names, skipped setting names, profile_included).

    Settings follow the rules of ``import_settings``. Profile and applicant data replace the current ones when the
    file has them; device-specific paths on this computer (e.g. the stored CV) are kept.
    """
    import copy
    import tempfile

    from core.config import _dump_yaml, load_config

    settings, applied, skipped = import_settings(config.settings, path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    new = copy.deepcopy(config)
    new.settings = settings
    profile, application = payload.get("profile"), payload.get("application")
    included = isinstance(profile, dict) or isinstance(application, dict)
    if included:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _dump_yaml(tmp_path / "p.yaml", profile if isinstance(profile, dict) else {})
            _dump_yaml(tmp_path / "a.yaml", _without_paths(application) if isinstance(application, dict) else {})
            _dump_yaml(tmp_path / "s.yaml", {})
            loaded = load_config(profile_path=tmp_path / "p.yaml", application_path=tmp_path / "a.yaml",
                                 settings_path=tmp_path / "s.yaml", root=config.root, strip_placeholders=False)
        if isinstance(profile, dict):
            new.profile = loaded.profile
        if isinstance(application, dict):
            keep = {k: getattr(config.application, k) for k in vars(config.application) if k.endswith("_path")}
            new.application = loaded.application
            for key, value in keep.items():
                setattr(new.application, key, value)
    return new, applied, skipped, included
