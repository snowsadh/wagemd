"""OpenAI Responses client for agent tool calls and JSON generation."""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import settings


class OpenAIClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or settings.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is required; set it in .env.local")
        self._client = OpenAI(api_key=key)

    @staticmethod
    def build_tools(tool_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters") or {"type": "object", "properties": {}},
                "strict": False,
            }
            for t in tool_specs
        ]

    @staticmethod
    def user_content(text: str) -> dict[str, str]:
        return {"role": "user", "content": text}

    @staticmethod
    def function_response_content(call_id: str, result: Any) -> dict[str, str]:
        return {"type": "function_call_output", "call_id": call_id, "output": json.dumps(result)}

    @staticmethod
    def function_calls(resp: Any) -> list[tuple[str, dict[str, Any], str]]:
        calls = []
        for item in resp.output:
            if item.type == "function_call":
                args = json.loads(item.arguments)
                if not isinstance(args, dict):
                    raise ValueError(f"OpenAI tool {item.name} returned non-object arguments")
                calls.append((item.name, args, item.call_id))
        return calls

    @staticmethod
    def model_content(resp: Any) -> list[Any]:
        return resp.output

    @staticmethod
    def text_of(resp: Any) -> str:
        return (resp.output_text or "").strip()

    def generate(
        self,
        *,
        model: str,
        contents: list[Any],
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, str] | None = None,
        response_json: bool = False,
    ) -> Any:
        kwargs: dict[str, Any] = {"model": model, "input": contents}
        if system_instruction:
            kwargs["instructions"] = system_instruction
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if response_json:
            kwargs["text"] = {"format": {"type": "json_object"}}
        resp = self._client.responses.create(**kwargs)
        if resp.status != "completed":
            raise RuntimeError(f"OpenAI response did not complete: {resp.status}")
        return resp

    def generate_json(
        self, *, prompt: str, system_instruction: str | None = None, model: str | None = None
    ) -> Any:
        resp = self.generate(
            model=model or settings.openai_model,
            contents=[self.user_content(prompt)],
            system_instruction=system_instruction,
            response_json=True,
        )
        return json.loads(self.text_of(resp))


_client: OpenAIClient | None = None


def get_openai() -> OpenAIClient:
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client
