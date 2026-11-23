"""SearchIntent domain model — what to find in *this* search (not profile evidence).

PROFILE (ApplicationProfile + QualificationsConfig)
  → What can I do? Evidence for match quality / form fill.

SEARCH INTENT (this module)
  → What do I want to find in this concrete search?

STRICT mode (Tester A): target_roles drive discovery; profile experience may
raise fitness scores later but must NOT introduce new role families into the
search query. Actual filtering/ranking is PR23 — this module only models and
persists intent.

Schema is versioned. Legacy JobsConfig / FiltersConfig fields are dual-read
during migration; ambiguous mappings are flagged for user re-selection, never
guessed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

SEARCH_INTENT_SCHEMA_VERSION = 1

# Documented remote_mode values when set; unset (None) means not chosen yet.
REMOTE_MODE_VALUES = frozenset({"remote", "hybrid", "onsite", "flexible"})


class Strictness(str, Enum):
    """How tightly search may expand beyond explicit intent.

    STRICT   — only target/required roles & mandatory skills drive discovery;
               profile evidence must not add new role families (Tester A).
    BALANCED — intent leads; limited expansion may be allowed later (PR23).
    EXPLORE  — broader discovery; still respects excludes / mandatory filters.
    """

    STRICT = "strict"
    BALANCED = "balanced"
    EXPLORE = "explore"


class SearchIntentError(ValueError):
    """A stored or entered search intent that does not fit the schema."""


_WISH_LISTS = (
    "target_roles",
    "required_roles",
    "excluded_roles",
    "mandatory_skills",
    "preferred_skills",
    "excluded_skills",
    "required_keywords",
    "excluded_keywords",
    "preferred_industries",
    "excluded_industries",
    "employment_types",
    "working_time",
    "countries",
)
_FLAG_LISTS = ("needs_user_review", "legacy_fields_deprecated")
_FIELD_ORDER = (
    "schema_version",
    "target_roles", "required_roles", "excluded_roles",
    "mandatory_skills", "preferred_skills", "excluded_skills",
    "required_keywords", "excluded_keywords",
    "preferred_industries", "excluded_industries",
    "strictness", "remote_mode", "employment_types", "working_time", "salary_min", "countries", "radius_km",
    "needs_user_review", "legacy_fields_deprecated",
)
_NON_FINITE_WORDS = frozenset({"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity", "nan", "+nan", "-nan"})


def _clean_str_list(value: Any) -> list[str]:
    """Wish lists: trimmed, without empties, first spelling of case-insensitive duplicates kept."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("expected a list of strings")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _str_list(name: str, value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise SearchIntentError(f"{name}: expected a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SearchIntentError(f"{name}: expected a list of strings")
        out.append(item.strip())
    return out


