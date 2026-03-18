from pathlib import Path

from app.utils import sha256_file, slugify, stable_slug


def test_slugify_fallback() -> None:
    assert slugify("中文 标题") == "report"
    assert slugify("Alpha Report 2025") == "alpha-report-2025"


def test_sha256_file(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello", encoding="utf-8")
    assert sha256_file(file_path)


def test_stable_slug_is_deterministic() -> None:
    left = stable_slug("中文 标题", "input/sample.pdf")
    right = stable_slug("中文 标题", "input/sample.pdf")
    assert left == right
    assert left.startswith("report-")
