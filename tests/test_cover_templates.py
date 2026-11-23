"""Own cover-letter templates: made from a letter, saved, chosen and rendered by the normal writer."""
import pytest

from core import cover_templates as ct


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path))


LETTER = """Sehr geehrte Frau Beispiel,

mit großem Interesse habe ich die Stelle als Bürokraft bei der Muster GmbH gelesen. {Klammern} bleiben Text.

Mit freundlichen Grüßen
Alex Muster"""


def test_letter_becomes_template():
    template, used = ct.template_from_letter(LETTER, company="Muster GmbH", position="Bürokraft", full_name="Alex Muster")
    assert template.startswith("{salutation},")
    assert "bei der {company}" in template and "als {job_title}" in template and template.endswith("{full_name}")
    assert set(used) == {"company", "job_title", "full_name", "salutation"}
    rendered = template.format_map({"salutation": "Sehr geehrte Damen und Herren", "company": "Beispiel AG",
                                    "job_title": "Sachbearbeitung", "full_name": "Kim Test"})
    assert "{Klammern} bleiben Text" in rendered and "Beispiel AG" in rendered and "Muster" not in rendered


def test_save_list_delete():
    path = ct.save_template("Mein Stil", "{salutation},\nText")
    assert [t.name for t in ct.list_templates()] == ["Mein Stil"]
    assert ct.is_user_template(str(path))
    ct.delete_template(path)
    assert ct.list_templates() == []


def test_names_and_paths_are_safe(tmp_path):
    path = ct.save_template("../../evil", "x")
    assert path.parent == ct.templates_dir()
    with pytest.raises(ValueError):
        ct.delete_template(tmp_path / "outside.txt")
    with pytest.raises(ValueError):
        ct.save_template("  ", "x")
    with pytest.raises(ValueError):
        ct.save_template("a", "x" * (ct.MAX_CHARS + 1))


def test_writer_uses_the_chosen_template(tmp_path):
    from core.config import empty_app_config
    from core.cover_letter import _render_template
    from core.models import Job

    path = ct.save_template("Kurz", "{salutation},\n\nich möchte zu {company}.\n\nViele Grüße\n{full_name}")
    cfg = empty_app_config(root=tmp_path)
    cfg.settings.cover_letter_template = str(path)
    cfg.application.first_name, cfg.application.last_name = "Kim", "Test"
    text = _render_template(Job(title="Bürokraft", company="Beispiel AG", description="x"), cfg,
                            contact_claims=None, skills_list=[], experience_sentence="")
    assert "ich möchte zu Beispiel AG." in text


def test_dialog_save_use_and_delete(qtbot, tmp_path, monkeypatch):
    from core.config import empty_app_config
    from desktop.widgets import cover_templates_dialog as dlg

    class _Service:
        def __init__(self):
            self.cfg = empty_app_config(root=tmp_path)

        def load(self):
            import copy
            return copy.deepcopy(self.cfg)

        def save(self, cfg):
            self.cfg = cfg

    service = _Service()
    dialog = dlg.CoverTemplatesDialog(service)
    qtbot.addWidget(dialog)
    assert dialog.choice.currentData() == "" and "{salutation}" in dialog.editor.toPlainText()
    assert not dialog.delete_btn.isEnabled()

    monkeypatch.setattr(dlg.FromLetterDialog, "exec", lambda self: dlg.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(dlg.FromLetterDialog, "result_template",
                        lambda self: ("{salutation},\nIch will zu {company}.\n{full_name}", ["company", "salutation"]))
    dialog._from_letter()
    assert dialog.name.text() == "Mein Anschreiben"
    dialog._use()  # edited text on top of the standard is saved as a new template, never lost
    assert service.cfg.settings.cover_letter_template.endswith("Mein Anschreiben.txt")
    assert "Ich will zu {company}." in (ct.templates_dir() / "Mein Anschreiben.txt").read_text(encoding="utf-8")

    ct.delete_template(ct.templates_dir() / "Mein Anschreiben.txt")
    service.cfg.settings.cover_letter_template = ct.DEFAULT_SETTING
    dialog = dlg.CoverTemplatesDialog(service)
    qtbot.addWidget(dialog)
    dialog.editor.setPlainText("{salutation},\nKurz.\n{full_name}")
    dialog.name.setText("Kurz")
    dialog._save()
    assert dialog.choice.currentText() == "Kurz"
    dialog._use()
    assert service.cfg.settings.cover_letter_template.endswith("Kurz.txt")

    dialog = dlg.CoverTemplatesDialog(service)
    qtbot.addWidget(dialog)
    assert dialog.choice.currentText() == "Kurz" and dialog.delete_btn.isEnabled()
    dialog._delete()
    assert service.cfg.settings.cover_letter_template == ct.DEFAULT_SETTING and ct.list_templates() == []


def test_placeholder_help_in_both_languages():
    assert "{company} Firma" in ct.placeholder_help()
    english = ct.placeholder_help(english=True)
    assert "{company} company" in english and "Firma" not in english


@pytest.mark.parametrize("style", list(ct.STYLES))
@pytest.mark.parametrize("english", [False, True])
def test_generated_styles_render_with_only_known_placeholders(style, english):
    import string

    name, text = ct.generate_template(style, english=english)
    fields = {f for _, f, _, _ in string.Formatter().parse(text) if f}
    assert name and fields <= set(ct.PLACEHOLDERS) and {"salutation", "full_name"} <= fields
    assert fields & {"company", "company_bei"}


def test_dialog_generates_a_style(qtbot, tmp_path, monkeypatch):
    import copy

    from core.config import empty_app_config
    from desktop.widgets import cover_templates_dialog as dlg

    class _Service:
        cfg = empty_app_config(root=tmp_path)

        def load(self):
            return copy.deepcopy(self.cfg)

        def save(self, cfg):
            self.cfg = cfg

    dialog = dlg.CoverTemplatesDialog(_Service())
    qtbot.addWidget(dialog)
    monkeypatch.setattr(dlg.QInputDialog, "getItem", lambda *a, **k: ("Quereinstieg", True))
    dialog._generate()
    assert dialog.name.text() == "Quereinstieg" and "neues Aufgabenfeld" in dialog.editor.toPlainText()