def _text_of_bytes(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value
    return value


def _schema_version(value: Any) -> int:
    value = _text_of_bytes(value)
    if not isinstance(value, (int, float, str)):
        raise SearchIntentError("schema_version: expected an integer")
    if isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            raise SearchIntentError("schema_version: expected an integer") from None
    if isinstance(value, float):
        if not value.is_integer():
            raise SearchIntentError("schema_version: expected an integer")
        value = int(value)
    value = int(value)
    if value < 1:
        raise SearchIntentError("schema_version: must be at least 1")
    return value


def _optional_number(name: str, value: Any) -> float | None:
    if value is None:
        return None
    value = _text_of_bytes(value)
    if not isinstance(value, (int, float, str)):
        raise SearchIntentError(f"{name}: expected a number or null")
    if isinstance(value, str):
        text = value.strip()
        try:
            number = float(text)
        except ValueError:
            raise SearchIntentError(f"{name}: expected a number or null") from None
        if not math.isfinite(number) and text.lower() not in _NON_FINITE_WORDS:
            raise SearchIntentError(f"{name}: expected a number or null")
        return number
    return float(value)


def _remote_mode(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text not in REMOTE_MODE_VALUES:
        raise SearchIntentError(f"remote_mode must be one of {sorted(REMOTE_MODE_VALUES)} or null")
    return text


def _strictness(value: Any) -> Strictness | None:
    if value is None or value == "":
        return None
    if isinstance(value, Strictness):
        return value
    try:
        return Strictness(str(value).strip().lower())
    except ValueError:
        raise SearchIntentError(f"strictness must be one of {[s.value for s in Strictness]} or null") from None


class SearchIntent:
    """Explicit search wish for one search session / saved preference set.

    A plain class with the validation the settings need, so reading the configuration at startup does not load
    pydantic (about 0.6 s). It keeps the parts of the pydantic interface the program uses: ``model_validate``,
    ``model_dump(mode=...)``, ``model_fields``, ``model_copy`` and ``model_json_schema``. Unknown fields and invalid
    values raise :class:`SearchIntentError`, a ``ValueError``; a wish list that is not a list raises ``TypeError``.
    """

    __slots__ = _FIELD_ORDER
    model_fields: ClassVar[dict[str, None]] = dict.fromkeys(_FIELD_ORDER)

    schema_version: int
    target_roles: list[str]
    required_roles: list[str]
    excluded_roles: list[str]
    mandatory_skills: list[str]
    preferred_skills: list[str]
    excluded_skills: list[str]
    required_keywords: list[str]
    excluded_keywords: list[str]
    preferred_industries: list[str]
    excluded_industries: list[str]
    # None = not chosen yet (do not invent BALANCED as silent default).
    strictness: Strictness | None
    remote_mode: str | None
    employment_types: list[str]
    working_time: list[str]
    salary_min: float | None
    countries: list[str]
    radius_km: float | None
    # Migration / UX flags — not search filters.
    needs_user_review: list[str]
    legacy_fields_deprecated: list[str]

    def __init__(self, **data: Any) -> None:
        # Wish lists first: a non-list there is a TypeError whatever else is wrong (as with pydantic before).
        wishes = {name: _clean_str_list(data.get(name)) for name in _WISH_LISTS}
        unknown = sorted(set(data) - set(_FIELD_ORDER))
        if unknown:
            raise SearchIntentError("unknown search intent fields: " + ", ".join(unknown))
        put = object.__setattr__
        put(self, "schema_version", _schema_version(data.get("schema_version", SEARCH_INTENT_SCHEMA_VERSION)))
        for name, value in wishes.items():
            put(self, name, value)
        for name in _FLAG_LISTS:
            put(self, name, _str_list(name, data[name]) if name in data else [])
        put(self, "strictness", _strictness(data.get("strictness")))
        put(self, "remote_mode", _remote_mode(data.get("remote_mode")))
        put(self, "salary_min", _optional_number("salary_min", data.get("salary_min")))
        put(self, "radius_km", _optional_number("radius_km", data.get("radius_km")))
        self._flag_include_exclude_conflicts()

    def _flag_include_exclude_conflicts(self) -> None:
        """Record conflicts; do not silently drop user data."""
        conflicts = list(self.needs_user_review)

        def _overlap(include: list[str], exclude: list[str], label: str) -> None:
            inc = {x.casefold() for x in include}
            exc = {x.casefold() for x in exclude}
            hit = sorted(inc & exc)
            if hit:
                marker = f"conflict:{label}:{','.join(hit)}"
                if marker not in conflicts:
                    conflicts.append(marker)

        _overlap(self.target_roles, self.excluded_roles, "roles_target")
        _overlap(self.required_roles, self.excluded_roles, "roles_required")
        _overlap(self.mandatory_skills, self.excluded_skills, "skills_mandatory")
        _overlap(self.preferred_skills, self.excluded_skills, "skills_preferred")
        _overlap(self.required_keywords, self.excluded_keywords, "keywords")
        _overlap(self.preferred_industries, self.excluded_industries, "industries")

        if conflicts != self.needs_user_review:
            self.needs_user_review = conflicts

    @classmethod
    def model_validate(cls, data: Any) -> "SearchIntent":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise SearchIntentError("search intent must be a mapping")
        return cls(**data)

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in _FIELD_ORDER:
            value = getattr(self, name)
            if isinstance(value, list):
                value = list(value)
            elif isinstance(value, Strictness) and mode == "json":
                value = value.value
            out[name] = value
        return out

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False) -> "SearchIntent":
        """Copy without validation, like pydantic: ``update`` values are taken as given."""
        clone = object.__new__(type(self))
        for name in _FIELD_ORDER:
            value = getattr(self, name)
            object.__setattr__(clone, name, list(value) if deep and isinstance(value, list) else value)
        for name, value in (update or {}).items():
            setattr(clone, name, value)
        return clone

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        properties: dict[str, Any] = {"schema_version": {"type": "integer", "minimum": 1,
                                                         "default": SEARCH_INTENT_SCHEMA_VERSION}}
        for name in _FIELD_ORDER[1:]:
            properties[name] = {"type": "array", "items": {"type": "string"}}
        properties["strictness"] = {"anyOf": [{"enum": [s.value for s in Strictness]}, {"type": "null"}]}
        properties["remote_mode"] = {"anyOf": [{"enum": sorted(REMOTE_MODE_VALUES)}, {"type": "null"}]}
        properties["salary_min"] = {"anyOf": [{"type": "number"}, {"type": "null"}]}
        properties["radius_km"] = {"anyOf": [{"type": "number"}, {"type": "null"}]}
        return {"title": "SearchIntent", "type": "object", "additionalProperties": False, "properties": properties}

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in _FIELD_ORDER:
            raise SearchIntentError(f'"SearchIntent" object has no field "{name}"')
        object.__setattr__(self, name, value)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name) for name in _FIELD_ORDER)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return "SearchIntent(" + ", ".join(f"{n}={getattr(self, n)!r}" for n in _FIELD_ORDER) + ")"

    def __getstate__(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in _FIELD_ORDER}

    def __setstate__(self, state: dict[str, Any]) -> None:
        for name in _FIELD_ORDER:
            object.__setattr__(self, name, state[name])

    def is_empty(self) -> bool:
        """True when no role/skill/keyword/industry wish is configured.

        Geo/salary/working_time alone do **not** count: they often mirror
        LocationConfig/EmploymentConfig defaults after migration and must not
        block lifting ``jobs.desired_titles`` into ``target_roles`` on save.
        """
        return not any(
            [
                self.target_roles,
                self.required_roles,
                self.excluded_roles,
                self.mandatory_skills,
                self.preferred_skills,
                self.excluded_skills,
                self.required_keywords,
                self.excluded_keywords,
                self.preferred_industries,
                self.excluded_industries,
                self.strictness is not None,
            ]
        )

    def to_persist_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass
