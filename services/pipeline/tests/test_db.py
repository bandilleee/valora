"""Unit tests for valora_pipeline.db (M1.12).

Same isolation approach as the other suites: a function-scoped connection
whose transaction is rolled back at teardown, so each test's inserts never
leak into another test or into whatever was in the database before the
test ran. `test_publish_fact_first_time_has_no_partial_state_on_failure`
is the exception — like M1.9's end-to-end restatement test, it needs a
transaction to genuinely fail and commit-or-not for real, so it manages
its own connection and cleans up explicitly.

No skip logic anywhere in this file: a database that is unreachable must
fail these tests, not silently skip them.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest

from valora_pipeline.db import Fact, get_connection, get_facts_as_of, publish_fact, transaction

BBOX = {"x0": 0.0, "y0": 0.0, "x1": 0.1, "y1": 0.1}


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    connection = get_connection()
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


def _publish(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    document_id: int,
    effective_at: datetime.datetime,
    value: Decimal,
    period_start: datetime.date = datetime.date(2024, 7, 1),
    period_end: datetime.date = datetime.date(2025, 6, 30),
    period_type: str = "FY",
    basis: str = "as_reported",
) -> int:
    return publish_fact(
        cur,
        company_id=company_id,
        concept_id=concept_id,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        basis=basis,
        value=value,
        currency="ZAR",
        scale="units",
        document_id=document_id,
        page=1,
        bbox=BBOX,
        effective_at=effective_at,
    )


def test_publish_fact_first_time_inserts_open_ended(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D01")
        concept_id = _insert_concept(cur, "d01_revenue")
        document_id = _insert_document(cur, "d01")

        fact_id = _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(0),
            value=Decimal("1000"),
        )

        cur.execute(
            "select value, upper_inf(knowledge_period) from facts where id = %s",
            (fact_id,),
        )
        row = cur.fetchone()
        assert row == (Decimal("1000"), True)


def test_publish_fact_supersedes_existing_current_fact(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D02")
        concept_id = _insert_concept(cur, "d02_revenue")
        document_id = _insert_document(cur, "d02")

        original_id = _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(0),
            value=Decimal("1000"),
        )
        revised_id = _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(10),
            value=Decimal("1050"),
        )

        assert revised_id != original_id

        cur.execute(
            "select id, value, upper_inf(knowledge_period) from facts "
            "where company_id = %s and concept_id = %s order by id",
            (company_id, concept_id),
        )
        rows = cur.fetchall()
        assert rows == [
            (original_id, Decimal("1000"), False),
            (revised_id, Decimal("1050"), True),
        ]


def test_publish_fact_identity_excludes_line_item_id(conn: psycopg.Connection) -> None:
    """Fact identity is exactly the exclusion constraint's key — company_id,
    concept_id, period_start, period_type, basis — not line_item_id.
    Publishing again with a different line_item_id for the same identity
    must be treated as a supersession, not a second independent fact."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D03")
        concept_id = _insert_concept(cur, "d03_revenue")
        document_id = _insert_document(cur, "d03")
        cur.execute(
            """
            insert into company_line_items
              (company_id, as_reported_label, mapping_status, concept_id, first_seen_doc_id)
            values (%s, 'Sale of merchandise', 'mapped', %s, %s)
            returning id
            """,
            (company_id, concept_id, document_id),
        )
        line_item_a = cur.fetchone()
        assert line_item_a is not None
        cur.execute(
            """
            insert into company_line_items
              (company_id, as_reported_label, mapping_status, concept_id, first_seen_doc_id)
            values (%s, 'Revenue from contracts with customers', 'mapped', %s, %s)
            returning id
            """,
            (company_id, concept_id, document_id),
        )
        line_item_b = cur.fetchone()
        assert line_item_b is not None

        first_id = publish_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            period_start=datetime.date(2024, 7, 1),
            period_end=datetime.date(2025, 6, 30),
            period_type="FY",
            basis="as_reported",
            value=Decimal("1000"),
            currency="ZAR",
            scale="units",
            document_id=document_id,
            page=1,
            bbox=BBOX,
            effective_at=_instant(0),
            line_item_id=line_item_a[0],
        )
        second_id = publish_fact(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            period_start=datetime.date(2024, 7, 1),
            period_end=datetime.date(2025, 6, 30),
            period_type="FY",
            basis="as_reported",
            value=Decimal("1050"),
            currency="ZAR",
            scale="units",
            document_id=document_id,
            page=1,
            bbox=BBOX,
            effective_at=_instant(10),
            line_item_id=line_item_b[0],
        )

        cur.execute(
            "select count(*) from facts where company_id = %s and concept_id = %s",
            (company_id, concept_id),
        )
        total = cur.fetchone()
        assert total is not None
        assert total[0] == 2, "relabelling must supersede, not add a third independent fact"

        cur.execute("select upper_inf(knowledge_period) from facts where id = %s", (first_id,))
        assert cur.fetchone() == (False,)
        cur.execute("select upper_inf(knowledge_period) from facts where id = %s", (second_id,))
        assert cur.fetchone() == (True,)


