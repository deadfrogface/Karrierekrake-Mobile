"""One place where the program opens a URL with ``urllib``.

``urllib.request.urlopen`` also opens ``file:``, ``ftp:`` and ``data:`` URLs. Every URL the program
opens is a web address, so anything other than ``https`` (and ``http`` where a caller allows it, e.g. a
local Ollama or routing server) is refused before a connection is made.
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any


class UnsafeUrlError(ValueError):
    """The URL does not use an allowed web scheme."""


def check_url(url: str, *, allow_http: bool = False) -> str:
    """Return ``url`` when its scheme is allowed; raise :class:`UnsafeUrlError` otherwise."""
    parts = urllib.parse.urlsplit(str(url))
    allowed = {"https", "http"} if allow_http else {"https"}
    if parts.scheme.lower() not in allowed or not parts.hostname:
        raise UnsafeUrlError(f"url_scheme_not_allowed:{parts.scheme or '-'}")
    return str(url)


def open_url(request: urllib.request.Request | str, *, timeout: float, context: Any = None,
             allow_http: bool = False) -> Any:
    """``urllib.request.urlopen`` for web addresses only (see :func:`check_url`)."""
    url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
    check_url(url, allow_http=allow_http)
    if context is not None:
        return urllib.request.urlopen(request, timeout=timeout, context=context)  # nosec B310  # scheme checked
    return urllib.request.urlopen(request, timeout=timeout)  # nosec B310  # scheme checked