class SearchIntentMigrationResult:
    """Outcome of mapping legacy SearchPreferences slices → SearchIntent."""

    intent: SearchIntent
    migrated_fields: list[str] = field(default_factory=list)
    needs_user_review: list[str] = field(default_factory=list)
    preserved_legacy: bool = True
    notes: list[str] = field(default_factory=list)


def empty_search_intent() -> SearchIntent:
    return SearchIntent(schema_version=SEARCH_INTENT_SCHEMA_VERSION)


def parse_search_intent(raw: dict[str, Any] | None) -> SearchIntent:
    if not raw:
        return empty_search_intent()
    data = dict(raw)
    # Forward-compatible: unknown future keys rejected by extra=forbid —
    # strip unknown only when schema_version is newer than we understand.
    version = int(data.get("schema_version") or SEARCH_INTENT_SCHEMA_VERSION)
    if version > SEARCH_INTENT_SCHEMA_VERSION:
        # Keep original bytes path: caller should not destroy; we parse known fields only.
        known = set(SearchIntent.model_fields.keys())
        data = {k: v for k, v in data.items() if k in known}
        data["schema_version"] = SEARCH_INTENT_SCHEMA_VERSION
        data.setdefault("needs_user_review", [])
        marker = f"schema_version_downgraded_from:{version}"
        if marker not in data["needs_user_review"]:
            data["needs_user_review"] = list(data["needs_user_review"]) + [marker]
    return SearchIntent.model_validate(data)


