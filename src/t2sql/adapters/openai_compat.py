# SPDX-License-Identifier: Apache-2.0
"""Optional OpenAI-compatible adapter. Untested in CI; no accuracy claim."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class OpenAICompatModel:
    def __init__(self) -> None:
        self.base_url = os.environ.get("T2SQL_LLM_BASE_URL")
        self.api_key = os.environ.get("T2SQL_LLM_API_KEY")
        self.model = os.environ.get("T2SQL_LLM_MODEL")
        if not self.base_url or not self.api_key or not self.model:
            raise SystemExit(2)

    def to_sql(self, question: str) -> str | None:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Return exactly one fenced ```sql block with a single PostgreSQL "
                        f"SELECT for: {question}"
                    ),
                }
            ],
        }
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        content = payload["choices"][0]["message"]["content"]
        match = SQL_FENCE.search(content)
        if not match:
            return None
        return match.group(1).strip() or None
