"""Save the application overview as PDF (printable proof for the employment agency) or CSV (Excel)."""
from __future__ import annotations

from pathlib import Path

from core.application_export import build_rows, overview_html, write_csv


def export_overview(db, path: str | Path, *, applicant: str = "", german: bool = True) -> int:
    """Write the overview to ``path``; the file ending decides the format. Returns the number of rows."""
    from desktop.status_labels import status_label

    path = Path(path)
    rows = build_rows(db, status_label=status_label)
    if path.suffix.lower() == ".csv":
        write_csv(rows, path, german=german)
        return len(rows)
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    write_html_pdf(overview_html(rows, applicant=applicant, german=german), path,
                   title="Bewerbungsübersicht" if german else "Applications", landscape=True)
    return len(rows)


def write_html_pdf(html: str, path: str | Path, *, title: str, landscape: bool = False) -> Path:
    """Render simple HTML to an A4 PDF."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    path = Path(path)
    writer = QPdfWriter(str(path))
    writer.setResolution(96)  # the text document lays out in screen points; 1200 dpi would print it tiny
    orientation = QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), orientation,
                                     QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter))
    writer.setTitle(title)
    document = QTextDocument()
    document.setHtml(html)
    document.setPageSize(QSizeF(writer.width(), writer.height()))
    document.print_(writer)
    del writer  # finishes the file
    if not path.is_file():
        raise OSError("pdf_not_written")
    return path
