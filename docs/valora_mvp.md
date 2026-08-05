# Valora — MVP Specification

**Version:** 0.1 (draft)
**Date:** August 2026
**Status:** For review with engineering and design partners

---

## 1. What Valora is

Valora turns JSE-listed company filings into a verified, source-linked database of financial and operational facts, and delivers those facts directly into the Excel models that equity analysts already use.

**One line:** *The only place JSE company data exists as clean, verified, source-linked numbers — delivered straight into the models analysts already work in.*

### The problem

An equity analyst covering South African companies spends two to three days initiating coverage on a new name, almost entirely on typing numbers out of PDFs. On results day they spend the first two hours of the most time-sensitive morning of the quarter re-typing actuals into a model instead of forming a view. Their historicals are unverified, occasionally wrong, and silently rot when companies restate.

No vendor solves this for the JSE. Global providers (Bloomberg, Capital IQ, Daloopa) cover South African issuers thinly or not at all, because the market is too small to justify their cost structure and because — unlike the SEC's EDGAR — South Africa has no free machine-readable filing repository to build on.

### Why it hasn't been built

CIPC mandated iXBRL for annual financial statements in 2018, but those filings are not published — access requires a per-entity request, and they are statutory legal-entity accounts rather than the group consolidations analysts model. There is no shortcut. The extraction layer has to be built from PDFs, which is exactly why the position is defensible once built.

---

## 2. Market and buyer

**Primary buyer (MVP):** South African buy-side equity analysts and their teams — asset managers and hedge funds with domestic equity mandates. Realistically 30–40 firms.

**Why buy-side first:** they cover more names per analyst than sell-side, so breadth of coverage is their acute pain; they buy without procurement cycles; and they carry no FSCA research publication obligations, which removes a compliance surface from the MVP.

**Deferred buyers:** sell-side research (larger prize, slower sale — displaces existing offshore spreading desks), corporate finance and PE, IR teams.

**Pricing anchor:** not "what does software cost" but what the firm currently spends on the associate hours or offshore desk doing this by hand.

**Honest ceiling:** the SA institutional buy-side is a small pool. The MVP proves the product; expansion into sell-side, corporates, and eventually other African exchanges needs to be a live plan before any raise, not a discovery afterwards.

---

## 3. MVP scope

The discipline of this document is in what it excludes. The full product described in planning has ~32 modules. The MVP has 6.

### In scope

| # | Capability |
|---|---|
| 1 | Verified fact database — 12 companies, 10 years |
| 2 | Extraction pipeline with human verification |
| 3 | Excel add-in: fact sync (facts sheet + live references) |
| 4 | Excel add-in: existing-model import and diagnostic |
| 5 | Provenance viewer (as-reported / standardized / source PDF) |
| 6 | Results-day pipeline and breach alerting |

### Explicitly out of scope for MVP

Valuation engine, DCF, reverse DCF, comps · AI model review layer · report drafting and chart generation · guidance tracking · macro linkage (SARB/StatsSA) · full-text corpus search · on-demand extraction of arbitrary uploaded documents · screening · team and sharing features · price data of any kind · insurers · banks (phase 2) · mobile · any JSE-licensed data

### Coverage universe (MVP)

**12 companies, retail and consumer**, chosen because they are the cleanest reporters on the JSE, several publish Excel databooks alongside results, and one sector fully covered serves a real analyst's entire mandate — which a scattered 40-name partial coverage does not.

Target list: Shoprite, Pick n Pay, Boxer, Spar, Woolworths, Mr Price, Truworths, Foschini (TFG), Clicks, Dis-Chem, Pepkor, AVI.

Boxer (majority-owned by Pick n Pay, JSE-listed November 2024) replaces
Bidcorp. Bidcorp is a global foodservice distributor with most earnings
offshore — the weakest fit for an SA-consumer product and the most
expensive to extract. AVI, an SA consumer staples business held and
covered by consumer-mandate funds, stays: dropping it would send those
analysts back to their existing process for a name they care about,
undermining the case for depth over breadth that this coverage list
exists to make. See `docs/jse_coverage_universe.md` for the verified
company directory (JSE codes, fiscal year ends, sourcing) backing this
list.

**History depth:** 10 financial years, both interim and final reporting
periods — except Boxer, only JSE-listed since November 2024, whose
publicly available financial history goes back three years (52-week
periods ended February 2022–2024, per its pre-listing statement), not ten.

