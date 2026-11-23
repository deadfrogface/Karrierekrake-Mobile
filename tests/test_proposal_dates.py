"""Employer interview proposals with dates as people write them (DE/EN), with and without a year."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.scheduling_preferences import empty_scheduling_preferences, migrate_scheduling_preferences
from integrations.calendar_freebusy import MockFreeBusyProvider
from integrations.calendar_scheduling import propose_ranked_slots
from integrations.calendar_timezone import to_zone
from integrations.proposal_parse import parse_result_to_dict, parse_scheduling_proposal

REF = datetime(2026, 11, 16, 9, 0)  # a Monday


def _parse(text: str) -> dict:
    return parse_result_to_dict(parse_scheduling_proposal(text, default_tz="Europe/Berlin", reference=REF))


@pytest.mark.parametrize("text,expected", [
    ("Passt Ihnen der 24. November um 14 Uhr?", ["2026-11-24T14:00:00+01:00"]),
    ("Wie wäre es am 24.11. um 14:30 Uhr?", ["2026-11-24T14:30:00+01:00"]),
    ("Gerne am 24. November 2026 um 14:00 Uhr.", ["2026-11-24T14:00:00+01:00"]),
    ("Dienstag, 24. November um 14 Uhr", ["2026-11-24T14:00:00+01:00"]),
    ("Dienstag, den 24.11.26 um 9.30 Uhr", ["2026-11-24T09:30:00+01:00"]),
    ("Hätten Sie am 3. Dez. um 9 Uhr Zeit?", ["2026-12-03T09:00:00+01:00"]),
    ("Would November 24 at 2 pm work?", ["2026-11-24T14:00:00+01:00"]),
    ("Could you do Tuesday, Nov. 24th at 10:15am?", ["2026-11-24T10:15:00+01:00"]),
    ("am 2.3. um 9 Uhr", ["2027-03-02T09:00:00+01:00"]),  # already past this year: next March
    ("am 24.11. oder 26.11. jeweils um 10 Uhr", ["2026-11-24T10:00:00+01:00", "2026-11-26T10:00:00+01:00"]),
    ("am 24.11., 25.11. oder am 26.11. um 10 Uhr",
     ["2026-11-24T10:00:00+01:00", "2026-11-25T10:00:00+01:00", "2026-11-26T10:00:00+01:00"]),
])
def test_dated_offers_become_exactly_those_slots(text, expected):
    r = _parse(text)
    assert r["fixed_slots"] == expected
    assert r["windows"] == [] and r["explicit_slots"] == [] and r["errors"] == []


@pytest.mark.parametrize("text,expected", [
    ("am 24.11. von 14 bis 15 Uhr", [["2026-11-24T14:00:00+01:00", "2026-11-24T15:00:00+01:00"]]),
    ("Tuesday, Nov. 24, 2026 from 2 to 3 pm", [["2026-11-24T14:00:00+01:00", "2026-11-24T15:00:00+01:00"]]),
    ("Dienstag, 24.11. oder Donnerstag, 26.11., jeweils 10-11 Uhr",
     [["2026-11-24T10:00:00+01:00", "2026-11-24T11:00:00+01:00"],
      ["2026-11-26T10:00:00+01:00", "2026-11-26T11:00:00+01:00"]]),
])
def test_dated_ranges_are_the_employers_own_slots(text, expected):
    assert sorted(_parse(text)["explicit_slots"]) == expected


def test_a_weekday_with_a_date_opens_no_weekday_window():
    """"Montag, 21. September 2026, 10:30" offered one Monday, not every Monday from 9 to 17."""
    r = parse_result_to_dict(parse_scheduling_proposal(
        "Montag, 21. September 2026, 10:30", default_tz="Europe/Berlin", reference=datetime(2026, 9, 1)))
    assert r["fixed_slots"] == ["2026-09-21T10:30:00+02:00"] and r["windows"] == []


def test_weekday_and_date_that_disagree_are_asked_not_guessed():
    r = parse_scheduling_proposal("Dienstag, 25.11. um 10 Uhr", default_tz="Europe/Berlin", reference=REF)
    assert not r.ok and r.errors == ["ambiguous:weekday_date_mismatch:2026-11-25"]
    proposal = propose_ranked_slots("Dienstag, 25.11. um 10 Uhr", reference=REF.replace(tzinfo=timezone.utc))
    assert proposal.ranked_slots == [] and proposal.stop_reason.startswith("fail_safe:ambiguous")


@pytest.mark.parametrize("text", [
    "Wir haben am 24. November 2026, 3 Bewerber.",   # a bare number after a date is not an hour
    "Am 24.11. sind wir im Haus.",
    "Die Stelle ist ab 1.1.2027 zu besetzen",
])
def test_dates_without_a_clock_time_make_no_slot(text):
    assert _parse(text)["fixed_slots"] == [] and _parse(text)["explicit_slots"] == []


def test_a_date_separated_by_a_sentence_does_not_borrow_the_time():
    assert _parse("Am 24.11. sind wir im Haus. Am 26.11. um 10 Uhr passt.")["fixed_slots"] == [
        "2026-11-26T10:00:00+01:00"]


def test_dateparser_results_far_from_now_are_dropped(monkeypatch):
    import dateparser

    from integrations import proposal_parse

    far = (REF + timedelta(days=365 * 88)).replace(tzinfo=timezone(timedelta(hours=1)))
    monkeypatch.setattr(dateparser, "parse", lambda *a, **k: far)
    ref = REF.replace(tzinfo=timezone(timedelta(hours=1)))
    assert proposal_parse._try_dateparser("irgendwann", default_tz="Europe/Berlin", reference=ref) is None
    near = ref + timedelta(days=1)
    monkeypatch.setattr(dateparser, "parse", lambda *a, **k: near)
    assert proposal_parse._try_dateparser("morgen", default_tz="Europe/Berlin", reference=ref) == near


def test_offered_dates_reach_the_ranked_slots():
    prefs = migrate_scheduling_preferences(empty_scheduling_preferences())
    prefs.buffer_before_minutes = prefs.buffer_after_minutes = 0
    proposal = propose_ranked_slots("am 24.11. oder 26.11. jeweils um 10 Uhr", prefs=prefs,
                                    freebusy=MockFreeBusyProvider([]), reference=REF.replace(tzinfo=timezone.utc))
    assert proposal.status == "proposed"
    assert sorted(to_zone(s.start, "Europe/Berlin").isoformat() for s in proposal.ranked_slots) == [
        "2026-11-24T10:00:00+01:00", "2026-11-26T10:00:00+01:00"]