def migrate_legacy_search_preferences(
    *,
    jobs: Any,
    filters: Any,
    location: Any,
    employment: Any,
    existing_intent: SearchIntent | None = None,
) -> SearchIntentMigrationResult:
    """Map clear legacy fields into SearchIntent; never guess ambiguous ones.

    Clear mappings
    --------------
    jobs.desired_titles          → target_roles
    jobs.unwanted_titles         → excluded_roles
    jobs.desired_industries      → preferred_industries
    jobs.excluded_industries     → excluded_industries
    filters.exclusion_keywords   → excluded_keywords
    employment.minimum_salary    → salary_min
    location.country             → countries[]
    location.max_distance_km     → radius_km
    employment.full_time/part_time → working_time[]
    employment.remote/hybrid/onsite → remote_mode only if exactly one True

    Ambiguous (flagged, not copied into required/mandatory)
    -------------------------------------------------------
    filters.desired_keywords — preferred vs required unknown
    jobs.alternative_titles — if still present after soft-migrate fold;
      already folded into desired_titles by soft_migrate_jobs_config; if
      residual non-empty list remains, flag for review and do not dual-map
    strictness — never present in legacy → leave None + review flag if any
      target_roles exist (user should confirm STRICT/BALANCED/EXPLORE)

    Qualifications / profile skills are NEVER copied into SearchIntent.
    """
    if existing_intent is not None and not existing_intent.is_empty():
        return SearchIntentMigrationResult(
            intent=existing_intent,
            migrated_fields=[],
            needs_user_review=list(existing_intent.needs_user_review),
            preserved_legacy=True,
            notes=["existing_search_intent_kept"],
        )

    migrated: list[str] = []
    review: list[str] = []
    notes: list[str] = []
    deprecated: list[str] = []

    def _list(obj: Any, name: str) -> list[str]:
        raw = getattr(obj, name, None) if obj is not None else None
        if not raw:
            return []
        return [str(x).strip() for x in raw if str(x).strip()]

    target_roles = _list(jobs, "desired_titles")
    if target_roles:
        migrated.append("jobs.desired_titles→target_roles")

    alts = _list(jobs, "alternative_titles")
    if alts:
        # Soft-migrate should have folded these; residual = ambiguous.
        review.append("legacy_alternative_titles_need_review")
        deprecated.append("jobs.alternative_titles")
        notes.append(
            "alternative_titles still set; not auto-merged into target_roles "
            "(ambiguous vs soft-folded desired). Soft-migrate on load folds "
            "into desired_titles first when possible."
        )
    else:
        deprecated.append("jobs.alternative_titles")

    excluded_roles = _list(jobs, "unwanted_titles")
    if excluded_roles:
        migrated.append("jobs.unwanted_titles→excluded_roles")

    preferred_industries = _list(jobs, "desired_industries")
    if preferred_industries:
        migrated.append("jobs.desired_industries→preferred_industries")

    excluded_industries = _list(jobs, "excluded_industries")
    if excluded_industries:
        migrated.append("jobs.excluded_industries→excluded_industries")

    excluded_keywords = _list(filters, "exclusion_keywords")
    if excluded_keywords:
        migrated.append("filters.exclusion_keywords→excluded_keywords")

    desired_kw = _list(filters, "desired_keywords")
    if desired_kw:
        review.append("legacy_desired_keywords_unmapped")
        notes.append(
            "filters.desired_keywords not mapped: unknown whether required_keywords "
            "or preferred_skills; user must re-select."
        )
        deprecated.append("filters.desired_keywords")

    salary_min = getattr(employment, "minimum_salary", None) if employment else None
    if salary_min is not None:
        try:
            salary_min = float(salary_min)
            migrated.append("employment.minimum_salary→salary_min")
        except (TypeError, ValueError):
            salary_min = None
            review.append("legacy_minimum_salary_invalid")

    countries: list[str] = []
    country = str(getattr(location, "country", "") or "").strip() if location else ""
    if country:
        countries = [country]
        migrated.append("location.country→countries")

    radius_km = None
    if location is not None and getattr(location, "max_distance_km", None) is not None:
        try:
            radius_km = float(location.max_distance_km)
            migrated.append("location.max_distance_km→radius_km")
        except (TypeError, ValueError):
            review.append("legacy_max_distance_km_invalid")

    working_time: list[str] = []
    if employment is not None:
        if getattr(employment, "full_time", False):
            working_time.append("full_time")
        if getattr(employment, "part_time", False):
            working_time.append("part_time")
        if working_time:
            migrated.append("employment.full_time/part_time→working_time")

    remote_mode = None
    if employment is not None:
        flags = {
            "remote": bool(getattr(employment, "remote", False)),
            "hybrid": bool(getattr(employment, "hybrid", False)),
            "onsite": bool(getattr(employment, "onsite", False)),
        }
        enabled = [k for k, v in flags.items() if v]
        if len(enabled) == 1:
            remote_mode = enabled[0]
            migrated.append("employment.remote_flags→remote_mode")
        elif len(enabled) > 1:
            review.append("legacy_remote_flags_ambiguous")
            notes.append(
                "Multiple remote/hybrid/onsite flags true — remote_mode left unset."
            )

    employment_types: list[str] = []
    # No clear legacy employment_type enum beyond working_time; leave empty.

    if target_roles or excluded_roles or preferred_industries:
        review.append("strictness_unset_confirm_with_user")
        notes.append(
            "Legacy configs had no strictness; leave null until user chooses "
            "STRICT/BALANCED/EXPLORE."
        )

    intent = SearchIntent(
        schema_version=SEARCH_INTENT_SCHEMA_VERSION,
        target_roles=target_roles,
        excluded_roles=excluded_roles,
        preferred_industries=preferred_industries,
        excluded_industries=excluded_industries,
        excluded_keywords=excluded_keywords,
        salary_min=salary_min,
        countries=countries,
        radius_km=radius_km,
        working_time=working_time,
        remote_mode=remote_mode,
        employment_types=employment_types,
        strictness=None,
        needs_user_review=review,
        legacy_fields_deprecated=sorted(set(deprecated + [
            "jobs.desired_titles",
            "jobs.unwanted_titles",
            "jobs.desired_industries",
            "jobs.excluded_industries",
            "jobs.alternative_titles",
        ])),
    )

    # Role-empty intents are still "empty" for title-lift, but explicit geo /
    # salary / remote / strictness on existing_intent must not be overwritten
    # by LocationConfig/EmploymentConfig defaults (radius 20, country DE, …).
    if existing_intent is not None:
        data = intent.model_dump()
        preserved: list[str] = []
        if existing_intent.radius_km is not None:
            data["radius_km"] = existing_intent.radius_km
            preserved.append("radius_km")
        if existing_intent.countries:
            data["countries"] = list(existing_intent.countries)
            preserved.append("countries")
        if existing_intent.remote_mode is not None:
            data["remote_mode"] = existing_intent.remote_mode
            preserved.append("remote_mode")
        if existing_intent.salary_min is not None:
            data["salary_min"] = existing_intent.salary_min
            preserved.append("salary_min")
        if existing_intent.employment_types:
            data["employment_types"] = list(existing_intent.employment_types)
            preserved.append("employment_types")
        if existing_intent.working_time:
            data["working_time"] = list(existing_intent.working_time)
            preserved.append("working_time")
        if existing_intent.strictness is not None:
            data["strictness"] = existing_intent.strictness
            preserved.append("strictness")
        if preserved:
            intent = SearchIntent.model_validate(data)
            notes.append(
                "preserved_explicit_geo_from_existing_intent:" + ",".join(preserved)
            )

    return SearchIntentMigrationResult(
        intent=intent,
        migrated_fields=migrated,
        needs_user_review=review,
        preserved_legacy=True,
        notes=notes,
    )


