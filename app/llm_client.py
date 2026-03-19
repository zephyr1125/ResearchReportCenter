from __future__ import annotations

import time

import requests


class LLMClient:
    """OpenAI 兼容的 HTTP 客户端，供翻译、总结、高亮模块共用。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def chat(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0,
        max_input_chars: int | None = None,
    ) -> str:
        """发送 chat/completions 请求，返回助手回复文本。"""
        if max_input_chars is not None:
            user_content = user_content[:max_input_chars]

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
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                },
                timeout=self.timeout,
            )

            if response.ok:
                payload = response.json()
                try:
                    return payload["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, TypeError) as error:
                    raise LLMError(f"LLM 接口返回格式异常：{payload}") from error

            message = _build_error_message(response)
            if response.status_code == 429 and attempt < self.max_retries:
                last_error = LLMError(message)
                time.sleep(self.retry_delay_seconds * attempt)
                continue
            raise LLMError(message)

        raise LLMError(str(last_error) if last_error else "LLM 请求失败，原因未知。")


class LLMError(RuntimeError):
    """LLM 请求失败时抛出的统一异常。"""


def _build_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    return f"LLM 请求失败（HTTP {response.status_code}）：{payload}"
