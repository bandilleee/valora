"""Regression tests for facts.knowledge_period's GiST exclusion constraint (M1.8).

Per CLAUDE.md, this is the one schema guarantee that cannot be retrofitted
without migrating live customer data. These tests exist so a regression
(the constraint dropped, weakened, or its key columns changed) fails loudly
in CI, not months later when someone notices duplicate current facts.

Connection handling uses valora_pipeline.db's get_connection (M1.12), as
promised when this file was written in M1.9.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.range import Range

from valora_pipeline.db import get_connection as _connect

FactRange = Range[datetime.datetime]


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A connection whose transaction is always rolled back, isolating each
    test's inserts (seed rows and facts alike) from every other test and
    from whatever was in the database before the test ran."""
    connection = _connect()
    try:
        yield connection
    finally:
        # Always valid, even if the transaction is already aborted by a
        # constraint violation the test triggered on purpose.
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


def _insert_line_item(
    cur: psycopg.Cursor, *, company_id: int, concept_id: int, document_id: int, label: str
) -> int:
    cur.execute(
        """
        insert into company_line_items
          (company_id, as_reported_label, mapping_status, concept_id, first_seen_doc_id)
        values (%s, %s, 'mapped', %s, %s)
        returning id
        """,
        (company_id, label, concept_id, document_id),
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
    line_item_id: int | None = None,
    period_start: datetime.date = datetime.date(2024, 7, 1),
    period_end: datetime.date = datetime.date(2025, 6, 30),
    period_type: str = "FY",
    basis: str = "as_reported",
    value: int = 1000,
) -> None:
    cur.execute(
        """
        insert into facts (
          company_id, concept_id, line_item_id, period_start, period_end,
          period_type, basis, value, currency, scale, document_id, page, bbox,
          knowledge_period
        ) values (
          %s, %s, %s, %s, %s, %s, %s, %s, 'ZAR', 'units', %s, 1,
          '{"x0": 0, "y0": 0, "x1": 0.1, "y1": 0.1}', %s
        )
        """,
        (
            company_id,
            concept_id,
            line_item_id,
            period_start,
            period_end,
            period_type,
            basis,
            value,
            document_id,
            knowledge_period,
        ),
    )


def _assert_exclusion_violation(exc: BaseException) -> None:
    assert isinstance(exc, pg_errors.ExclusionViolation)
    assert exc.sqlstate == "23P01"
    assert exc.diag.constraint_name == "facts_no_overlapping_knowledge_periods"


def _assert_shape_check_violation(exc: BaseException) -> None:
    assert isinstance(exc, pg_errors.CheckViolation)
    assert exc.sqlstate == "23514"
    assert exc.diag.constraint_name == "facts_knowledge_period_shape"


def test_identical_key_both_open_ended_rejected(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T01")
        concept_id = _insert_concept(cur, "t01_revenue")
        document_id = _insert_document(cur, "t01")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(_instant(0), None, bounds="[)"),
        )
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(_instant(1), None, bounds="[)"),
                value=2000,
            )
        _assert_exclusion_violation(exc_info.value)


def test_identical_key_partially_overlapping_rejected(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T02")
        concept_id = _insert_concept(cur, "t02_revenue")
        document_id = _insert_document(cur, "t02")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(_instant(0), _instant(10), bounds="[)"),
        )
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(_instant(5), _instant(15), bounds="[)"),
                value=2000,
            )
        _assert_exclusion_violation(exc_info.value)


def test_identical_key_one_contains_other_rejected(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T03")
        concept_id = _insert_concept(cur, "t03_revenue")
        document_id = _insert_document(cur, "t03")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(_instant(0), _instant(20), bounds="[)"),
        )
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(_instant(5), _instant(10), bounds="[)"),
                value=2000,
            )
        _assert_exclusion_violation(exc_info.value)


