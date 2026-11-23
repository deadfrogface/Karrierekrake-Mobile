"""Repository backup: one verified git bundle that can be cloned again."""
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("backup_repo", ROOT / "scripts/backup_repo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_is_written_verified_and_clonable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "test@example.org"], ["config", "user.name", "Test"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    module = _module()
    module.ROOT = repo
    bundle = module.backup(tmp_path / "out")
    assert bundle.is_file() and Path(str(bundle) + ".sha256").read_text().endswith(bundle.name + "\n")
    subprocess.run(["git", "clone", "-q", str(bundle), str(tmp_path / "restored")], check=True)
    assert (tmp_path / "restored" / "a.txt").read_text(encoding="utf-8") == "x"


def test_usage_without_target():
    import sys

    result = subprocess.run([sys.executable, str(ROOT / "scripts/backup_repo.py")], capture_output=True, text=True)
    assert result.returncode != 0 and "git clone" in result.stderr
