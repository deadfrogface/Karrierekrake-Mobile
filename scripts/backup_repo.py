"""Full copy of the repository (all branches, tags and history) as one file, e.g. on a USB stick or NAS.

    python scripts/backup_repo.py <target folder>

Writes karrierekrake-<date>-<commit>.bundle plus a .sha256 file and checks the bundle. Restore anywhere with
    git clone karrierekrake-<…>.bundle Karrierekrake
The bundle holds only what is committed: no models, no build output, no local user data.
"""
from __future__ import annotations

import hashlib
import subprocess  # nosec B404 - fixed git commands, no shell
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()  # nosec B603 B607


def backup(target: Path) -> Path:
    target = Path(target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    head = _git("rev-parse", "--short=10", "HEAD")
    bundle = target / f"karrierekrake-{date.today().isoformat()}-{head}.bundle"
    _git("bundle", "create", str(bundle), "--all")
    _git("bundle", "verify", str(bundle))
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    Path(str(bundle) + ".sha256").write_text(f"{digest}  {bundle.name}\n", encoding="ascii")
    return bundle


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = backup(Path(sys.argv[1]))
    print(f"Sicherung geprüft: {path} ({path.stat().st_size / 1e6:.1f} MB)")
