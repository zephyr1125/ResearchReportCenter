from __future__ import annotations

import json
import re
import textwrap

from app.llm_client import LLMClient, LLMError

HIGHLIGHT_SYSTEM_PROMPT = textwrap.dedent(
    """
    你是研报重点标注助手。
    请从用户提供的中文页面内容中，挑出最值得高亮的 2 到 5 个短语或短句，要求：
    1. 必须逐字摘自原文，不能改写。
    2. 优先选择包含关键判断、政策方向、风险提示、关键数字附近的短句。
    3. 每个候选尽量控制在 8 到 50 个字符。
    4. 不要返回重复或大段整段内容。
    5. 只返回 JSON 数组字符串，例如 ["句子1", "句子2"]。
    """
).strip()

HighlightError = LLMError


class OpenAICompatibleHighlighter:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def pick_highlights(self, text: str) -> list[str]:
        stripped = text.strip()
        if not stripped:
            return []
        content = self._client.chat(
            HIGHLIGHT_SYSTEM_PROMPT,
            stripped[:12000],
            temperature=0.1,
        )
        return parse_highlight_candidates(content)


def parse_highlight_candidates(content: str) -> list[str]:
    stripped = content.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        pass
    matches = re.findall(r'"([^"]+)"', stripped)
    return [match.strip() for match in matches if match.strip()]


def apply_numeric_highlights(text: str) -> str:
    pattern = re.compile(
        r"(?P<num>(?:\d{4}年\d{1,2}月\d{1,2}日)|(?:\d+(?:\.\d+)?%)+|(?:\d+(?:,\d{3})*(?:\.\d+)?(?:万亿元人民币|亿元人民币|万亿元|亿元|万亿|人民币|美元|trn|bn|mn|m|b))|(?:同比|环比|复合年增长率|CAGR))"
    )
    protected_pattern = re.compile(r"<mark class=\"rrc-highlight-insight\">.*?</mark>", re.DOTALL)
    result: list[str] = []
    last_end = 0
    for match in protected_pattern.finditer(text):
        plain_segment = text[last_end:match.start()]
        result.append(pattern.sub(r'<mark class="rrc-highlight-data">\g<num></mark>', plain_segment))
        result.append(match.group(0))
        last_end = match.end()
    result.append(pattern.sub(r'<mark class="rrc-highlight-data">\g<num></mark>', text[last_end:]))
    return "".join(result)


def apply_phrase_highlights(text: str, phrases: list[str]) -> str:
    highlighted = text
    for phrase in sorted(set(phrases), key=len, reverse=True):
        cleaned = phrase.strip()
        if not cleaned or cleaned not in highlighted:
            continue
        highlighted = highlighted.replace(
            cleaned,
            f'<mark class="rrc-highlight-insight">{cleaned}</mark>',
            1,
        )
    return highlighted
