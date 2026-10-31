"""Tools available to the Negotiation Counselor (OpenAI function calling)."""
from __future__ import annotations

from ..core.agent_loop import Tool
from . import queries


def ensure_company_data(company: str) -> dict:
    """Fetch-on-miss: if we have no filings for this company, pull them from DOL data on demand."""
    from ..ingestion.on_demand import ingest_company

    return ingest_company(company)


def done(report: str) -> dict:
    return {"report": report}


def get_tools() -> list[Tool]:
    return [
        Tool(
            "ensure_company_data",
            "If query_salary_distribution returns sample_size 0 for a company, call this FIRST to "
            "fetch that company's DOL filings on demand (it resolves the legal employer name and "
            "ingests from DOL data), then re-query. No-op if the company is already loaded.",
            ensure_company_data,
            {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"]},
        ),
        Tool(
            "query_salary_distribution",
            "DOL-verified wage distribution (p25/p50/p75/p90, sample_size, example case numbers) "
            "for an exact company + role_family + level + location. role_family is one of "
            "SWE/PM/Design/FDE/ML/Data; level is L1-L7. location can be a city or 2-letter state.",
            queries.salary_distribution,
            {"type": "object", "properties": {
                "company": {"type": "string"}, "role_family": {"type": "string"},
                "level": {"type": "string"}, "location": {"type": "string"}},
             "required": ["company", "role_family"]},
        ),
        Tool(
            "query_role_distribution_broadened",
            "Broaden a thin sample: query across a level range (e.g. 'L4-L6') and statewide "
            "(2-letter state) instead of one city. Use when sample_size < 10.",
            queries.broadened_distribution,
            {"type": "object", "properties": {
                "company": {"type": "string"}, "role_family": {"type": "string"},
                "level_range": {"type": "string"}, "location_state": {"type": "string"}},
             "required": ["company", "role_family"]},
        ),
        Tool(
            "query_peer_companies",
            "Median wage at peer companies for a role_family, for comparison.",
            queries.peer_companies,
            {"type": "object", "properties": {
                "company": {"type": "string"}, "role_family": {"type": "string"}},
             "required": ["company", "role_family"]},
        ),
        Tool(
            "query_warn_context",
            "Recent California WARN layoff notices for the company (affects negotiating leverage).",
            queries.warn_context,
            {"type": "object", "properties": {
                "company": {"type": "string"}, "timeframe_days": {"type": "integer"}},
             "required": ["company"]},
        ),
        Tool(
            "fetch_filing_details",
            "Look up one DOL filing by case number to confirm a citation resolves.",
            queries.filing_details,
            {"type": "object", "properties": {"case_number": {"type": "string"}},
             "required": ["case_number"]},
        ),
        Tool(
            "done",
            "Finish with the final markdown negotiation report. Every number must cite a DOL "
            "case number or WARN notice; include a specific recommended ask in dollars.",
            done, {"type": "object", "properties": {"report": {"type": "string"}},
                   "required": ["report"]}, terminal=True,
        ),
    ]
