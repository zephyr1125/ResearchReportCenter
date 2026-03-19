from __future__ import annotations

import argparse
import logging
import shutil
import warnings
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.highlighter import OpenAICompatibleHighlighter, apply_numeric_highlights, apply_phrase_highlights
from app.llm_client import LLMClient, LLMError
from app.manifest import load_manifest, save_manifest
from app.models import ImageBlock, ManifestRecord, PageKind, TextBlock
from app.pdf_processor import PdfProcessor
from app.summarizer import OpenAICompatibleSummarizer, SummaryError
from app.site_builder import normalize_translated_report_title, render_index_markdown, render_report_markdown
from app.translator import OpenAICompatibleTranslator, TranslationError, Translator, VolcengineTranslator
from app.utils import ensure_relative_posix, sha256_file, stable_slug


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="研报 PDF 增量翻译并同步到静态网站")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-site", help="增量构建静态网站")
    build.add_argument("--force", action="store_true", help="忽略 manifest，强制全量重建")
    build.add_argument("--file", help="仅处理指定文件名，例如 report.pdf")
    build.add_argument("--skip-translation", action="store_true", help="跳过真实翻译，先生成预览站点")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root_dir = Path.cwd()
    settings = Settings.load(root_dir)
    settings.ensure_directories()
    logger = configure_logger(settings.logs_dir / "build-site.log")

    if args.command == "build-site":
        return run_build_site(
            settings,
            logger,
            force=args.force,
            file_name=args.file,
            skip_translation=args.skip_translation,
        )

    parser.error(f"未知命令：{args.command}")
    return 2