**Estimated fact volume:** ~170,000 verified facts — 11 companies × 10
years × 2 filings × ~750 facts (165,000), plus Boxer at 3 years × 2
filings × ~750 facts (4,500).

Banks follow immediately after MVP. The schema must accommodate them from day one; the coverage does not.

---

## 4. Core user journeys

### Journey A — Connect an existing model (primary)

The highest-value journey and the one that closes deals. Most target users already have models.

1. Analyst installs the add-in, points it at an existing workbook.
2. Valora reads the workbook: identifies typed numeric cells, time-series rows, and period columns from headers.
3. **Value-fingerprint matching** — each row of historical values is matched against the fact database by the numbers themselves, not by row labels (labels are idiosyncratic and unreliable). Scale factors and sign conventions are tested automatically.
4. Diagnostic returned: rows matched cleanly; rows matched with discrepancies (transcription errors, missed restatements) each linked to the source page; rows unmatched (the analyst's own derived metrics, left untouched).
5. On approval, Valora adds a **facts sheet** to a copy of the workbook and repoints matched historical cells at it (`252842` becomes `=Facts!C12`).
6. A reversible diff is shown before anything is written. The original file is never modified.

**Never touched:** forecast formulas, model logic, layout, macros, sheet structure.

**Acceptance:** the diagnostic surfaces at least one genuine, verifiable error in a majority of real analyst models tested.

### Journey B — Results morning

1. Company publishes results; IR email alert lands in the Valora inbox.
2. Pipeline ingests, extracts, validates, routes to human verification.
3. Facts published to the store; connected models refresh on next open or on demand.
4. Analyst's own forecast assumptions (parsed from their model) are compared against actuals; breaches surfaced in the dashboard.

**MVP target:** verified and live within **90 minutes** of publication for 90% of filings. (Steady-state target of 40 minutes is a post-MVP optimisation.)

### Journey C — Initiate a new name

1. Analyst selects a covered company.
2. Valora generates a workbook containing: facts sheet (10 years, as-reported and standardized), operating KPI sheet, and mechanical schedules (IFRS 16 roll-forward, deferred tax, share count movements, HEPS bridge).
3. Forecast columns are left to the analyst. No model skeleton is generated in MVP — template generation is post-MVP.

---

## 5. Functional requirements

### 5.1 Entity master

- Company records: name, JSE alpha code, sector, archetype, financial year-end month
- Instrument records: ISIN, share code, class, listing dates
- Corporate action history (manual entry in MVP; 12 companies produce few events)

### 5.2 Document ingestion

- **Primary channel:** IR email alerts routed to a dedicated SES inbox, parsed to extract document links. Replaces polling with push; substantially more reliable than crawling.
- **Fallback:** per-company crawlers, polite rate limiting, loud failure alerting
- **Manual:** direct upload for backfill and gap-filling
- All documents hashed (SHA-256), deduplicated, written to versioned S3 with object lock. Never modified, never deleted.

### 5.3 Extraction pipeline

Stages: ingest → classify (company, doc type, period) → segment (locate the ~15 relevant pages of ~300) → extract → post-process (scale, sign, period alignment) → validate → route → publish.

Extraction sends both the PDF text layer (PyMuPDF) and a rendered page image to the model with a strict JSON schema via tool calling. Cross-checking the two catches a substantial share of errors before validation. A second verification pass over the first pass's output is required — the token cost is negligible relative to the accuracy gain.

### 5.4 Validation

Rules as versioned code with test fixtures, not configuration. MVP rule set:

- Balance sheet balances
- Cash flow ties to balance sheet cash movement
- Revenue less cost of sales equals printed gross profit
- Headline earnings reconciliation foots to printed HEPS
- Segments sum to group totals
- Period-on-period comparatives match prior-period stored facts (see §5.8)
- Units and scale internally consistent within a statement

### 5.5 Human verification

- Review queue UI: extracted value and source page side by side, confirm or correct
- Anything below confidence threshold or failing any rule is routed to review
- Two-person confirmation for facts published during a results window
- Every correction is written back to the golden dataset as a regression case

### 5.6 Taxonomy

One fact model; archetype-specific concept sets layered on top. Retail concepts include like-for-like growth (split volume/price where disclosed), trading space, trading density, store counts by banner, format mix. Bank concepts (NII, NIM, IFRS 9 staging, RWA, capital ratios) must be representable in the schema even though banks are out of MVP coverage.

**As-reported representation is never destroyed.** Both the company's own line-item labels and the standardized mapping persist, and both are visible to the analyst.

### 5.7 Provenance

Every fact carries document ID, page number, and bounding box. **A fact without provenance cannot be published** — this is enforced, not encouraged. The three-pane viewer (as-reported / standardized / source PDF, with click-through highlighting) is the interface that converts sceptical analysts and warrants disproportionate polish.

### 5.8 Bitemporality and restatements

Two time axes: the fiscal period a fact describes, and the period during which Valora believed it. Required for restatement handling, audit defence, and answering "what was known on date X."

**Free reconciliation:** each new filing restates prior periods as comparatives. Diffing those against stored facts audits Valora's own prior extraction *and* detects genuine restatements using the same mechanism. This is a required MVP feature, not an enhancement.

### 5.9 Assumption parsing

Forecast formulas in connected models are parsed into typed assumption objects (growth rates, margins, working capital days, space growth), enabling results-day breach detection.

**Realistic expectation:** 60–70% of assumptions parse cleanly on a typical model. Messier models bury literals inside formulas. Ask the analyst about the remainder; do not over-promise coverage.

### 5.10 Web application (minimal)

Four surfaces only:

1. **Dashboard** — action-shaped feed scoped to the analyst's coverage. Every row states a consequence and offers a verb. Includes an explicit "nothing needs you" section.
2. **Provenance viewer** — three-pane, per §5.7
3. **Results diff** — new concepts, changed definitions, restated periods
4. **Review queue** — internal, for the verification team

No charts, no KPI tiles, no analytics. If the analyst is in the web app instead of Excel, the design has failed.

---

## 6. Data sourcing and legal position

### Sources (all free for MVP)

| Source | Content | Access |
|---|---|---|
| Company IR sites | Annual reports, interim results, presentations, Excel databooks | Direct download, free |
| Company IR email alerts | Push notification of new filings | Free subscription |
| Moneyweb SENS archive | Manual completeness check | Free, read-only |

### Position

Extracting facts from published annual financial statements is standard industry practice and is what every analyst does manually. Facts are not copyrightable. Valora builds a database of figures, not a document library — original PDFs are stored for provenance, never redistributed.

**Not used in MVP:** JSE-licensed market data (prices, live SENS feed, corporate action schedules). None is required for a historical-fundamentals product.

**When prices are needed** (post-MVP, for comps and reverse DCF), the options are: purchase end-of-day only from an existing licensed redistributor for a named 12–40 instrument universe; or reference the client's own Bloomberg/Iress cell so Valora never touches the data. The direct JSE vendor agreement becomes an operating cost paid from revenue, not a pre-launch capital barrier.

**Action item:** a few hours with a South African IP lawyer on the facts-versus-compilation question, documented, before first customer contract.

---

## 7. Technical architecture

### Topology

```
DOCUMENT SOURCES
  SES inbox (IR alerts) ──┐
  Crawler fallback ───────┼──→ [ingest-svc] ──→ S3 (raw, immutable)
  Manual upload ──────────┘         │
                                    ↓
                          Step Functions: extraction workflow
                                    │
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                     ↓
        [classify-svc]      [extract-svc]         [validate-svc]
                                    │
                        confidence + rules pass?
                          no ↓              ↓ yes
                    review queue            │
                    (waitForTaskToken)      │
                          └────→ [publish] ←┘
                                    ↓
                        Aurora Postgres — FACT STORE
                                    ↓
                              [api-svc]
                                    ↓
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                     ↓
        Next.js web app      Excel add-in           Public API
                                    │
                        Aurora Postgres — TENANT STORE
```

### Language split

- **Python** — extraction pipeline, PDF processing, validation rules, derivations. Non-negotiable: the document and LLM tooling ecosystems are Python-first.
- **TypeScript** — API, Next.js web app, Excel add-in (Office.js is JS/TS), auth. Shared types generated from the API schema.

Boundary is the queue and the API. Python services consume from SQS and write to Postgres; they never serve the web app directly.

### Services (AWS)

| Need | Service |
|---|---|
| Documents | S3, versioned, object lock |
| Facts and tenant data | Aurora Postgres Serverless v2 (two databases) |
| Queues and events | SQS + EventBridge |
| Workflow orchestration | Step Functions (`waitForTaskToken` for human review) |
| Services | ECS Fargate |
| Event handlers, SES parsing | Lambda |
| LLM | Bedrock |
| Secrets | Secrets Manager |
| IaC | CDK (TypeScript) |
| CI/CD | GitHub Actions |

**Deliberate exceptions to AWS-only:** WorkOS for SSO/SCIM (institutions require SAML; Cognito is the wrong tool); Vercel for Next.js hosting; Grafana Cloud or Datadog for observability.

**Not used:** Airflow, Dagster, Prefect (batch schedulers, wrong shape for human-in-the-loop workflows); data warehouse, data lake, Spark, time-series DB (volume does not remotely justify them).

### Data model (core)

```sql
companies (id, name, jse_code, sector, archetype, fye_month)
instruments (id, company_id, isin, share_code, class, listed_from, listed_to)

documents (id, company_id, doc_type, fiscal_period, published_at,
           s3_key, sha256, page_count, ingested_at)

concepts (id, code, label, archetype_set, statement, sign_convention, unit_type)
company_line_items (id, company_id, as_reported_label, concept_id, first_seen_doc_id)

facts (
  id, company_id, concept_id,
  period_start, period_end, period_type,      -- FY / H1 / Q3
  basis,                                       -- as_reported | restated
  value numeric, currency, scale,
  document_id, page, bbox,                     -- provenance, NOT NULL
  knowledge_period tstzrange,                  -- bitemporal
  confidence, verified_by, verified_at, extraction_run_id,

  EXCLUDE USING gist (
    company_id WITH =, concept_id WITH =, period_start WITH =,
    period_type WITH =, basis WITH =, knowledge_period WITH &&
  )
)
```

The exclusion constraint makes overlapping fact versions physically impossible at the database level rather than relying on correct application code.

### Two-database separation

The fact store (shared, public-derived) and the tenant store (models, assumptions, coverage) are physically separate with no join path. This makes "we do not pool customer forecasts" a structural fact rather than a policy promise — a material advantage in institutional procurement, since a buy-side firm's forecasts are its alpha.

### Excel add-in specifics

- **Tagging:** facts-sheet pattern, not cell metadata. Stable fact IDs live on Valora's sheet; user cells reference in by formula. Office.js cell metadata support is thin and bloats workbooks.
- **Performance:** `context.sync()` is the bottleneck. All reads and writes batched. This single factor determines whether the add-in feels professional.
- **Deployment:** centralised deployment via Microsoft 365 admin. Manifest and IT documentation required before first pilot.
- **Safety:** always operate on a copy; always present a reversible diff.

### API

REST, versioned from day one. Every client — including Valora's own add-in and web app — uses the same public API with no privileged internal path.

```
GET /v1/facts?companies=SHP,MRP&concepts=revenue,gross_margin
              &periods=FY2020:FY2025&basis=as_reported&as_of=2025-06-30
```

The `as_of` parameter exposes bitemporality and costs nothing once the schema is correct.

---

## 8. Accuracy operating model

Accuracy is a manufacturing process, not a model property. Comparable operators run several hundred verification staff; the equivalent function must exist here at appropriate scale.

1. **Golden dataset** — hand-verified figures, immutable, versioned. Built *before* the pipeline, starting with 3 companies. Every extraction change runs against it in CI, with no deploy override. This is the single most valuable asset in the company.
2. **Validation rules as tested code**, each with known-good and known-bad fixtures.
3. **Comparative reconciliation** — every new filing audits the prior year's extraction for free (§5.8).
4. **Cross-source checks** — where a company publishes an Excel databook, extract both and require agreement.
5. **Per-company confidence drift monitoring** — accuracy degrades silently when a company redesigns its results booklet. Alert on the trend, not the absolute.
6. **One-click error reporting from any cell** — every customer report becomes a golden dataset entry.

### Seasonality

South African reporting concentrates around February/March and August/September. Verification capacity must surge accordingly — contracted CA(SA) or CFA-candidate reviewers on retainer, trained in advance, dormant between peaks. This is a standing operational cost that scales with coverage, not revenue.

### Structural advantage

Valora verifies South African filings with South African accountants who understand headline earnings, IAS 29 hyperinflation treatment, and B-BBEE scheme accounting natively. Global competitors verify foreign filings with remote staff pattern-matching an unfamiliar disclosure regime. Unit economics and quality both favour the local operator.

---

## 9. Definition of done

The MVP ships when all of the following hold:

| Criterion | Target |
|---|---|
| Coverage | 12 retail/consumer companies, 10 years, both reporting periods |
| Accuracy against golden dataset | ≥ 99.0% |
| Facts published without provenance | 0 (enforced) |
| Import diagnostic finds ≥1 genuine error | in ≥ 80% of real models tested |
| Results-day: publication to verified-and-live | ≤ 90 min for ≥ 90% of filings |
| Add-in refresh, full model | < 5 seconds |
| Design partners with ≥1 connected model | 3 |
| Full results season survived | 1 complete cycle |

The last criterion is the real one. Everything before it is preparation.

---

## 10. Timeline

| Phase | Months | Deliverable |
|---|---|---|
| Foundations | 0–1 | Entity master, fact schema, S3 store, 3 companies loaded **by hand**. Golden dataset begun. No pipeline yet. |
| Pipeline | 2–3 | Extraction, validation, review UI, Step Functions workflow. Target: 3 companies fully automated, matching the hand-built golden set. |
| Backfill | 4 | Scale to 12 companies, 10 years. Grind, not invention. |
| Add-in | 5 | Fact sync, facts sheet, model import and diagnostic. |
| Web + partners | 6 | Dashboard, provenance viewer, results diff. Design partners onboarded. |
| Live season | 7–8 | Operate through a full reporting cycle. Fix what breaks. |

Documents for the entire backfill can be downloaded manually in 2–3 days during Phase 1. This is not a blocker and should not be automated first.

**Build order rationale:** the fact schema is the only component where a mistake requires migrating live customer data rather than redeploying a service. It is the one thing worth over-engineering on day one.

---

## 11. Team and budget

### Team (minimum viable)

| Role | Focus |
|---|---|
| Founder | Product, customers, JSE and partner relationships |
| Python engineer | Extraction pipeline, validation, derivations |
| TypeScript engineer | API, web app, Excel add-in |
| CA(SA) | Taxonomy, validation rules, verification, golden dataset |

The CA(SA) is the most commonly skipped hire and the one that determines whether the product is trusted. Validation rules encode accounting knowledge; an engineer guessing at a headline earnings reconciliation will produce rules that are subtly wrong in ways nobody catches for a year.

### Non-headcount running cost

| Item | Monthly (USD) |
|---|---|
| Aurora Serverless v2 | 50–150 |
| ECS Fargate | 100–150 |
| S3, Lambda, Step Functions | < 50 |
| Bedrock / LLM | 100–500 |
| Vercel | 20–150 |
| WorkOS | 125+ |
| Observability | 100–300 |
| **Total** | **~1,000–1,500** |

Infrastructure is not a material cost. Verification headcount is. LLM spend should not be optimised — full backfill extraction is roughly 12,000 pages, a few hundred dollars total, and running a second verification pass is worth far more than the tokens saved.

---

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Taxonomy requires rework once banks are added | High | Design bank concept sets into the schema during MVP even though banks aren't covered |
| Verification capacity insufficient at season peak | High | Contracted reviewers retained and trained before first peak |
| Add-in damages a customer model | Critical | Always operate on a copy; reversible diff; extensive testing. One incident spreads across the entire Sandton buy-side. |
| Confusion between verified and unverified data | Critical | Post-MVP on-demand extraction must be visually and structurally distinct. Blurring the two destroys the trust the verified set earns. |
| Market ceiling (~30–40 buyers) | Medium | Expansion path (sell-side, corporates, other exchanges) planned before any raise |
| Key person dependency on the CA(SA) | Medium | Validation rules documented as code with fixtures, not held as tacit knowledge |
| Customer forecast data governance | Critical | Two-database separation; contractual position that customer assumptions are never used to improve shared models — written before the feature is built |

---

## 13. Deferred roadmap

**Phase 2 (post-MVP):** banks coverage · valuation engine (DCF, reverse DCF, comps) · AI model review layer · assumption sync (bidirectional) · guidance tracking · macro linkage · full-text corpus search · on-demand extraction of arbitrary documents · model template generation and house-format learning

**Phase 3:** report drafting with linked numbers and chart generation · team and sharing · MCP/LLM-accessible data layer

**Conditional:** price data (once revenue supports licensing) · insurers (once IFRS 17 comparatives stabilise) · additional African exchanges

**Never:** consensus estimates · real-time market data · generating the investment thesis or recommendation

---

## 14. Principles

Five rules that resolve most design arguments:

1. **Excel is the model; Valora is the data.** Never try to replace the spreadsheet.
2. **No fact without provenance.** Enforced in the schema, not by convention.
3. **As-reported is never destroyed.** Analysts will disagree with the standardization and need the escape hatch.
4. **Automate the typing, never the judgment.** A model the analyst didn't build is a model they have to check — which converts creative work into checking work and makes the job worse while appearing faster.
5. **The golden dataset is the company.** Extraction code can be rewritten in a month. Verified, provenance-linked history cannot be bought.
