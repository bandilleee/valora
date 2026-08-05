"""Regression tests for the canonical facts_as_of() query (M1.10).

Backlog condition: "Fact revised, historical query returns old value."
facts_as_of() is the single, database-resident definition of "what did
Valora believe as of instant X" (see db/migrations/20260805184045_facts_as_of.sql).
M9.3 (GET /v1/facts?as_of=) is required to call this function rather than
reimplement the bitemporal containment check in TypeScript — these tests
are what makes a silent divergence between the two impossible: there is
only one query to test, and every consumer must call it.

Connection handling mirrors test_facts_knowledge_period_exclusion.py
exactly: a single isolated `_connect()` function, replaceable by M1.12
with a one-line import change, no rewrite.

Setup style, stated per test: tests about the REVISION/write path (one or
two successive restatements) use `_restate_fact`, which performs the
operation the same way M2.12's loader and M6's publish stage will —
close the old row's window, insert the new one, in the same transaction.
Tests about pure QUERY BOUNDARY behaviour (the exact-instant edge case,
and the before-any-knowledge case) insert facts directly with the
knowledge_period already shaped as needed; there is no "revision" to
perform realistically in either of those, since they are about how
facts_as_of() reads a period, not about how a period comes to change.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import psycopg
import pytest
from psycopg.types.range import Range

from valora_pipeline.config import get_settings

FactRange = Range[datetime.datetime]


def _connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A connection whose transaction is always rolled back, isolating each
    test's inserts (seed rows and facts alike) from every other test and
    from whatever was in the database before the test ran."""
    connection = _connect()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _instant(offset_days: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(
        days=offset_days
    )


def _insert_company(cur: psycopg.Cursor, jse_code: str) -> int:
    cur.execute(
        """
        insert into companies (name, jse_code, sector, archetype, fye_month)
        values (%s, %s, 'Retail', 'retail', 6)
        returning id
        """,
        (f"Test Co {jse_code}", jse_code),
    )
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def _insert_concept(cur: psycopg.Cursor, code: str) -> int:
    cur.execute(
        """
        insert into concepts (code, label, archetype_set, sign_convention, unit_type)
        values (%s, %s, array['retail'], 'natural', 'currency')
        returning id
        """,
        (code, code),
    )
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def _insert_document(cur: psycopg.Cursor, key: str) -> int:
    cur.execute(
        """
        insert into documents (s3_key, sha256)
        values (%s, %s)
        returning id
        """,
        (f"test/{key}.pdf", key.encode().hex().ljust(64, "0")[:64]),
    )
    row = cur.fetchone()
    assert row is not None
    return int(row[0])


def _insert_fact(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    document_id: int,
    knowledge_period: FactRange,
    period_start: datetime.date = datetime.date(2024, 7, 1),
    period_end: datetime.date = datetime.date(2025, 6, 30),
    period_type: str = "FY",
    basis: str = "as_reported",
    value: int = 1000,
) -> None:
    cur.execute(
        """
        insert into facts (
          company_id, concept_id, period_start, period_end,
          period_type, basis, value, currency, scale, document_id, page, bbox,
          knowledge_period
        ) values (
          %s, %s, %s, %s, %s, %s, %s, 'ZAR', 'units', %s, 1,
          '{"x0": 0, "y0": 0, "x1": 0.1, "y1": 0.1}', %s
        )
        """,
        (
            company_id,
            concept_id,
            period_start,
            period_end,
            period_type,
            basis,
            value,
            document_id,
            knowledge_period,
        ),
    )


def _restate_fact(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    document_id: int,
    restated_at: datetime.datetime,
    new_value: int,
    period_start: datetime.date = datetime.date(2024, 7, 1),
    period_end: datetime.date = datetime.date(2025, 6, 30),
    period_type: str = "FY",
    basis: str = "as_reported",
) -> None:
    """Performs a realistic restatement: close the currently-open row's
    knowledge_period, then insert the new value open-ended — the same
    close-then-open sequence M2.12's loader and M6's publish stage will
    perform, and the same order verified safe under immediate constraint
    checking in M1.8."""
    cur.execute(
        """
        update facts
        set knowledge_period = tstzrange(lower(knowledge_period), %s, '[)')
        where company_id = %s and concept_id = %s and period_type = %s and basis = %s
          and upper_inf(knowledge_period)
        """,
        (restated_at, company_id, concept_id, period_type, basis),
    )
    assert cur.rowcount == 1, "expected exactly one currently-open row to restate"
    _insert_fact(
        cur,
        company_id=company_id,
        concept_id=concept_id,
        document_id=document_id,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        basis=basis,
        knowledge_period=Range(restated_at, None, bounds="[)"),
        value=new_value,
    )


def _query_as_of(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    as_of: datetime.datetime | None = None,
    basis: str | None = None,
) -> list[tuple[int, str]]:
    """Calls the canonical facts_as_of() function and layers company/concept
    (and optionally basis) filters on top of its result — exactly the
    pattern M9.3 is expected to use for GET /v1/facts. Returns (value,
    basis) pairs so callers assert on actual values, not row counts."""
    params: tuple[object, ...]
    if as_of is None:
        query = "select value, basis from facts_as_of() where company_id = %s and concept_id = %s"
        params = (company_id, concept_id)
    else:
        query = (
            "select value, basis from facts_as_of(%s) where company_id = %s and concept_id = %s"
        )
        params = (as_of, company_id, concept_id)
    if basis is not None:
        query += " and basis = %s"
        params = (*params, basis)
    cur.execute(query, params)
    return [(int(row[0]), row[1]) for row in cur.fetchall()]


def test_as_of_before_revision_returns_original_value(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A01")
        concept_id = _insert_concept(cur, "a01_revenue")
        document_id = _insert_document(cur, "a01")
        original_instant = _instant(0)
        restated_at = _instant(10)
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(original_instant, None, bounds="[)"),
            value=47000,
        )
        _restate_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            restated_at=restated_at,
            new_value=47500,
        )

        before_revision = _instant(5)
        results = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=before_revision
        )
        assert results == [(47000, "as_reported")]