def sync_legacy_jobs_from_intent(intent: SearchIntent, jobs: Any) -> None:
    """Dual-write bridge: keep JobsConfig mirrors for pre-PR23 callers.

    Does not invent data. Clears alternative_titles (deprecated).
    """
    jobs.desired_titles = list(intent.target_roles)
    jobs.alternative_titles = []
    jobs.unwanted_titles = list(intent.excluded_roles)
    jobs.desired_industries = list(intent.preferred_industries)
    jobs.excluded_industries = list(intent.excluded_industries)


def apply_clear_jobs_edit_to_intent(intent: SearchIntent, jobs: Any) -> SearchIntent:
    """When UI still edits JobsConfig, copy clearly mapped lists into intent."""
    data = intent.model_dump()
    data["target_roles"] = _list_attr(jobs, "desired_titles")
    data["excluded_roles"] = _list_attr(jobs, "unwanted_titles")
    data["preferred_industries"] = _list_attr(jobs, "desired_industries")
    data["excluded_industries"] = _list_attr(jobs, "excluded_industries")
    return SearchIntent.model_validate(data)


def apply_location_employment_to_intent(
    intent: SearchIntent,
    *,
    location: Any,
    employment: Any,
) -> SearchIntent:
    """Copy clearly mapped location/employment scalars into intent (no guessing)."""
    data = intent.model_dump()
    country = str(getattr(location, "country", "") or "").strip()
    data["countries"] = [country] if country else []
    try:
        data["radius_km"] = float(location.max_distance_km)
    except (TypeError, ValueError, AttributeError):
        data["radius_km"] = None
    salary = getattr(employment, "minimum_salary", None)
    try:
        data["salary_min"] = float(salary) if salary is not None else None
    except (TypeError, ValueError):
        data["salary_min"] = None
    working: list[str] = []
    if getattr(employment, "full_time", False):
        working.append("full_time")
    if getattr(employment, "part_time", False):
        working.append("part_time")
    data["working_time"] = working
    flags = {
        "remote": bool(getattr(employment, "remote", False)),
        "hybrid": bool(getattr(employment, "hybrid", False)),
        "onsite": bool(getattr(employment, "onsite", False)),
    }
    enabled = [k for k, v in flags.items() if v]
    data["remote_mode"] = enabled[0] if len(enabled) == 1 else None
    return SearchIntent.model_validate(data)


def _list_attr(obj: Any, name: str) -> list[str]:
    raw = getattr(obj, name, None) or []
    return [str(x).strip() for x in raw if str(x).strip()]


# --- Golden case helpers (tests / docs; fictional) ---------------------------------


def golden_tester_a_payroll_strict() -> SearchIntent:
    """Tester A: only payroll titles; other experience stays on profile."""
    return SearchIntent(
        schema_version=SEARCH_INTENT_SCHEMA_VERSION,
        target_roles=[
            "Lohnbuchhalter",
            "Gehaltsbuchhalter",
            "Lohn- und Gehaltsbuchhalter",
            "Payroll Specialist",
        ],
        strictness=Strictness.STRICT,
    )


def golden_tester_b_sap_mandatory() -> SearchIntent:
    """Tester B: SAP mandatory — jobs without SAP are FILTERED_OUT in PR23."""
    return SearchIntent(
        schema_version=SEARCH_INTENT_SCHEMA_VERSION,
        mandatory_skills=["SAP"],
        strictness=Strictness.STRICT,
    )
