"""Verify OpenAI tool-call IDs and results round-trip through the shared agent loop."""
from types import SimpleNamespace

import pytest

from src.core.agent_loop import AgentLoopExhausted, Tool, run_agent
from src.core.openai_client import OpenAIClient


def test_openai_tool_result_round_trip():
    requests = []
    call = SimpleNamespace(type="function_call", name="echo", arguments='{"text":"BANANA"}', call_id="call_1")
    first = SimpleNamespace(status="completed", output=[call], output_text="", usage=None)
    second = SimpleNamespace(status="completed", output=[], output_text="done", usage=None)
    responses = iter([first, second])

    def create(**kwargs):
        requests.append(kwargs)
        return next(responses)

    client = OpenAIClient.__new__(OpenAIClient)
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    result = run_agent(
        goal="Echo BANANA and finish",
        tools=[Tool(name="echo", description="Echo text", impl=lambda text: {"echoed": text},
                    parameters={"type": "object", "properties": {"text": {"type": "string"}},
                                "required": ["text"]})],
        system_prompt="Use the echo tool.",
        openai=client,
    )

    assert result["result"] == "done"
    assert result["trace"][0]["result"] == {"echoed": "BANANA"}
    assert requests[1]["input"][-1] == {
        "type": "function_call_output", "call_id": "call_1", "output": '{"echoed": "BANANA"}'
    }
    assert requests[1]["input"][-2] is call


def test_last_iteration_requires_terminal_tool():
    requests = []
    calls = [
        SimpleNamespace(type="function_call", name="echo", arguments='{"text":"BANANA"}', call_id="call_1"),
        SimpleNamespace(type="function_call", name="done", arguments='{"report":"ready"}', call_id="call_2"),
    ]
    responses = iter(SimpleNamespace(status="completed", output=[call], output_text="") for call in calls)

    def create(**kwargs):
        requests.append(kwargs)
        return next(responses)

    client = OpenAIClient.__new__(OpenAIClient)
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    result = run_agent(
        goal="Echo then report", system_prompt="Use tools", openai=client, max_iterations=2,
        final_tool="done", tools=[
            Tool("echo", "Echo", lambda text: {"echoed": text}),
            Tool("done", "Finish", lambda report: {"report": report}, terminal=True),
        ],
    )

    assert requests[1]["tool_choice"] == {"type": "function", "name": "done"}
    assert result["result"] == {"report": "ready"}
    assert [step["tool"] for step in result["trace"]] == ["echo", "done"]


def test_exhaustion_preserves_tool_trace():
    calls = [SimpleNamespace(type="function_call", name="echo", arguments='{"text":"x"}',
                             call_id=f"call_{i}") for i in range(2)]
    responses = iter(SimpleNamespace(status="completed", output=[call], output_text="") for call in calls)
    client = OpenAIClient.__new__(OpenAIClient)
    client._client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: next(responses)))

    with pytest.raises(AgentLoopExhausted) as exc:
        run_agent(goal="Keep echoing", system_prompt="Use tools", openai=client,
                  max_iterations=2, tools=[Tool("echo", "Echo", lambda text: {"echoed": text})])

    assert exc.value.iterations == 2
    assert [step["tool"] for step in exc.value.trace] == ["echo", "echo"]
