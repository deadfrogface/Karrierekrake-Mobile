"""A short, stable code for this computer, used to bind a license key to the buyer's devices.

It is derived from the operating system's own installation ID and hashed with a product salt, so it reveals
nothing about the computer and cannot be turned back into the original ID. Reinstalling the operating system
changes it; the owner then issues a new key.
"""
from __future__ import annotations

import hashlib
import platform
import re
import subprocess  # nosec B404 - fixed system commands below, no user input
import sys
import uuid
from pathlib import Path

_SALT = b"karrierekrake-device-v1"
_CODE = re.compile(r"^KK(-[0-9A-F]{4}){4}$")


def _windows_id() -> str:
    import winreg  # type: ignore[import-not-found]

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
        return str(winreg.QueryValueEx(key, "MachineGuid")[0])


def _mac_id() -> str:
    out = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],  # nosec B603
                         capture_output=True, text=True, timeout=5, check=False).stdout
    match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
    return match.group(1) if match else ""


def _linux_id() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text(encoding="ascii").strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def raw_machine_id() -> str:
    try:
        if sys.platform == "win32":
            return _windows_id()
        if sys.platform == "darwin":
            return _mac_id()
        return _linux_id()
    except Exception:  # noqa: BLE001 - fall back below
        return ""


def device_code(raw: str | None = None) -> str:
    """KK-XXXX-XXXX-XXXX-XXXX (64 bits of a salted SHA-256)."""
    source = raw if raw is not None else raw_machine_id()
    if not source:  # last resort: hardware address + host name, still stable on most machines
        source = f"{uuid.getnode():x}-{platform.node()}"
    digest = hashlib.sha256(_SALT + source.strip().lower().encode("utf-8")).hexdigest().upper()[:16]
    return "KK-" + "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def is_device_code(value: str) -> bool:
    return bool(_CODE.match((value or "").strip().upper()))
