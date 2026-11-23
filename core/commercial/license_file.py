"""Ed25519-signed offline entitlements. No secret key in the app.

Schema 1: a license file that expires after at most 31 days (for a future renewal service).
Schema 2: a license key bound to the buyer's devices (device codes, see core.commercial.device_id), without a
server: valid until ``expires_at`` or without end when it is 0. A key copied to another computer does not unlock
anything there.

Local administrator tampering/clock resets cannot be made server-proof offline.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import re
import tempfile
import time
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from core.commercial.release_policy import FREE_FEATURES, PAID_FEATURES, load_policy
from core.platform_paths import user_data_dir

MAX_LICENSE_BYTES = 32768
MAX_OFFLINE_SECONDS = 31 * 86400
KEY_PREFIX = 'KKL1.'
MAX_DEVICES = 5


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def key_to_envelope(text: str) -> bytes:
    """A pasted license key (KKL1.<base64url>) as the signed JSON envelope; spaces and line breaks are ignored."""
    compact = ''.join((text or '').split())
    if not compact.startswith(KEY_PREFIX) or len(compact) > MAX_LICENSE_BYTES * 2:
        raise ValueError('license_key_format')
    body = compact[len(KEY_PREFIX):]
    try:
        return base64.urlsafe_b64decode(body + '=' * (-len(body) % 4))
    except (ValueError, TypeError):
        raise ValueError('license_key_format') from None


def envelope_to_key(raw: bytes) -> str:
    return KEY_PREFIX + base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _schema2_ok(payload, now, device):
    devices = payload.get('devices')
    expires = payload.get('expires_at')
    return (isinstance(devices, list) and 0 < len(devices) <= MAX_DEVICES
            and all(isinstance(d, str) for d in devices) and device in devices
            and type(expires) is int and (expires == 0 or now < expires)
            and type(payload.get('issued_at')) is int and payload['issued_at'] - 300 <= now)


def verify_license(raw: bytes, *, policy=None, now=None, device=None):
    if len(raw) > MAX_LICENSE_BYTES:
        raise ValueError('license_too_large')
    policy = load_policy() if policy is None else policy
    now = int(time.time()) if now is None else now
    try:
        envelope = json.loads(raw)
        payload = envelope['payload']
        key_id = envelope['key_id']
        key = base64.b64decode(policy['public_keys'][key_id], validate=True)
        signature = base64.b64decode(envelope['signature'], validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(signature, canonical(payload))
    except (ValueError, KeyError, TypeError, InvalidSignature):
        raise ValueError('license_signature_invalid') from None
    if not isinstance(payload, dict) or payload.get('schema') not in (1, 2):
        raise ValueError('license_invalid_or_expired')
    common_ok = (payload.get('product') == 'karrierekrake'
                 and payload.get('environment') == policy['environment']
                 and re.fullmatch(r'[a-zA-Z0-9_-]{8,128}', str(payload.get('license_id', '')))
                 and type(payload.get('revision')) is int and payload['revision'] >= 1
                 and isinstance(payload.get('features'), list)
                 and all(feature in PAID_FEATURES for feature in payload['features']))
    if payload['schema'] == 1:
        valid = (common_ok
                 and type(payload.get('issued_at')) is int and type(payload.get('expires_at')) is int
                 and payload['issued_at'] - 300 <= now < payload['expires_at']
                 and 0 < payload['expires_at'] - payload['issued_at'] <= MAX_OFFLINE_SECONDS)
    else:
        if device is None:
            from core.commercial.device_id import device_code
            device = device_code()
        valid = common_ok and _schema2_ok(payload, now, device)
    if not valid:
        raise ValueError('license_invalid_or_expired')
    return payload


def license_path():
    return user_data_dir() / 'commerce/license.json'


def import_license(path: Path, *, policy=None, destination=None, now=None):
    path = Path(path)
    if path.stat().st_size > MAX_LICENSE_BYTES:
        raise ValueError('license_too_large')
    return import_license_bytes(path.read_bytes(), policy=policy, destination=destination, now=now)


def import_license_key(text: str, *, policy=None, destination=None, now=None):
    """A pasted license key; stored like a license file."""
    return import_license_bytes(key_to_envelope(text), policy=policy, destination=destination, now=now)


def import_license_bytes(raw: bytes, *, policy=None, destination=None, now=None):
    policy = load_policy() if policy is None else policy
    payload = verify_license(raw, policy=policy, now=now)
    destination = Path(destination) if destination else license_path()
    if destination.exists():
        # Expiry must not allow an older signed grant to replace a newer revoke.
        try:
            previous_raw = destination.read_bytes()
            previous = json.loads(previous_raw)['payload']
            verify_license(previous_raw, policy=policy, now=previous['issued_at'])
        except (ValueError, KeyError, TypeError):
            raise ValueError('existing_license_unreadable') from None
        if (previous['license_id'] != payload['license_id']
                or payload['revision'] < previous['revision']
                or (payload['revision'] == previous['revision'] and canonical(payload) != canonical(previous))):
            raise ValueError('license_revision_conflict')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.license-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return payload


def current_license(*, policy=None):
    try:
        path = license_path()
        if path.stat().st_size > MAX_LICENSE_BYTES:
            return None
        return verify_license(path.read_bytes(), policy=policy)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def feature_allowed(feature):
    if feature in FREE_FEATURES:
        return True
    try:
        policy = load_policy()
        payload = current_license(policy=policy)
        # Sandbox entitlements are visible in Settings but never unlock production.
        return bool(policy['environment'] == 'production' and feature in policy['enabled_features']
                    and payload and feature in payload['features'])
    except (OSError, ValueError, KeyError, TypeError):
        return False
