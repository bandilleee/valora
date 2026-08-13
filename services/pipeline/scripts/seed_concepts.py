r"""Seeds `concepts` from docs/taxonomy_v0.md (M2.12).

Same conventions as scripts/seed-companies.sh: idempotent, warns on
divergence rather than overwriting, not part of any migration or test
suite (reference data, not schema).

The document is the single source of truth — this script does NOT restate
the concept list. It parses every markdown table row of the form
`| \`code\` | label | sign | unit | archetype_set | definition | ... |`
out of taxonomy_v0.md's §3.1-3.5 sections directly. Adding, renaming, or
correcting a concept means editing the document; this script picks up the
change on next run. There is deliberately no second copy of the concept
list anywhere in this codebase.

statement is derived from which numbered subsection a table row appears
under (§3.1 income_statement, §3.2 balance_sheet, §3.3 cash_flow); §3.4
(HEPS) and §3.5 (segments) are both NULL, matching taxonomy_v0.md's own
documented convention ("NULL for note-level/non-statement concepts").

Idempotent via ON CONFLICT (code) DO NOTHING, matching seed-companies.sh's
own reasoning: never silently overwrites a hand correction made directly
in the database. Re-reads every row back afterward and WARNS (does not
fail, does not touch the row) on any field that differs from the document,
so a genuine document update or an accidental hand-edit becomes visible
rather than silently masked either way.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from valora_pipeline.db import get_connection, transaction

REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = REPO_ROOT / "docs" / "taxonomy_v0.md"

_STATEMENT_BY_SECTION_TITLE = {
    "3.1 Income statement": "income_statement",
    "3.2 Balance sheet": "balance_sheet",
    "3.3 Cash flow": "cash_flow",
    "3.4 HEPS reconciliation (note 36)": None,
    "3.5 Segment note (note 2.1) — retail-only": None,
}

_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ConceptRow:
    code: str
    label: str
    sign_convention: str
    unit_type: str
    archetype_set: tuple[str, ...]
    statement: str | None


def parse_concepts(markdown: str) -> list[ConceptRow]:
    r"""Extracts every concept table row from §3.1-3.5. A row is
    recognised by starting a line with `| \`code\` |` inside a section
    whose heading matches one of the five known statement sections —
    this deliberately excludes concept codes mentioned only in prose
    (§2's reasoning sections quote codes in backticks too, but never at
    the start of a table row), which was confirmed by running this same
    regex shape as a verification script against the document during
    drafting and finding zero false positives from prose.
    """
    sections = re.split(r"\n### ", markdown)
    rows: list[ConceptRow] = []
    seen_codes: set[str] = set()

    for section in sections:
        heading = section.split("\n", 1)[0].strip()
        if heading not in _STATEMENT_BY_SECTION_TITLE:
            continue
        statement = _STATEMENT_BY_SECTION_TITLE[heading]

        for line in section.split("\n"):
            if not line.startswith("| `"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            code = cols[0].strip("` ")
            if not _CODE_PATTERN.match(code):
                raise ValueError(
                    f"concept code {code!r} in section {heading!r} does not match "
                    "the concepts.code CHECK constraint (^[a-z][a-z0-9_]*$) -- fix "
                    "docs/taxonomy_v0.md, do not fix it here."
                )
            if code in seen_codes:
                raise ValueError(
                    f"concept code {code!r} appears more than once in "
                    "docs/taxonomy_v0.md -- the document must be corrected, this "
                    "script will not silently pick one."
                )
            seen_codes.add(code)

            label = cols[1]
            sign_convention = cols[2]
            unit_type = cols[3]
            archetype_set = tuple(a.strip() for a in cols[4].split(","))

            rows.append(
                ConceptRow(
                    code=code,
                    label=label,
                    sign_convention=sign_convention,
                    unit_type=unit_type,
                    archetype_set=archetype_set,
                    statement=statement,
                )
            )

    return rows


def seed(cur: psycopg.Cursor, concepts: list[ConceptRow]) -> None:
    for c in concepts:
        cur.execute(
            """
            insert into concepts (code, label, archetype_set, statement, sign_convention, unit_type)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (code) do nothing
            """,
            (c.code, c.label, list(c.archetype_set), c.statement, c.sign_convention, c.unit_type),
        )


def verify(cur: psycopg.Cursor, concepts: list[ConceptRow]) -> None:
    row_count_result = cur.execute("select count(*) from concepts").fetchone()
    assert row_count_result is not None
    row_count = row_count_result[0]
    print(f"  {row_count} concepts present (document defines {len(concepts)}).")

    mismatches: list[str] = []
    for c in concepts:
        cur.execute(
            "select label, archetype_set, statement, sign_convention, unit_type "
            "from concepts where code = %s",
            (c.code,),
        )
        row = cur.fetchone()
        if row is None:
            mismatches.append(f"  {c.code}: MISSING from database entirely")
            continue
        db_label, db_archetype_set, db_statement, db_sign, db_unit = row
        expected = (c.label, list(c.archetype_set), c.statement, c.sign_convention, c.unit_type)
        actual = (db_label, list(db_archetype_set), db_statement, db_sign, db_unit)
        if expected != actual:
            mismatches.append(f"  {c.code}: document={expected!r} database={actual!r}")

    if mismatches:
        print(
            "WARNING: the following concepts differ from docs/taxonomy_v0.md "
            "(not modified, review and reconcile by hand):",
            file=sys.stderr,
        )
        for m in mismatches:
            print(m, file=sys.stderr)
    else:
        print("  All concepts match docs/taxonomy_v0.md exactly.")


def main() -> None:
    if not TAXONOMY_PATH.is_file():
        print(f"ERROR: {TAXONOMY_PATH} does not exist.", file=sys.stderr)
        sys.exit(1)

    markdown = TAXONOMY_PATH.read_text()
    concepts = parse_concepts(markdown)
    if not concepts:
        print("ERROR: parsed zero concepts from docs/taxonomy_v0.md.", file=sys.stderr)
        sys.exit(1)

    print(f"Parsed {len(concepts)} concepts from {TAXONOMY_PATH.relative_to(REPO_ROOT)}.")
    print("Seeding (ON CONFLICT (code) DO NOTHING)...")

    conn = get_connection()
    with transaction(conn) as cur:
        seed(cur, concepts)

    print("Verifying...")
    with conn.cursor() as cur:
        verify(cur, concepts)
    conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