def test_as_of_after_revision_returns_revised_value(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A02")
        concept_id = _insert_concept(cur, "a02_revenue")
        document_id = _insert_document(cur, "a02")
        original_instant = _instant(0)
        restated_at = _instant(10)
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(original_instant, None, bounds="[)"),
            value=47000,
        )
        _restate_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            restated_at=restated_at,
            new_value=47500,
        )

        after_revision = _instant(20)
        results = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=after_revision
        )
        assert results == [(47500, "as_reported")]


def test_as_of_now_default_returns_current_value(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A03")
        concept_id = _insert_concept(cur, "a03_revenue")
        document_id = _insert_document(cur, "a03")
        # A believable "since the past, still current" fact — knowledge of
        # it did not begin at this instant, it began sometime before and
        # is still open-ended now.
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(_instant(-30), None, bounds="[)"),
            value=51000,
        )

        results = _query_as_of(cur, company_id=company_id, concept_id=concept_id)
        assert results == [(51000, "as_reported")]


def test_as_of_at_exact_boundary_instant_returns_second_row(conn: psycopg.Connection) -> None:
    """Query-boundary test: fabricates two adjacent, already-closed windows
    directly rather than performing a live restatement, since the second
    window here is deliberately bounded (not open-ended/"currently
    believed") to isolate exactly the @> containment behaviour at a shared
    edge.

    M1.8 decided knowledge_period bounds are always [lower, upper): lower
    inclusive, upper exclusive. For windows [t1,t2) and [t2,t3), the
    instant t2 is excluded from the first (upper bound, exclusive) and
    included in the second (lower bound, inclusive). An as_of query at
    exactly t2 must therefore return the SECOND row. Getting this backwards
    would mean the query believes the OLD value is still current at the
    exact moment a restatement takes effect.
    """
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A04")
        concept_id = _insert_concept(cur, "a04_revenue")
        document_id = _insert_document(cur, "a04")
        t1, t2, t3 = _instant(0), _instant(10), _instant(20)
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(t1, t2, bounds="[)"),
            value=1111,
        )
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(t2, t3, bounds="[)"),
            value=2222,
        )

        results = _query_as_of(cur, company_id=company_id, concept_id=concept_id, as_of=t2)
        assert results == [(2222, "as_reported")]


def test_as_of_before_any_knowledge_returns_no_rows(conn: psycopg.Connection) -> None:
    """Query-boundary test: a single, ordinary fact — nothing fabricated
    about its shape — queried at an instant before its knowledge_period
    even begins. Must return an empty result, not an error and not the
    fact anyway (e.g. from an off-by-one on the lower bound)."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A05")
        concept_id = _insert_concept(cur, "a05_revenue")
        document_id = _insert_document(cur, "a05")
        knowledge_begins = _instant(10)
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(knowledge_begins, None, bounds="[)"),
            value=9999,
        )

        before_any_knowledge = _instant(0)
        results = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=before_any_knowledge
        )
        assert results == []


def test_two_successive_revisions_four_query_points(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A06")
        concept_id = _insert_concept(cur, "a06_revenue")
        document_id = _insert_document(cur, "a06")

        t_original = _instant(0)
        t_first_revision = _instant(10)
        t_second_revision = _instant(20)

        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(t_original, None, bounds="[)"),
            value=100,
        )
        _restate_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            restated_at=t_first_revision,
            new_value=200,
        )
        _restate_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            restated_at=t_second_revision,
            new_value=300,
        )

        before_first = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=_instant(5)
        )
        assert before_first == [(100, "as_reported")]

        between_first_and_second = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=_instant(15)
        )
        assert between_first_and_second == [(200, "as_reported")]

        after_second = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, as_of=_instant(25)
        )
        assert after_second == [(300, "as_reported")]

        now = _query_as_of(cur, company_id=company_id, concept_id=concept_id)
        assert now == [(300, "as_reported")]


def test_as_reported_and_restated_both_current_returned_unless_basis_filtered(
    conn: psycopg.Connection,
) -> None:
    """basis is part of the fact identity (M1.7/M1.8): an as_reported row
    and a restated row for the identical period are two distinct, both-
    current facts, not competing versions. It is easy to write an as_of
    query that accidentally collapses them to one (e.g. a naive DISTINCT ON
    company_id, concept_id, period_start without basis in the key) — assert
    both are actually returned, and that basis genuinely filters."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "A07")
        concept_id = _insert_concept(cur, "a07_revenue")
        document_id = _insert_document(cur, "a07")
        overlapping = Range(_instant(0), None, bounds="[)")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
            basis="as_reported",
            value=40000,
        )
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
            basis="restated",
            value=39500,
        )

        both = _query_as_of(cur, company_id=company_id, concept_id=concept_id)
        assert sorted(both) == [(39500, "restated"), (40000, "as_reported")]

        as_reported_only = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, basis="as_reported"
        )
        assert as_reported_only == [(40000, "as_reported")]

        restated_only = _query_as_of(
            cur, company_id=company_id, concept_id=concept_id, basis="restated"
        )
        assert restated_only == [(39500, "restated")]
