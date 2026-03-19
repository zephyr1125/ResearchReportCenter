from __future__ import annotations

import textwrap

from app.llm_client import LLMClient, LLMError

SummaryError = LLMError

SUMMARY_SYSTEM_PROMPT = textwrap.dedent(
    """
    你是金融研报总结助手。
    请基于提供的研报正文内容，用简体中文输出一个高信息密度总结，严格遵守：
    1. 只总结用户提供的内容，不要补充外部信息。
    2. 先给"核心结论"，再给"关键数字"。
    3. "关键数字"必须优先提取文中的时间、同比、环比、规模、金额、比例、目标值、预测值。
    4. 不要使用空泛套话，不要写成散文。
    5. 使用 Markdown，控制在 8-12 个要点内。
    """
).strip()


class OpenAICompatibleSummarizer:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def summarize(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        return self._client.chat(
            SUMMARY_SYSTEM_PROMPT,
            stripped,
            temperature=0.2,
            max_input_chars=20000,
        )
