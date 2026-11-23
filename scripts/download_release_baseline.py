"""Download the package of the newest published release as the "old version" for the upgrade tests.

The upgrade tests install the previous version, then update it to the build under test. The previous version used
to come from an earlier CI run's artifact; in a private repository artifacts count against a small storage quota,
release files do not. The workflow token reads private releases.

Usage: python scripts/download_release_baseline.py --target linux-x86_64 --out <folder>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
# Release file name ends with this suffix; the upgrade scripts look the file up by this name pattern.
SUFFIXES = {
    "linux-x86_64": "Linux-x86_64.tar.gz",
    "macos-arm64": "macOS-AppleSilicon.dmg",
    "macos-x86_64": "macOS-Intel.dmg",
    "windows": "Windows-x86_64.zip",
}
# scripts/ci_windows_upgrade.py looks for exactly this name.
SAVE_AS = {"windows": "Karrierekrake-Windows.zip"}
# Keys publish_native_assets.py adds to the package identity (native-current.json) in native-manifest-<target>.json.
MANIFEST_ONLY_KEYS = ("protocol", "tag", "size", "sha256", "url", "model")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 - keep the redirect for us
        return None


def _get_json(url: str, token: str) -> object:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310  # fixed GitHub HTTPS API
        return json.loads(response.read().decode("utf-8"))


def pick_asset(releases: list[dict], suffix: str) -> tuple[str, dict]:
    """(tag, asset) of the newest published, non-draft release that has a file ending with ``suffix``."""
    for release in sorted(releases, key=lambda r: r.get("published_at") or "", reverse=True):
        if release.get("draft") or not release.get("published_at"):
            continue
        for asset in release.get("assets", []):
            if str(asset.get("name", "")).endswith(suffix):
                return release["tag_name"], asset
    raise LookupError(f"release_baseline_unavailable:{suffix}")


def identity_from_manifest(manifest: dict) -> dict:
    """native-current.json of a released package: its release manifest without the release-only fields."""
    return {key: value for key, value in manifest.items() if key not in MANIFEST_ONLY_KEYS}


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(asset: dict, token: str, target: Path) -> None:
    """Asset API with the token; the signed storage URL it redirects to must be fetched without it."""
    request = urllib.request.Request(asset["url"], headers={"Authorization": f"Bearer {token}",
                                                            "Accept": "application/octet-stream"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        response = opener.open(request, timeout=120)
    except urllib.error.HTTPError as redirect:
        if redirect.code not in (301, 302, 303, 307, 308):
            raise
        location = redirect.headers["Location"]
        if not location.startswith("https://"):
            raise ValueError("release_baseline_redirect_not_https") from None
        response = urllib.request.urlopen(location, timeout=600)  # nosec B310  # https checked above
    with response, target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if target.stat().st_size != int(asset.get("size") or -1):
        raise ValueError(f"release_baseline_size_mismatch:{target.stat().st_size}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, choices=sorted(SUFFIXES))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repository:
        print("::error title=release baseline::GITHUB_TOKEN and GITHUB_REPOSITORY are required", flush=True)
        return 1
    releases = _get_json(f"{API}/repos/{repository}/releases?per_page=30", token)
    try:
        tag, asset = pick_asset(list(releases), SUFFIXES[args.target])
    except LookupError as missing:
        print(f"::error title=release baseline::{missing}", flush=True)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / SAVE_AS.get(args.target, asset["name"])
    download(asset, token, target)
    print(f"release baseline: {tag} {asset['name']} -> {target} ({target.stat().st_size} bytes)", flush=True)
    if args.target != "windows":
        # The native upgrade test compares the package's embedded identity with native-current.json.
        release = next(r for r in releases if r.get("tag_name") == tag)
        name = f"native-manifest-{args.target}.json"
        manifest_asset = next((a for a in release.get("assets", []) if a.get("name") == name), None)
        if manifest_asset is None:
            print(f"::error title=release baseline::{name} missing in {tag}", flush=True)
            return 1
        manifest_path = args.out / name
        download(manifest_asset, token, manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != _sha256(target):
            print("::error title=release baseline::package does not match its release manifest", flush=True)
            return 1
        (args.out / "native-current.json").write_text(json.dumps(identity_from_manifest(manifest), indent=2),
                                                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
