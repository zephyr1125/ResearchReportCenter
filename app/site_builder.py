from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import DocumentContent, ImageBlock, ManifestRecord, TextBlock


def render_report_markdown(document: DocumentContent, docs_dir: Path) -> str:
    lines: list[str] = [
        f"# {document.title}",
        "",
        f"- 原始文件：`{document.source_pdf.name}`",
        f"- 生成时间：`{datetime.now().isoformat(timespec='seconds')}`",
        "",
    ]

    for page in document.pages:
        lines.extend([f"## 第 {page.page_number} 页", ""])
        for item in page.items:
            if isinstance(item, TextBlock):
                lines.extend(
                    [
                        item.text,
                        "",
                        item.translated_text or "翻译缺失",
                        "",
                        "---",
                        "",
                    ]
                )
            elif isinstance(item, ImageBlock):
                relative_path = Path("..") / item.image_path.relative_to(docs_dir)
                lines.extend(
                    [
                        f"![{item.caption}]({relative_path.as_posix()})",
                        "",
                        f"*{item.caption}*",
                        "",
                    ]
                )
    return "\n".join(lines).strip() + "\n"


def render_index_markdown(records: list[ManifestRecord]) -> str:
    lines = [
        "# 研报中心",
        "",
        "本页面展示已成功处理并发布到站点的研报。",
        "",
    ]
    if not records:
        lines.extend(["当前暂无可展示的研报。", ""])
        return "\n".join(lines)

    lines.extend(["| 标题 | 原始文件 | 处理时间 |", "| --- | --- | --- |"])
    for record in records:
        article = record.article_path or ""
        title = Path(article).stem if article else record.source_name
        lines.append(
            f"| [{title}]({article}) | `{record.source_name}` | `{record.processed_at or '-'} ` |"
        )
    lines.append("")
    return "\n".join(lines)
