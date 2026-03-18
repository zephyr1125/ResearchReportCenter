from pathlib import Path

from app.manifest import load_manifest, save_manifest
from app.models import ManifestRecord


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    records = {
        "input/sample.pdf": ManifestRecord(
            source_path="input/sample.pdf",
            source_name="sample.pdf",
            sha256="abc",
            article_path="reports/sample.md",
            status="success",
            processed_at="2026-03-18T20:30:00",
            translated_title="示例标题",
            error=None,
        )
    }

    save_manifest(manifest_path, records)
    loaded = load_manifest(manifest_path)

    assert loaded["input/sample.pdf"].sha256 == "abc"
    assert loaded["input/sample.pdf"].article_path == "reports/sample.md"
    assert loaded["input/sample.pdf"].translated_title == "示例标题"
