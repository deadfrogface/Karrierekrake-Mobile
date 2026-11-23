"""Where the phone app keeps API keys: a file in the app's private folder.

Android and iOS give every app its own folder that other apps cannot read; desktop keyrings do not exist there.
The core stores keys through the ``keyring`` package, so this module plugs in as its backend. Keys never go into
settings files, exports or logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from keyring.backend import KeyringBackend
except ImportError:  # keyring is a dependency; this only keeps the module importable in odd test setups
    KeyringBackend = object  # type: ignore[assignment,misc]

FILE_NAME = "keys.json"


class AppFolderKeyring(KeyringBackend):  # type: ignore[misc,valid-type]
    priority = 1

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.path = Path(folder) / FILE_NAME

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.replace(tmp, self.path)

    def get_password(self, service: str, username: str) -> str | None:
        return self._read().get(f"{service}\n{username}")

    def set_password(self, service: str, username: str, password: str) -> None:
        data = self._read()
        data[f"{service}\n{username}"] = password
        self._write(data)

    def delete_password(self, service: str, username: str) -> None:
        data = self._read()
        data.pop(f"{service}\n{username}", None)
        self._write(data)


def install(folder: Path) -> AppFolderKeyring:
    import keyring

    backend = AppFolderKeyring(folder)
    keyring.set_keyring(backend)
    return backend
