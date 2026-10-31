"""Exclude implausible disclosed wages before they skew wage percentiles."""

from datetime import date

from openpyxl import Workbook

from src.ingestion.dol_flag import parse_filtered


def test_parse_filtered_skips_implausible_annualized_wages(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "CASE_NUMBER", "DECISION_DATE", "EMPLOYER_NAME", "JOB_TITLE",
        "WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO", "WAGE_UNIT_OF_PAY",
    ])
    for case, low, high, unit in (
        ("valid", 180_000, 200_000, "Year"),
        ("bad-year", 28_000_000, 28_000_000, "Year"),
        ("bad-hour", 160_000, 160_000, "Hour"),
        ("bad-upper", 100, 160_000, "Hour"),
    ):
        sheet.append([case, date(2026, 6, 30), "Google LLC", "Software Engineer", low, high, unit])
    path = tmp_path / "filings.xlsx"
    workbook.save(path)

    rows = parse_filtered(path, "LCA")

    assert [row["case_number"] for row in rows] == ["valid"]
    assert rows[0]["wage_low_usd"] == 180_000
