"""Application folder ("Bewerbungsmappe"): the approved cover letter as a letter page, plus CV and documents.

This module builds the letter page as HTML and finds the files; the desktop app renders and joins the PDF.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import escape
from pathlib import Path

SIGNATURE_RESOURCE = "signature.png"
_CLOSING = re.compile(r"^(mit freundlichen grüßen|freundliche grüße|viele grüße|beste grüße|herzliche grüße|"
                      r"kind regards|best regards|sincerely|yours sincerely|regards)[,.!]?$", re.I)


@dataclass
class FolderParts:
    letter: str = ""
    pdfs: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # file names that are not PDFs or are missing


def approved_letter(root: str | Path, job_id: str) -> str:
    path = Path(root) / "cover_letters" / f"{job_id}.txt"
    try:
        return path.read_text(encoding="utf-8").strip() if job_id and path.is_file() else ""
    except OSError:
        return ""


def collect_parts(letter: str, cv_path: str, documents: list[dict]) -> FolderParts:
    parts = FolderParts(letter=letter)
    candidates = [cv_path] + [str(d.get("path") or "") for d in documents if d.get("send", True)]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw)
        if path.suffix.lower() == ".pdf" and path.is_file():
            if path not in parts.pdfs:
                parts.pdfs.append(path)
        else:
            parts.skipped.append(path.name)
    return parts


def _body_html(letter: str, *, with_signature: bool) -> str:
    lines = letter.replace("\r\n", "\n").split("\n")
    closing_at = max((i for i, line in enumerate(lines) if _CLOSING.match(line.strip())), default=-1)
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(escape(line) if line.strip() else "")
        if with_signature and i == closing_at:
            out.append(f"<img src='{SIGNATURE_RESOURCE}' width='170'>")
    if with_signature and closing_at < 0:
        out.append(f"<img src='{SIGNATURE_RESOURCE}' width='170'>")
    return "<br>".join(out)


def letter_html(letter: str, *, sender: dict[str, str], company: str, position: str,
                with_signature: bool, german: bool = True, today: date | None = None) -> str:
    """One letter page: sender block, recipient, date, subject, body (signature under the closing line)."""
    today = today or date.today()
    sender_lines = [sender.get("name", ""), sender.get("street", ""),
                    " ".join(p for p in (sender.get("postal_code", ""), sender.get("city", "")) if p),
                    sender.get("phone", ""), sender.get("email", "")]
    sender_html = "<br>".join(escape(x) for x in sender_lines if x.strip())
    city = sender.get("city", "").strip()
    day = today.strftime("%d.%m.%Y") if german else today.strftime("%d %B %Y")
    dateline = f"{city}, {day}" if city and german else day
    subject = (f"Bewerbung als {position}" if german else f"Application: {position}") if position else ""
    return (
        "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;font-size:11pt;color:#111}"
        ".sender{font-size:9.5pt;color:#333}.date{text-align:right}</style></head><body>"
        f"<p class='sender' align='right'>{sender_html}</p>"
        f"<p>{escape(company)}</p><p class='date' align='right'>{escape(dateline)}</p>"
        + (f"<p><b>{escape(subject)}</b></p>" if subject else "")
        + f"<p>{_body_html(letter, with_signature=with_signature)}</p></body></html>"
    )