def test_identical_key_adjacent_periods_both_accepted(conn: psycopg.Connection) -> None:
    """The restatement path. If this fails, restatements are impossible:
    closing an old row and opening a new one at the exact same instant
    would itself be rejected as an overlap."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T04")
        concept_id = _insert_concept(cur, "t04_revenue")
        document_id = _insert_document(cur, "t04")
        boundary = _instant(10)
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(_instant(0), boundary, bounds="[)"),
        )
        # Does not raise.
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=Range(boundary, None, bounds="[)"),
            value=2000,
        )
        cur.execute(
            "select count(*) from facts where company_id = %s and concept_id = %s",
            (company_id, concept_id),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 2


def test_same_period_different_basis_both_accepted(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T05")
        concept_id = _insert_concept(cur, "t05_revenue")
        document_id = _insert_document(cur, "t05")
        overlapping = Range(_instant(0), None, bounds="[)")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
            basis="as_reported",
        )
        # Does not raise: different basis is a different fact series.
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
            basis="restated",
            value=2000,
        )


def test_same_everything_different_concept_both_accepted(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T06")
        concept_id_a = _insert_concept(cur, "t06_revenue")
        concept_id_b = _insert_concept(cur, "t06_gross_profit")
        document_id = _insert_document(cur, "t06")
        overlapping = Range(_instant(0), None, bounds="[)")
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id_a,
            document_id=document_id,
            knowledge_period=overlapping,
        )
        # Does not raise: different concept_id is a different fact identity.
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id_b,
            document_id=document_id,
            knowledge_period=overlapping,
            value=2000,
        )


def test_same_everything_different_company_both_accepted(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id_a = _insert_company(cur, "T07")
        company_id_b = _insert_company(cur, "T08")
        concept_id = _insert_concept(cur, "t07_revenue")
        document_id = _insert_document(cur, "t07")
        overlapping = Range(_instant(0), None, bounds="[)")
        _insert_fact(
            cur,
            company_id=company_id_a,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
        )
        # Does not raise: different company_id is a different fact identity.
        _insert_fact(
            cur,
            company_id=company_id_b,
            concept_id=concept_id,
            document_id=document_id,
            knowledge_period=overlapping,
            value=2000,
        )


def test_different_line_item_id_otherwise_identical_overlapping_rejected(
    conn: psycopg.Connection,
) -> None:
    """Established in M1.7: relabelling an as-reported line does not create
    a new fact identity. line_item_id is deliberately NOT part of the
    exclusion constraint's key."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T09")
        concept_id = _insert_concept(cur, "t09_revenue")
        document_id = _insert_document(cur, "t09")
        line_item_a = _insert_line_item(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            label="Sale of merchandise",
        )
        line_item_b = _insert_line_item(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            label="Revenue from contracts with customers",
        )
        _insert_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            line_item_id=line_item_a,
            knowledge_period=Range(_instant(0), None, bounds="[)"),
        )
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                line_item_id=line_item_b,
                knowledge_period=Range(_instant(1), None, bounds="[)"),
                value=2000,
            )
        _assert_exclusion_violation(exc_info.value)


def test_empty_knowledge_period_rejected_by_shape_check(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T10")
        concept_id = _insert_concept(cur, "t10_revenue")
        document_id = _insert_document(cur, "t10")
        same_instant = _instant(0)
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(same_instant, same_instant, bounds="[)"),
            )
        _assert_shape_check_violation(exc_info.value)


def test_unbounded_lower_bound_rejected_by_shape_check(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "T11")
        concept_id = _insert_concept(cur, "t11_revenue")
        document_id = _insert_document(cur, "t11")
        with pytest.raises(psycopg.Error) as exc_info:
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(None, _instant(10), bounds="[)"),
            )
        _assert_shape_check_violation(exc_info.value)


def test_restatement_end_to_end_exactly_one_current_row() -> None:
    """The operation M2.12's loader and M6's publish stage will perform:
    close the existing row's knowledge_period, insert the new value
    open-ended, commit. Demonstrably possible, not merely theoretically
    legal — this test genuinely commits, so it cleans up explicitly rather
    than relying on rollback."""
    connection = _connect()
    try:
        with connection.cursor() as cur:
            company_id = _insert_company(cur, "T12")
            concept_id = _insert_concept(cur, "t12_revenue")
            document_id = _insert_document(cur, "t12")
            original_instant = _instant(0)
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(original_instant, None, bounds="[)"),
                value=47000,
            )
        connection.commit()

        # A later pipeline run, in a new transaction, restates the value.
        restatement_instant = _instant(30)
        with connection.cursor() as cur:
            cur.execute(
                """
                update facts
                set knowledge_period = tstzrange(lower(knowledge_period), %s, '[)')
                where company_id = %s and concept_id = %s
                """,
                (restatement_instant, company_id, concept_id),
            )
            _insert_fact(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                knowledge_period=Range(restatement_instant, None, bounds="[)"),
                value=47500,
            )
        connection.commit()

        with connection.cursor() as cur:
            cur.execute(
                """
                select value from facts
                where company_id = %s and concept_id = %s and upper_inf(knowledge_period)
                """,
                (company_id, concept_id),
            )
            current_rows = cur.fetchall()
            assert len(current_rows) == 1
            assert current_rows[0][0] == 47500

            cur.execute(
                "select count(*) from facts where company_id = %s and concept_id = %s",
                (company_id, concept_id),
            )
            total_row = cur.fetchone()
            assert total_row is not None
            assert total_row[0] == 2
    finally:
        with connection.cursor() as cur:
            cur.execute("delete from facts where company_id = %s", (company_id,))
            cur.execute("delete from companies where id = %s", (company_id,))
            cur.execute("delete from concepts where id = %s", (concept_id,))
            cur.execute("delete from documents where id = %s", (document_id,))
        connection.commit()
        connection.close()
