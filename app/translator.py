from __future__ import annotations

import json
import textwrap
from collections import OrderedDict
from typing import Any

from volcengine.ApiInfo import ApiInfo
from volcengine.Credentials import Credentials
from volcengine.ServiceInfo import ServiceInfo
from volcengine.base.Service import Service

from app.llm_client import LLMClient, LLMError

SYSTEM_PROMPT = textwrap.dedent(
    """
    你是金融研报翻译助手。
    请将用户提供的英文或其他外文段落翻译成简体中文，并严格遵守以下规则：
    1. 不要总结，不要删减，不要扩写。
    2. 保留数字、日期、百分比、专有名词、评级、公司名、产品名的准确性。
    3. 如果原文已经是中文，直接返回原文。
    4. 输出只包含译文正文，不要添加解释。
    """
).strip()

TranslationError = LLMError


class Translator:
    def translate(self, text: str) -> str:
        raise NotImplementedError


class OpenAICompatibleTranslator(Translator):
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def translate(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        return self._client.chat(SYSTEM_PROMPT, stripped, temperature=0)


class VolcengineTranslator(Translator):
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        target_language: str = "zh",
        region: str = "cn-north-1",
        timeout_seconds: int = 120,
    ) -> None:
        if not access_key or not secret_key:
            raise ValueError("缺少火山引擎 Access Key 或 Secret Key，无法执行翻译。")
        self.target_language = target_language
        self.region = region
        self.service = Service(
            ServiceInfo(
                "translate.volcengineapi.com",
                {},
                Credentials(access_key, secret_key, "translate", region),
                timeout_seconds,
                timeout_seconds,
                "https",
            ),
            {
                "TranslateText": ApiInfo(
                    "POST",
                    "/",
                    OrderedDict({"Action": "TranslateText", "Version": "2020-06-01"}),
                    {},
                    {},
                )
            },
        )

    def translate(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        parts = _split_text_for_volcengine(stripped, limit=4500)
        translated_parts = [self._translate_batch([part])[0] for part in parts]
        return "\n".join(part for part in translated_parts if part.strip()).strip()

    def _translate_batch(self, texts: list[str]) -> list[str]:
        body: dict[str, Any] = {
            "TargetLanguage": self.target_language,
            "TextList": texts,
        }
        try:
            raw = self.service.json("TranslateText", {}, json.dumps(body, ensure_ascii=False))
        except Exception as error:  # noqa: BLE001
            raise LLMError(f"火山引擎翻译请求失败：{error}") from error

        payload = json.loads(raw)
        metadata = payload.get("ResponseMetadata", {})
        error_info = metadata.get("Error")
        if error_info:
            raise LLMError(f"火山引擎翻译返回错误：{error_info}")

        translations = payload.get("TranslationList", [])
        results: list[str] = []
        for item in translations:
            translation = item.get("Translation", "").strip()
            if not translation:
                raise LLMError(f"火山引擎翻译返回格式异常：{payload}")
            results.append(translation)
        if len(results) != len(texts):
            raise LLMError(f"火山引擎翻译返回数量异常：{payload}")
        return results


def _split_text_for_volcengine(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for piece in text.splitlines():
        candidate = piece if not current else f"{current}\n{piece}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(piece) <= limit:
            current = piece
            continue
        start = 0
        while start < len(piece):
            chunks.append(piece[start : start + limit])
            start += limit
    if current:
        chunks.append(current)
    return chunks
