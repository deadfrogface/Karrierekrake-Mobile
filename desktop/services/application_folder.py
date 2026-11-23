"""Render the application folder: letter page (with signature) + CV + documents, joined into one PDF."""
from __future__ import annotations

from pathlib import Path

from core.application_folder import SIGNATURE_RESOURCE, FolderParts, letter_html


def build_folder_pdf(parts: FolderParts, target: str | Path, *, sender: dict[str, str], company: str,
                     position: str, signature: Path | None, german: bool = True) -> list[str]:
    """Write the PDF; returns names of attachments that could not be added (not PDF, damaged, protected)."""
    from PySide6.QtCore import QMarginsF, QSizeF, QUrl
    from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    from pypdf import PdfReader, PdfWriter

    target = Path(target)
    letter_pdf = target.with_suffix(".letter.tmp.pdf")
    skipped = list(parts.skipped)
    try:
        writer = QPdfWriter(str(letter_pdf))
        writer.setResolution(96)
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                         QMarginsF(22, 18, 20, 18), QPageLayout.Unit.Millimeter))
        writer.setTitle("Anschreiben" if german else "Cover letter")
        document = QTextDocument()
        image = QImage(str(signature)) if signature and signature.is_file() else QImage()
        if not image.isNull():
            document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(SIGNATURE_RESOURCE), image)
        document.setHtml(letter_html(parts.letter, sender=sender, company=company, position=position,
                                     with_signature=not image.isNull(), german=german))
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.print_(writer)
        del writer
        joined = PdfWriter()
        joined.append(str(letter_pdf))
        for pdf in parts.pdfs:
            try:
                reader = PdfReader(str(pdf))
                if reader.is_encrypted:
                    raise ValueError("encrypted")
                joined.append(reader)
            except Exception:  # noqa: BLE001 - one bad attachment must not stop the folder
                skipped.append(pdf.name)
        with target.open("wb") as handle:
            joined.write(handle)
    finally:
        letter_pdf.unlink(missing_ok=True)
    return skipped
