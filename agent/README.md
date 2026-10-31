# agent/ — WAGE.md backend

Python 3.11+ backend: the three agents, shared infrastructure, ingestion, normalization,
publishing, and the FastAPI server. Managed with **uv**.

## Layout

```
src/
  core/           agent_loop.py (generic run_agent), openai_client, tiger_client
  agents/         scout.py, investigator.py, counselor.py  (specialize run_agent)
  tools/          scout_tools.py, investigator_tools.py, counselor_tools.py
  ingestion/      download.py, dol_flag.py, warn_ca/wa/ny.py, career_pages.py
  normalization/  title_normalizer.py  (OpenAI)
  publishing/     local_briefs.py, publish_briefs.py, brief_generator.py
  api/            server.py  (FastAPI exposing the agents)
tests/
```

## Run

```bash
uv sync                 # install deps (provisions Python 3.11+)
uv run pytest           # tests
uv run uvicorn src.api.server:app --reload   # API (or: make api from repo root)
```

The generic `run_agent(goal, tools, system_prompt, max_iterations=5)` in
[src/core/agent_loop.py](src/core/agent_loop.py) is the foundation — Scout, Investigator,
and Counselor are all specializations of it. Build it first.