def configure_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("research-report-center")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def run_build_site(
    settings: Settings,
    logger: logging.Logger,
    force: bool = False,
    file_name: str | None = None,
    skip_translation: bool = False,
) -> int:
    manifest = load_manifest(settings.manifest_path)
    processor = PdfProcessor()

    pdf_files = sorted(settings.input_dir.glob("*.pdf"))
    if file_name:
        pdf_files = [path for path in pdf_files if path.name == file_name]
        if not pdf_files:
            logger.error("未在 input 目录找到指定文件：%s", file_name)
            return 1

    if not pdf_files:
        logger.info("input 目录中没有 PDF 文件，已跳过构建。")
        write_index(settings, manifest)
        save_manifest(settings.manifest_path, manifest)
        return 0

    changed = 0
    translator: Translator | None = None
    summarizer: OpenAICompatibleSummarizer | None = None
    highlighter: OpenAICompatibleHighlighter | None = None
    for pdf_path in pdf_files:
        source_key = ensure_relative_posix(pdf_path, settings.root_dir)
        sha256 = sha256_file(pdf_path)
        existing = manifest.get(source_key)
        needs_process = force or existing is None or existing.sha256 != sha256
        if not needs_process:
            logger.info("跳过未变化文件：%s", pdf_path.name)
            continue

        changed += 1
        logger.info("开始处理：%s", pdf_path.name)
        slug = stable_slug(pdf_path.stem, source_key)
        article_path = settings.reports_dir / f"{slug}.md"
        asset_dir = settings.assets_dir / slug

        try:
            if translator is None and not skip_translation:
                logger.info("初始化翻译器：%s", settings.translator_provider)
                translator = build_translator(settings)
            if asset_dir.exists():
                shutil.rmtree(asset_dir)
            logger.info("开始解析 PDF：%s", pdf_path.name)
            document = processor.extract(pdf_path, asset_dir)
            document.translated_title = build_document_title(
                document.title,
                translator,
                skip_translation=skip_translation,
            )
            total_pages = len(document.pages)
            logger.info("PDF 解析完成：共 %s 页", total_pages)
            for page_index, page in enumerate(document.pages, start=1):
                text_blocks = [item for item in page.items if isinstance(item, TextBlock)]
                logger.info(
                    "处理第 %s/%s 页：类型=%s，文本块=%s",
                    page_index,
                    total_pages,
                    page.page_kind.value,
                    len(text_blocks),
                )
                translated_blocks = 0
                for item in text_blocks:
                    if page.page_kind == PageKind.APPENDIX:
                        item.translated_text = ""
                        continue
                    item.translated_text = build_translated_text(
                        item.text,
                        translator,
                        skip_translation=skip_translation,
                    )
                    translated_blocks += 1
                    if translated_blocks == len(text_blocks) or translated_blocks % 5 == 0:
                        logger.info(
                            "第 %s 页翻译进度：%s/%s",
                            page_index,
                            translated_blocks,
                            len(text_blocks),
                        )
                if settings.highlight_enabled and page.page_kind == PageKind.CONTENT:
                    if highlighter is None and settings.summary_enabled and not skip_translation:
                        logger.info("初始化高亮模型")
                        highlighter = build_highlighter(settings)
                    logger.info("开始高亮第 %s 页", page_index)
                    apply_page_highlights(page, highlighter)
                    logger.info("完成高亮第 %s 页", page_index)
            if settings.summary_enabled and not skip_translation:
                summary_text = build_summary_source(document)
                if summary_text.strip():
                    try:
                        logger.info("开始生成 AI 总结")
                        if summarizer is None:
                            summarizer = build_summarizer(settings)
                        document.ai_summary = summarizer.summarize(summary_text)
                        if settings.highlight_enabled:
                            if highlighter is None:
                                logger.info("初始化高亮模型")
                                highlighter = build_highlighter(settings)
                            logger.info("开始高亮 AI 总结")
                            document.highlighted_ai_summary = apply_summary_highlights(
                                document.ai_summary,
                                highlighter,
                            )
                            logger.info("完成高亮 AI 总结")
                        logger.info("AI 总结生成完成")
                    except SummaryError as error:
                        logger.warning("AI 总结生成失败，已跳过：%s", error)
            logger.info("开始生成文章 Markdown：%s", article_path.name)
            markdown = render_report_markdown(document, settings.docs_dir)
            article_path.write_text(markdown, encoding="utf-8")
            manifest[source_key] = ManifestRecord(
                source_path=source_key,
                source_name=pdf_path.name,
                sha256=sha256,
                article_path=ensure_relative_posix(article_path, settings.docs_dir),
                status="success",
                processed_at=datetime.now().isoformat(timespec="seconds"),
                translated_title=document.translated_title or document.title,
                error=None,
            )
            logger.info("处理完成：%s", pdf_path.name)
        except Exception as error:  # noqa: BLE001
            logger.exception("处理失败：%s", pdf_path.name)
            manifest[source_key] = ManifestRecord(
                source_path=source_key,
                source_name=pdf_path.name,
                sha256=sha256,
                article_path=existing.article_path if existing else None,
                status="failed",
                processed_at=datetime.now().isoformat(timespec="seconds"),
                translated_title=existing.translated_title if existing else None,
                error=str(error),
            )

    if changed == 0:
        logger.info("没有新增或变更的 PDF，直接更新首页索引。")

    write_index(settings, manifest)
    write_failures(settings, manifest)
    save_manifest(settings.manifest_path, manifest)
    logger.info("站点索引与状态文件已更新。")
    return 0


def build_translated_text(text: str, translator: Translator | None, skip_translation: bool) -> str:
    if skip_translation:
        return f"[预览模式，未调用翻译接口]\n{text}"
    if translator is None:
        raise TranslationError("翻译器未初始化。")
    return translator.translate(text)


def build_document_title(title: str, translator: Translator | None, skip_translation: bool) -> str:
    if skip_translation:
        return title
    translated = build_translated_text(title, translator, skip_translation=False)
    compact = " ".join(translated.split()).strip()
    return normalize_translated_report_title(compact) or title


def _build_llm_client(settings: Settings) -> LLMClient:
    return LLMClient(
        api_key=settings.summary_api_key,
        base_url=settings.summary_base_url,
        model=settings.summary_model,
    )


