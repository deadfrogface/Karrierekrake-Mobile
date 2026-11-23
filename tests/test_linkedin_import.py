"""LinkedIn data export (ZIP with CSV files) → profile, without scraping and without AI."""
import zipfile

import pytest

from core.linkedin_import import LinkedInImportError, read_linkedin_export

FILES = {
    "Profile.csv": "First Name,Last Name,Headline,Summary\nKim,Test,Bürokauffrau | Buchhaltung | SAP,Ich organisiere gern.\n",
    "Skills.csv": "Name\nBuchhaltung\nSAP\nKundenservice\n",
    "Positions.csv": ("Company Name,Title,Description,Location,Started On,Finished On\n"
                      "Muster GmbH,Sachbearbeiterin,\"Rechnungen prüfen\n• Mahnwesen\",Berlin,Mar 2019,\n"),
    "Education.csv": "School Name,Start Date,End Date,Notes,Degree Name,Activities\nIHK Berlin,2016,2019,,Kauffrau für Büromanagement,\n",
    "Languages.csv": "Name,Proficiency\nDeutsch,Native or bilingual proficiency\nEnglisch,Professional working proficiency\n",
    "Certifications.csv": "Name,Url,Authority,Started On,Finished On,License Number\nDATEV Grundlagen,,DATEV eG,Jun 2021,,\n",
    "Connections.csv": "Notes:\n\"private\"\n\nFirst Name,Last Name\nA,B\n",
    "messages.csv": "secret\n",
}


def _zip(tmp_path, files=FILES):
    path = tmp_path / "Basic_LinkedInDataExport.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return path


def test_everything_useful_is_read(tmp_path):
    data = read_linkedin_export(_zip(tmp_path))
    q = data.qualifications
    assert [s.value for s in q.skills] == ["Buchhaltung", "SAP", "Kundenservice"]
    job = q.work_experience[0]
    assert (job.title, job.company, job.start_date, job.end_date) == ("Sachbearbeiterin", "Muster GmbH", "03/2019", "")
    assert job.responsibilities == ["Rechnungen prüfen", "Mahnwesen"]
    assert q.education[0].qualification == "Kauffrau für Büromanagement"
    assert [(lang.language, lang.level) for lang in q.languages] == [("Deutsch", "Muttersprache"), ("Englisch", "fließend")]
    assert q.certificates[0].issuer == "DATEV eG" and q.certificates[0].date == "06/2021"
    assert data.keywords == ["Bürokauffrau", "Buchhaltung", "SAP"]
    assert data.counts() == {"skills": 3, "positions": 1, "education": 1, "languages": 2, "certificates": 1}


def test_messages_and_connections_are_never_read(tmp_path):
    data = read_linkedin_export(_zip(tmp_path))
    assert "secret" not in repr(data) and "private" not in repr(data)


def test_unpacked_folder_works_too(tmp_path):
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "Skills.csv").write_text("Name\nExcel\n", encoding="utf-8")
    assert [s.value for s in read_linkedin_export(folder).qualifications.skills] == ["Excel"]


def test_wrong_files_are_refused(tmp_path):
    bad = tmp_path / "x.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(LinkedInImportError):
        read_linkedin_export(bad)
    with pytest.raises(LinkedInImportError):
        read_linkedin_export(_zip(tmp_path, {"other.txt": "x"}))


def test_merge_keeps_existing_and_skips_duplicates(tmp_path):
    from core.config import QualificationsConfig, SourcedText
    from desktop.services.profile_merge import merge_qualifications

    existing = QualificationsConfig(skills=[SourcedText(value="SAP", source="manual")])
    merged = merge_qualifications(existing, read_linkedin_export(_zip(tmp_path)).qualifications)
    assert [s.value for s in merged.skills] == ["SAP", "Buchhaltung", "Kundenservice"]


def test_profile_page_imports_the_export(tmp_path, monkeypatch, qtbot):
    from desktop import paths as paths_mod
    from desktop.i18n import i18n

    def fake_dirs():
        root = tmp_path / "Karrierekrake"
        dirs = {n: root / n for n in ("config", "data", "logs", "browser_profile", "browsers", "cvs", "cache",
                                       "cover_letters")}
        dirs["root"] = root
        for p in dirs.values():
            p.mkdir(parents=True, exist_ok=True)
        return dirs

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(paths_mod, "ensure_app_dirs", fake_dirs)
    monkeypatch.setattr("desktop.services.ensure_app_dirs", fake_dirs)
    from desktop.pages import profile
    from desktop.services import ConfigService

    i18n.set_language("de")
    archive = _zip(tmp_path)
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getOpenFileName", lambda *a, **k: (str(archive), ""))
    monkeypatch.setattr(profile.QMessageBox, "exec", lambda self: profile.QMessageBox.StandardButton.Yes)
    infos = []
    monkeypatch.setattr(profile.QMessageBox, "information", lambda *a, **k: infos.append(a[-1]))
    service = ConfigService()
    page = profile.ProfilePage(service)
    qtbot.addWidget(page)
    page.import_from_linkedin()
    skills = service.load().profile.qualifications.skill_values()
    assert {"Buchhaltung", "SAP", "Kundenservice", "Bürokauffrau"} <= set(skills)
    assert service.load().profile.qualifications.languages[0].language == "Deutsch"
    assert infos and "LinkedIn" in infos[-1]
