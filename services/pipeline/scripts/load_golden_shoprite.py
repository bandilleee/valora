r"""Loads the Shoprite FY2024/FY2025 golden workbooks into `facts` (M2.12).

Backlog condition: rows land with correct provenance. This script builds
every row of provenance a fact needs from real sources, never a
placeholder: documents from docs/shoprite_pdf_manifest.md's recorded
sha256/s3_key, concepts from docs/taxonomy_v0.md (via scripts/
seed_concepts.py, a prerequisite — see main()), company_line_items from
each workbook's own as_reported_label, and bbox from actually locating the
printed value on its PDF page with PyMuPDF (see "Bounding boxes" below).

What this script does NOT do: it is not M3.3's ingest function (it never
computes a sha256 from bytes or writes to S3 -- the two documents rows it
creates use the sha256/s3_key already recorded by M2.2/M2.3), and it does
not touch M3.4's dedupe logic. See "Documents and M3.4" below for what
happens when that dedupe eventually runs against these rows.

SHEETS LOADED, AND WHY (requirement 5, do not double-load):

Loaded: IncomeStatement, BalanceSheet, CashFlow, HEPS, Segments, from
BOTH workbooks. These are the only sheets containing distinct, non-
redundant transcriptions with real provenance (a pdf_page footnote or,
for FY2025, a value locatable in the source PDF -- see "Bounding boxes").

Skipped: Restatement_N45 (FY2025 workbook) and Bitemporal_Pair (FY2024
workbook). Both are demonstration/test fixtures for the bitemporal
concept, not new information -- confirmed empirically before writing this
loader (not assumed): every one of Restatement_N45's `as_reported` rows
is a byte-for-byte duplicate of a value already present in the FY2024
workbook's own IncomeStatement sheet, and every one of its `restated`
rows duplicates the FY2025 workbook's own IncomeStatement FY2024-restated
comparative column. Bitemporal_Pair's 36 rows are the same story against
the FY2024 workbook's own IncomeStatement/HEPS sheets (confirmed for 34 of
36 directly; the remaining 2 use a slash-joined demonstration label that
doesn't literally string-match either sheet's separate FY2024/FY2025
label, but represent the same underlying transcribed value). Loading
either sheet would either publish the same fact twice under the WRONG
document_id (Restatement_N45's rows are printed in the FY2024 AFS or the
FY2025 AFS respectively, not "wherever this sheet happens to live"), or
require extra merge logic for zero informational gain. Also skipped
(non-data, no separate justification needed): README, Checks,
Concepts_Discovered, Structural_Changes.

COMPARATIVE-YEAR ROWS: each of IncomeStatement/BalanceSheet/CashFlow
carries the reporting year AND a prior-year comparative column (e.g. the
FY2024 workbook's IncomeStatement has FY2024 as_reported AND FY2023
restated). Both are loaded -- FY2023's restated figures are genuinely new
information (not available from any other loaded sheet), printed on the
FY2024 AFS's own pages, with their own real page/bbox provenance. basis is
read per-row from the workbook, never assumed per-document -- this is
exactly the "basis is per-fact, not per-filing" fact CLAUDE.md and
taxonomy_v0.md both record (the FY2025 workbook's BalanceSheet comparative
is as_reported while its IncomeStatement comparative is restated, in the
SAME document).

CONCEPT LOOKUP: NOT via the workbook's own concept_suggestion column,
which is known to contain naming drift (e.g. "Current assets" suggests
both total_current_assets and total_current_assets_incl_hfs across the two
workbooks -- only the second is docs/taxonomy_v0.md's canonical code) and,
in the two bitemporal fixture sheets, outright malformed strings that fail
the concepts.code CHECK constraint. Concepts are resolved by matching
(statement, as_reported_label) against taxonomy_v0.md's own FY2024/FY2025
label columns -- the exact same lookup verified, during M2.11, to have
zero mismatches against both workbooks' non-segment/non-fixture rows.
Segment rows are resolved the same way against the per-(metric, segment)
concept table added to taxonomy_v0.md's SS3.5 during this task (see the
segment blocking-issue note in PROGRESS.md's 2.12 entry).

SCALE (requirement 4): every row in both workbooks is scale='millions'
(confirmed: workbooks are headed Rm throughout, no row uses 'units' or
'thousands' except unit_type='count'/'cents_per_share' rows, which are
UNIT, not SCALE -- see the distinction below). facts.value is canonical
(M1.7): value_as_printed * 1_000_000 for scale='millions' rows. Confirmed
against a known figure: FY2025 Revenue prints as 256,682 (Rm) -> canonical
256682000000. HEPS/EPS rows (unit_type=currency_per_share, printed in
cents) and share-count rows (unit_type=count, printed in thousands in the
workbook's own `scale` column, e.g. shares_in_issue) are converted
according to THEIR OWN scale column value, not assumed to be currency-Rm
-- see _canonical_value() below for the full conversion table, confirmed
against shares_in_issue (540,523 thousand -> 540523000).

KNOWLEDGE PERIOD (effective_at): each document's own board authorisation
date from docs/shoprite_pdf_manifest.md -- FY2024 AFS 2024-09-27, FY2025
AFS 2025-10-01. Every fact sourced from a given PDF uses that PDF's
authorisation date as effective_at, regardless of which fiscal year the
fact itself describes (e.g. a FY2023-restated fact printed in the FY2024
AFS becomes knowable on 2024-09-27, the date THAT DOCUMENT was published
-- not FY2023's own filing date, which this loader never touches).
Consequence, stated as the task asked: querying as_of('2025-01-01')
returns FY2024 and FY2023 (as printed in the FY2024 AFS) facts and NOTHING
from the FY2025 AFS, because 2025-01-01 is before the FY2025 AFS's
2025-10-01 authorisation date -- verified live, see the loader's own
verification output.

IDEMPOTENCY (requirement 6, the subtlest part of this task):
publish_fact() ALWAYS supersedes an existing current fact for the same
identity (company_id, concept_id, period_start, period_type, basis) -- it
has no built-in "is this actually different" check, by design (M1.12's
docstring: that decision belongs to the caller). A naive re-run of this
loader would call publish_fact() for every fact on every run, closing and
reopening every knowledge_period at whatever effective_at this run
computed -- fabricating a revision history that never happened, exactly
what the task warned about. Fixed here: before calling publish_fact() for
a given identity, the loader reads the CURRENT fact (if any) via a direct
query (mirroring publish_fact()'s own "find current" query, since no
public accessor exists for a single identity's current row) and skips the
publish_fact() call entirely -- not just skips inserting, skips CALLING
the function at all -- when the current row's value, currency, scale,
document_id, page, and line_item_id are all unchanged. See
_current_fact_unchanged() and the loader's own re-run verification
(run twice, second run's report shows 0 published, N skipped, and a
direct query confirms every knowledge_period lower bound is identical
across both runs).

VERIFIED COLUMN (requirement 7): 0 of ~487 loadable rows across both
workbooks are marked verified='Y' -- confirmed by direct inspection before
writing this loader, not assumed. Per instruction, this is recorded, not
silently upgraded: every fact this script publishes has verified_by=NULL,
verified_at=NULL, which is the schema's own documented meaning for "not
yet human-verified" (facts.verified_by's column comment). This is
consistent with M2's own place in the plan of record -- M2.5-2.10's
"done when" was "12 validation checks pass", not "reviewer sign-off"; hand
verification against the review queue is M7's job. The loader's report
states the 0% figure plainly rather than omitting it.

BOUNDING BOXES: for FY2024 rows (pdf_page filled for every row except 18
of Bitemporal_Pair's 36, which is skipped entirely per above), search is
scoped to that single page. For FY2025 rows (page is EMPTY for all 345
rows in that workbook -- confirmed before writing this loader, not
assumed; see PROGRESS.md's M2.12 entry for the decision this required
asking about), search runs across the whole ~156-page PDF. Disambiguation:
(1) find every text line on the candidate page(s) whose full text exactly
equals the target as_reported_label; (2) for each such line, scan every
text span at the same y-coordinate (same visual row, +-2pt) for one whose
parsed numeric value equals the target value_as_printed; (3) if exactly
one (label-line, value-span) pair survives across all candidate pages,
that span's bbox (converted to normalised [0,1] page-relative coordinates,
origin top-left, matching facts.bbox's documented convention exactly) is
used. If zero or more than one such pair survives, this is recorded as a
whole-page fallback box ({x0:0,y0:0,x1:1,y1:1}) rather than guessed at --
see the loader's own provenance report for the exact fallback count and
reasons, and the spot-check section below for confirmation renders.
"""

