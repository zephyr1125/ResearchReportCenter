from __future__ import annotations

import textwrap

import requests


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


class OpenAICompatibleTranslator(Translator):
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 120) -> None:
        if not api_key:
            raise ValueError("缺少环境变量 LLM_API_KEY，无法执行翻译。")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def translate(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""

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
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(f"翻译接口返回格式异常：{payload}") from error
