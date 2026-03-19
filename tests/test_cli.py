from pathlib import Path

from app.cli import build_summary_source
from app.models import DocumentContent, PageContent, PageKind, TextBlock


def test_build_summary_source_skip_appendix_and_report_list() -> None:
    document = DocumentContent(
        title="test",
        source_pdf=Path("input/sample.pdf"),
        pages=[
            PageContent(
                page_number=1,
                page_kind=PageKind.CONTENT,
                items=[TextBlock(order=0, page_number=1, text="a", translated_text="正文")],
            ),
            PageContent(
                page_number=2,
                page_kind=PageKind.REPORT_LIST,
                items=[TextBlock(order=0, page_number=2, text="list", translated_text="列表")],
            ),
            PageContent(
                page_number=3,
                page_kind=PageKind.APPENDIX,
                items=[TextBlock(order=0, page_number=3, text="disc", translated_text="披露")],
            ),
        ],
    )
    assert build_summary_source(document) == "正文"
