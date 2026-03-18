from __future__ import annotations

import textwrap

import requests


SUMMARY_SYSTEM_PROMPT = textwrap.dedent(
    """
    你是金融研报总结助手。
    请基于提供的研报正文内容，用简体中文输出一个高信息密度总结，严格遵守：
    1. 只总结用户提供的内容，不要补充外部信息。
    2. 先给“核心结论”，再给“关键数字”。
    3. “关键数字”必须优先提取文中的时间、同比、环比、规模、金额、比例、目标值、预测值。
    4. 不要使用空泛套话，不要写成散文。
    5. 使用 Markdown，控制在 8-12 个要点内。
    """
).strip()


class SummaryError(RuntimeError):
    """总结请求失败时抛出的统一异常。"""


class OpenAICompatibleSummarizer:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 180) -> None:
        if not api_key or not base_url or not model:
            raise ValueError("总结模型配置不完整。")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def summarize(self, text: str) -> str:
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
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": stripped[:20000]},
                ],
            },
            timeout=self.timeout,
        )
        if not response.ok:
            raise SummaryError(f"总结请求失败（HTTP {response.status_code}）：{response.text}")
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise SummaryError(f"总结接口返回格式异常：{payload}") from error
