"""Issue Karrierekrake license keys offline – for the owner only. No server needed.

1. Once:  python scripts/issue_license_key.py keygen --out <safe place>/karrierekrake-signing.key
   Keep that file secret and backed up (never in the repository). Put the printed key id and public key into
   config/commercial_release.json → "public_keys".
2. Per sale: the buyer copies the device code from Settings → "Lizenz" (KK-XXXX-XXXX-XXXX-XXXX) and sends it.
   python scripts/issue_license_key.py issue --private-key <file> --key-id <id> --device KK-... \
       --license-id <order number> --features ad_free,cloud_models [--expires 2027-12-31]
   Send the printed KKL1.… key to the buyer; they paste it under "Lizenzschlüssel eingeben".
   New computer or reinstalled system: same --license-id, --revision one higher, old + new device codes.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from core.commercial.device_id import is_device_code  # noqa: E402
from core.commercial.license_file import MAX_DEVICES, canonical, envelope_to_key  # noqa: E402
from core.commercial.release_policy import PAID_FEATURES  # noqa: E402


def keygen(out: Path) -> tuple[str, str]:
    if out.exists():
        raise SystemExit(f"{out} exists – refusing to overwrite a signing key")
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(base64.b64encode(raw).decode("ascii"))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return f"kk-{datetime.now(timezone.utc):%Y%m%d}", base64.b64encode(public).decode("ascii")


def issue(private_key: Path, *, key_id: str, devices: list[str], license_id: str, features: list[str],
          revision: int = 1, expires: str = "", environment: str = "production", now: int | None = None) -> str:
    devices = [d.strip().upper() for d in devices]
    if not devices or len(devices) > MAX_DEVICES or not all(is_device_code(d) for d in devices):
        raise SystemExit(f"1–{MAX_DEVICES} device codes of the form KK-XXXX-XXXX-XXXX-XXXX are needed")
    unknown = [f for f in features if f not in PAID_FEATURES]
    if unknown:
        raise SystemExit(f"unknown features: {unknown}; allowed: {sorted(PAID_FEATURES)}")
    expires_at = 0
    if expires:
        expires_at = int(datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86399
    payload = {"schema": 2, "product": "karrierekrake", "environment": environment, "license_id": license_id,
               "revision": revision, "issued_at": int(time.time()) if now is None else now, "expires_at": expires_at,
               "devices": devices, "features": sorted(set(features))}
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key.read_text(encoding="ascii").strip()))
    envelope = {"key_id": key_id, "payload": payload,
                "signature": base64.b64encode(key.sign(canonical(payload))).decode("ascii")}
    return envelope_to_key(json.dumps(envelope, separators=(",", ":")).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("keygen")
    gen.add_argument("--out", type=Path, required=True)
    iss = sub.add_parser("issue")
    iss.add_argument("--private-key", type=Path, required=True)
    iss.add_argument("--key-id", required=True)
    iss.add_argument("--device", action="append", required=True)
    iss.add_argument("--license-id", required=True)
    iss.add_argument("--features", default="")
    iss.add_argument("--revision", type=int, default=1)
    iss.add_argument("--expires", default="", help="YYYY-MM-DD; empty = no end")
    iss.add_argument("--environment", default="production", choices=("production", "sandbox"))
    args = parser.parse_args(argv)
    if args.command == "keygen":
        key_id, public = keygen(args.out)
        print(f'Private key saved: {args.out} (keep it secret)\nAdd to config/commercial_release.json "public_keys":\n'
              f'  "{key_id}": "{public}"')
    else:
        print(issue(args.private_key, key_id=args.key_id, devices=args.device, license_id=args.license_id,
                    features=[f for f in args.features.split(",") if f], revision=args.revision,
                    expires=args.expires, environment=args.environment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
