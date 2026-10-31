"""Exclude implausible disclosed wages before they skew wage percentiles."""

from datetime import date

from openpyxl import Workbook

from src.ingestion.dol_flag import parse_filtered


def test_parse_filtered_skips_implausible_annualized_wages(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "CASE_NUMBER", "CASE_STATUS", "VISA_CLASS", "FULL_TIME_POSITION",
        "DECISION_DATE", "EMPLOYER_NAME", "JOB_TITLE",
        "WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO", "WAGE_UNIT_OF_PAY",
    ])
    for case, low, high, unit in (
        ("valid", 180_000, 200_000, "Year"),
        ("bad-year", 28_000_000, 28_000_000, "Year"),
        ("bad-hour", 160_000, 160_000, "Hour"),
        ("bad-upper", 100, 160_000, "Hour"),
    ):
        sheet.append([case, "Certified", "H-1B", "Y", date(2026, 6, 30),
                      "Google LLC", "Software Engineer", low, high, unit])
    path = tmp_path / "filings.xlsx"
    workbook.save(path)

    rows = parse_filtered(path, "LCA")

    assert [row["case_number"] for row in rows] == ["valid"]
    assert rows[0]["wage_low_usd"] == 180_000


def test_parse_filtered_keeps_only_certified_full_time_h1b(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "CASE_NUMBER", "CASE_STATUS", "VISA_CLASS", "FULL_TIME_POSITION",
        "DECISION_DATE", "EMPLOYER_NAME", "JOB_TITLE", "WAGE_RATE_OF_PAY_FROM",
    ])
    for case, status, visa, full_time in (
        ("eligible", "Certified", "H-1B", "Y"),
        ("denied", "Denied", "H-1B", "Y"),
        ("other-visa", "Certified", "E-3 Australian", "Y"),
        ("part-time", "Certified", "H-1B", "N"),
    ):
        sheet.append([case, status, visa, full_time, date(2026, 6, 30),
                      "Google LLC", "Software Engineer", 180_000])
    path = tmp_path / "filings.xlsx"
    workbook.save(path)

    assert [row["case_number"] for row in parse_filtered(path, "LCA")] == ["eligible"]


def test_parse_filtered_keeps_only_certified_perm(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "CASE_NUMBER", "CASE_STATUS", "DECISION_DATE", "EMP_BUSINESS_NAME",
        "JOB_TITLE", "JOB_OPP_WAGE_FROM",
    ])
    for case, status in (("eligible", "Certified"), ("expired", "Certified-Expired")):
        sheet.append([case, status, date(2026, 6, 30), "Google LLC", "Software Engineer", 180_000])
    path = tmp_path / "perm.xlsx"
    workbook.save(path)

    assert [row["case_number"] for row in parse_filtered(path, "PERM")] == ["eligible"]
