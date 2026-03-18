from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TextBlock:
    order: int
    page_number: int
    text: str
    translated_text: str = ""
    highlighted_translated_text: str = ""


@dataclass
class ImageBlock:
    order: int
    page_number: int
    image_path: Path
    caption: str


@dataclass
class PageContent:
    page_number: int
    items: list[TextBlock | ImageBlock] = field(default_factory=list)
    page_kind: str = "content"


@dataclass
class DocumentContent:
    title: str
    source_pdf: Path
    pages: list[PageContent] = field(default_factory=list)
    ai_summary: str = ""
    highlighted_ai_summary: str = ""


@dataclass
class ManifestRecord:
    source_path: str
    source_name: str
    sha256: str
    article_path: str | None
    status: str
    processed_at: str | None
    error: str | None = None