def test_publish_fact_rejects_effective_at_before_current_lower_bound(
    conn: psycopg.Connection,
) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D04")
        concept_id = _insert_concept(cur, "d04_revenue")
        document_id = _insert_document(cur, "d04")

        _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(10),
            value=Decimal("1000"),
        )

        with pytest.raises(ValueError, match="must be strictly after"):
            _publish(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                effective_at=_instant(5),
                value=Decimal("2000"),
            )

        # No partial state: still exactly the one, unmodified fact.
        cur.execute(
            "select count(*), max(value) from facts where company_id = %s and concept_id = %s",
            (company_id, concept_id),
        )
        row = cur.fetchone()
        assert row == (1, Decimal("1000"))


def test_publish_fact_rejects_effective_at_equal_to_current_lower_bound(
    conn: psycopg.Connection,
) -> None:
    """Equal, not just earlier, must also be rejected: closing at the same
    instant the current fact began would construct a zero-duration empty
    range."""
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D05")
        concept_id = _insert_concept(cur, "d05_revenue")
        document_id = _insert_document(cur, "d05")
        same_instant = _instant(0)

        _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=same_instant,
            value=Decimal("1000"),
        )

        with pytest.raises(ValueError, match="must be strictly after"):
            _publish(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                effective_at=same_instant,
                value=Decimal("2000"),
            )


def test_get_facts_as_of_reads_via_canonical_database_function(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        company_id = _insert_company(cur, "D06")
        concept_id = _insert_concept(cur, "d06_revenue")
        document_id = _insert_document(cur, "d06")

        _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(0),
            value=Decimal("1000"),
        )
        _publish(
            cur,
            company_id=company_id,
            concept_id=concept_id,
            document_id=document_id,
            effective_at=_instant(10),
            value=Decimal("1050"),
        )

        before = [f for f in get_facts_as_of(cur, _instant(5)) if f.company_id == company_id]
        assert [f.value for f in before] == [Decimal("1000")]

        current = [f for f in get_facts_as_of(cur) if f.company_id == company_id]
        assert [f.value for f in current] == [Decimal("1050")]
        assert isinstance(current[0], Fact)
        assert current[0].concept_id == concept_id
        assert current[0].bbox == BBOX


def test_transaction_rolls_back_on_exception_leaving_no_partial_state() -> None:
    """A failed transaction must leave no partial state — not "the first
    write happened but the second didn't", genuinely nothing. Manages its
    own connection (like M1.9's end-to-end restatement test) because this
    needs a real commit/rollback boundary, not the fixture's blanket
    rollback."""
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            company_id = _insert_company(cur, "D07")
            concept_id = _insert_concept(cur, "d07_revenue")
            document_id = _insert_document(cur, "d07")
        connection.commit()

        class _DeliberateFailure(Exception):
            pass

        with pytest.raises(_DeliberateFailure), transaction(connection) as cur:
            _publish(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                effective_at=_instant(0),
                value=Decimal("1000"),
            )
            raise _DeliberateFailure("simulated failure after a write")

        with connection.cursor() as cur:
            cur.execute(
                "select count(*) from facts where company_id = %s and concept_id = %s",
                (company_id, concept_id),
            )
            row = cur.fetchone()
            assert row == (0,), "the publish before the failure must have been rolled back"
    finally:
        with connection.cursor() as cur:
            cur.execute("delete from facts where company_id = %s", (company_id,))
            cur.execute("delete from companies where id = %s", (company_id,))
            cur.execute("delete from concepts where id = %s", (concept_id,))
            cur.execute("delete from documents where id = %s", (document_id,))
        connection.commit()
        connection.close()


def test_transaction_commits_on_clean_exit() -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            company_id = _insert_company(cur, "D08")
            concept_id = _insert_concept(cur, "d08_revenue")
            document_id = _insert_document(cur, "d08")
        connection.commit()

        with transaction(connection) as cur:
            _publish(
                cur,
                company_id=company_id,
                concept_id=concept_id,
                document_id=document_id,
                effective_at=_instant(0),
                value=Decimal("1000"),
            )

        # A second, independent connection must also see it — proves it was
        # actually committed, not just visible within the same session.
        other_connection = get_connection()
        try:
            with other_connection.cursor() as cur:
                cur.execute(
                    "select count(*) from facts where company_id = %s and concept_id = %s",
                    (company_id, concept_id),
                )
                row = cur.fetchone()
                assert row == (1,)
        finally:
            other_connection.close()
    finally:
        with connection.cursor() as cur:
            cur.execute("delete from facts where company_id = %s", (company_id,))
            cur.execute("delete from companies where id = %s", (company_id,))
            cur.execute("delete from concepts where id = %s", (concept_id,))
            cur.execute("delete from documents where id = %s", (document_id,))
        connection.commit()
        connection.close()


def test_transaction_nesting_raises_runtime_error() -> None:
    connection = get_connection()
    try:
        with (
            pytest.raises(RuntimeError, match="does not support nesting"),
            transaction(connection) as _outer_cur,
            transaction(connection) as _inner_cur,
        ):
            pass
    finally:
        connection.rollback()
        connection.close()
