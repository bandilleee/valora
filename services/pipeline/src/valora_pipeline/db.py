"""Thin Postgres helper: a connection factory, a transaction scope, and the
one non-trivial write this project has — publishing a bitemporal fact.

This is deliberately not a data-access layer or an ORM. It does not wrap
companies, concepts, documents, instruments, or company_line_items — no
consumer needs that yet, and M2.12/M3.3 (the two consumers this module is
built for) do not touch those tables in a way that benefits from a wrapper.
See the module docstring section "Deliberately out of scope" below for the
full list and reasoning.

Every function here operates on a caller-supplied ``psycopg.Cursor`` rather
than opening its own connection or transaction, so a caller can compose
several operations (e.g. several ``publish_fact`` calls) into one atomic
unit via ``transaction()``. Nothing in this module calls ``commit()`` or
``rollback()`` except ``transaction()`` itself.

Deliberately out of scope for this milestone (M1.12), and why:

- CRUD for companies/concepts/documents/instruments/company_line_items —
  no consumer needs it yet. The existing test suites build these rows with
  raw SQL because they are test fixtures, not production call sites.
- Connection pooling — M2.12 and M3.3 are batch/single-process pipeline
  jobs, not a concurrent web server. Add pooling when a real throughput
  need appears (most likely M9's API, which is TypeScript anyway).
- Automatic retry on a concurrent-write conflict — retry policy (attempt
  count, backoff) belongs to the caller. This module surfaces the conflict
  as an exception and stops.
- Filtering beyond `as_of` on the read side — no concrete consumer need
  yet. A caller wanting company/concept/period filtering can write that
  SQL directly against `facts_as_of()`, which is exactly how it is
  designed to be composed (see that function's own comment).
- Async support — nothing in this project runs an event loop yet.

Add what M2.12 or M3.3 turn out to actually need when they are built,
rather than guessing at their shape now.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg.types.range import Range

from valora_pipeline.config import get_settings

KnowledgePeriod = Range[datetime.datetime]

_IN_TRANSACTION_ATTR = "_valora_in_transaction"


def get_connection() -> psycopg.Connection:
    """Opens a connection using the single source of truth for DATABASE_URL
    (valora_pipeline.config), not the environment directly — that was
    M0.8's whole point. Autocommit is off (psycopg3's default): nothing is
    persisted until something calls .commit(), which only `transaction()`
    does in this module.
    """
    return psycopg.connect(get_settings().database_url)


@contextmanager
def transaction(conn: psycopg.Connection) -> Iterator[psycopg.Cursor]:
    """Commits on clean exit, rolls back on exception.

    Nested use is NOT supported and is a loud error, not a silent one: a
    naive nested implementation would let the inner block's commit()
    durably persist the outer block's earlier work, breaking the "all or
    nothing" guarantee the outer call appears to promise the moment the
    inner block exits — a bug that would only surface later, when the
    outer block fails and the caller wrongly assumes everything rolled
    back. Calling `transaction()` again on a connection already inside one
    raises RuntimeError immediately instead.
    """
    if getattr(conn, _IN_TRANSACTION_ATTR, False):
        raise RuntimeError(
            "transaction() does not support nesting on the same connection. "
            "Pass the existing cursor through instead of opening a second "
            "transaction() scope."
        )
    setattr(conn, _IN_TRANSACTION_ATTR, True)
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        setattr(conn, _IN_TRANSACTION_ATTR, False)


@dataclass(frozen=True, slots=True)
class Fact:
    """One row of `facts`, as returned by `facts_as_of()`. A dataclass
    rather than a TypedDict or tuple: the values come from constructing
    typed objects out of query results we control (not from parsing
    external untyped data, which is TypedDict's strength), and named
    fields make call sites self-documenting in a way a positional tuple
    cannot for a 19-column row.
    """

    id: int
    company_id: int
    concept_id: int
    line_item_id: int | None
    period_start: datetime.date
    period_end: datetime.date
    period_type: str
    basis: str
    value: Decimal
    currency: str
    scale: str
    document_id: int
    page: int
    bbox: dict[str, Any]
    confidence: float | None
    verified_by: int | None
    verified_at: datetime.datetime | None
    extraction_run_id: int | None
    knowledge_period: KnowledgePeriod


def _fact_from_row(row: dict[str, Any]) -> Fact:
    return Fact(
        id=row["id"],
        company_id=row["company_id"],
        concept_id=row["concept_id"],
        line_item_id=row["line_item_id"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        period_type=row["period_type"],
        basis=row["basis"],
        value=row["value"],
        currency=row["currency"],
        scale=row["scale"],
        document_id=row["document_id"],
        page=row["page"],
        bbox=row["bbox"],
        confidence=row["confidence"],
        verified_by=row["verified_by"],
        verified_at=row["verified_at"],
        extraction_run_id=row["extraction_run_id"],
        knowledge_period=row["knowledge_period"],
    )


def get_facts_as_of(cur: psycopg.Cursor, as_of: datetime.datetime | None = None) -> list[Fact]:
    """Facts as of a given instant (default: now — the current view).

    Calls the canonical `facts_as_of()` database function (M1.10) rather
    than reimplementing the knowledge_period containment check — CLAUDE.md
    records that reimplementing that boundary check is the specific risk
    this project has already decided to close off. A caller wanting
    company/concept/period filtering composes it on top of this function's
    result, the same way `facts_as_of()`'s own design expects.
    """
    with cur.connection.cursor(row_factory=dict_row) as dict_cur:
        if as_of is None:
            dict_cur.execute("select * from facts_as_of()")
        else:
            dict_cur.execute("select * from facts_as_of(%s)", (as_of,))
        return [_fact_from_row(row) for row in dict_cur.fetchall()]


def publish_fact(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    period_start: datetime.date,
    period_end: datetime.date,
    period_type: str,
    basis: str,
    value: Decimal | float | int,
    currency: str,
    scale: str,
    document_id: int,
    page: int,
    bbox: dict[str, Any],
    effective_at: datetime.datetime,
    line_item_id: int | None = None,
    confidence: float | None = None,
    verified_by: int | None = None,
    verified_at: datetime.datetime | None = None,
    extraction_run_id: int | None = None,
) -> int:
    """Publishes a fact, handling both cases in one call:

    - no current fact for this identity: inserts with an open-ended
      knowledge_period starting at `effective_at`.
    - a current fact exists: closes its knowledge_period at `effective_at`,
      then inserts the new row open-ended, in the same transaction (i.e.
      on the same cursor/connection the caller passed in — this function
      does not commit; wrap the call in `transaction()`).

    `effective_at` is a required parameter, never `now()` inside this
    function. M1.8 established that belief time is not row-write time, and
    that the exclusion constraint cannot catch the difference — a wrong
    default here would be silently wrong, the same failure mode M1.8's own
    knowledge_period column avoids by having no default. The caller must
    decide what instant belief actually began (extraction completion,
    verification, or publish time) and supply it.

    "Fact identity" is exactly the exclusion constraint's key: company_id,
    concept_id, period_start, period_type, basis. NOT line_item_id — a
    relabelled as-reported line supersedes the same fact, per M1.7/M1.8;
    it does not start a new one. If this function's notion of identity
    ever disagreed with the exclusion constraint's, the constraint would
    win (it would reject an insert this function thought was safe) and
    this function's key list, not the constraint, would be the bug.

    Raises ValueError if `effective_at` is not strictly after the current
    fact's knowledge_period lower bound — publishing an earlier
    supersession would either construct an empty range (rejected by the
    database's own shape check) or silently misorder the belief timeline,
    and this function refuses it before issuing any SQL rather than
    relying on the database to catch it.

    Concurrency: safe in the sense that two concurrent calls for the same
    identity can never both succeed with corrupted or duplicated state —
    not safe in the sense of never conflicting. Read Committed lets two
    concurrent callers both see the same "current" row and both compute a
    plan to close it; only one closing UPDATE can hold the row lock first,
    and when the loser's UPDATE proceeds, its WHERE clause (matching only
    an open-ended row) will match zero rows against the now-closed row,
    which this function detects and raises RuntimeError for rather than
    silently inserting an orphaned row. If both callers instead raced to
    the "no current fact" branch, the second INSERT collides with the
    first under the exclusion constraint and psycopg raises
    ExclusionViolation. Either way, one caller gets an explicit exception
    and must retry; this function does not retry automatically.
    """
    cur.execute(
        """
        select id, lower(knowledge_period) as lower_bound
        from facts
        where company_id = %s and concept_id = %s and period_start = %s
          and period_type = %s and basis = %s and upper_inf(knowledge_period)
        """,
        (company_id, concept_id, period_start, period_type, basis),
    )
    current = cur.fetchone()

    if current is not None:
        current_id, current_lower = current
        if effective_at <= current_lower:
            raise ValueError(
                f"effective_at ({effective_at!r}) must be strictly after the current "
                f"fact's knowledge_period lower bound ({current_lower!r}); publishing "
                "an earlier supersession would corrupt the belief timeline."
            )
        cur.execute(
            """
            update facts
            set knowledge_period = tstzrange(lower(knowledge_period), %s, '[)')
            where id = %s and upper_inf(knowledge_period)
            """,
            (effective_at, current_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError(
                f"expected to close exactly one current fact (id={current_id}) but "
                f"updated {cur.rowcount} — it was concurrently modified or closed by "
                "another writer between the lookup and this update. Retry."
            )

    cur.execute(
        """
        insert into facts (
          company_id, concept_id, line_item_id, period_start, period_end,
          period_type, basis, value, currency, scale, document_id, page, bbox,
          confidence, verified_by, verified_at, extraction_run_id, knowledge_period
        ) values (
          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        returning id
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
            currency,
            scale,
            document_id,
            page,
            Jsonb(bbox),
            confidence,
            verified_by,
            verified_at,
            extraction_run_id,
            Range(effective_at, None, bounds="[)"),
        ),
    )
    new_row = cur.fetchone()
    assert new_row is not None
    return int(new_row[0])
