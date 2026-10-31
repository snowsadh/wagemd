"""Investigator — handles anomaly flags and decides whether to republish.

Observe an anomaly -> decide real vs. suspicious vs. noise -> act (query data, regenerate
the brief, store it in Tiger Data) -> observe publication -> done. Specializes
run_agent with investigator_tools + the SPEC prompt. Conservative by design.
"""
from __future__ import annotations

from ..core.agent_loop import AgentLoopExhausted, run_agent
from ..core.config import settings
from ..core.tiger_client import command, query
from ..tools.investigator_tools import get_tools

SYSTEM_PROMPT = """You are the Investigator for WAGE.md. You handle anomaly flags from the Scout
and from automated data checks. Your goal: decide whether each anomaly is real and meaningful,
and if so, regenerate and republish the affected company brief.

When you receive an anomaly:
1. Query the underlying data to understand what changed (WARN filings, distribution shift).
2. Compare to historical norms.
3. Decide: is this real (publish), suspicious (need more data), or noise (dismiss)?
4. If real: regenerate the brief with the new context, then store it in the Index.

Be conservative. Don't republish for noise. The published index must remain credible. When you
publish, confirm you received a local brief URL. Call done() with a summary of what you decided
and why (include any published URL)."""


def _next_open_anomaly() -> dict | None:
    rows = query(
        "SELECT anomaly_id, severity, description, company FROM anomalies "
        "WHERE investigation_status='open' ORDER BY detected_at DESC LIMIT 1"
    ).result_rows
    if not rows:
        return None
    r = rows[0]
    return {"anomaly_id": r[0], "severity": r[1], "description": r[2], "company": r[3]}


def _set_anomaly_status(anomaly_id: str, status: str, notes: str = "") -> None:
    """Move an anomaly through open -> investigating -> resolved/dismissed (synchronous mutation
    so a subsequent run won't re-pick the same one)."""
    if not anomaly_id:
        return
    command(
        "UPDATE anomalies SET investigation_status=%(s)s, investigation_notes=%(n)s "
        "WHERE anomaly_id=%(id)s",
        {"s": status, "n": notes[:2000], "id": anomaly_id},
    )


def run(anomaly: dict | None = None, model: str | None = None) -> dict:
    anomaly = anomaly or _next_open_anomaly()
    if not anomaly:
        return {"status": "no_open_anomalies"}
    goal = (
        "Investigate this anomaly and decide whether to republish the company's brief:\n"
        f"- Company: {anomaly.get('company')}\n"
        f"- Severity: {anomaly.get('severity')}\n"
        f"- Description: {anomaly.get('description')}\n"
        "Query the WARN and salary data to verify it, and if it's real and material, regenerate "
        "and store the company's brief in the Index. Then call done() with your decision and the URL."
    )
    aid = anomaly.get("anomaly_id")
    _set_anomaly_status(aid, "investigating")
    try:
        result = run_agent(
            goal=goal,
            tools=get_tools(),
            system_prompt=SYSTEM_PROMPT,
            model=model or settings.openai_model,
            agent_name="investigator",
            max_iterations=8,
        )
    except AgentLoopExhausted as e:
        result = {"status": "exhausted", "iterations": e.iterations, "goal": e.goal, "trace": []}

    # Resolve if the agent published a brief; otherwise mark dismissed (so it isn't re-investigated).
    trace = result.get("trace", []) if isinstance(result, dict) else []
    published = any(
        t.get("tool") == "publish_company_brief"
        and isinstance(t.get("result"), dict) and t["result"].get("url")
        for t in trace
    )
    res = result.get("result") if isinstance(result, dict) else None
    notes = res.get("summary", "") if isinstance(res, dict) else str(res or result.get("status", ""))
    _set_anomaly_status(aid, "resolved" if published else "dismissed", notes)
    result["anomaly_id"] = aid
    result["republished"] = published
    return result


if __name__ == "__main__":
    import json

    demo = {"company": "Amazon", "severity": "high",
            "description": "Amazon filed WARN notices for ~6,975 layoffs in California."}
    print(json.dumps(run(demo), indent=2, default=str))
