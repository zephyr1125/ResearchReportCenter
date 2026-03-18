from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.manifest import load_manifest, save_manifest
from app.models import ImageBlock, ManifestRecord, TextBlock
from app.pdf_processor import PdfProcessor
from app.site_builder import render_index_markdown, render_report_markdown
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

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)

    changed = 0
    translator: Translator | None = None
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
                translator = build_translator(settings)
            if asset_dir.exists():
                shutil.rmtree(asset_dir)
            document = processor.extract(pdf_path, asset_dir)
            for page in document.pages:
                for item in page.items:
                    if isinstance(item, TextBlock):
                        item.translated_text = build_translated_text(
                            item.text,
                            translator,
                            skip_translation=skip_translation,
                        )
            markdown = render_report_markdown(document, settings.docs_dir)
            article_path.write_text(markdown, encoding="utf-8")
            manifest[source_key] = ManifestRecord(
                source_path=source_key,
                source_name=pdf_path.name,
                sha256=sha256,
                article_path=ensure_relative_posix(article_path, settings.docs_dir),
                status="success",
                processed_at=datetime.now().isoformat(timespec="seconds"),
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
                error=str(error),
            )

    if changed == 0:
        logger.info("没有新增或变更的 PDF，直接更新首页索引。")

    write_index(settings, manifest)
    write_failures(settings, manifest)
    save_manifest(settings.manifest_path, manifest)
    return 0


def build_translated_text(text: str, translator: Translator | None, skip_translation: bool) -> str:
    if skip_translation:
        return f"[预览模式，未调用翻译接口]\n{text}"
    if translator is None:
        raise TranslationError("翻译器未初始化。")
    return translator.translate(text)


def build_translator(settings: Settings) -> Translator:
    if settings.translator_provider == "openai":
        return OpenAICompatibleTranslator(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    if settings.translator_provider == "volcengine":
        return VolcengineTranslator(
            access_key=settings.volcengine_access_key,
            secret_key=settings.volcengine_secret_key,
            target_language=settings.target_language,
            region=settings.volcengine_region,
        )
    raise ValueError(f"不支持的翻译提供商：{settings.translator_provider}")


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
