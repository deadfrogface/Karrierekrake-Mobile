"""The user's scanned signature: stored once as a small PNG in the data folder, never sent anywhere by itself."""
from __future__ import annotations

from pathlib import Path

from core.platform_paths import user_data_dir

MAX_SOURCE_BYTES = 10_000_000
MAX_SIZE = (900, 300)


def signature_path() -> Path:
    return user_data_dir() / "signature.png"


def has_signature() -> bool:
    return signature_path().is_file()


def store_signature(source: str | Path) -> Path:
    """Read an image (PNG/JPG), scale it down and save it as PNG."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    source = Path(source)
    if not source.is_file() or source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("signature_unreadable")
    image = QImage(str(source))
    if image.isNull() or image.width() < 20 or image.height() < 10:
        raise ValueError("signature_unreadable")
    if image.width() > MAX_SIZE[0] or image.height() > MAX_SIZE[1]:
        image = image.scaled(MAX_SIZE[0], MAX_SIZE[1], Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    target = signature_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target), "PNG"):  # re-encoding drops metadata such as camera or location data
        raise OSError("signature_not_saved")
    return target


def remove_signature() -> None:
    signature_path().unlink(missing_ok=True)
