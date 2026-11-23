"""Plain texts for employer replies (shared by the desktop pop-up and the phone app)."""
from __future__ import annotations

EVENT_TEXT = {
    "APPLICATION_RECEIVED": ("Eingangsbestätigung", "Confirmation of receipt"),
    "UNDER_REVIEW": ("Bewerbung wird geprüft", "Application under review"),
    "DOCUMENT_REQUESTED": ("Unterlagen angefordert", "Documents requested"),
    "ASSESSMENT_RECEIVED": ("Test oder Aufgabe erhalten", "Assessment received"),
    "INTERVIEW_REQUESTED": ("Einladung zum Gespräch", "Interview invitation"),
    "INTERVIEW_SCHEDULED": ("Gesprächstermin steht", "Interview scheduled"),
    "INTERVIEW_RESCHEDULED": ("Termin verschoben", "Interview rescheduled"),
    "INTERVIEW_CANCELLED": ("Termin abgesagt", "Interview cancelled"),
    "INTERVIEW_COMPLETED": ("Gespräch abgeschlossen", "Interview completed"),
    "OFFER_RECEIVED": ("Angebot erhalten 🎉", "Offer received 🎉"),
    "REJECTION_RECEIVED": ("Absage", "Rejection"),
}


def describe(row: dict, *, english: bool = False) -> str:
    pick = 1 if english else 0
    who = row.get("company") or ("A company" if english else "Eine Firma")
    if row.get("kind") == "mail":
        what = ("New mail" if english else "Neue Mail") + (f": {row['detail']}" if row.get("detail") else "")
    else:
        what = EVENT_TEXT.get(str(row.get("detail")), ("Neue Antwort", "New reply"))[pick]
    return f"{who} – {what}"