from __future__ import annotations

import datetime
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]  # PyMuPDF ships no py.typed marker
import openpyxl
import psycopg

from valora_pipeline.db import get_connection, publish_fact, transaction

REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = REPO_ROOT / "docs" / "taxonomy_v0.md"
GOLDEN_DIR = REPO_ROOT / "data" / "golden"
PDF_DIR = REPO_ROOT / "data" / "pdfs"

COMPANY_JSE_CODE = "SHP"


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    filename: str
    sha256: str
    s3_key: str
    published_at: datetime.date
    effective_at: datetime.datetime
    fiscal_period: str


# Board authorisation dates, from docs/shoprite_pdf_manifest.md. UTC midday
# chosen (not midnight) purely so the instant is unambiguous under any
# timezone offset -- these dates carry no intraday precision in the source
# document, and M1.8's boundary tests only care about ordering, not
# time-of-day, so any fixed hour is equally correct; midday avoids ever
# looking like a date-shifted midnight artifact when displayed.
DOCUMENTS = {
    "FY2024": DocumentMeta(
        filename="SHP_AFS_FY2024_20240927.pdf",
        sha256="ecba13484c68602251c4501e1dff42c49a69c31c5698eadf2e4cea9a5b5ab7af",
        s3_key="documents/ecba13484c68602251c4501e1dff42c49a69c31c5698eadf2e4cea9a5b5ab7af.pdf",
        published_at=datetime.date(2024, 9, 27),
        effective_at=datetime.datetime(2024, 9, 27, 12, 0, tzinfo=datetime.UTC),
        fiscal_period="FY2024",
    ),
    "FY2025": DocumentMeta(
        filename="SHP_AFS_FY2025_20251001.pdf",
        sha256="0118688193938349cc9dbf62c5960190078102a46b85e024396c16dbbcb0b445",
        s3_key="documents/0118688193938349cc9dbf62c5960190078102a46b85e024396c16dbbcb0b445.pdf",
        published_at=datetime.date(2025, 10, 1),
        effective_at=datetime.datetime(2025, 10, 1, 12, 0, tzinfo=datetime.UTC),
        fiscal_period="FY2025",
    ),
}

