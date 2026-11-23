"""Weekly hours and working days: read them from a job ad and compare them with the user's wish."""
from __future__ import annotations

import re

WEEKDAYS = ("mo", "di", "mi", "do", "fr", "sa", "so")
_UNIT = r"(?:std\.?|stunden|h)"
_WEEK = r"(?:/\s*woche|pro\s+woche|in\s+der\s+woche|wöchentlich|/\s*wo\.?|/\s*week|per\s+week|a\s+week)"
_NUM = r"(\d{1,2})(?:[,.]\d)?"
_PATTERNS = (
    re.compile(_NUM + r"\s*(?:-|–|bis|to)\s*" + _NUM + r"\s*" + _UNIT + r"\s*" + _WEEK, re.I),
    re.compile(_NUM + r"\s*(?:-|–|bis|to)\s*" + _NUM + r"\s*(?:wochenstunden|stunden-woche|hours)", re.I),
    re.compile(_NUM + r"\s*" + _UNIT + r"\s*" + _WEEK, re.I),
    re.compile(_NUM + r"\s*(?:wochenstunden|stunden-woche|-stunden-woche|hours\s+per\s+week)", re.I),
    re.compile(r"(?:wochenarbeitszeit|wöchentliche\s+arbeitszeit|arbeitszeit)\D{0,25}?" + _NUM
               + r"(?:\s*(?:-|–|bis)\s*" + _NUM + r")?\s*" + _UNIT, re.I),
)
_WEEKEND = re.compile(r"wochenende|samstag|sonntag|sa\.?\s*/\s*so\.?|weekend|saturday|sunday", re.I)


def parse_weekly_hours(text: str) -> tuple[int, int] | None:
    """(min, max) weekly hours stated in the ad, or None. Implausible numbers are ignored."""
    for pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            numbers = [int(g) for g in match.groups() if g]
            low, high = min(numbers), max(numbers)
            if 1 <= low <= high <= 60:
                return low, high
    return None


def mentions_weekend(text: str) -> bool:
    return bool(_WEEKEND.search(text or ""))


def hours_label(low: int, high: int) -> str:
    return f"{low} Std./Woche" if low == high else f"{low}–{high} Std./Woche"


def compare(job_text: str, *, wish_min: int, wish_max: int, work_days: list[str]) -> tuple[list[str], list[str]]:
    """Return (reasons, issues) in plain German for the fit explanation."""
    reasons: list[str] = []
    issues: list[str] = []
    if wish_min or wish_max:
        wish_low, wish_high = wish_min or 1, wish_max or 60
        found = parse_weekly_hours(job_text)
        if found:
            low, high = found
            if low <= wish_high and high >= wish_low:
                reasons.append(f"Arbeitszeit passt: {hours_label(low, high)}")
            else:
                issues.append(f"Arbeitszeit: Anzeige {hours_label(low, high)}, gewünscht {hours_label(wish_low, wish_high)}")
    days = {d.lower()[:2] for d in work_days or []}
    if days and not ({"sa", "so"} & days) and mentions_weekend(job_text):
        issues.append("Anzeige erwähnt Arbeit am Wochenende")
    return reasons, issues
