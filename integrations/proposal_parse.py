"""Natural-language employer scheduling proposal parser (DE/EN).

Understands phrases like:
  \"Dienstag oder Mittwoch zwischen 9 und 15 Uhr\"
  \"Tue/Wed 9am–3pm\"
  \"am 20.09.2026 um 14:00\"
  \"Passt Ihnen der 24. November um 14 Uhr?\" / \"am 24.11. von 14 bis 15 Uhr\"
  \"Would Tuesday, November 24 at 2 pm work?\"

A date without a year is the next such day from the reference date on. A dated proposal is a
fixed offer: weekday names in it name that day and do not open weekday windows.

Fail-closed on timezone ambiguity: fixed clock times without zone context are
anchored only when the caller supplies ``default_tz``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from integrations.calendar_timezone import (
    TimezoneAmbiguityError,
    combine_local,
    parse_iso_datetime,
    resolve_zone,
)

WEEKDAY_DE = {
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonntag": 6,
}
WEEKDAY_EN = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "mon": 0,
    "tue": 1,
    "tues": 1,
    "wed": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
WEEKDAY_ALIASES = {**WEEKDAY_DE, **WEEKDAY_EN}

MONTH_DE = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}
MONTH_ALIASES = {
    **MONTH_DE,
    "jan": 1, "feb": 2, "mär": 3, "maer": 3, "mrz": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7, "october": 10,
    "december": 12, "mar": 3, "oct": 10, "dec": 12,
}

_WINDOW_RE = re.compile(
    r"(?:zwischen|between)\s+(\d{1,2})(?::(\d{2}))?\s*(?:uhr|h|am|pm)?"
    r"\s+(?:und|and|–|-|—)\s+(\d{1,2})(?::(\d{2}))?\s*(?:uhr|h|am|pm)?",
    re.I,
)
_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(?:uhr|h)?\s*(?:–|-|—|bis|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*(?:uhr|h)?",
    re.I,
)
_MONTH_NAMES = "|".join(sorted(MONTH_ALIASES, key=len, reverse=True))
_WEEKDAY_NAMES = "|".join(sorted(WEEKDAY_ALIASES, key=len, reverse=True))
# One dated proposal: optional weekday, a date (24.11.2026 / 24.11. / 24. November [2026] /
# November 24[, 2026]), then a start time and optionally an end time. "Dienstag, 27.10.2026,
# 10:00-11:00 Uhr" and "am 24.11. von 14 bis 15 Uhr" are explicit employer slots with their own end.
_DATE_PART = (
    rf"(?:\b(?P<wd>{_WEEKDAY_NAMES})\b\.?,?\s+(?:(?:den|the)\s+)?)?"
    r"(?:"
    r"(?<![\d.:])(?P<d1>\d{1,2})\.(?P<m1>\d{1,2})\.(?P<y1>\d{4}|\d{2}(?!\d))?"
    rf"|\b(?P<d2>\d{{1,2}})\.?\s*(?P<mon2>{_MONTH_NAMES})\b\.?(?:\s+(?P<y2>\d{{4}}))?"
    rf"|\b(?P<mon3>{_MONTH_NAMES})\b\.?\s+(?P<d3>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(?P<y3>\d{{4}}))?"
    r")"
)
_DATE_ONLY = re.compile(_DATE_PART, re.IGNORECASE)
# "am 24.11. oder 26.11. jeweils um 10 Uhr": the dates before a dated offer share its time when
# only these words stand between them.
_SHARED_TIME_GAP = re.compile(
    r"(?:[\s,;/&+]|\b(?:oder|und|bzw|sowie|am|den|jeweils|or|and|on|the|each)\b\.?)*", re.IGNORECASE
)
_DATED = re.compile(
    _DATE_PART +
    r"[,\s]+(?:(?:jeweils|each)\s+)?(?:(?:um|ab|gegen|von|at|from)\s+)?"
    r"(?P<h>\d{1,2})(?:[:\.](?P<mi>\d{2}))?\s*(?P<u>uhr|h\b|a\.?m\.?|p\.?m\.?)?"
    r"(?:\s*(?:–|-|—|bis|to|until)\s*(?P<h2>\d{1,2})(?:[:\.](?P<mi2>\d{2}))?"
    r"\s*(?P<u2>uhr|h\b|a\.?m\.?|p\.?m\.?)?)?",
    re.IGNORECASE,
)
_ISO_FIXED = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)
_ONSITE_RE = re.compile(
    r"\b(vor\s*ort|onsite|on-site|persönlich|persoenlich|in\s+unserem\s+büro)\b", re.I
)
_REMOTE_RE = re.compile(
    r"\b(remote|online|video|teams|zoom|google\s*meet|telefon|phone|virtuell)\b", re.I
)


@dataclass(frozen=True)
class ProposalWindow:
    """A flexible day + local time window (timezone-aware bounds when resolved)."""

    weekdays: tuple[int, ...]
    start_time: time
    end_time: time
    fixed_dates: tuple[date, ...] = ()
    modality: str = "remote"
    raw_text: str = ""
    timezone: str = "Europe/Berlin"
    ambiguous: bool = False
    ambiguity_reason: str = ""

    def is_usable(self) -> bool:
        return (
            not self.ambiguous
            and (bool(self.weekdays) or bool(self.fixed_dates))
            and self.start_time < self.end_time
        )


@dataclass
class ParseResult:
    windows: list[ProposalWindow] = field(default_factory=list)
    fixed_slots: list[datetime] = field(default_factory=list)
    # Employer-offered slots with explicit start and end (authoritative when present).
    explicit_slots: list[tuple[datetime, datetime]] = field(default_factory=list)
    modality: str = "unknown"
    raw_text: str = ""
    errors: list[str] = field(default_factory=list)
    used_dateparser: bool = False

    @property
    def ok(self) -> bool:
        return (bool(self.windows) or bool(self.fixed_slots) or bool(self.explicit_slots)) and not any(
            e.startswith("ambiguous") or e.startswith("timezone") for e in self.errors
        )


def _clock(h: int, m: int = 0) -> time:
    h = max(0, min(23, int(h)))
    m = max(0, min(59, int(m)))
    return time(h, m)


def _hour(h: str, minutes: str | None, unit: str | None) -> time | None:
    hour, minute = int(h), int(minutes or 0)
    marker = (unit or "").lower().replace(".", "")
    if marker == "pm" and hour < 12:
        hour += 12
    elif marker == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _date_of(m: re.Match, ref_day: date) -> tuple[date, int | None] | None:
    if m.group("d1"):
        day, month, year = int(m.group("d1")), int(m.group("m1")), m.group("y1")
    elif m.group("d2"):
        day, month, year = int(m.group("d2")), MONTH_ALIASES[m.group("mon2").lower()], m.group("y2")
    else:
        day, month, year = int(m.group("d3")), MONTH_ALIASES[m.group("mon3").lower()], m.group("y3")
    try:
        if year:
            found = date(int(year) + (2000 if len(year) == 2 else 0), month, day)
        else:
            found = date(ref_day.year, month, day)
            if found < ref_day:
                found = date(ref_day.year + 1, month, day)
    except ValueError:
        return None
    wd = m.group("wd")
    return found, (WEEKDAY_ALIASES[wd.lower()] if wd else None)


def _dated_offers(text: str, ref_day: date) -> list[tuple[date, time, time | None, int | None]]:
    """(day, start, end-or-None, weekday-or-None) for every dated proposal in ``text``."""
    timed: list[tuple[int, int, date, time, time | None, int | None]] = []
    for m in _DATED.finditer(text):
        if not (m.group("mi") or m.group("u") or (m.group("h2") and (m.group("mi2") or m.group("u2")))):
            continue  # "24. November 2026, 3 Bewerber": a bare number is never read as an hour
        dated = _date_of(m, ref_day)
        if dated is None:
            continue
        found, weekday = dated
        start = _hour(m.group("h"), m.group("mi"), m.group("u"))
        if start is None:
            continue
        end = None
        if m.group("h2"):
            # "2 to 3 pm": the end's am/pm also applies to the start.
            unit2 = m.group("u2") or m.group("u")
            end = _hour(m.group("h2"), m.group("mi2"), unit2)
            if m.group("u") is None and unit2 and unit2.lower().startswith("p") and start.hour < 12:
                start = _hour(m.group("h"), m.group("mi"), unit2)
        timed.append((m.start(), m.end(), found, start, end, weekday))

    offers = [(day, start, end, weekday) for _s, _e, day, start, end, weekday in timed]
    for m in _DATE_ONLY.finditer(text):
        if any(s <= m.start() < e for s, e, *_rest in timed):
            continue
        following = next((t for t in timed if t[0] >= m.end()), None)
        if following is None:
            continue
        gap = _DATE_ONLY.sub(" ", text[m.end():following[0]])
        if not _SHARED_TIME_GAP.fullmatch(gap):
            continue
        dated = _date_of(m, ref_day)
        if dated is not None:
            offers.append((dated[0], following[3], following[4], dated[1]))
    return sorted(offers, key=lambda offer: (offer[0], offer[1]))


def _extract_weekdays(text: str) -> list[int]:
    lowered = text.lower()
    found: list[int] = []
    for name, idx in sorted(WEEKDAY_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            if idx not in found:
                found.append(idx)
    return found


def _extract_modality(text: str) -> str:
    if _ONSITE_RE.search(text):
        return "onsite"
    if _REMOTE_RE.search(text):
        return "remote"
    return "unknown"


def _extract_time_window(text: str) -> tuple[time, time] | None:
    for rx in (_WINDOW_RE, _RANGE_RE):
        m = rx.search(text)
        if not m:
            continue
        sh, sm, eh, em = m.group(1), m.group(2), m.group(3), m.group(4)
        start = _clock(int(sh), int(sm or 0))
        end = _clock(int(eh), int(em or 0))
        if start < end:
            return start, end
    return None


def _upcoming_weekdays(ref: date, weekdays: list[int], *, weeks: int = 2) -> list[date]:
    out: list[date] = []
    for i in range(0, 7 * max(1, weeks)):
        d = ref + timedelta(days=i)
        if d.weekday() in weekdays:
            out.append(d)
    return out


def _try_dateparser(text: str, *, default_tz: str, reference: datetime) -> datetime | None:
    try:
        import dateparser
    except ImportError:
        return None
    settings = {
        "TIMEZONE": default_tz,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": reference.replace(tzinfo=None),
    }
    dt = dateparser.parse(text, languages=["de", "en"], settings=settings)
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise TimezoneAmbiguityError("dateparser_naive_result")
    # It reads "24. November um 14 Uhr" as the year 2114: an interview lies within the next year.
    if not reference - timedelta(days=1) <= dt <= reference + timedelta(days=366):
        return None
    return dt


def parse_scheduling_proposal(
    text: str,
    *,
    default_tz: str = "Europe/Berlin",
    reference: datetime | date | None = None,
    horizon_weeks: int = 2,
) -> ParseResult:
    """Parse employer free-text into windows and/or fixed slots."""
    raw = (text or "").strip()
    result = ParseResult(raw_text=raw, modality=_extract_modality(raw))
    if not raw:
        result.errors.append("empty_proposal")
        return result

    try:
        resolve_zone(default_tz)
    except TimezoneAmbiguityError:
        result.errors.append(f"timezone_unknown:{default_tz}")
        return result

    if reference is None:
        ref_dt = datetime.now(resolve_zone(default_tz))
    elif isinstance(reference, datetime):
        ref_dt = (
            reference
            if reference.tzinfo
            else combine_local(reference.date(), reference.time(), default_tz)
        )
    else:
        ref_dt = combine_local(reference, time(12, 0), default_tz)
    ref_day = ref_dt.date()

    offers = list(_dated_offers(raw, ref_day))
    for day, _start, _end, weekday in offers:
        if weekday is not None and weekday != day.weekday():
            # "Dienstag, 25.11." when the 25th is a Wednesday: ask, do not guess which one is meant.
            result.errors.append(f"ambiguous:weekday_date_mismatch:{day.isoformat()}")
            return result
    for day, start_t, end_t, _weekday in offers:
        if end_t is None or start_t >= end_t:
            continue
        try:
            start = combine_local(day, start_t, default_tz)
            end = combine_local(day, end_t, default_tz)
        except TimezoneAmbiguityError as exc:
            result.errors.append(str(exc))
            continue
        if (start, end) not in result.explicit_slots:
            result.explicit_slots.append((start, end))
    if result.explicit_slots:
        # The employer listed concrete slots: offer exactly those. Weekday names and
        # deadlines in the same text must not be turned into extra windows.
        return result

    for m in _ISO_FIXED.finditer(raw):
        iso = f"{m.group(1)}T{m.group(2)}"
        try:
            dt = parse_iso_datetime(iso, default_tz=default_tz)
        except TimezoneAmbiguityError:
            result.errors.append("ambiguous_timezone:iso_naive")
            continue
        if dt:
            result.fixed_slots.append(dt)

    for day, start_t, _end, _weekday in offers:
        try:
            slot = combine_local(day, start_t, default_tz)
        except TimezoneAmbiguityError as exc:
            result.errors.append(str(exc))
            continue
        if slot not in result.fixed_slots:
            result.fixed_slots.append(slot)
    if result.fixed_slots:
        # Concrete dates offered: weekday names name those days and open no further windows.
        return result

    weekdays = _extract_weekdays(raw)
    window = _extract_time_window(raw)

    if weekdays and window:
        start_t, end_t = window
        dates = tuple(_upcoming_weekdays(ref_day, weekdays, weeks=horizon_weeks))
        result.windows.append(
            ProposalWindow(
                weekdays=tuple(weekdays),
                start_time=start_t,
                end_time=end_t,
                fixed_dates=dates,
                modality=result.modality if result.modality != "unknown" else "remote",
                raw_text=raw,
                timezone=default_tz,
            )
        )
    elif weekdays and not window:
        result.windows.append(
            ProposalWindow(
                weekdays=tuple(weekdays),
                start_time=time(9, 0),
                end_time=time(17, 0),
                fixed_dates=tuple(_upcoming_weekdays(ref_day, weekdays, weeks=horizon_weeks)),
                modality=result.modality if result.modality != "unknown" else "remote",
                raw_text=raw,
                timezone=default_tz,
            )
        )
    elif window and not weekdays and not result.fixed_slots:
        start_t, end_t = window
        result.windows.append(
            ProposalWindow(
                weekdays=(),
                start_time=start_t,
                end_time=end_t,
                modality=result.modality,
                raw_text=raw,
                timezone=default_tz,
                ambiguous=True,
                ambiguity_reason="time_window_without_weekdays",
            )
        )
        result.errors.append("ambiguous:time_window_without_weekdays")

    if not result.fixed_slots and not any(w.is_usable() for w in result.windows):
        try:
            parsed = _try_dateparser(raw, default_tz=default_tz, reference=ref_dt)
            if parsed is not None:
                result.fixed_slots.append(parsed)
                result.used_dateparser = True
        except TimezoneAmbiguityError as exc:
            result.errors.append(str(exc))
        except Exception:
            result.errors.append("dateparser_failed")

    if not result.fixed_slots and not any(w.is_usable() for w in result.windows):
        if "empty_proposal" not in result.errors:
            result.errors.append("unparseable_proposal")

    return result


def parse_result_to_dict(result: ParseResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "modality": result.modality,
        "raw_text": result.raw_text,
        "errors": list(result.errors),
        "used_dateparser": result.used_dateparser,
        "fixed_slots": [dt.isoformat() for dt in result.fixed_slots],
        "explicit_slots": [[s.isoformat(), e.isoformat()] for s, e in result.explicit_slots],
        "windows": [
            {
                "weekdays": list(w.weekdays),
                "start_time": w.start_time.strftime("%H:%M"),
                "end_time": w.end_time.strftime("%H:%M"),
                "fixed_dates": [d.isoformat() for d in w.fixed_dates],
                "modality": w.modality,
                "timezone": w.timezone,
                "ambiguous": w.ambiguous,
                "ambiguity_reason": w.ambiguity_reason,
                "usable": w.is_usable(),
            }
            for w in result.windows
        ],
    }
