"""Repo-wide pytest hooks (applies to tests/ and tools/**/tests alike)."""

from __future__ import annotations

import os

import pytest

# Tests never fetch job ad pages in the background (the applications page would otherwise go online).
os.environ.setdefault("KARRIEREKRAKE_NO_AD_PAGE_CAPTURE", "1")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record the pytest node id on the JUnit testcase.

    The unit-tests shard gate compares these ids to ``pytest --collect-only``.
    Counts are not enough: one id run twice and another missing still sum equal.
    Skipped tests are included; the property is attached on teardown, which is
    the report pytest writes into the JUnit file. It lives at the repo root so
    collected tests outside ``tests/`` (``tools/perf/thinkpad/tests``) carry it too.
    """
    outcome = yield
    report = outcome.get_result()
    if getattr(report, "when", None) == "teardown":
        report.user_properties.append(("nodeid", item.nodeid))
