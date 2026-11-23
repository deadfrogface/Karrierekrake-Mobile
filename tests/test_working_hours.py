"""Exact part-time: weekly hours and days from the ad, compared with the user's wish."""
import pytest

from core.working_hours import compare, mentions_weekend, parse_weekly_hours


@pytest.mark.parametrize("text,expected", [
    ("Teilzeit (20 Std./Woche)", (20, 20)),
    ("Arbeitszeit: 20-30 Stunden pro Woche", (20, 30)),
    ("25 bis 30 Wochenstunden", (25, 30)),
    ("in Teilzeit mit 30 Stunden wöchentlich", (30, 30)),
    ("Die wöchentliche Arbeitszeit beträgt 39,5 Stunden", (39, 39)),
    ("part-time, 15-20 hours per week", (15, 20)),
    ("eine 4-Tage-Woche", None),
    ("Gehalt 3000 Euro, 2 Standorte", None),
    ("99 Stunden pro Woche", None),
])
def test_parse_weekly_hours(text, expected):
    assert parse_weekly_hours(text) == expected


def test_overlap_is_a_reason_and_mismatch_an_issue():
    assert compare("20-30 Std./Woche", wish_min=25, wish_max=30, work_days=[]) == (["Arbeitszeit passt: 20–30 Std./Woche"], [])
    reasons, issues = compare("Vollzeit, 40 Stunden pro Woche", wish_min=20, wish_max=25, work_days=[])
    assert not reasons and issues == ["Arbeitszeit: Anzeige 40 Std./Woche, gewünscht 20–25 Std./Woche"]


def test_no_wish_or_no_hours_says_nothing():
    assert compare("40 Stunden pro Woche", wish_min=0, wish_max=0, work_days=[]) == ([], [])
    assert compare("Teilzeit", wish_min=20, wish_max=30, work_days=[]) == ([], [])


def test_weekend_hint_only_when_user_excludes_weekends():
    text = "Schichtdienst inkl. Wochenende"
    assert mentions_weekend(text)
    assert compare(text, wish_min=0, wish_max=0, work_days=["mo", "di", "mi"])[1] == ["Anzeige erwähnt Arbeit am Wochenende"]
    assert compare(text, wish_min=0, wish_max=0, work_days=["mo", "sa"]) == ([], [])
    assert compare(text, wish_min=0, wish_max=0, work_days=[]) == ([], [])


def test_matcher_uses_the_wish(tmp_path):
    from core.config import empty_app_config
    from core.matcher import score_job
    from core.models import Job

    cfg = empty_app_config(root=tmp_path)
    cfg.profile.employment.part_time = True
    cfg.profile.employment.weekly_hours_min, cfg.profile.employment.weekly_hours_max = 20, 25
    job = Job(id="j", title="Bürokraft", company="Muster GmbH", employment_type="Teilzeit",
              description="Wir bieten 40 Stunden pro Woche.")
    result = score_job(job, cfg)
    assert any("Arbeitszeit: Anzeige 40" in r for r in result.rejection_reasons + result.match_reasons)