def build_translator(settings: Settings) -> Translator:
    if settings.translator_provider == "openai":
        client = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
        return OpenAICompatibleTranslator(client)
    if settings.translator_provider == "volcengine":
        return VolcengineTranslator(
            access_key=settings.volcengine_access_key,
            secret_key=settings.volcengine_secret_key,
            target_language=settings.target_language,
            region=settings.volcengine_region,
        )
    raise ValueError(f"不支持的翻译提供商：{settings.translator_provider}")


def build_summarizer(settings: Settings) -> OpenAICompatibleSummarizer:
    return OpenAICompatibleSummarizer(_build_llm_client(settings))


def build_highlighter(settings: Settings) -> OpenAICompatibleHighlighter:
    return OpenAICompatibleHighlighter(_build_llm_client(settings))


def build_summary_source(document) -> str:
    parts: list[str] = []
    for page in document.pages:
        if page.page_kind in {PageKind.APPENDIX, PageKind.REPORT_LIST}:
            continue
        for item in page.items:
            if isinstance(item, TextBlock):
                parts.append(item.translated_text or item.text)
    return "\n\n".join(parts)


def apply_page_highlights(page, highlighter: OpenAICompatibleHighlighter | None) -> None:
    text_blocks = [item for item in page.items if isinstance(item, TextBlock)]
    chinese_page_text = "\n".join(block.translated_text for block in text_blocks if block.translated_text.strip())
    phrases: list[str] = []
    if highlighter is not None and chinese_page_text.strip():
        try:
            phrases = highlighter.pick_highlights(chinese_page_text)
        except LLMError:
            logger = logging.getLogger("research-report-center")
            logger.warning("高亮短语提取失败，已跳过。")
    for item in text_blocks:
        highlighted = apply_phrase_highlights(item.translated_text or "翻译缺失", phrases)
        if should_skip_numeric_highlight(item.translated_text):
            item.highlighted_translated_text = highlighted
        else:
            item.highlighted_translated_text = apply_numeric_highlights(highlighted)


def apply_summary_highlights(summary_text: str, highlighter: OpenAICompatibleHighlighter | None) -> str:
    stripped = summary_text.strip()
    if not stripped:
        return ""
    phrases: list[str] = []
    if highlighter is not None:
        try:
            phrases = highlighter.pick_highlights(stripped)
        except LLMError:
            logger = logging.getLogger("research-report-center")
            logger.warning("总结高亮短语提取失败，已跳过。")
    highlighted = apply_phrase_highlights(stripped, phrases)
    return apply_numeric_highlights(highlighted)


def looks_like_contact_block(text: str) -> bool:
    stripped = text.strip()
    return "@" in stripped or "电话" in stripped or stripped.count("+") >= 1


def should_skip_numeric_highlight(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if looks_like_contact_block(stripped):
        return True
    if len(stripped) <= 20 and any(token in stripped for token in ("经济学", "中国", "广州", "香港")):
        return True
    return stripped.endswith("日") and stripped.count("年") == 1 and stripped.count("月") == 1


def write_index(settings: Settings, manifest: dict[str, ManifestRecord]) -> None:
    success_records = [
        record
        for key, record in manifest.items()
        if Path(settings.root_dir / key).exists() and record.status == "success" and record.article_path
    ]
    success_records.sort(key=lambda item: item.processed_at or "", reverse=True)
    index_content = render_index_markdown(success_records)
    (settings.docs_dir / "index.md").write_text(index_content, encoding="utf-8")


def write_failures(settings: Settings, manifest: dict[str, ManifestRecord]) -> None:
    failed_records = [
        record
        for key, record in manifest.items()
        if Path(settings.root_dir / key).exists() and record.status == "failed"
    ]
    lines = ["失败文件清单", ""]
    if not failed_records:
        lines.append("当前没有失败文件。")
    else:
        for record in failed_records:
            lines.append(f"- {record.source_name}: {record.error or '未知错误'}")
    (settings.logs_dir / "failures.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
