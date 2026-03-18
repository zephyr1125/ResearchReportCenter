from pathlib import Path

from app.models import DocumentContent, ImageBlock, ManifestRecord, PageContent, TextBlock
from app.site_builder import normalize_translated_report_title, parse_report_list_entry, render_index_markdown, render_report_markdown


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


def test_render_report_list_page(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    image_path = docs_dir / "assets" / "sample" / "figure.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")

    document = DocumentContent(
        title="测试列表页",
        source_pdf=Path("input/sample.pdf"),
        pages=[
            PageContent(
                page_number=8,
                page_kind="report_list",
                items=[
                    TextBlock(order=0, page_number=8, text="Links to recent reports in the China Macro Tracker series", translated_text="中国宏观跟踪系列近期报告链接"),
                    TextBlock(order=1, page_number=8, text="A balanced approach, 12 November 2025", translated_text="平衡的方法，2025年11月12日"),
                    ImageBlock(order=2, page_number=8, image_path=image_path, caption="图片"),
                ],
            )
        ],
    )

    markdown = render_report_markdown(document, docs_dir)
    assert "### 近期报告" in markdown
    assert "| 日期 | 中文标题 | 原文标题 |" in markdown
    assert "12 November 2025" in markdown
    assert "平衡的方法，2025年11月12日" in markdown


def test_parse_report_list_entry() -> None:
    parsed = parse_report_list_entry("A balanced approach, 12 November 2025")
    assert parsed == ("A balanced approach", "12 November 2025")


def test_normalize_translated_report_title() -> None:
    assert normalize_translated_report_title("平衡的方法，2025年11月12日") == "平衡的方法"
    assert normalize_translated_report_title("2025年10月1日黄金周前的新措施") == "黄金周前的新措施"
