# Shoprite PDF naming manifest (M2.2)

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

## Tooling

PyMuPDF (`pymupdf`) added to `services/pipeline`'s `dev` dependency group via
`uv add --group dev pymupdf` — used only for this one-off manifest-building
inspection, not wired into the extraction pipeline (that is M4's job). No
global install.
