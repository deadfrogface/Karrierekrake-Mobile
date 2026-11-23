"""Günther die Krake — optional local AI intelligence for Karrierekrake.

Günther may THINK. Karrierekrake DECIDES. The USER authorizes consequential actions.
LLM output is untrusted input — validate everything. No cloud AI required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guenther.service import GuentherService, get_guenther_service

__all__ = ["GuentherService", "get_guenther_service"]


def __getattr__(name: str):
    # The service pulls in pydantic contracts and validation; the start page only reads the model setup.
    if name in __all__:
        from guenther import service

        return getattr(service, name)
    raise AttributeError(f"module 'guenther' has no attribute {name!r}")
