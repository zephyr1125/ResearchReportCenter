from pathlib import Path

from app.models import DocumentContent, ImageBlock, ManifestRecord, PageContent, TextBlock
from app.site_builder import render_index_markdown, render_report_markdown


def test_render_report_markdown(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    image_path = docs_dir / "assets" / "sample" / "figure.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")

    document = DocumentContent(
        title="测试研报",
        source_pdf=Path("input/sample.pdf"),
        pages=[
            PageContent(
                page_number=1,
                items=[
                    TextBlock(order=0, page_number=1, text="Original text", translated_text="译文"),
                    ImageBlock(order=1, page_number=1, image_path=image_path, caption="图片"),
                ],
            )
        ],
    )

    markdown = render_report_markdown(document, docs_dir)

    assert "# 测试研报" in markdown
    assert "Original text" in markdown
    assert "译文" in markdown
    assert "### 段落" not in markdown
    assert "**原文**" not in markdown
    assert "**译文**" not in markdown
    assert "../assets/sample/figure.png" in markdown


def test_render_index_markdown() -> None:
    content = render_index_markdown(
        [
            ManifestRecord(
                source_path="input/sample.pdf",
                source_name="sample.pdf",
                sha256="abc",
                article_path="reports/sample.md",
                status="success",
                processed_at="2026-03-18T20:30:00",
                error=None,
            )
        ]
    )
    assert "[sample](reports/sample.md)" in content
