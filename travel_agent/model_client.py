from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen


class OpenAICompatibleClient:
    """Small chat-completions client for OpenAI-compatible endpoints."""

    def __init__(self, api_key: str, base_url: str, timeout: float = 45) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(
        self, *, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        payload = json.dumps(
            {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]


def client_from_env() -> tuple[OpenAICompatibleClient | None, str | None]:
    api_key = os.getenv("AGENT_API_KEY")
    model = os.getenv("AGENT_MODEL")
    if not api_key or not model:
        missing = [
            name
            for name, value in (("AGENT_API_KEY", api_key), ("AGENT_MODEL", model))
            if not value
        ]
        return None, f"Missing {', '.join(missing)}; using deterministic workflow."
    return (
        OpenAICompatibleClient(
            api_key=api_key,
            base_url=os.getenv("AGENT_BASE_URL", "https://api.openai.com/v1"),
        ),
        None,
    )