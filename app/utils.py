from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return cleaned or "report"


def stable_slug(name: str, source_key: str) -> str:
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:8]
    return f"{slugify(name)}-{digest}"


def ensure_relative_posix(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()
