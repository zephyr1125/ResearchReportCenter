from __future__ import annotations

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
