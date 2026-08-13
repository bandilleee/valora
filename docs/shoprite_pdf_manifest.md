# Shoprite PDF naming and S3 upload manifest (M2.2, M2.3)

Renames applied 2026-08-13. Every field below was determined by opening each
PDF with PyMuPDF (`services/pipeline`, dev dependency) and reading the
document's own text — never inferred from the original vendor filename.
Naming convention: `{code}_{type}_{period}_{published}.pdf`.

## Renamed (10 files)

| Old filename | New filename | Fiscal period evidence | Publication evidence | Pages | FS scope |
|---|---|---|---|---|---|
| `5740_Shoprite_IR_2016E.pdf` | `SHP_IR_FY2016_20160822.pdf` | "53 weeks" / "for the year ended June 2016" (p.7 five-year review; p.48 Statement of Responsibility) | "the summary consolidated financial statements ... were approved by the board of directors on **22 August 2016**" (p.48) | 78 | **Section within a larger document.** Cover: "INTEGRATED REPORT 2016". Contains business overview, corporate governance, non-financial report chapters. Only a "Summary Consolidated Financial Statements" section (TOC at p.47, spanning pages 47–63 of 78) — not full statements. |
| `6043_Shoprite_AFS_2018E.pdf` | `SHP_AFS_FY2018_20180820.pdf` | "The annual financial statements for the year ended **1 July 2018**" (p.1 currency note; p.2 responsibility statement) | "approved by the board of directors on **20 August 2018**" (p.2) | 84 | Whole document. Cover: "Annual Financial Statements 2018". TOC starts p.1; statements + notes + annexures; no wider report. |
| `Shoprite_Holdings_AFS_2017E.pdf` | `SHP_AFS_FY2017_20170821.pdf` | "for the year ended **2 July 2017**" (p.1 currency note; p.2 company secretary certificate) | "approved by the board of directors on **21 August 2017**" (p.2) | 76 | Whole document. Cover: "ANNUAL FINANCIAL STATEMENTS 2017". |
| `Shoprite_Holdings_AFS_2019.pdf` | `SHP_AFS_FY2019_20190819.pdf` | "for the year ended **30 June 2019**" (p.1, p.2) | "approved by the Board of Directors on **19 August 2019**" (p.2) | 102 | Whole document. Cover reads "I N T E G R A T E / Annual Financial Statements 2019" — stylised tagline text, **not** an Integrated Report designation (checked: no business/sustainability chapters; TOC and content confirm standalone AFS ending at Annexure B, p.97). |
| `Shoprite_Holdings_AFS_2020.pdf` | `SHP_AFS_FY2020_20200930.pdf` | "for the year ended **28 June 2020**" (p.1) | "approved by the Board of Directors on **30 September 2020**" (p.2) | 110 | Whole document. Cover: "Annual Financial Statements for Shoprite Holdings Ltd ... for the year ended 28 June 2020". **Note:** approval ~6 weeks later than the usual August date — plausibly a COVID-era audit delay; flagged as evidence, cause not confirmed from the document. |
| `shoprite-holdings-iafs-2021.pdf` | `SHP_AFS_FY2021_20210930.pdf` | "as at **4 July 2021**" (p.1, auditor's opinion) | "approved by the Board of Directors on **30 September 2021**" (p.3) | 72 | Whole document. **Flag: filename says "iafs" (integrated annual financial statements), but the document's own text never uses that term.** Auditor's report and directors' declarations use plain "annual financial statements" / "consolidated and separate financial statements" language, structurally identical to 2017–2020/2022/2023. No business-overview or sustainability narrative precedes the statements. Classified as standalone AFS on document content, contradicting the filename, per instruction to determine type from contents, not filename. |
| `shp-afs-2022.pdf` | `SHP_AFS_FY2022_20220930.pdf` | "for the year ended **3 July 2022**" (p.1) | "approved by the Board on **30 September 2022**" (p.2) | 70 | Whole document. Cover: "ANNUAL FINANCIAL STATEMENTS 2022". **Note:** PDF page count (70) is far lower than the printed page range its own TOC references (up to p.135) — a "digital/interactive" page-compression rendering, the same phenomenon documented for the FY2025 duplicate below. Only one rendering of 2022 was supplied, so no duplicate-handling decision was needed here. |
| `shp-afs-2023-print.pdf` | `SHP_AFS_FY2023_20230929.pdf` | "for the year ended **2 July 2023**" (p.2) | "approved by the Board on **29 September 2023**" (p.3) | 138 | Whole document. Cover: "ANNUAL FINANCIAL STATEMENTS 2023". Directors' report (p.6) states corporate-governance disclosures "will be set out in the forthcoming Integrated Report" — confirms AFS and IR are published as two separate documents from this year on. |
| `shp-afs-2024-print.pdf` | `SHP_AFS_FY2024_20240927.pdf` | "year ended 30 June 2024" (established in the FY2024 golden dataset; re-confirmed against this file) | "approved by the Board on **27 September 2024**" (p.3) | 152 | Whole document. |
| `shp-afs-2025-print.pdf` | `SHP_AFS_FY2025_20251001.pdf` | "year ended **29 June 2025**" (established in golden dataset; re-confirmed) | "approved by the Board on **1 October 2025**" (p.3) | 156 | Whole document. This is a **print-imposition rendering**: printed page numbers run 1–153, but each printed spread is split across two PDF pages (confirmed by comparing page-numbered content against the duplicate below, page-for-page). Chosen as canonical because it matches the naming pattern already used by FY2023/FY2024 (`-print.pdf` vendor filenames). |

## Not renamed (1 file) — duplicate, left as-is

| Filename (unchanged) | Reason |
|---|---|
| `Shoprite Holdings - Annual Financial Statements 2025.pdf` | Same report as `SHP_AFS_FY2025_20251001.pdf` — same fiscal period (year ended 29 June 2025), same authorisation date (1 October 2025), same printed page range (1–153). Different PDF rendering: a "digital reader" export where each printed spread is one PDF page (79 total) instead of two (156 total in the print rendering). Checksums differ (not a byte-identical copy), confirmed same content by comparing page-numbered text at multiple points. Decision: keep only the print version under the naming convention; this file is left under its original vendor filename, visibly excluded, rather than deleted. |

## Finding: 11 files supplied for 10 fiscal-year documents

M2.1 downloaded ten annual documents (FY2016–FY2025) as intended; the eleventh
file is a duplicate rendering of FY2025, not an eleventh fiscal year. See table
above.

## Document type is not consistent across the ten years

- **FY2016** is an Integrated Report; the financial statements are a
  ~17-page "Summary Consolidated Financial Statements" section within a
  78-page document, not full statements.
- **FY2017–FY2025** are all standalone Annual Financial Statements — the
  filename pattern (`iafs` for 2021, `AFS` for others) does not reliably
  predict this; 2021's filename claims "integrated" but its content does not.
- Relevant to **M4.16** (page segmentation): only FY2016 needs the
  financial-statements section located within a larger document; every other
  year's financial statements span effectively the whole file.
- Relevant to **M4.17** (classification): fiscal period must be read from
  each document's own statement headers / directors' declarations, never
  inferred from the filename year — confirmed necessary in practice, since
  several fiscal years end in early July, not June, and the "iafs" filename
  for 2021 does not match the document's own self-description.

## Fields I could not determine from the documents

None. All ten distinct fiscal years (2016–2025) resolved to company, document
type, fiscal period, and publication date directly from document text.

## Tooling (M2.2)

PyMuPDF (`pymupdf`) added to `services/pipeline`'s `dev` dependency group via
`uv add --group dev pymupdf` — used only for this one-off manifest-building
inspection, not wired into the extraction pipeline (that is M4's job). No
global install.

## S3 upload (M2.3)

Uploaded to LocalStack S3 via `make upload-documents`
(`services/pipeline/scripts/upload_documents.py`), which is repeatable — see
that script's module docstring and `PROGRESS.md`'s 2.3 entry for the full
reasoning on bucket setup, key scheme, and idempotency. Bucket:
`valora-documents-dev` (from `S3_BUCKET`, read through
`valora_pipeline.config.get_settings()`).

Key scheme: `documents/{sha256}.pdf` — content-addressed, matching what
M3.3's ingest function (bytes → sha256 → S3 → `documents` row) will
independently derive from the same bytes. **M3.3 needs no migration**: it
computes the identical key from the identical hash.

All 11 files present in `data/pdfs/` were uploaded, including the FY2025
duplicate — retained deliberately as the only real fixture we have for the
case M3.4's SHA-256 dedupe cannot detect (same report, two renderings, two
different hashes; see the Open Questions entry in `PROGRESS.md`).

| Filename | SHA-256 | S3 key |
|---|---|---|
| `SHP_IR_FY2016_20160822.pdf` | `9086cb81368cf07ece2c71a82090778bd83371d6a32d059aef419911bec8496e` | `documents/9086cb81368cf07ece2c71a82090778bd83371d6a32d059aef419911bec8496e.pdf` |
| `SHP_AFS_FY2017_20170821.pdf` | `7c84830172c93c54618d531e110239e7f2958bb5da1f3bf53a3f781db2180825` | `documents/7c84830172c93c54618d531e110239e7f2958bb5da1f3bf53a3f781db2180825.pdf` |
| `SHP_AFS_FY2018_20180820.pdf` | `ef43832498e3cb3a2de5422add2fbbdc0bf3128318c1fc3aab5891ebb1d716c9` | `documents/ef43832498e3cb3a2de5422add2fbbdc0bf3128318c1fc3aab5891ebb1d716c9.pdf` |
| `SHP_AFS_FY2019_20190819.pdf` | `845b73284dd67d7b1886692cc4a6e1fbc3b40a8487edda269fe1be88aad7a019` | `documents/845b73284dd67d7b1886692cc4a6e1fbc3b40a8487edda269fe1be88aad7a019.pdf` |
| `SHP_AFS_FY2020_20200930.pdf` | `6edaa055e5aa956cdf6d8c592f912f19e6f6fc044d4dd9fa5a390874c977bb09` | `documents/6edaa055e5aa956cdf6d8c592f912f19e6f6fc044d4dd9fa5a390874c977bb09.pdf` |
| `SHP_AFS_FY2021_20210930.pdf` | `97cb713c18814df879b6497e672f005f5520f08b0da4237ff4adc59b904badcc` | `documents/97cb713c18814df879b6497e672f005f5520f08b0da4237ff4adc59b904badcc.pdf` |
| `SHP_AFS_FY2022_20220930.pdf` | `4a5f924dcb3f44d59e5f2fa7af1ae8fabd0f02edbb06abf84e373a79b0fbc124` | `documents/4a5f924dcb3f44d59e5f2fa7af1ae8fabd0f02edbb06abf84e373a79b0fbc124.pdf` |
| `SHP_AFS_FY2023_20230929.pdf` | `5cc2b70c5dd075bc85be4a0be573cc1f22d2c5c636d363e07a1003adac6776df` | `documents/5cc2b70c5dd075bc85be4a0be573cc1f22d2c5c636d363e07a1003adac6776df.pdf` |
| `SHP_AFS_FY2024_20240927.pdf` | `ecba13484c68602251c4501e1dff42c49a69c31c5698eadf2e4cea9a5b5ab7af` | `documents/ecba13484c68602251c4501e1dff42c49a69c31c5698eadf2e4cea9a5b5ab7af.pdf` |
| `SHP_AFS_FY2025_20251001.pdf` | `0118688193938349cc9dbf62c5960190078102a46b85e024396c16dbbcb0b445` | `documents/0118688193938349cc9dbf62c5960190078102a46b85e024396c16dbbcb0b445.pdf` |
| `Shoprite Holdings - Annual Financial Statements 2025.pdf` (deliberate M3.4 duplicate fixture) | `aaa5f3b137e79566c736da0be865f23b4ca830c56bbeef68f82abdd4ebcb691b` | `documents/aaa5f3b137e79566c736da0be865f23b4ca830c56bbeef68f82abdd4ebcb691b.pdf` |

### Bucket configuration

- **Versioning:** enabled (spec §5.2 "versioned storage"). Confirmed live
  via `get_bucket_versioning` → `Status: Enabled`.
- **Object lock:** requested at bucket creation
  (`ObjectLockEnabledForBucket=True`). **LocalStack community (3.8, the
  version pinned in `docker-compose.yml`) accepts the object-lock API calls
  and reports the configuration back correctly on read, but does not
  enforce it** — confirmed live: a `PUT` with `ObjectLockMode=GOVERNANCE`
  and a future `ObjectLockRetainUntilDate` succeeded, and the retention was
  readable back via `get_object_retention`, but a subsequent
  `delete_object` on that same key succeeded anyway, when a real S3 bucket
  would have refused it. This is a known LocalStack Pro-vs-community gap,
  not a bug in the upload script. Real AWS (M10.2) enforces object lock for
  real; local dev cannot verify that enforcement, only that the
  configuration round-trips.
- One consequence of object lock being requested at creation: S3 makes a
  lock-enabled bucket versioned implicitly and **rejects** an explicit
  `PutBucketVersioning` call afterward (`InvalidBucketState`) — confirmed
  live against LocalStack. `upload_documents.py` checks the current
  versioning status first and only calls `PutBucketVersioning` if it is not
  already enabled.

### Idempotency

Re-running `make upload-documents` is a no-op in every way that matters:
same 11 keys, same content, no new documents, exit 0. Verified live,
including across a full `make reset` (LocalStack has no `PERSISTENCE` flag
set, so its state — unlike Postgres's, which is also destroyed by `reset`
— does not survive it; re-running the script after `make reset` + `make
dev` recreated the bucket and restored all 11 objects). Also verified the
failure path: a key manually overwritten with different-length content
causes the script to hard-fail (`exit 2`, no partial upload) rather than
silently overwrite — see the script's `_check_key_conflicts` docstring for
why this is a size check, not an ETag comparison (multipart upload ETags
are not the object's plain MD5, confirmed live when a false-positive
conflict fired against the ~9 MB FY2022 file).

## Hand verification of the golden workbooks (M2.12)

Every figure in both `data/golden/shoprite_SHP_FY2024_hand_entry.xlsx` and
`data/golden/shoprite_SHP_FY2025_hand_entry.xlsx` was checked by hand
against these source PDFs (`SHP_AFS_FY2024_20240927.pdf`,
`SHP_AFS_FY2025_20251001.pdf`) on **2026-08-14**.

This is a **source-level** statement, not a row-level one: the workbooks'
own `verified` column was never filled in during that check (confirmed at
M2.12 — 0 of 634 loadable rows across both workbooks are marked
`verified='Y'`), so there is no per-row record of which specific cell was
checked when. `facts.verified_by`/`verified_at` were deliberately left
`NULL` for all 634 facts loaded from these workbooks rather than
backfilled from this statement — writing `verified_at` across all 634
rows would convert one honest blanket claim into 634 individual
assertions that were never separately made row by row. See `PROGRESS.md`'s
M2.12 entry for the full reasoning, including why the schema's
`facts_verification_consistency` CHECK was left unmigrated rather than
relaxed to accept a `verified_at` with no `verified_by`.
