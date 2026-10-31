"""Smoke test for the generic agent loop — a trivial echo agent over run_agent().

Run: `uv run python -m tests.echo_agent` (from agent/). Hits the configured OpenAI model and
checks that tool calls remain visible in the returned trace.
Not collected by pytest (no test_ prefix); it makes real API calls.
"""
from __future__ import annotations

import json

from src.core.agent_loop import Tool, run_agent


def _echo(text: str) -> dict:
    return {"echoed": text}


def _done() -> dict:
    return {"status": "done"}


ECHO_TOOLS = [
    Tool(
        name="echo",
        description="Echo the given text back verbatim.",
        impl=_echo,
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "text to echo"}},
            "required": ["text"],
        },
    ),
    Tool(name="done", description="Call when the task is complete.", impl=_done, terminal=True),
]


def main() -> None:
    result = run_agent(
        goal="Use the echo tool to echo the exact word BANANA, then call done.",
        tools=ECHO_TOOLS,
        system_prompt=(
            "You are a tiny test agent. Use the provided tools to accomplish the goal. "
            "Always finish by calling done()."
        ),
        agent_name="echo",
    )
    print("\n--- result ---")
    print(json.dumps(result, indent=2, default=str))
    assert any(t["tool"] == "echo" for t in result["trace"]), "echo tool was not called"
    assert any("BANANA" in str(t["args"]) for t in result["trace"] if t["tool"] == "echo")
    print("\n✅ echo agent smoke test passed")


if __name__ == "__main__":
    main()
