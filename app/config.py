from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    input_dir: Path
    output_dir: Path
    docs_dir: Path
    site_dir: Path
    logs_dir: Path
    state_dir: Path
    manifest_path: Path
    translator_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    volcengine_access_key: str
    volcengine_secret_key: str
    volcengine_region: str
    target_language: str
    summary_enabled: bool
    summary_api_key: str
    summary_base_url: str
    summary_model: str

    @classmethod
    def load(cls, root_dir: Path) -> "Settings":
        # 优先读取项目根目录下的 .env，系统环境变量继续作为兜底。
        load_dotenv(root_dir / ".env", override=False)
        output_dir = root_dir / "output"
        docs_dir = output_dir / "site_src" / "docs"
        state_dir = output_dir / "state"
        return cls(
            root_dir=root_dir,
            input_dir=root_dir / "input",
            output_dir=output_dir,
            docs_dir=docs_dir,
            site_dir=output_dir / "site",
            logs_dir=output_dir / "logs",
            state_dir=state_dir,
            manifest_path=state_dir / "manifest.json",
            translator_provider=os.getenv("TRANSLATOR_PROVIDER", "openai").strip().lower(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
            llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini").strip(),
            volcengine_access_key=os.getenv("VOLCENGINE_ACCESS_KEY", "").strip(),
            volcengine_secret_key=os.getenv("VOLCENGINE_SECRET_KEY", "").strip(),
            volcengine_region=os.getenv("VOLCENGINE_REGION", "cn-north-1").strip(),
            target_language=os.getenv("TARGET_LANGUAGE", "zh").strip(),
            summary_enabled=os.getenv("SUMMARY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            summary_api_key=os.getenv("SUMMARY_API_KEY", "").strip(),
            summary_base_url=os.getenv("SUMMARY_BASE_URL", "").strip(),
            summary_model=os.getenv("SUMMARY_MODEL", "").strip(),
        )

    def ensure_directories(self) -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.site_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def reports_dir(self) -> Path:
        return self.docs_dir / "reports"

    @property
    def assets_dir(self) -> Path:
        return self.docs_dir / "assets"
