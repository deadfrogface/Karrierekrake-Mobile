import urllib.request

import pytest

from core.security.url_open import UnsafeUrlError, check_url, open_url


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x", "data:text/plain,hi",
                                 "http://example.org/", "https:///no-host", "C:\\\\models\\\\x.gguf"])
def test_non_web_or_plain_http_urls_are_refused(url):
    with pytest.raises(UnsafeUrlError):
        check_url(url)


def test_http_only_where_the_caller_allows_it():
    assert check_url("http://127.0.0.1:11434/api/tags", allow_http=True)
    with pytest.raises(UnsafeUrlError):
        check_url("file:///etc/passwd", allow_http=True)


def test_refused_url_never_reaches_urlopen(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("opened"))
    with pytest.raises(UnsafeUrlError):
        open_url(urllib.request.Request("file:///etc/passwd"), timeout=1)


def test_https_request_is_passed_on(monkeypatch):
    seen = {}

    def fake(request, **kwargs):
        seen["url"], seen["kwargs"] = request.full_url, kwargs
        return "response"

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert open_url(urllib.request.Request("https://example.org/x"), timeout=5) == "response"
    assert seen == {"url": "https://example.org/x", "kwargs": {"timeout": 5}}
