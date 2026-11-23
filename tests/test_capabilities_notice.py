"""The setup assistant and About dialog say plainly what the app does and where the local AI has limits."""
from desktop.i18n import tr
from desktop.widgets.capabilities_notice import CapabilitiesNotice, capabilities_html


def test_notice_names_hardware_speed_and_review(qtbot):
    widget = CapabilitiesNotice()
    qtbot.addWidget(widget)
    text = widget.text.text()
    for needle in ("8 GB", "ChatGPT", "Freigabe", "KI-Anbieter wählen"):
        assert needle in text
    assert text.count("<li>") == len([x for x in (tr("caps.can") + "\n" + tr("caps.limits")).split("\n") if x])


def test_english_text_exists():
    from desktop.i18n import i18n
    i18n.set_language("en")
    try:
        assert "8 GB of memory" in capabilities_html()
    finally:
        i18n.set_language("de")
