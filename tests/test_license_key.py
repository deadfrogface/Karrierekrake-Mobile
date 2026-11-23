"""License keys without a server: signed by the owner, bound to the buyer's device codes."""
import importlib.util
from pathlib import Path

import pytest

from core.commercial import license_file as lf
from core.commercial.device_id import device_code, is_device_code

_spec = importlib.util.spec_from_file_location("issue_license_key",
                                               Path(__file__).resolve().parents[1] / "scripts/issue_license_key.py")
issuer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(issuer)

NOW = 1_800_000_000
HERE = device_code("this-computer")
OTHER = device_code("someone-else")


@pytest.fixture()
def signing(tmp_path):
    key_id, public = issuer.keygen(tmp_path / "signing.key")
    policy = {"environment": "production", "public_keys": {key_id: public}}
    return tmp_path / "signing.key", key_id, policy


def _key(signing, **kw):
    private, key_id, _ = signing
    args = {"devices": [HERE], "license_id": "order-0001", "features": ["ad_free"], "now": NOW}
    args.update(kw)
    return issuer.issue(private, key_id=key_id, **args)


def test_device_code_is_stable_and_well_formed():
    assert device_code("abc") == device_code("ABC ") and is_device_code(device_code("abc"))
    assert device_code("abc") != device_code("abd") and is_device_code(device_code())


def test_key_works_on_the_named_device_only(signing):
    policy = signing[2]
    raw = lf.key_to_envelope(_key(signing))
    assert lf.verify_license(raw, policy=policy, now=NOW, device=HERE)["features"] == ["ad_free"]
    with pytest.raises(ValueError):
        lf.verify_license(raw, policy=policy, now=NOW, device=OTHER)


def test_no_end_date_and_expiry(signing):
    policy = signing[2]
    forever = lf.key_to_envelope(_key(signing))
    assert lf.verify_license(forever, policy=policy, now=NOW + 10 * 365 * 86400, device=HERE)
    dated = lf.key_to_envelope(_key(signing, expires="2027-01-31"))
    with pytest.raises(ValueError):
        lf.verify_license(dated, policy=policy, now=NOW + 10 * 365 * 86400, device=HERE)


def test_tampering_and_foreign_keys_fail(signing, tmp_path):
    policy = signing[2]
    key = _key(signing)
    raw = lf.key_to_envelope(key).replace(b"ad_free", b"cloud_models")
    with pytest.raises(ValueError):
        lf.verify_license(raw, policy=policy, now=NOW, device=HERE)
    other_id, other_public = issuer.keygen(tmp_path / "other.key")
    with pytest.raises(ValueError):
        lf.verify_license(lf.key_to_envelope(key), policy={"environment": "production",
                                                            "public_keys": {other_id: other_public}}, now=NOW, device=HERE)
    with pytest.raises(ValueError):
        lf.key_to_envelope("not a key")


def test_pasted_key_with_line_breaks_is_stored(signing, tmp_path, monkeypatch):
    policy = signing[2]
    monkeypatch.setattr("core.commercial.device_id.device_code", lambda raw=None: HERE)
    key = _key(signing)
    pasted = "\n".join(key[i:i + 40] for i in range(0, len(key), 40))
    payload = lf.import_license_key(pasted, policy=policy, destination=tmp_path / "license.json", now=NOW)
    assert payload["license_id"] == "order-0001" and (tmp_path / "license.json").is_file()


def test_issuer_refuses_bad_input(signing):
    with pytest.raises(SystemExit):
        _key(signing, devices=["nonsense"])
    with pytest.raises(SystemExit):
        _key(signing, features=["everything"])
    with pytest.raises(SystemExit):
        issuer.keygen(signing[0])  # never overwrites a signing key


def test_panel_shows_device_code_and_takes_a_key(qtbot, monkeypatch, signing, tmp_path):
    from desktop.widgets import commerce_panel

    monkeypatch.setenv("KARRIEREKRAKE_DATA_DIR", str(tmp_path / "data"))
    panel = commerce_panel.CommercePanel()
    qtbot.addWidget(panel)
    assert is_device_code(panel.device_code.text())
    seen = []
    monkeypatch.setattr(commerce_panel, "import_license_key", lambda text: seen.append(text))
    monkeypatch.setattr(commerce_panel.QInputDialog, "getMultiLineText", lambda *a, **k: ("KKL1.abc", True))
    panel.enter_key()
    assert seen == ["KKL1.abc"]
    monkeypatch.setattr(commerce_panel, "import_license_key", lambda text: (_ for _ in ()).throw(ValueError("x")))
    warnings = []
    monkeypatch.setattr(commerce_panel.QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    panel.enter_key()
    assert panel.device_code.text() in warnings[0]
