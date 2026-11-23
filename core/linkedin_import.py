"""Import the profile from LinkedIn's own data export ("Get a copy of your data" → ZIP with CSV files).

No scraping and no AI: the CSV files are read as they are. Skills, positions, education, languages and
certificates go into the profile; the headline and summary are shown as keywords for the user to pick from.
Only known CSV files are read, straight from the ZIP, with size limits; nothing is extracted to disk.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from core.config import CertificateEntry, EducationEntry, ExperienceEntry, LanguageEntry, QualificationsConfig, SourcedText

SOURCE = "linkedin"
_FILES = ("profile", "skills", "positions", "education", "languages", "certifications")
MAX_CSV_BYTES = 5_000_000
_LEVELS = {
    "native or bilingual proficiency": "Muttersprache",
    "full professional proficiency": "verhandlungssicher",
    "professional working proficiency": "fließend",
    "limited working proficiency": "gute Kenntnisse",
    "elementary proficiency": "Grundkenntnisse",
}


class LinkedInImportError(ValueError):
    pass


@dataclass
class LinkedInProfile:
    qualifications: QualificationsConfig = field(default_factory=QualificationsConfig)
    headline: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        q = self.qualifications
        return {"skills": len(q.skills), "positions": len(q.work_experience), "education": len(q.education),
                "languages": len(q.languages), "certificates": len(q.certificates)}


def _rows(text: str) -> list[dict[str, str]]:
    """CSV rows; LinkedIn puts a few 'Notes:' lines before the header in some files."""
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if "," in line and not line.lower().startswith("notes")), 0)
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]


def _read_sources(path: Path) -> dict[str, list[dict[str, str]]]:
    found: dict[str, list[dict[str, str]]] = {}
    if path.is_dir():
        entries = {p.stem.lower(): p for p in path.glob("*.csv")}
        for name in _FILES:
            if name in entries and entries[name].stat().st_size <= MAX_CSV_BYTES:
                found[name] = _rows(entries[name].read_text(encoding="utf-8", errors="replace"))
        return found
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                stem = Path(info.filename).stem.lower()
                if (stem in _FILES and info.filename.lower().endswith(".csv") and stem not in found
                        and info.file_size <= MAX_CSV_BYTES):
                    found[stem] = _rows(archive.read(info).decode("utf-8", errors="replace"))
    except (zipfile.BadZipFile, OSError) as exc:
        raise LinkedInImportError("not_a_linkedin_export") from exc
    return found


def _date(value: str) -> str:
    """LinkedIn writes 'Jan 2020' or '2020'; keep it readable as MM/YYYY when possible."""
    value = (value or "").strip()
    months = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                          "nov", "dec"), 1)}
    match = re.match(r"^([A-Za-z]{3})\w*\s+(\d{4})$", value)
    if match and match.group(1).lower() in months:
        return f"{months[match.group(1).lower()]:02d}/{match.group(2)}"
    return value


def _keywords(*texts: str) -> list[str]:
    parts = re.split(r"[|•·,;/\n]+", " ".join(t for t in texts if t))
    out: list[str] = []
    for part in parts:
        word = " ".join(part.split()).strip(" -–")
        if 2 <= len(word) <= 40 and word.lower() not in {w.lower() for w in out} and not word.lower().startswith(("at ", "bei ")):
            out.append(word)
    return out[:30]


def read_linkedin_export(path: str | Path) -> LinkedInProfile:
    sources = _read_sources(Path(path))
    if not sources:
        raise LinkedInImportError("not_a_linkedin_export")
    q = QualificationsConfig()
    for row in sources.get("skills", []):
        if row.get("name"):
            q.skills.append(SourcedText(value=row["name"], source=SOURCE))
    for row in sources.get("positions", []):
        if row.get("title") or row.get("company name"):
            description = row.get("description", "")
            q.work_experience.append(ExperienceEntry(
                title=row.get("title", ""), company=row.get("company name", ""), location=row.get("location", ""),
                start_date=_date(row.get("started on", "")), end_date=_date(row.get("finished on", "")),
                responsibilities=[line.strip(" •-") for line in description.splitlines() if line.strip(" •-")][:12],
                source=SOURCE))
    for row in sources.get("education", []):
        if row.get("school name") or row.get("degree name"):
            q.education.append(EducationEntry(
                qualification=row.get("degree name", ""), institution=row.get("school name", ""),
                start_date=_date(row.get("start date", "")), end_date=_date(row.get("end date", "")), source=SOURCE))
    for row in sources.get("languages", []):
        if row.get("name"):
            level = row.get("proficiency", "")
            q.languages.append(LanguageEntry(language=row["name"], level=_LEVELS.get(level.lower(), level), source=SOURCE))
    for row in sources.get("certifications", []):
        if row.get("name"):
            q.certificates.append(CertificateEntry(name=row["name"], issuer=row.get("authority", ""),
                                                   date=_date(row.get("started on", "")), source=SOURCE))
    profile = (sources.get("profile") or [{}])[0]
    headline, summary = profile.get("headline", ""), profile.get("summary", "")
    return LinkedInProfile(qualifications=q, headline=headline, summary=summary, keywords=_keywords(headline))
