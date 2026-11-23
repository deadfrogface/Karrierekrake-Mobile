"""The production model is never taken from a folder other accounts can write to."""
from pathlib import Path

from core import cv_llm_runtime


def test_shared_temp_folders_are_not_searched(monkeypatch, tmp_path):
    monkeypatch.delenv("KARRIEREKRAKE_CV_LLM_MODEL", raising=False)
    monkeypatch.setenv("KARRIEREKRAKE_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr("guenther.setup_models.selected_model_id", lambda: None)
    monkeypatch.setattr(cv_llm_runtime, "bundled_cv_model_candidates", lambda: [])
    real_is_file = Path.is_file

    def planted(path: Path) -> bool:
        text = path.as_posix()
        if text.startswith(("/tmp/karrierekrake-models/", "/var/tmp/karrierekrake-models/")):
            return True  # a file another account left there
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", planted)

    assert cv_llm_runtime.resolve_cv_model_path() is None
