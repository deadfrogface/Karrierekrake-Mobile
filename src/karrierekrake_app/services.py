"""The phone app's link to the Karrierekrake core: data folder, profile, database, search, letters.

Everything here is plain Python without any UI, so it is tested without a phone. The screens call these functions;
long work (search, AI) runs in a background thread so the UI never freezes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from core.config import AppConfig, empty_app_config, load_config, save_config
from core.database import Database
from core.models import ApplicationRecord, Job, JobStatus, utc_now_iso


@dataclass
class SearchOutcome:
    jobs: list[Job] = field(default_factory=list)
    error: str = ""


class AppServices:
    """One instance per app. ``data_dir`` is the app's private folder on the phone."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # The core finds its files (cloud settings, templates, signature, license) through this variable.
        os.environ["KARRIEREKRAKE_DATA_DIR"] = str(self.data_dir)
        from karrierekrake_app.keystore import install as install_keystore

        install_keystore(self.data_dir)
        self.config_dir = self.data_dir / "config"
        self.config_dir.mkdir(exist_ok=True)
        self._db: Database | None = None

    # --- profile and settings -------------------------------------------------------------------------------
    @property
    def _paths(self) -> dict[str, Path]:
        return {"profile_path": self.config_dir / "profile.yaml",
                "application_path": self.config_dir / "application_profile.yaml",
                "settings_path": self.config_dir / "settings.yaml"}

    def load_config(self) -> AppConfig:
        paths = self._paths
        if not paths["settings_path"].exists():
            config = empty_app_config(root=self.data_dir)
        else:
            config = load_config(root=self.data_dir, strip_placeholders=False, **paths)
        config.root = self.data_dir
        config.settings.database_path = str(self.data_dir / "jobs.db")
        return config

    def save_config(self, config: AppConfig) -> None:
        save_config(config, **self._paths)

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.data_dir / "jobs.db")
        return self._db

    # --- jobs -------------------------------------------------------------------------------------------------
    def search_jobs(self, keyword: str, location: str, radius_km: int = 25) -> SearchOutcome:
        """Bundesagentur für Arbeit (free, official, no key). Scored and stored like on the desktop."""
        from core.matcher import score_job
        from search.base import PartialResultsError, SearchQuery
        from search.bundesagentur import BundesagenturSource

        keyword = (keyword or "").strip()
        if not keyword:
            return SearchOutcome(error="keyword_missing")
        config = self.load_config()
        query = SearchQuery(keyword=keyword, location=(location or "").strip(), radius_km=radius_km,
                            max_results=40, published_within_days=int(config.settings.published_within_days or 14))
        error = ""
        try:
            jobs = BundesagenturSource().search([query])
        except PartialResultsError as exc:
            jobs, error = exc.jobs, "partial"
        except Exception as exc:  # noqa: BLE001 - shown as a short message, never a crash
            return SearchOutcome(error=f"network:{type(exc).__name__}")
        for job in jobs:
            result = score_job(job, config)
            job.match_score = result.score
            job.match_reasons = result.match_reasons
            job.rejection_reasons = result.rejection_reasons
            self.db.upsert_job(job)
        jobs.sort(key=lambda j: j.match_score, reverse=True)
        return SearchOutcome(jobs=jobs, error=error)

    def fit_lines(self, job: Job) -> tuple[list[str], list[str]]:
        """Plain reasons why a job fits (pass) and what to check (warn)."""
        good = [r.lstrip("✓ ").strip() for r in job.match_reasons or [] if r and not r.startswith(("✗", "⚠"))]
        check = [r.lstrip("✗⚠ ").strip() for r in [*(job.rejection_reasons or []),
                                                    *[m for m in job.match_reasons or [] if m.startswith(("✗", "⚠"))]]]
        return good[:8], check[:8]

    # --- cover letter -----------------------------------------------------------------------------------------
    def draft_cover_letter(self, job: Job) -> tuple[str, str]:
        """(text, problem). The checked letter from the profile; with a cloud model set up, its refined version."""
        from core.cover_letter import compose_cover_letter

        config = self.load_config()
        seed = compose_cover_letter(job, config)
        if not seed.ok:
            return "", seed.reason_code
        try:
            from core.cloud_ai import active_settings

            if active_settings("cover") is not None:
                from core.cover_quality import rewrite_cover_letter

                rewrite = rewrite_cover_letter(job, config)
                if getattr(rewrite, "ok", False) and getattr(rewrite, "text", ""):
                    return rewrite.text, ""
        except Exception:  # noqa: BLE001 - the checked draft is always there
            pass
        return seed.text, ""

    # --- applications -----------------------------------------------------------------------------------------
    def record_application(self, job: Job, *, letter: str = "") -> str:
        record = ApplicationRecord(job_id=job.id, company=job.company, position=job.title,
                                   application_date=utc_now_iso(), platform=job.source,
                                   status=JobStatus.APPLIED.value, cover_letter_used=letter[:20000])
        return self.db.save_application(record)

    def applications(self, *, archived: bool = False, starred_only: bool = False) -> list[ApplicationRecord]:
        config = self.load_config()
        self.db.archive_inactive_applications(int(getattr(config.settings, "archive_after_days", 14) or 0))
        return self.db.list_applications(archived=None if archived else False, starred_only=starred_only)

    def new_replies(self) -> list[dict]:
        """Employer replies since the last look (for the in-app pop-up); each reply is reported once."""
        import json

        state_path = self.data_dir / "replies_seen.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {"since": utc_now_iso(), "ids": []}
            state_path.write_text(json.dumps(state), encoding="utf-8")
            return []
        rows = [r for r in self.db.employer_replies_since(state["since"])
                if f"{r['kind']}:{r['id']}" not in state["ids"]]
        if rows:
            state["since"] = max(str(r.get("at") or state["since"]) for r in rows)
            state["ids"] = (state["ids"] + [f"{r['kind']}:{r['id']}" for r in rows])[-200:]
            state_path.write_text(json.dumps(state), encoding="utf-8")
        return rows

    def export_overview_csv(self, target: str | Path) -> int:
        from core.application_export import build_rows, write_csv

        rows = build_rows(self.db)
        write_csv(rows, Path(target), german=True)
        return len(rows)
