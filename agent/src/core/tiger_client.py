"""PostgreSQL client and TimescaleDB schema for the WAGE.md agent."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql as psql

from .config import settings

SCHEMA = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb",
    """
    CREATE TABLE IF NOT EXISTS filings (
        case_number TEXT NOT NULL,
        case_type TEXT NOT NULL CHECK (case_type IN ('PERM', 'LCA')),
        decision_date DATE NOT NULL,
        employer_name_raw TEXT NOT NULL,
        employer_normalized TEXT NOT NULL,
        job_title_raw TEXT NOT NULL,
        soc_code TEXT NOT NULL,
        soc_title TEXT NOT NULL,
        role_family TEXT NOT NULL CHECK (role_family IN ('SWE', 'PM', 'Design', 'FDE', 'ML', 'Data', 'Other')),
        level_normalized TEXT NOT NULL CHECK (level_normalized IN ('L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'Unknown')),
        normalization_confidence DOUBLE PRECISION NOT NULL,
        wage_low_usd DOUBLE PRECISION NOT NULL,
        wage_high_usd DOUBLE PRECISION NOT NULL,
        wage_unit TEXT NOT NULL,
        worksite_city TEXT NOT NULL,
        worksite_state TEXT NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (case_number, case_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS filings_lookup_idx ON filings (employer_normalized, role_family, level_normalized, decision_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS warn_filings (
        filing_id TEXT NOT NULL,
        employer_normalized TEXT NOT NULL,
        state TEXT NOT NULL,
        notice_date DATE NOT NULL,
        effective_date DATE NOT NULL,
        employees_affected BIGINT NOT NULL CHECK (employees_affected >= 0),
        raw_data TEXT NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (filing_id, notice_date)
    )
    """,
    "SELECT create_hypertable('warn_filings', by_range('notice_date', INTERVAL '30 days'), if_not_exists => TRUE)",
    "CREATE INDEX IF NOT EXISTS warn_filings_lookup_idx ON warn_filings (employer_normalized, notice_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS company_levels (
        employer_normalized TEXT NOT NULL,
        internal_level TEXT NOT NULL,
        canonical_level TEXT NOT NULL CHECK (canonical_level IN ('L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7')),
        role_family TEXT NOT NULL,
        source_url TEXT NOT NULL,
        notes TEXT NOT NULL,
        PRIMARY KEY (employer_normalized, internal_level, role_family)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS published_pages (
        employer_normalized TEXT NOT NULL,
        page_url TEXT NOT NULL,
        last_published TIMESTAMPTZ NOT NULL,
        sample_size BIGINT NOT NULL CHECK (sample_size >= 0),
        version BIGINT NOT NULL CHECK (version > 0),
        PRIMARY KEY (employer_normalized)
    )
    """,
    "ALTER TABLE published_pages ADD COLUMN IF NOT EXISTS markdown TEXT NOT NULL DEFAULT ''",
    """
    CREATE TABLE IF NOT EXISTS anomalies (
        anomaly_id TEXT PRIMARY KEY,
        detected_at TIMESTAMPTZ NOT NULL,
        severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
        description TEXT NOT NULL,
        company TEXT NOT NULL,
        investigation_status TEXT NOT NULL CHECK (investigation_status IN ('open', 'investigating', 'resolved', 'dismissed')),
        investigation_notes TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS anomalies_open_idx ON anomalies (detected_at DESC) WHERE investigation_status = 'open'",
]


@dataclass
class QueryResult:
    result_rows: list[tuple]
    column_names: list[str]


def transaction() -> psycopg.Connection:
    """Return a connection context manager that commits or rolls back on exit."""
    if not settings.tiger_database_url:
        raise ValueError("TIGER_DATABASE_URL is required; set it in .env.local")
    return psycopg.connect(settings.tiger_database_url, connect_timeout=10)


def query(sql: str, parameters: dict | None = None, kind: str = "select") -> QueryResult:
    with transaction() as conn, conn.cursor() as cur:
        conn.autocommit = True  # SELECTs need no BEGIN/COMMIT round trips to Tiger Cloud.
        cur.execute(sql, parameters)
        rows = cur.fetchall()
        return QueryResult(rows, [col.name for col in cur.description or ()])


def query_dicts(sql: str, parameters: dict | None = None) -> list[dict]:
    result = query(sql, parameters)
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def query_many(statements: Sequence[str], parameters: dict | None = None) -> list[list[tuple]]:
    """Read related aggregates from one consistent Tiger Data snapshot."""
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        results = []
        for statement in statements:
            cur.execute(statement, parameters)
            results.append(cur.fetchall())
        return results


def command(sql: str, parameters: dict | None = None) -> None:
    with transaction() as conn, conn.cursor() as cur:
        cur.execute(sql, parameters)


def insert(table: str, data: Sequence[Sequence[Any]], column_names: list[str]) -> int:
    if not data:
        return 0
    statement = psql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        psql.Identifier(table),
        psql.SQL(", ").join(map(psql.Identifier, column_names)),
        psql.SQL(", ").join([psql.Placeholder()] * len(column_names)),
    )
    if table == "filings":
        derived = {"role_family", "level_normalized", "normalization_confidence"}
        updates = [name for name in column_names if name not in {"case_number", "case_type"} | derived]
        same_title = psql.SQL(
            "filings.employer_normalized = EXCLUDED.employer_normalized "
            "AND filings.job_title_raw = EXCLUDED.job_title_raw"
        )
        statement += psql.SQL(" ON CONFLICT (case_number, case_type) DO UPDATE SET {}").format(
            psql.SQL(", ").join([
                psql.SQL("{} = EXCLUDED.{}").format(psql.Identifier(name), psql.Identifier(name))
                for name in updates
            ] + [
                psql.SQL("{} = CASE WHEN {} THEN filings.{} ELSE EXCLUDED.{} END").format(
                    psql.Identifier(name), same_title, psql.Identifier(name), psql.Identifier(name)
                )
                for name in derived
            ])
        )
    elif table == "warn_filings":
        statement += psql.SQL(" ON CONFLICT DO NOTHING")
    with transaction() as conn, conn.cursor() as cur:
        cur.executemany(statement, data)
        return cur.rowcount


def apply_schema() -> None:
    """Create the five tables and WARN hypertable, failing on missing TimescaleDB."""
    with transaction() as conn, conn.cursor() as cur:
        for ddl in SCHEMA:
            cur.execute(ddl)
        for table, expected in (
            ("filings", "PRIMARY KEY (case_number, case_type)"),
            ("published_pages", "PRIMARY KEY (employer_normalized)"),
        ):
            cur.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = %s::regclass AND contype = 'p'",
                (table,),
            )
            actual = cur.fetchone()
            if not actual or actual[0] != expected:
                raise RuntimeError(f"{table} has an incompatible primary key; use a clean Tiger Data database")
    print(f"Applied {len(SCHEMA)} schema statements to Tiger Data")


def ping() -> bool:
    try:
        return query("SELECT 1").result_rows[0][0] == 1
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        print(f"Tiger Data ping failed: {exc}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tiger Data schema management")
    parser.add_argument("--apply-schema", action="store_true", help="Create tables and WARN hypertable")
    parser.add_argument("--ping", action="store_true", help="SELECT 1 connectivity check")
    parser.add_argument("--tables", action="store_true", help="List tables")
    args = parser.parse_args()
    if args.ping:
        print("ping ok" if ping() else "ping FAILED")
    elif args.apply_schema:
        apply_schema()
    elif args.tables:
        for row in query("SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename").result_rows:
            print(row[0])
    else:
        parser.print_help()
