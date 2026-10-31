"""Canonical employer matching for the demo's target companies.

DOL filings spell employers many ways ("Meta Platforms, Inc.", "AMAZON.COM SERVICES LLC").
We map those to canonical names and, crucially, use precise patterns so noise like
"Pinstripes, Inc." (not Stripe) or "FAR EAST METALS" (not Meta) is excluded.
"""
from __future__ import annotations

import re

# canonical name -> list of regex patterns (matched against the UPPERCASED raw employer)
TARGET_PATTERNS: dict[str, list[str]] = {
    "Anthropic": [r"\bANTHROPIC\b"],
    "OpenAI": [r"\bOPEN\s?AI\b"],
    "Stripe": [r"\bSTRIPE,?\s+INC", r"\bSTRIPE\s+PAYMENTS", r"^STRIPE\b"],
    "Google": [r"\bGOOGLE\b"],
    "Meta": [r"\bMETA\s+PLATFORMS\b", r"^META,?\s+INC\b"],
    "Amazon": [r"\bAMAZON\b"],
    "Microsoft": [r"\bMICROSOFT\b"],
    "Apple": [r"\bAPPLE,?\s+INC\b"],
    "Databricks": [r"\bDATABRICKS\b"],
    "Netflix": [r"\bNETFLIX\b"],
}

_COMPILED = {name: [re.compile(p) for p in pats] for name, pats in TARGET_PATTERNS.items()}

TARGET_COMPANIES = list(TARGET_PATTERNS.keys())

_SUFFIX = re.compile(
    r"\b(INC|LLC|CORP|CORPORATION|LTD|CO|LP|LLP|COMPANY|HOLDINGS|TECHNOLOGIES|TECHNOLOGY)\b",
    re.I,
)


def match_target(raw: str | None) -> str | None:
    """Return the canonical target-company name if `raw` matches one, else None."""
    if not raw:
        return None
    u = raw.upper()
    for name, pats in _COMPILED.items():
        if any(p.search(u) for p in pats):
            return name
    return None


def normalize_employer(raw: str | None) -> str:
    """Canonical name for any employer: target name if matched, else a light cleanup."""
    t = match_target(raw)
    if t:
        return t
    if not raw:
        return "Unknown"
    s = re.sub(r"[,\.]", " ", raw)
    s = _SUFFIX.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() or "Unknown"
