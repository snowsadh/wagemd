"""Generic agent loop — the foundation Scout, Investigator, and Counselor all share.

Each agent IS this loop, specialized only by its tool set + system prompt. The loop runs
observe -> decide -> act -> observe: OpenAI decides (native function calling), we execute the
chosen tool(s), feed results back, and repeat until the model calls a terminal tool (done),
returns a final text answer, or hits the hard iteration cap.

Design rules (SPEC.md / DECISIONS.md):
  - OpenAI function calling drives tool selection. The loop NEVER hard-codes a
    sequence of tool calls — that would make it a pipeline, not an agent.
  - max_iterations=5 is a hard safety cap; exhaustion raises AgentLoopExhausted.
  - Tool calls and results are returned in the trace for the UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .config import settings
from .openai_client import OpenAIClient, get_openai


class AgentLoopExhausted(Exception):
    """Raised when an agent hits max_iterations without reaching a final answer."""

    def __init__(self, goal: str, iterations: int):
        self.goal = goal
        self.iterations = iterations
        super().__init__(f"Agent exhausted {iterations} iterations without finishing: {goal!r}")


@dataclass
class Tool:
    """A tool exposed to an agent via OpenAI function calling."""

    name: str
    description: str
    impl: Callable[..., Any]
    parameters: dict | None = None  # JSON-schema dict; omit for no-arg tools
    terminal: bool = False  # done()-style tools that end the loop when called


_SENTINEL = object()

# Hard safety ceiling on agent loops. The documented default is 5; individual agents may
# request up to this ceiling for multi-tool flows (see DECISIONS.md D14). run_agent clamps
# any larger value so the runaway-cost bound is always enforced.
MAX_ITERATIONS_CEILING = 8


def _json_safe(v: Any) -> Any:
    return json.loads(json.dumps(v, default=str))


def run_agent(
    *,
    goal: str,
    tools: list[Tool],
    system_prompt: str,
    model: str | None = None,
    max_iterations: int = 5,
    agent_name: str = "agent",
    openai: OpenAIClient | None = None,
) -> dict:
    """Run the generic observe -> decide -> act loop for one agent.

    Returns {"status": "ok", "result": <terminal tool result or final text>,
             "iterations": n, "trace": [...tool calls...], "agent": agent_name}.
    Raises AgentLoopExhausted if no final answer within max_iterations.
    """
    openai = openai or get_openai()
    model = model or settings.openai_model
    max_iterations = max(1, min(int(max_iterations), MAX_ITERATIONS_CEILING))  # enforce hard ceiling
    impls = {t.name: t for t in tools}
    model_tools = openai.build_tools(
        [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]
    )

    contents = [openai.user_content(goal)]
    trace: list[dict] = []

    for i in range(max_iterations):
        resp = openai.generate(
            model=model,
            contents=contents,
            system_instruction=system_prompt,
            tools=model_tools,
        )
        calls = openai.function_calls(resp)

        if not calls:  # model returned a final answer
            text = openai.text_of(resp)
            if not text:
                raise RuntimeError("OpenAI returned neither a tool call nor a final answer")
            return {
                "status": "ok",
                "result": text,
                "iterations": i + 1,
                "trace": trace,
                "agent": agent_name,
            }

        contents.extend(openai.model_content(resp))

        terminal_result: Any = _SENTINEL
        for name, args, call_id in calls:
            tool = impls.get(name)
            if tool is None:
                result: Any = {"error": f"unknown tool: {name}"}
            else:
                try:
                    result = tool.impl(**args)
                except Exception as e:  # feed the error back so the agent can recover
                    result = {"error": f"{type(e).__name__}: {e}"}
            result = _json_safe(result)
            trace.append({"tool": name, "args": args, "result": result})
            contents.append(openai.function_response_content(call_id, result))
            if tool is not None and tool.terminal:
                terminal_result = result if result not in (None, {}) else (args or {"done": True})

        if terminal_result is not _SENTINEL:
            return {
                "status": "ok",
                "result": terminal_result,
                "iterations": i + 1,
                "trace": trace,
                "agent": agent_name,
            }

    raise AgentLoopExhausted(goal, max_iterations)