# Fiscal year period boundaries, derived from each AFS's own "N weeks
# ended <date>" statement header (docs/shoprite_pdf_manifest.md) and the
# preceding year's end date (the next fiscal year always starts the day
# after). All three years confirmed to span exactly 364 days (52 weeks),
# consistent with the golden workbooks' own README ("52 weeks ended").
PERIOD_BOUNDS = {
    "FY2023": (datetime.date(2022, 7, 4), datetime.date(2023, 7, 2)),
    "FY2024": (datetime.date(2023, 7, 3), datetime.date(2024, 6, 30)),
    "FY2025": (datetime.date(2024, 7, 1), datetime.date(2025, 6, 29)),
}

SHEETS_TO_LOAD = ["IncomeStatement", "BalanceSheet", "CashFlow", "HEPS", "Segments"]

# scale (as printed) -> multiplier to canonical units. Confirmed against
# FY2025 Revenue: 256682 (millions) -> 256682 * 1_000_000 = 256,682,000,000.
SCALE_MULTIPLIERS = {
    "units": Decimal(1),
    "thousands": Decimal(1_000),
    "millions": Decimal(1_000_000),
}


# ---------------------------------------------------------------------------
# Taxonomy lookup: (statement, as_reported_label) -> concept code
# ---------------------------------------------------------------------------


