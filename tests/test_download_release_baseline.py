import pytest

from scripts.download_release_baseline import SAVE_AS, SUFFIXES, identity_from_manifest, pick_asset


def _release(tag, published, names, draft=False):
    return {"tag_name": tag, "published_at": published, "draft": draft,
            "assets": [{"name": n, "url": f"https://api.github.com/assets/{n}", "size": 1} for n in names]}


def test_newest_published_release_with_the_platform_file_wins():
    releases = [
        _release("old", "2026-11-11T00:00:00Z", ["Karrierekrake-Alpha-1.1-Linux-x86_64.tar.gz"]),
        _release("draft", None, ["Karrierekrake-Alpha-1.2-Linux-x86_64.tar.gz"], draft=True),
        _release("new", "2026-11-13T00:00:00Z", ["Karrierekrake-Alpha-1.1-Linux-x86_64.tar.gz", "update-manifest.json"]),
        _release("mac-only", "2026-11-14T00:00:00Z", ["Karrierekrake-Alpha-1.1-macOS-Intel.dmg"]),
    ]
    tag, asset = pick_asset(releases, SUFFIXES["linux-x86_64"])
    assert tag == "new" and asset["name"].endswith("Linux-x86_64.tar.gz")


def test_no_release_with_the_file_is_an_error():
    with pytest.raises(LookupError):
        pick_asset([_release("x", "2026-11-13T00:00:00Z", ["notes.txt"])], SUFFIXES["windows"])


def test_windows_zip_gets_the_name_the_upgrade_test_looks_for():
    assert SAVE_AS["windows"] == "Karrierekrake-Windows.zip"


def test_identity_is_the_manifest_without_release_fields():
    identity = {"target": "linux-x86_64", "commit": "abc", "sequence": 7, "version": "Alpha 1.1"}
    manifest = dict(identity, protocol=1, tag="update-7-abc", size=10, sha256="00", url="https://x", model={"a": 1})
    assert identity_from_manifest(manifest) == identity
