from __future__ import annotations

import re
from pathlib import Path

import fitz

from app.models import DocumentContent, ImageBlock, PageContent, TextBlock


class PdfProcessor:
    def extract(self, pdf_path: Path, asset_dir: Path) -> DocumentContent:
        asset_dir.mkdir(parents=True, exist_ok=True)
        document = fitz.open(pdf_path)
        try:
            title = pdf_path.stem
            metadata_title = (document.metadata or {}).get("title", "").strip()
            if metadata_title:
                title = metadata_title

            result = DocumentContent(title=title, source_pdf=pdf_path)
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                page_content = self._extract_page(page, asset_dir, page_index)
                result.pages.append(page_content)
            return result
        finally:
            document.close()

    def _extract_page(self, page: fitz.Page, asset_dir: Path, page_index: int) -> PageContent:
        page_content = PageContent(page_number=page_index + 1)
        text_dict = page.get_text("dict")
        blocks = sorted(text_dict.get("blocks", []), key=lambda item: (item["bbox"][1], item["bbox"][0]))
        item_order = 0
        image_count = 0

        for block in blocks:
            block_type = block.get("type")
            if block_type == 0:
                text = self._extract_text_from_block(block)
                if text:
                    page_content.items.append(
                        TextBlock(order=item_order, page_number=page_index + 1, text=text)
                    )
                    item_order += 1
            elif block_type == 1:
                image_count += 1
                image_path = asset_dir / f"page-{page_index + 1}-image-{image_count}.png"
                self._save_clip_image(page, fitz.Rect(block["bbox"]), image_path)
                page_content.items.append(
                    ImageBlock(
                        order=item_order,
                        page_number=page_index + 1,
                        image_path=image_path,
                        caption=f"第 {page_index + 1} 页图片 {image_count}",
                    )
                )
                item_order += 1

        page_content.page_kind = self._detect_page_kind(page_content.items)
        if page_content.page_kind != "appendix":
            page_content.items = self._filter_page_items(page_content.items)
        for index, item in enumerate(page_content.items):
            item.order = index

        drawings = page.get_drawings()
        if drawings and image_count == 0:
            preview_path = asset_dir / f"page-{page_index + 1}-preview.png"
            pixmap = page.get_pixmap(dpi=150, alpha=False)
            pixmap.save(preview_path)
            page_content.items.append(
                ImageBlock(
                    order=item_order,
                    page_number=page_index + 1,
                    image_path=preview_path,
                    caption=f"第 {page_index + 1} 页图表预览",
                )
            )

        return page_content

    @staticmethod
    def _extract_text_from_block(block: dict) -> str:
        fragments: list[str] = []
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            if line_text.strip():
                fragments.append(line_text.strip())
        return "\n".join(fragments).strip()

    @staticmethod
    def _save_clip_image(page: fitz.Page, rect: fitz.Rect, output_path: Path) -> None:
        pixmap = page.get_pixmap(clip=rect, dpi=180, alpha=False)
        pixmap.save(output_path)

    def _filter_page_items(self, items: list[TextBlock | ImageBlock]) -> list[TextBlock | ImageBlock]:
        text_blocks = [item for item in items if isinstance(item, TextBlock)]
        chart_heavy_page = self._is_chart_heavy_page(text_blocks)
        filtered: list[TextBlock | ImageBlock] = []
        for item in items:
            if isinstance(item, ImageBlock):
                filtered.append(item)
                continue
            if self._should_drop_text_block(item.text, chart_heavy_page=chart_heavy_page):
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _detect_page_kind(items: list[TextBlock | ImageBlock]) -> str:
        text_blocks = [item for item in items if isinstance(item, TextBlock)]
        if not text_blocks:
            return "content"
        texts = [block.text.strip() for block in text_blocks if block.text.strip()]
        if PdfProcessor._is_disclaimer_page(texts):
            return "appendix"
        if any("Links to recent reports in the China Macro Tracker series" in text for text in texts):
            dated_titles = sum(1 for text in texts if PdfProcessor._looks_like_report_list_entry(text))
            if dated_titles >= 8:
                return "report_list"
        return "content"

    @staticmethod
    def _is_disclaimer_page(texts: list[str]) -> bool:
        compact = "\n".join(texts).lower()
        normalized_texts = {" ".join(text.split()).strip().lower() for text in texts if text.strip()}
        title_markers = {
            "disclosures & disclaimer",
            "disclosure appendix",
            "additional disclosures",
            "disclaimer",
        }
        if normalized_texts & title_markers:
            return True
        keywords = [
            "issuer of report",
            "legal entities as at",
            "all rights reserved",
            "research business",
            "financial conduct authority",
            "monetary authority",
        ]
        hits = sum(1 for keyword in keywords if keyword in compact)
        return hits >= 3

    @staticmethod
    def _looks_like_report_list_entry(text: str) -> bool:
        compact = " ".join(text.split())
        return bool(
            re.search(
                r",\s+\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$",
                compact,
                re.I,
            )
        )

    @staticmethod
    def _is_chart_heavy_page(text_blocks: list[TextBlock]) -> bool:
        if len(text_blocks) < 15:
            return False
        short_count = sum(1 for block in text_blocks if len(block.text.strip()) <= 40)
        numericish_count = sum(1 for block in text_blocks if PdfProcessor._is_numericish_block(block.text))
        return short_count / len(text_blocks) >= 0.6 or numericish_count / len(text_blocks) >= 0.35

    @staticmethod
    def _should_drop_text_block(text: str, chart_heavy_page: bool) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if PdfProcessor._is_page_number(stripped):
            return True
        if PdfProcessor._is_numericish_block(stripped) and len(stripped) <= 40:
            return True
        if chart_heavy_page:
            if not PdfProcessor._looks_like_narrative_block(stripped):
                return True
            if (
                PdfProcessor._has_chart_keywords(stripped)
                or PdfProcessor._looks_like_figure_title(stripped)
                or PdfProcessor._is_source_note(stripped)
                or PdfProcessor._is_date_axis_label(stripped)
            ):
                return True
        return False

    @staticmethod
    def _is_page_number(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return len(lines) == 1 and bool(re.fullmatch(r"\[?\d{1,3}\]?", lines[0]))

    @staticmethod
    def _is_numericish_block(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        pattern = re.compile(r"^[\d\s,.\-+%():/=]+$")
        month_date = re.compile(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z\-0-9\s]*$", re.I)
        year_only = re.compile(r"^(19|20)\d{2}$")
        matched = 0
        for line in lines:
            compact = line.replace("\u200b", "").strip()
            if pattern.fullmatch(compact) or year_only.fullmatch(compact) or month_date.fullmatch(compact):
                matched += 1
        return matched == len(lines) and any(any(ch.isdigit() for ch in line) for line in lines)

    @staticmethod
    def _looks_like_figure_title(text: str) -> bool:
        compact = text.strip().lower()
        return bool(re.match(r"^\d+\s*:", compact))

    @staticmethod
    def _is_source_note(text: str) -> bool:
        compact = text.strip().lower()
        return compact.startswith("source:") or compact.startswith("note:") or compact.startswith("资料来源：")

    @staticmethod
    def _is_date_axis_label(text: str) -> bool:
        compact = " ".join(text.strip().split()).lower()
        patterns = [
            r"^\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$",
            r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\-\d{2})?(\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\-\d{2})?)*$",
            r"^days before/after cny.*$",
            r"^day 0.*$",
        ]
        return any(re.match(pattern, compact) for pattern in patterns)

    @staticmethod
    def _has_chart_keywords(text: str) -> bool:
        compact = text.strip().lower()
        keywords = [
            "source:",
            "rhs",
            "lhs",
            "y-o-y",
            "m-o-m",
            "q-o-q",
            "cagr",
            "7dma",
            "rolling average",
            "day 0",
            "days before/after cny",
            "million people",
            "thousand square meters",
            "number of flights",
            "housing sales",
            "box office revenue",
            "index, nationwide",
            "special bonds",
            "资料来源：",
            "同比",
            "元旦前/元旦后",
            "日滚动平均线",
            "一千平方米",
            "百万人",
            "票房收入",
            "住房销售",
            "执行航班数目",
        ]
        return any(keyword in compact for keyword in keywords)

    @staticmethod
    def _looks_like_narrative_block(text: str) -> bool:
        stripped = text.strip()
        if len(stripped) >= 180:
            return True
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if len(lines) >= 4 and sum(len(line) for line in lines) >= 120:
            return True
        sentence_markers = [". ", "; ", ": ", "。", "；", "："]
        marker_hits = sum(stripped.count(marker) for marker in sentence_markers)
        return len(stripped) >= 120 and marker_hits >= 2
