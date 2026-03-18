from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.models import ManifestRecord


def load_manifest(path: Path) -> dict[str, ManifestRecord]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, ManifestRecord] = {}
    for item in data.get("records", []):
        record = ManifestRecord(**item)
        records[record.source_path] = record
    return records


def save_manifest(path: Path, records: dict[str, ManifestRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "records": [asdict(record) for record in sorted(records.values(), key=lambda x: x.source_name.lower())]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
