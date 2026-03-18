from __future__ import annotations

import textwrap
import time
from collections import OrderedDict
from typing import Any

import requests
from volcengine.ApiInfo import ApiInfo
from volcengine.Credentials import Credentials
from volcengine.ServiceInfo import ServiceInfo
from volcengine.base.Service import Service


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


class Translator:
    def translate(self, text: str) -> str:
        raise NotImplementedError


class TranslationError(RuntimeError):
    """翻译请求失败时抛出的统一异常。"""


class OpenAICompatibleTranslator(Translator):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ) -> None:
        if not api_key:
            raise ValueError("缺少环境变量 LLM_API_KEY，无法执行翻译。")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def translate(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": stripped},
                    ],
                },
                timeout=self.timeout,
            )
            if response.ok:
                payload = response.json()
                try:
                    return payload["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, TypeError) as error:
                    raise TranslationError(f"翻译接口返回格式异常：{payload}") from error

            message = _build_error_message(response)
            if response.status_code == 429 and attempt < self.max_retries:
                last_error = TranslationError(message)
                time.sleep(self.retry_delay_seconds * attempt)
                continue
            raise TranslationError(message)

        raise TranslationError(str(last_error) if last_error else "翻译失败，原因未知。")


def _build_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    return f"翻译请求失败（HTTP {response.status_code}）：{payload}"


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
        body = {
            "TargetLanguage": self.target_language,
            "TextList": texts,
        }
        try:
            raw = self.service.json("TranslateText", {}, json_dumps(body))
        except Exception as error:  # noqa: BLE001
            raise TranslationError(f"火山引擎翻译请求失败：{error}") from error

        payload = json_loads(raw)
        metadata = payload.get("ResponseMetadata", {})
        error_info = metadata.get("Error")
        if error_info:
            raise TranslationError(f"火山引擎翻译返回错误：{error_info}")

        translations = payload.get("TranslationList", [])
        results: list[str] = []
        for item in translations:
            translation = item.get("Translation", "").strip()
            if not translation:
                raise TranslationError(f"火山引擎翻译返回格式异常：{payload}")
            results.append(translation)
        if len(results) != len(texts):
            raise TranslationError(f"火山引擎翻译返回数量异常：{payload}")
        return results


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


def json_loads(payload: str) -> dict[str, Any]:
    import json

    return json.loads(payload)


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
