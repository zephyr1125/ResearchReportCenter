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
    if document.ai_summary.strip():
        lines.extend(["## AI 总结", "", (document.highlighted_ai_summary or document.ai_summary).strip(), ""])

    for page in document.pages:
        lines.extend([f"## 第 {page.page_number} 页", ""])
        if page.page_kind == "report_list":
            lines.extend(render_report_list_page(page, docs_dir))
            continue
        if page.page_kind == "appendix":
            lines.extend(render_appendix_page(page, docs_dir))
            continue
        lines.extend(render_bilingual_page(page, docs_dir))
    return "\n".join(lines).strip() + "\n"


def render_bilingual_page(page, docs_dir: Path) -> list[str]:
    chinese_blocks: list[str] = []
    english_blocks: list[str] = []
    images: list[ImageBlock] = []
    for item in page.items:
        if isinstance(item, TextBlock):
            english_blocks.append(item.text)
            chinese_blocks.append(item.highlighted_translated_text or item.translated_text or "翻译缺失")
        elif isinstance(item, ImageBlock):
            images.append(item)

    lines: list[str] = []
    if chinese_blocks:
        lines.extend(["### 中文", ""])
        for block in chinese_blocks:
            lines.extend([block, ""])
    if english_blocks:
        lines.extend(["### 英文", ""])
        for block in english_blocks:
            lines.extend([block, ""])
    if images:
        lines.extend(["### 原页图表", ""])
        for image in images:
            relative_path = Path("..") / image.image_path.relative_to(docs_dir)
            lines.extend(
                [
                    f"![{image.caption}]({relative_path.as_posix()})",
                    "",
                    f"*{image.caption}*",
                    "",
                ]
            )
    return lines


def render_report_list_page(page, docs_dir: Path) -> list[str]:
    lines: list[str] = []
    entries: list[tuple[str, str, str]] = []
    for item in page.items:
        if isinstance(item, TextBlock):
            text = item.text.strip()
            translated = (item.translated_text or "").strip()
            if "Links to recent reports in the China Macro Tracker series" in text:
                lines.extend(["### 近期报告", ""])
                continue
            parsed = parse_report_list_entry(text)
            if parsed:
                english_title, date_text = parsed
                entries.append((date_text, normalize_translated_report_title(translated or english_title), english_title))
        elif isinstance(item, ImageBlock):
            if entries:
                lines.extend(["| 日期 | 中文标题 | 原文标题 |", "| --- | --- | --- |"])
                for date_text, chinese_title, english_title in entries:
                    lines.append(f"| {date_text} | {chinese_title} | {english_title} |")
                lines.extend(["", "### 原页预览", ""])
                entries.clear()
            relative_path = Path("..") / item.image_path.relative_to(docs_dir)
            lines.extend(
                [
                    f"![{item.caption}]({relative_path.as_posix()})",
                    "",
                    f"*{item.caption}*",
                    "",
                ]
            )
    if entries:
        lines.extend(["| 日期 | 中文标题 | 原文标题 |", "| --- | --- | --- |"])
        for date_text, chinese_title, english_title in entries:
            lines.append(f"| {date_text} | {chinese_title} | {english_title} |")
        lines.append("")
    return lines


def render_appendix_page(page, docs_dir: Path) -> list[str]:
    lines: list[str] = ["### 披露与免责声明", "", "_以下内容保留原文，不做翻译。_", ""]
    for item in page.items:
        if isinstance(item, TextBlock):
            lines.extend([item.text, "", "---", ""])
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
    return lines


def parse_report_list_entry(text: str) -> tuple[str, str] | None:
    compact = " ".join(text.split())
    import re

    match = re.match(
        r"^(?P<title>.+),\s+(?P<date>\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})$",
        compact,
        re.I,
    )
    if not match:
        return None
    return match.group("title").strip(), match.group("date").strip()


def normalize_translated_report_title(text: str) -> str:
    compact = " ".join(text.split()).strip().strip("，,")
    import re

    compact = re.sub(r"^\d{4}年\d{1,2}月\d{1,2}日[，,\s]*", "", compact)
    compact = re.sub(r"^\d{1,2}月\d{1,2}日[，,\s]*", "", compact)
    compact = re.sub(r"[，,]?\s*\d{4}年\d{1,2}月\d{1,2}日$", "", compact)
    compact = re.sub(r"[，,]?\s*\d{1,2}月\d{1,2}日$", "", compact)
    return compact.strip().strip("，,")


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
