"""A cloud model set up by the user writes the letter / reads the CV; every check after it stays local."""
import json

import pytest

from core import cloud_ai
from core.cover_quality import rewrite_cover_letter
from tests.test_cover_quality import GOOD, applicant  # noqa: F401 - fixture

CLOUD = cloud_ai.CloudAiSettings(provider="anthropic", model="claude-opus-5-5", use_for_import=True,
                                 use_for_cover=True, consent_version=cloud_ai.CONSENT_VERSION)


def _use_cloud(monkeypatch, answer):
    calls = []
    monkeypatch.setattr(cloud_ai, "active_settings", lambda task: CLOUD)

    def fake_chat(messages, **kwargs):
        calls.append((messages, kwargs))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(cloud_ai, "chat", fake_chat)
    monkeypatch.setattr("core.cv_llm_runtime.resolve_cv_model_path", lambda: pytest.fail("local model must not load"))
    monkeypatch.setattr("core.cv_llm_runtime.chat_completion_inprocess",
                        lambda *a, **k: pytest.fail("local writer must not run"))
    return calls


def test_cloud_writer_letter_passes_the_same_local_checks(applicant, monkeypatch):  # noqa: F811
    calls = _use_cloud(monkeypatch, json.dumps(dict(body=GOOD, anchors_used=[], invented_flag=False,
                                                    confidence="medium")))
    result = rewrite_cover_letter(*applicant)
    assert result.ok, result.reason
    assert result.text.strip() == GOOD.strip()
    messages, kwargs = calls[0]
    assert kwargs["task"] == "cover" and kwargs["json_output"] is True
    assert "required_profile_references" in messages[1]["content"]


def test_cloud_letter_with_invented_facts_is_still_caught_locally(applicant, monkeypatch):  # noqa: F811
    invented = GOOD.replace("Mit SAP Business One habe ich praktische Erfahrung.",
                            "Mit Zendesk und SAP Business One habe ich praktische Erfahrung.")
    _use_cloud(monkeypatch, json.dumps(dict(body=invented, anchors_used=[], invented_flag=False,
                                            confidence="medium")))
    result = rewrite_cover_letter(*applicant)
    assert "Zendesk" not in (result.text or "")


def test_cloud_error_is_reported_without_a_local_retry(applicant, monkeypatch):  # noqa: F811
    calls = _use_cloud(monkeypatch, cloud_ai.CloudAiError("quota"))
    result = rewrite_cover_letter(*applicant)
    assert not result.ok and result.reason == "cloud_quota"
    assert len(calls) == 1


def test_cv_import_reads_through_the_cloud_model(monkeypatch):
    pytest.importorskip("docpick")
    from core import cv_docpick_import as imp

    calls = _use_cloud(monkeypatch, '{"personal": {"first_name": "Mara"}}')
    data = imp._llm_extract("Mara König\nmara@example.com", transport="cloud")
    assert data["personal"]["first_name"] == "Mara"
    assert calls[0][1]["task"] == "import" and calls[0][1]["json_output"] is True


def test_cv_import_cloud_error_becomes_a_visible_import_error(monkeypatch):
    pytest.importorskip("docpick")
    from core import cv_docpick_import as imp

    _use_cloud(monkeypatch, cloud_ai.CloudAiError("auth"))
    with pytest.raises(imp.CvImportError) as err:
        imp._llm_extract("Mara König", transport="cloud")
    assert err.value.code == "cloud_auth"
