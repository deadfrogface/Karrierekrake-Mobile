"""Application folder: letter page with signature under the closing line, plus CV and PDF documents."""
from datetime import date

from core.application_folder import SIGNATURE_RESOURCE, approved_letter, collect_parts, letter_html

LETTER = "Sehr geehrte Damen und Herren,\n\nich bewerbe mich.\n\nMit freundlichen Grüßen\nAlex Muster"
SENDER = {"name": "Alex Muster", "street": "Musterweg 1", "postal_code": "10115", "city": "Berlin",
          "phone": "", "email": "alex@example.org"}


def test_signature_sits_between_closing_and_name():
    html = letter_html(LETTER, sender=SENDER, company="Beispiel AG", position="Bürokraft",
                       with_signature=True, today=date(2026, 11, 22))
    closing, rest = html.split("Mit freundlichen Grüßen", 1)
    assert rest.index(SIGNATURE_RESOURCE) < rest.index("Alex Muster")
    assert "Berlin, 22.11.2026" in html and "Bewerbung als Bürokraft" in html and "10115 Berlin" in html


def test_without_signature_and_without_closing():
    assert SIGNATURE_RESOURCE not in letter_html(LETTER, sender=SENDER, company="X", position="", with_signature=False)
    html = letter_html("Nur Text", sender=SENDER, company="X", position="", with_signature=True)
    assert html.count(SIGNATURE_RESOURCE) == 1


def test_letter_text_is_escaped():
    html = letter_html("<script>x</script>", sender={"name": "<b>"}, company="<i>", position="", with_signature=False)
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;" in html


def test_parts_keep_pdfs_and_name_the_rest(tmp_path):
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF-1.4")
    ref = tmp_path / "zeugnis.pdf"
    ref.write_bytes(b"%PDF-1.4")
    docs = [{"path": str(ref), "send": True}, {"path": str(tmp_path / "x.docx"), "send": True},
            {"path": str(tmp_path / "hidden.pdf"), "send": False}]
    parts = collect_parts("Brief", str(cv), docs)
    assert parts.pdfs == [cv, ref] and parts.skipped == ["x.docx"]


def test_approved_letter_is_read(tmp_path):
    (tmp_path / "cover_letters").mkdir()
    (tmp_path / "cover_letters" / "j1.txt").write_text("Brief\n", encoding="utf-8")
    assert approved_letter(tmp_path, "j1") == "Brief" and approved_letter(tmp_path, "nope") == ""


def _pdf(path, text):
    from PySide6.QtGui import QPdfWriter, QTextDocument
    writer = QPdfWriter(str(path))
    doc = QTextDocument()
    doc.setPlainText(text)
    doc.print_(writer)
    del writer
    return path


def test_signature_is_stored_small_and_folder_pdf_is_joined(tmp_path, monkeypatch, qapp):
    from PySide6.QtGui import QColor, QImage
    from pypdf import PdfReader

    from desktop.services import signature
    from desktop.services.application_folder import build_folder_pdf

    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path / "data"))
    big = QImage(2400, 800, QImage.Format.Format_RGB32)
    big.fill(QColor("white"))
    big.save(str(tmp_path / "scan.jpg"))
    stored = signature.store_signature(tmp_path / "scan.jpg")
    image = QImage(str(stored))
    assert stored.suffix == ".png" and image.width() <= 900 and image.height() <= 300

    cv = _pdf(tmp_path / "cv.pdf", "Lebenslauf")
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    parts = collect_parts(LETTER, str(cv), [{"path": str(broken), "send": True}])
    out = tmp_path / "mappe.pdf"
    skipped = build_folder_pdf(parts, out, sender=SENDER, company="Beispiel AG", position="Bürokraft",
                               signature=stored)
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2 and skipped == ["broken.pdf"]
    assert "Bewerbung als Bürokraft" in " ".join(reader.pages[0].extract_text().split())
    assert "Lebenslauf" in reader.pages[1].extract_text()
    assert not list(tmp_path.glob("*.tmp.pdf"))


def test_bad_signature_file_is_refused(tmp_path, monkeypatch, qapp):
    import pytest

    from desktop.services import signature

    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path))
    (tmp_path / "x.png").write_bytes(b"nope")
    with pytest.raises(ValueError):
        signature.store_signature(tmp_path / "x.png")
    assert not signature.has_signature()


def test_delete_all_removes_the_signature(tmp_path):
    from core.privacy.lifecycle import PrivacyLifecycleService as PrivacyLifecycle

    (tmp_path / "signature.png").write_bytes(b"png")
    life = PrivacyLifecycle.__new__(PrivacyLifecycle)
    life.dirs = {"root": tmp_path}
    result = life.delete_signature()
    assert result.ok and not (tmp_path / "signature.png").exists()
