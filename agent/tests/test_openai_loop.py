"""Verify OpenAI tool-call IDs and results round-trip through the shared agent loop."""
from types import SimpleNamespace

from src.core.agent_loop import Tool, run_agent
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
