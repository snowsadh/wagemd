"""Ingestion Scout — keeps the salary corpus fresh.

Observe source freshness (DOL FLAG, WARN portals) -> decide which to poll next (staleness x
change-probability x rate budget) -> fetch public sources -> observe -> decide: commit, flag to the
Investigator, or continue. A specialization of run_agent with scout_tools + the SPEC prompt.
"""
from __future__ import annotations

from ..core.agent_loop import AgentLoopExhausted, run_agent
from ..core.config import settings
from ..tools.scout_tools import get_tools

SYSTEM_PROMPT = """You are the Ingestion Scout for WAGE.md. Your goal is to maintain a fresh,
clean salary corpus.

You manage three source families:
- DOL FLAG quarterly disclosures: dol_lca, dol_perm (change ~4 times/year)
- State WARN Act portals: warn_ca (change weekly-ish)

This agent can stage and commit California WARN notices. DOL quarterly imports run through
make seed; if DOL looks stale, report that action instead of claiming it was refreshed.

On each iteration, observe source freshness and decide which source to poll next. Prioritize
sources where new data is most likely given their change rate and staleness_score. To be
efficient, you may check several sources' freshness in one step. Respect rate limits. After
polling a source, validate the data before committing it. If anomalies appear (a large layoff,
a missing or brand-new company, an implausible value), flag them via flag_anomaly() so the
Investigator can act.

Call done() once sources are reasonably fresh and any anomalies are flagged. Don't loop
pointlessly. Think before each tool call about WHY this tool is the right choice now."""


def run(model: str | None = None) -> dict:
    try:
        return run_agent(
            goal=(
                "Survey dol_lca, dol_perm, and warn_ca. If WARN likely has new data, fetch it, "
                "validate it, and commit anything new. If DOL is stale, report that make seed is needed. "
                "Then "
                "flag the most significant layoff at a company we track "
                "(biggest_layoff_at_tracked_company) for the Investigator. Then call done()."
            ),
            tools=get_tools(),
            system_prompt=SYSTEM_PROMPT,
            model=model or settings.openai_model,
            agent_name="scout",
            max_iterations=8,
        )
    except AgentLoopExhausted as e:
        return {"status": "exhausted", "iterations": e.iterations, "goal": e.goal}


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2, default=str))
