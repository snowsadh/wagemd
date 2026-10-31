"""Negotiation Counselor — produces the strongest defensible negotiation report.

Observe a user offer -> decide what evidence is needed -> act (percentiles, broaden on thin
samples, peer comps, WARN context, specific filings) -> decide ship vs. fetch more -> finish
with a fully-cited report. Specializes run_agent with counselor_tools + the SPEC prompt.
"""
from __future__ import annotations

from ..core.agent_loop import AgentLoopExhausted, run_agent
from ..core.config import settings
from ..tools.counselor_tools import get_tools

SYSTEM_PROMPT = """You are the Negotiation Counselor for WAGE.md. A user has provided their job
offer. Your goal: produce the strongest defensible negotiation report, grounded entirely in US
Department of Labor disclosures.

Strategy:
1. Look up the salary distribution for their exact (company, role, level, location). If it comes
   back with sample_size 0, we may not have ingested this company yet — call
   ensure_company_data(company) once to fetch its DOL filings on demand, then look up again.
2. If sample size < 10, broaden — adjacent levels and statewide instead of one city.
3. Pull peer companies for comparison.
4. Check WARN context — recent layoffs at this company affect leverage. If has_warn_data is
   false, say WARN data is not loaded; zero notices is not evidence of zero layoffs. If the
   loaded data has no matching notices, say only that no matching notices are in those records.
5. Cite specific DOL case numbers in the report.
6. Recommend a specific dollar ask with rationale, and state where their current base sits
   (which percentile).

Every number in your final report must trace to a DOL case number or WARN notice. No invented
data. If data is thin, say so honestly. Be efficient: gather what you need in a few tool calls,
then call done() with the final markdown report.

Format the report as clean GitHub-flavored markdown: use `##` section headings (Offer Analysis,
Percentile Distribution, Peer Comparison, WARN Context, Recommendation); render the percentile
distribution and the peer comparison as markdown tables; put the recommended ask in **bold**; and
list the cited DOL case numbers. Output raw markdown only — do NOT wrap the whole report in a
``` code fence."""


def run(offer: dict, model: str | None = None) -> dict:
    goal = (
        "Produce a negotiation report for this offer:\n"
        f"- Company: {offer.get('company')}\n"
        f"- Role family: {offer.get('role_family')}\n"
        f"- Level: {offer.get('level')}\n"
        f"- Location: {offer.get('location')}\n"
        f"- Base salary offered: ${offer.get('base')}\n"
        f"- Years of experience: {offer.get('yoe')}\n"
        "Gather DOL evidence (broaden if the sample is thin), then call done() with the report."
    )
    try:
        return run_agent(
            goal=goal,
            tools=get_tools(),
            system_prompt=SYSTEM_PROMPT,
            model=model or settings.openai_model,
            agent_name="counselor",
            max_iterations=7,
        )
    except AgentLoopExhausted as e:
        return {"status": "exhausted", "iterations": e.iterations, "goal": e.goal}


if __name__ == "__main__":
    import json

    demo = {"company": "Anthropic", "role_family": "SWE", "level": "L5",
            "location": "San Francisco", "base": 215000, "yoe": 8}
    print(json.dumps(run(demo), indent=2, default=str))
