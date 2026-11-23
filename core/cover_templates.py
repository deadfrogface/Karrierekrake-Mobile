"""The user's own cover-letter templates: save, choose, delete, and make one from a letter they wrote.

A template is plain text with placeholders such as {company}. The letter is still built by the normal writer
and checked by the cover guard; a template only changes the wording around the checked facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.platform_paths import user_data_dir

DEFAULT_SETTING = "templates/cover_letter.txt"
MAX_CHARS = 20_000
PLACEHOLDERS = {  # key: (German, English)
    "salutation": ("Anrede (z. B. „Sehr geehrte Frau …“)", "salutation (e.g. “Dear Ms …”)"),
    "company": ("Firma", "company"),
    "company_bei": ("„bei“ + Firma, richtig gebeugt", "“at” + company (German letters)"),
    "job_title": ("Stellentitel", "job title"),
    "position_phrase": ("Stelle für den Einleitungssatz", "position for the opening sentence"),
    "experience_sentence": ("Satz zu deiner Erfahrung (geprüft)", "sentence about your experience (checked)"),
    "skills": ("passende Kenntnisse (geprüft)", "matching skills (checked)"),
    "full_name": ("dein Name", "your name"),
}


def placeholder_help(*, english: bool = False) -> str:
    return " · ".join("{" + key + "} " + labels[1 if english else 0] for key, labels in PLACEHOLDERS.items())
_SALUTATION = re.compile(r"^\s*(sehr geehrte[^\n,]*|hallo[^\n,]*|liebe[^\n,]*|guten tag[^\n,]*|dear[^\n,]*|hello[^\n,]*)(,?)",
                         re.I)


@dataclass(frozen=True)
class Template:
    name: str
    path: Path


def templates_dir() -> Path:
    path = user_data_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_templates() -> list[Template]:
    return sorted((Template(p.stem, p) for p in templates_dir().glob("*.txt") if p.is_file()),
                  key=lambda t: t.name.lower())


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\- äöüÄÖÜß]", "", (name or "").strip())[:60].strip()
    if not cleaned:
        raise ValueError("name_missing")
    return cleaned


def save_template(name: str, text: str) -> Path:
    body = (text or "").replace("\r\n", "\n").strip()
    if not body:
        raise ValueError("text_missing")
    if len(body) > MAX_CHARS:
        raise ValueError("text_too_long")
    path = templates_dir() / f"{_safe_name(name)}.txt"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def delete_template(path: str | Path) -> None:
    """Only files inside the templates folder can be deleted."""
    target = Path(path).resolve()
    if target.parent != templates_dir().resolve() or target.suffix != ".txt":
        raise ValueError("not_a_template")
    target.unlink(missing_ok=True)


def is_user_template(setting: str) -> bool:
    try:
        return Path(setting).resolve().parent == templates_dir().resolve()
    except (OSError, ValueError):
        return False


def template_from_letter(text: str, *, company: str = "", position: str = "", full_name: str = "") -> tuple[str, list[str]]:
    """Turn a letter the user wrote into a template. Returns (template, placeholders that were inserted).

    Braces in the letter are kept as text; company, position, name and the salutation become placeholders.
    """
    body = (text or "").replace("\r\n", "\n").strip()
    body = body.replace("{", "{{").replace("}", "}}")
    used: list[str] = []
    for value, key in ((company, "company"), (position, "job_title"), (full_name, "full_name")):
        value = (value or "").strip()
        if len(value) >= 2:
            pattern = re.compile(re.escape(value), re.I)
            if pattern.search(body):
                body = pattern.sub("{" + key + "}", body)
                used.append(key)
    match = _SALUTATION.match(body)
    if match:
        body = "{salutation}," + body[match.end():]
        used.append("salutation")
    return body, used


# Ready-made styles. They only set structure and tone: every fact still comes from the checked placeholders.
STYLES: dict[str, dict[str, str]] = {
    "classic": {
        "de_label": "Klassisch", "en_label": "Classic",
        "de": "{salutation},\n\ndie {position_phrase} bei {company_bei} bietet mir die Möglichkeit, meine berufliche "
              "Erfahrung gezielt einzubringen.\n\n{experience_sentence}\n\n{skills}\n\nGerne erläutere ich Ihnen in einem "
              "persönlichen Gespräch, wie ich Ihre Aufgaben mit meiner Erfahrung unterstützen kann.\n\n"
              "Mit freundlichen Grüßen\n{full_name}",
        "en": "{salutation},\n\nI am applying for the {job_title} position at {company}.\n\n{experience_sentence}\n\n"
              "{skills}\n\nI would welcome the opportunity to discuss my experience with you.\n\nSincerely,\n{full_name}",
    },
    "short": {
        "de_label": "Kurz und direkt", "en_label": "Short and direct",
        "de": "{salutation},\n\nhiermit bewerbe ich mich als {job_title} bei {company}.\n\n{experience_sentence}\n\n"
              "{skills}\n\nÜber eine Einladung zum Gespräch freue ich mich.\n\nMit freundlichen Grüßen\n{full_name}",
        "en": "{salutation},\n\nplease accept my application for the {job_title} position at {company}.\n\n"
              "{experience_sentence}\n\n{skills}\n\nI look forward to hearing from you.\n\nKind regards,\n{full_name}",
    },
    "career_change": {
        "de_label": "Quereinstieg", "en_label": "Career change",
        "de": "{salutation},\n\nmit dieser Bewerbung als {job_title} bei {company} möchte ich meine bisherige Erfahrung "
              "in ein neues Aufgabenfeld einbringen.\n\n{experience_sentence}\n\n{skills}\n\nIch arbeite mich zügig in "
              "neue Aufgaben ein und freue mich darauf, Ihnen im Gespräch zu zeigen, was ich mitbringe.\n\n"
              "Mit freundlichen Grüßen\n{full_name}",
        "en": "{salutation},\n\nwith this application for the {job_title} position at {company} I would like to bring my "
              "experience to a new field.\n\n{experience_sentence}\n\n{skills}\n\nI learn new tasks quickly and would be "
              "glad to show you in an interview what I can contribute.\n\nKind regards,\n{full_name}",
    },
    "entry": {
        "de_label": "Berufseinstieg / Ausbildung", "en_label": "Career start / apprenticeship",
        "de": "{salutation},\n\nich bewerbe mich bei {company} als {job_title}.\n\n{experience_sentence}\n\n{skills}\n\n"
              "Ich möchte lernen, Verantwortung übernehmen und mich in Ihrem Team weiterentwickeln. Über eine Einladung "
              "zum Kennenlernen freue ich mich.\n\nMit freundlichen Grüßen\n{full_name}",
        "en": "{salutation},\n\nI am applying to {company} for the {job_title} position.\n\n{experience_sentence}\n\n"
              "{skills}\n\nI am keen to learn, take on responsibility and grow in your team. I would be glad to meet "
              "you.\n\nKind regards,\n{full_name}",
    },
    "unsolicited": {
        "de_label": "Initiativbewerbung", "en_label": "Unsolicited application",
        "de": "{salutation},\n\nauch ohne passende Ausschreibung möchte ich mich bei {company} bewerben – am liebsten als "
              "{job_title}.\n\n{experience_sentence}\n\n{skills}\n\nWenn Sie jetzt oder später Unterstützung suchen, "
              "freue ich mich über Ihre Rückmeldung.\n\nMit freundlichen Grüßen\n{full_name}",
        "en": "{salutation},\n\nalthough no matching vacancy is advertised, I would like to apply to {company}, ideally as "
              "{job_title}.\n\n{experience_sentence}\n\n{skills}\n\nIf you are looking for support now or later, I would "
              "be glad to hear from you.\n\nKind regards,\n{full_name}",
    },
}


def generate_template(style: str, *, english: bool = False) -> tuple[str, str]:
    """(suggested name, template text) for a ready-made style."""
    entry = STYLES[style]
    return (entry["en_label"] if english else entry["de_label"]), entry["en" if english else "de"]