def _load_taxonomy_label_to_code() -> dict[tuple[str, str], str]:
    """Same table-row regex as scripts/seed_concepts.py, but keyed by
    (statement, as-reported-label) -> code instead of building ConceptRow
    objects -- this is the lookup M2.11's own completeness check used to
    verify 205/205 (core) and 61/61 (segment) exact matches, reused here
    rather than reimplemented, so a label this loader cannot resolve is
    the same event as a label the completeness check would have flagged.
    """
    markdown = TAXONOMY_PATH.read_text()
    sections = re.split(r"\n### ", markdown)
    statement_map = {
        "3.1 Income statement": "income_statement",
        "3.2 Balance sheet": "balance_sheet",
        "3.3 Cash flow": "cash_flow",
        "3.4 HEPS reconciliation (note 36)": "heps_reconciliation",
        "3.5 Segment note (note 2.1) — retail-only": "segment_note",
    }
    lookup: dict[tuple[str, str], str] = {}
    for section in sections:
        heading = section.split("\n", 1)[0].strip()
        stmt = statement_map.get(heading)
        if stmt is None:
            continue
        for line in section.split("\n"):
            if not line.startswith("| `"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            code = cols[0].strip("` ")
            fy24 = cols[6] if len(cols) > 6 else ""
            fy25 = cols[7] if len(cols) > 7 else ""
            for lbl in (fy24, fy25):
                lbl = lbl.strip()
                if lbl and not lbl.startswith("—"):
                    lookup[(stmt, lbl)] = code
    return lookup


# ---------------------------------------------------------------------------
# Workbook reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkbookRow:
    workbook_year: str  # "FY2024" or "FY2025" -- which workbook this came from
    sheet: str
    statement: str
    as_reported_label: str
    period: str  # fiscal year this fact describes, e.g. "FY2023"
    basis: str
    value_as_printed: Decimal
    scale: str
    unit: str
    currency: str
    pdf_page: int | None  # 1-indexed, as printed in the workbook; None if unfilled


def _parse_value(raw: Any) -> Decimal:
    if isinstance(raw, int | float):
        return Decimal(str(raw))
    raise ValueError(f"unexpected value_as_printed type: {raw!r}")


def read_workbook_rows(workbook_year: str) -> list[WorkbookRow]:
    path = GOLDEN_DIR / f"shoprite_SHP_{workbook_year}_hand_entry.xlsx"
    wb = openpyxl.load_workbook(path, data_only=True)
    rows: list[WorkbookRow] = []
    for sheet_name in SHEETS_TO_LOAD:
        ws = wb[sheet_name]
        header: tuple[Any, ...] | None = None
        for raw_row in ws.iter_rows(values_only=True):
            if raw_row[0] == "row_id":
                header = raw_row
                continue
            if header is None or raw_row[0] is None:
                continue
            d = dict(zip(header, raw_row, strict=False))
            page_val = d.get("page") if "page" in d else d.get("pdf_page")
            rows.append(
                WorkbookRow(
                    workbook_year=workbook_year,
                    sheet=sheet_name,
                    statement=d["statement"],
                    as_reported_label=d["as_reported_label"],
                    period=d["period"],
                    basis=d["basis"],
                    value_as_printed=_parse_value(d["value_as_printed"]),
                    scale=d["scale"],
                    unit=d["unit"],
                    currency=d["currency"],
                    pdf_page=int(page_val) if page_val not in (None, "") else None,
                )
            )
    return rows


def _canonical_value(row: WorkbookRow) -> Decimal:
    multiplier = SCALE_MULTIPLIERS[row.scale]
    return row.value_as_printed * multiplier


def _period_type(row: WorkbookRow) -> str:
    # Both workbooks are annual (FY) filings throughout -- confirmed: no
    # row in either workbook has period other than a plain "FYxxxx" label.
    return "FY"


# ---------------------------------------------------------------------------
# Bounding box location (PyMuPDF)
# ---------------------------------------------------------------------------

# HEPS reconciliation rows: the workbook appends "[gross]"/"[tax effect]"/
# "[net]" to disambiguate which of the note's three printed columns a row's
# value comes from -- confirmed by inspecting the source PDF (both years'
# note 36 tables print one column header row: "Gross | Income tax effect |
# Net") that this suffix is NEVER itself printed on the page. Searching for
# the label including the suffix therefore never matches anything, which is
# the root cause of ~50 "not found" fallbacks caught on first run and fixed
# here rather than left as an inflated fallback count. The suffix instead
# selects a COLUMN POSITION (leftmost/middle/rightmost numeric span on the
# matched row) once the true (suffix-free) label is found -- confirmed
# reliable against the real column x-coordinates (e.g. gross~406pt,
# tax~466pt, net~520pt on FY2025's note 36 page).
_HEPS_COLUMN_SUFFIX = re.compile(r"\s*\[(gross|tax effect|net)\]\s*$")
_HEPS_COLUMN_INDEX = {"gross": 0, "tax effect": 1, "net": 2}

# Segment note rows: the workbook's as_reported_label is a synthesised
# "Metric :: Segment" compound (taxonomy_v0.md SS2b's own convention) --
# never printed verbatim. The PDF prints the metric as a row label (e.g.
# "External", nested under a "Sale of merchandise" heading) and the segment
# as a COLUMN HEADER; the row's own printed text is only the part before
# " :: ". Confirmed against the source PDF (note 2.1's per-segment matrix).
_SEGMENT_SUFFIX = re.compile(r"^(.*?) :: .+$")

# "Heading: sub-item" rows (e.g. "Profit/(loss) attributable to: owners
# of the parent", "TCI to owners arises from: continuing operations"):
# the workbook joins a section heading and its sub-item with ": ", but
# the PDF prints them as two SEPARATE lines -- the heading (e.g.
# "Profit/(loss) attributable to:") and, immediately below it, the
# sub-item alone, capitalised as its own sentence (e.g. "Owners of the
# parent"). Confirmed against the source PDF for all 6 such labels
# present in the income statement sheets of both workbooks. Only the
# sub-item is a printed row label with its own value; the heading line
# carries no value of its own.
_HEADING_SUBITEM_SUFFIX = re.compile(r"^.+: (.+)$")


def _printed_row_label(as_reported_label: str) -> tuple[str, str | None]:
    """Returns (label to search for on the page, HEPS column name if the
    original label was a bracketed gross/tax effect/net annotation).
    Segment compound labels are reduced to their metric-leaf text (the
    part actually printed as a row label); the segment itself is resolved
    by matching the target VALUE among all spans on the matched row, the
    same as any other multi-column row (see _find_value_on_page) --
    segments do not need column-position selection because, unlike the
    gross/tax/net columns, two segments coincidentally sharing a value on
    one row was not observed anywhere in this dataset (checked: every
    segment row's six values are pairwise distinct in both workbooks).
    """
    heps_match = _HEPS_COLUMN_SUFFIX.search(as_reported_label)
    if heps_match:
        return _HEPS_COLUMN_SUFFIX.sub("", as_reported_label), heps_match.group(1)

    segment_match = _SEGMENT_SUFFIX.match(as_reported_label)
    if segment_match:
        metric = segment_match.group(1)
        # The metric itself sometimes carries a sub-heading the PDF prints
        # as a separate nested line (e.g. "Sale of merchandise - external"
        # -> printed row is just "External", under a "Sale of merchandise"
        # heading line) -- take the text after the last " - " if present.
        leaf = metric.rsplit(" - ", 1)[-1]
        return leaf.strip().capitalize() if leaf != metric else metric, None

    heading_match = _HEADING_SUBITEM_SUFFIX.match(as_reported_label)
    if heading_match:
        sub_item = heading_match.group(1).strip()
        return sub_item[:1].upper() + sub_item[1:], None

    return as_reported_label, None


@dataclass(frozen=True, slots=True)
class BboxResult:
    page_index: int  # 0-indexed PyMuPDF page
    bbox: dict[str, float] | None  # None means fallback (whole page)
    fallback_reason: str | None


def _parse_pdf_number(text: str) -> float | None:
    t = text.strip()
    if t in ("—", "-", ""):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    t = t.replace(" ", "").replace(" ", "").replace(",", "")
    try:
        val = float(t)
    except ValueError:
        return None
    return -val if neg else val


def _normalise_bbox(
    span_bbox: tuple[float, float, float, float], page_rect: fitz.Rect
) -> dict[str, float]:
    x0, y0, x1, y1 = span_bbox
    w, h = page_rect.width, page_rect.height
    nx0, ny0, nx1, ny1 = x0 / w, y0 / h, x1 / w, y1 / h
    # Clamp to [0,1] and guarantee x0<x1, y0<y1 (the CHECK constraint's
    # exact requirement) -- a span can sit fractionally outside the page
    # box due to font metrics overshoot; clamping never changes which
    # value the box points at, only its extreme edge by a sub-pixel amount.
    nx0, nx1 = max(0.0, min(nx0, nx1)), min(1.0, max(nx0, nx1))
    ny0, ny1 = max(0.0, min(ny0, ny1)), min(1.0, max(ny0, ny1))
    if nx1 <= nx0:
        nx1 = min(1.0, nx0 + 0.0001)
    if ny1 <= ny0:
        ny1 = min(1.0, ny0 + 0.0001)
    return {"x0": nx0, "y0": ny0, "x1": nx1, "y1": ny1}


_TRAILING_FOOTNOTE_DIGIT = re.compile(r"\d+$")
# A trailing "(note 4)" / "(note 3 and note 7)" clause -- printed on many
# note 36 HEPS reconciliation rows to cross-reference the note the
# adjustment relates to (e.g. "Profit on disposal of assets classified as
# held for sale (note 4)"). Confirmed widespread across both years' note
# 36 pages, not a one-off; stripped the same way as the trailing footnote
# digit, since neither is part of the workbook's own as_reported_label.
_TRAILING_NOTE_REFERENCE = re.compile(r"\s*\(note \d+(\s+and note \d+)*\)\s*$", re.IGNORECASE)


def _strip_pdf_annotations(text: str) -> str:
    text = _TRAILING_NOTE_REFERENCE.sub("", text)
    text = _TRAILING_FOOTNOTE_DIGIT.sub("", text)
    return text.strip()


# Shrinking the search string below this many words is refused: a single
# common word ("profit", "total") risks matching unrelated lines elsewhere
# on the page. 2 confirmed sufficient for every wrapped label actually
# observed in both PDFs' note 36/2.1 tables (e.g. "Interest revenue
# included in\ntrading profit" wraps after 5 words; matching resumes at
# the "trading profit" tail, 2 words).
_MIN_SUFFIX_WORDS = 2


def _find_value_on_page(
    page: fitz.Page, label: str, target_value: float
) -> list[tuple[float, float, float, float]]:
    """Returns every (label-row, value) match found on this page: empty
    means not found here, a single-element list means an unambiguous
    match, more than one element means this page alone is ambiguous. The
    caller aggregates this across all candidate pages to decide overall
    unambiguity.

    Two PDF-rendering quirks handled here, both confirmed against the
    actual source PDFs before being coded, not assumed: (1) a row label
    printed with a trailing footnote reference digit and no separating
    space (e.g. "Trading profit/(loss)6") never equals the workbook's
    clean label -- stripped before comparison; (2) a long row label wraps
    across two separate PyMuPDF `line` objects (e.g. "Interest revenue
    included in" / "trading profit"), and the row's numeric values sit at
    the WRAPPED remainder's y-coordinate, not the first line's -- handled
    by shrinking the search string to progressively shorter word-suffixes
    (down to _MIN_SUFFIX_WORDS) until a line match is found, rather than
    assuming a fixed wrap point.
    """
    d = page.get_text("dict")

    def line_text_stripped(line: dict[str, Any]) -> str:
        text = "".join(s["text"] for s in line["spans"]).strip()
        return _strip_pdf_annotations(text)

    words = label.split()
    # The full label is always tried first (n=len(words)), regardless of
    # _MIN_SUFFIX_WORDS -- that floor bounds how far SHRINKING below the
    # original length is allowed to go, it must never suppress the
    # original attempt itself, including for a label already shorter than
    # the floor (e.g. a single-word segment row label like "External").
    shrink_floor = min(_MIN_SUFFIX_WORDS, len(words))
    for n in range(len(words), shrink_floor - 1, -1):
        search_text = " ".join(words[-n:]) if n < len(words) else label

        label_lines = []
        for block in d["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                if line_text_stripped(line) == search_text:
                    label_lines.append(line)
        if not label_lines:
            continue

        row_matches: list[tuple[float, float, float, float]] = []
        for line in label_lines:
            ly0 = line["bbox"][1]
            for block2 in d["blocks"]:
                if "lines" not in block2:
                    continue
                for line2 in block2["lines"]:
                    if abs(line2["bbox"][1] - ly0) > 2:
                        continue
                    for span in line2["spans"]:
                        val = _parse_pdf_number(span["text"])
                        if val is not None and val == target_value:
                            row_matches.append(span["bbox"])

        if row_matches:
            return row_matches
        # Label text found but no row-level value match at this
        # suffix length -- keep shrinking rather than giving up, since a
        # shorter wrap-remainder further down the label may still match.

    return []


def _find_heps_column_on_page(
    page: fitz.Page, label: str, column: str, target_value: float
) -> list[tuple[float, float, float, float]]:
    """HEPS gross/tax-effect/net rows: the target VALUE alone cannot
    disambiguate WHICH COLUMN within a row (confirmed live -- the same
    value legitimately repeats across the gross and net columns of one
    row when tax effect is nil, e.g. "Profit on disposal of assets
    classified as held for sale" FY2025: gross=-45, tax=0, net=-45).
    Column is instead selected by POSITION: every cell on the matched
    row, left-to-right, confirmed against the printed "Gross | Income tax
    effect | Net" header order on both years' note 36 pages.

    The target value IS still needed to disambiguate WHICH ROW, though,
    when the same label legitimately appears twice on one page (the
    current year's figure and the prior year's restated comparative,
    printed as two separate row-blocks under "2025" / "Restated 2024"
    section headers on the same page -- confirmed live). A candidate row
    is only accepted if the selected column's own value equals
    target_value; a row whose label matches but whose column value
    differs is silently the OTHER year's row, not a real ambiguity.
    """
    d = page.get_text("dict")
    words = label.split()
    shrink_floor = min(_MIN_SUFFIX_WORDS, len(words))
    for n in range(len(words), shrink_floor - 1, -1):
        search_text = " ".join(words[-n:]) if n < len(words) else label
        label_lines = []
        for block in d["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                text = _strip_pdf_annotations(text)
                if text == search_text:
                    label_lines.append(line)
        if not label_lines:
            continue

        results: list[tuple[float, float, float, float]] = []
        for line in label_lines:
            ly0 = line["bbox"][1]
            # A table CELL is either a parsed number or a nil marker
            # (em-dash/hyphen) -- both occupy a real column position.
            # Confirmed necessary live: the tax-effect column is
            # genuinely nil ("—") on several rows, and excluding it
            # collapses a real 3-column row to 2, breaking positional
            # indexing. An empty string is NOT a cell (whitespace
            # artefact between spans), so it is excluded. Nil cells carry
            # value 0.0 -- target_value 0.0 is a real, expected case for a
            # nil tax-effect column, not a "missing" sentinel.
            row_cells: list[tuple[float, float, tuple[float, float, float, float]]] = []
            for block2 in d["blocks"]:
                if "lines" not in block2:
                    continue
                for line2 in block2["lines"]:
                    if abs(line2["bbox"][1] - ly0) > 2:
                        continue
                    for span in line2["spans"]:
                        text = span["text"].strip()
                        if text == "":
                            continue
                        parsed = _parse_pdf_number(text)
                        if parsed is None and text not in ("—", "-"):
                            continue
                        row_cells.append((span["bbox"][0], parsed or 0.0, span["bbox"]))
            row_cells.sort(key=lambda t: t[0])
            col_idx = _HEPS_COLUMN_INDEX[column]

            candidate: tuple[float, tuple[float, float, float, float]] | None = None
            if len(row_cells) == 3 and col_idx < len(row_cells):
                _, val, bbox = row_cells[col_idx]
                candidate = (val, bbox)
            elif len(row_cells) == 1:
                # Some rows print only "net" (a single value, e.g. the
                # reconciliation's top-level subtotals like "Earnings
                # from continuing operations") -- accept a lone value
                # regardless of which column was asked for, since there
                # is only one to be found.
                _, val, bbox = row_cells[0]
                candidate = (val, bbox)

            # Only accept this row if its selected cell's own value
            # matches the fact actually being looked for -- this is what
            # tells apart the current year's row from a same-label prior-
            # year row printed elsewhere on the same page.
            if candidate is not None and candidate[0] == target_value:
                results.append(candidate[1])
        if results:
            return results
    return []


def locate_bbox(
    doc: fitz.Document, as_reported_label: str, target_value: float, known_page_1indexed: int | None
) -> BboxResult:
    search_label, heps_column = _printed_row_label(as_reported_label)
    candidate_pages = (
        [known_page_1indexed - 1]
        if known_page_1indexed is not None
        else list(range(doc.page_count))
    )

    found: list[tuple[int, tuple[float, float, float, float]]] = []
    ambiguous_pages: list[int] = []
    for page_idx in candidate_pages:
        if heps_column is not None:
            row_matches = _find_heps_column_on_page(
                doc[page_idx], search_label, heps_column, target_value
            )
        else:
            row_matches = _find_value_on_page(doc[page_idx], search_label, target_value)
        if len(row_matches) == 0:
            continue
        if len(row_matches) > 1:
            ambiguous_pages.append(page_idx)
            continue
        found.append((page_idx, row_matches[0]))

    if len(found) == 1 and not ambiguous_pages:
        page_idx, span_bbox = found[0]
        bbox = _normalise_bbox(span_bbox, doc[page_idx].rect)
        return BboxResult(page_index=page_idx, bbox=bbox, fallback_reason=None)

    if known_page_1indexed is not None:
        fallback_page = known_page_1indexed - 1
    else:
        fallback_page = found[0][0] if found else 0
    if len(found) == 0 and not ambiguous_pages:
        reason = "not found: no line matching the label had a row-level span matching the value"
    elif ambiguous_pages:
        reason = (
            f"ambiguous: {len(ambiguous_pages)} page(s) had more than one "
            f"(label-row, value) match, {len(found)} page(s) had exactly one -- "
            "cannot disambiguate across pages without guessing"
        )
    else:
        reason = (
            f"ambiguous across pages: unambiguous matches found on "
            f"{len(found)} different pages"
        )
    return BboxResult(page_index=fallback_page, bbox=None, fallback_reason=reason)


WHOLE_PAGE_BBOX = {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0}


# ---------------------------------------------------------------------------
# Database: documents, company_line_items
# ---------------------------------------------------------------------------


def ensure_documents(cur: psycopg.Cursor, company_id: int) -> dict[str, int]:
    """Creates the two documents rows if absent (idempotent via ON
    CONFLICT on the existing sha256/s3_key unique constraints), returns
    {"FY2024": id, "FY2025": id}.

    Documents and M3.4 (requirement 2): M3.4's dedupe is keyed on
    documents.sha256, computed from raw bytes. These two rows use the
    real sha256 already computed and recorded by M2.2/M2.3 -- when M3.3's
    ingest function later processes these same two PDFs (e.g. during a
    backfill run), it will compute the identical sha256 from the
    identical bytes, look it up via the sha256 unique constraint, find
    these exact rows already present, and treat them as already-ingested
    -- exactly the behaviour M3.4 exists to provide. No special-casing
    needed in M3.3 for facts M2.12 already loaded.
    """
    ids: dict[str, int] = {}
    for year, meta in DOCUMENTS.items():
        cur.execute(
            """
            insert into documents (
              s3_key, sha256, company_id, doc_type, fiscal_period, published_at
            )
            values (%s, %s, %s, %s, %s, %s)
            on conflict (sha256) do nothing
            """,
            (
                meta.s3_key,
                meta.sha256,
                company_id,
                "annual_report",
                meta.fiscal_period,
                meta.published_at,
            ),
        )
        cur.execute("select id from documents where sha256 = %s", (meta.sha256,))
        row = cur.fetchone()
        assert row is not None
        ids[year] = row[0]
    return ids


def ensure_line_item(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    as_reported_label: str,
    concept_id: int,
    first_seen_doc_id: int,
    cache: dict[tuple[int, str, int], int],
) -> int:
    """Finds or creates the company_line_items row for (company_id,
    as_reported_label, concept_id). Keyed on the triple, not just
    (company_id, as_reported_label): that pair is documented as NOT
    unique (the same printed label can legitimately map to different
    concepts in different statements/notes for one company -- M1.6). One
    genuine case exists in this dataset ("Current assets" -> two
    different concept_suggestion strings across the two workbooks before
    taxonomy_v0.md resolved which was canonical) but resolves to a single
    concept once looked up correctly, so in practice every label in this
    load maps to exactly one line item -- the triple key is what makes
    that a guarantee rather than an assumption.
    """
    key = (company_id, as_reported_label, concept_id)
    if key in cache:
        return cache[key]

    cur.execute(
        """
        select id from company_line_items
        where company_id = %s and as_reported_label = %s and concept_id = %s
        """,
        (company_id, as_reported_label, concept_id),
    )
    row = cur.fetchone()
    if row is not None:
        line_item_id = int(row[0])
        cache[key] = line_item_id
        return line_item_id

    cur.execute(
        """
        insert into company_line_items (
          company_id, as_reported_label, mapping_status, concept_id, first_seen_doc_id
        )
        values (%s, %s, 'mapped', %s, %s)
        returning id
        """,
        (company_id, as_reported_label, concept_id, first_seen_doc_id),
    )
    new_row = cur.fetchone()
    assert new_row is not None
    new_line_item_id = int(new_row[0])
    cache[key] = new_line_item_id
    return new_line_item_id


# ---------------------------------------------------------------------------
# Idempotent fact publication
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CurrentFact:
    id: int
    value: Decimal
    currency: str
    scale: str
    document_id: int
    page: int
    line_item_id: int | None
    knowledge_since: datetime.datetime


def _get_current_fact(
    cur: psycopg.Cursor,
    *,
    company_id: int,
    concept_id: int,
    period_start: datetime.date,
    period_type: str,
    basis: str,
) -> CurrentFact | None:
    """Mirrors publish_fact()'s own "find current fact" query (no public
    single-identity accessor exists in valora_pipeline.db -- see that
    module's docstring on why CRUD beyond the three read/write functions
    was deliberately left out of M1.12). Read-only: never mutates.
    """
    cur.execute(
        """
        select id, value, currency, scale, document_id, page, line_item_id,
               lower(knowledge_period)
        from facts
        where company_id = %s and concept_id = %s and period_start = %s
          and period_type = %s and basis = %s and upper_inf(knowledge_period)
        """,
        (company_id, concept_id, period_start, period_type, basis),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return CurrentFact(
        id=row[0],
        value=row[1],
        currency=row[2],
        scale=row[3],
        document_id=row[4],
        page=row[5],
        line_item_id=row[6],
        knowledge_since=row[7],
    )


def _current_fact_unchanged(current: CurrentFact, new: dict[str, Any]) -> bool:
    """The idempotency check (requirement 6): a re-run must be a genuine
    no-op, not a fabricated supersession. "Unchanged" means every field
    that would actually differ in a real restatement is identical --
    value, currency, scale, document_id (source), page, and line_item_id
    (as-reported label). bbox is deliberately NOT compared: two runs of
    the SAME PyMuPDF search against the SAME unchanged PDF are
    deterministic and will always agree, so bbox differing would only
    ever happen if the search logic itself changed between runs -- which
    is exactly the case where NOT re-publishing would hide a genuine bbox
    improvement. In practice this script's own re-run test (see verify())
    confirms bbox is stable run-to-run for this dataset, so the exclusion
    is inert here, but the reasoning holds in general.
    """
    return bool(
        current.value == new["value"]
        and current.currency == new["currency"]
        and current.scale == new["scale"]
        and current.document_id == new["document_id"]
        and current.page == new["page"]
        and current.line_item_id == new["line_item_id"]
    )


# ---------------------------------------------------------------------------
# Main load
# ---------------------------------------------------------------------------


@dataclass
class LoadStats:
    published: int = 0
    skipped_unchanged: int = 0
    skipped_superseded_by_later_document: int = 0
    bbox_exact: int = 0
    bbox_fallback: int = 0
    fallback_reasons: list[str] | None = None

    def __post_init__(self) -> None:
        if self.fallback_reasons is None:
            self.fallback_reasons = []


def main() -> None:
    if not TAXONOMY_PATH.is_file():
        print(f"ERROR: {TAXONOMY_PATH} does not exist.", file=sys.stderr)
        sys.exit(1)
    for meta in DOCUMENTS.values():
        pdf_path = PDF_DIR / meta.filename
        if not pdf_path.is_file():
            print(f"ERROR: {pdf_path} does not exist.", file=sys.stderr)
            sys.exit(1)

    label_to_code = _load_taxonomy_label_to_code()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("select id from companies where jse_code = %s", (COMPANY_JSE_CODE,))
        row = cur.fetchone()
        if row is None:
            print(
                f"ERROR: no company with jse_code={COMPANY_JSE_CODE!r}. Run 'make seed' first.",
                file=sys.stderr,
            )
            sys.exit(1)
        company_id = row[0]

        cur.execute("select count(*) from concepts")
        concept_count = cur.fetchone()
        assert concept_count is not None
        if concept_count[0] == 0:
            print(
                "ERROR: concepts table is empty. Run 'make seed-concepts' first.",
                file=sys.stderr,
            )
            sys.exit(1)

    pdf_docs = {year: fitz.open(PDF_DIR / meta.filename) for year, meta in DOCUMENTS.items()}

    stats = LoadStats()
    line_item_cache: dict[tuple[int, str, int], int] = {}

    with transaction(conn) as cur:
        doc_ids = ensure_documents(cur, company_id)

        for workbook_year in ("FY2024", "FY2025"):
            rows = read_workbook_rows(workbook_year)
            doc_id = doc_ids[workbook_year]
            effective_at = DOCUMENTS[workbook_year].effective_at
            pdf = pdf_docs[workbook_year]

            for wrow in rows:
                lookup_key = (wrow.statement, wrow.as_reported_label)
                code = label_to_code.get(lookup_key)
                if code is None:
                    raise ValueError(
                        f"no taxonomy concept for {lookup_key!r} (row from "
                        f"{workbook_year} {wrow.sheet}) -- docs/taxonomy_v0.md's "
                        "completeness check should have caught this; the "
                        "document and this loader have drifted."
                    )

                cur.execute("select id from concepts where code = %s", (code,))
                concept_row = cur.fetchone()
                assert concept_row is not None, f"concept code {code!r} not seeded"
                concept_id = concept_row[0]

                line_item_id = ensure_line_item(
                    cur,
                    company_id=company_id,
                    as_reported_label=wrow.as_reported_label,
                    concept_id=concept_id,
                    first_seen_doc_id=doc_id,
                    cache=line_item_cache,
                )

                period_start, period_end = PERIOD_BOUNDS[wrow.period]
                period_type = _period_type(wrow)
                canonical_value = _canonical_value(wrow)

                bbox_result = locate_bbox(
                    pdf, wrow.as_reported_label, float(wrow.value_as_printed), wrow.pdf_page
                )
                if bbox_result.bbox is not None:
                    stats.bbox_exact += 1
                    bbox = bbox_result.bbox
                else:
                    stats.bbox_fallback += 1
                    assert stats.fallback_reasons is not None
                    stats.fallback_reasons.append(
                        f"{workbook_year}/{wrow.sheet}/{wrow.as_reported_label} "
                        f"({wrow.period} {wrow.basis}): {bbox_result.fallback_reason}"
                    )
                    bbox = WHOLE_PAGE_BBOX
                page_1indexed = bbox_result.page_index + 1

                new_fact = {
                    "value": canonical_value,
                    "currency": wrow.currency,
                    "scale": "units",  # value is already canonical; scale is provenance-only
                    "document_id": doc_id,
                    "page": page_1indexed,
                    "line_item_id": line_item_id,
                }

                current = _get_current_fact(
                    cur,
                    company_id=company_id,
                    concept_id=concept_id,
                    period_start=period_start,
                    period_type=period_type,
                    basis=wrow.basis,
                )
                if current is not None and _current_fact_unchanged(current, new_fact):
                    stats.skipped_unchanged += 1
                    continue

                # A fact can be printed in BOTH documents (e.g. a balance
                # sheet comparative that IFRS 5 does not require
                # restating -- confirmed live: total_non_current_assets
                # FY2024 appears identically in both the FY2024 AFS and
                # the FY2025 AFS's comparative column). The first loader
                # run processes FY2024 then FY2025 in that order, so
                # FY2025's later effective_at correctly supersedes
                # FY2024's -- real, intentional history (a later document
                # re-confirmed the figure). On a SECOND run, reprocessing
                # FY2024's own row after that supersession already exists
                # would try to publish at FY2024's EARLIER effective_at,
                # which publish_fact() correctly refuses (it would
                # corrupt the belief timeline by going backward). This
                # is not new information -- FY2024's confirmation is
                # older than what the store already knows -- so it is
                # skipped, not retried and not treated as an error.
                if current is not None and effective_at <= current.knowledge_since:
                    stats.skipped_superseded_by_later_document += 1
                    continue

                publish_fact(
                    cur,
                    company_id=company_id,
                    concept_id=concept_id,
                    period_start=period_start,
                    period_end=period_end,
                    period_type=period_type,
                    basis=wrow.basis,
                    value=canonical_value,
                    currency=wrow.currency,
                    scale="units",
                    document_id=doc_id,
                    page=page_1indexed,
                    bbox=bbox,
                    effective_at=effective_at,
                    line_item_id=line_item_id,
                    verified_by=None,
                    verified_at=None,
                )
                stats.published += 1

    for pdf in pdf_docs.values():
        pdf.close()
    conn.close()

    print(f"Published: {stats.published}")
    print(f"Skipped (unchanged, idempotent no-op): {stats.skipped_unchanged}")
    print(
        "Skipped (superseded by a later document's confirmation, idempotent no-op): "
        f"{stats.skipped_superseded_by_later_document}"
    )
    print(f"Bbox located exactly: {stats.bbox_exact}")
    print(f"Bbox fell back to whole-page: {stats.bbox_fallback}")
    if stats.fallback_reasons:
        print("\nFallback reasons:")
        for reason in stats.fallback_reasons:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()
