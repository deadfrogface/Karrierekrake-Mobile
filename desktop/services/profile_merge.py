"""Moved to core.profile_merge (shared with the phone app); this name stays for existing imports."""
import sys

from core import profile_merge as _moved

sys.modules[__name__] = _moved
