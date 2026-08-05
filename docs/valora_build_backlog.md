# Valora — Build Backlog

**Granular task breakdown, sequenced.**
Every task has a *done when* condition. If you can't verify it, it's too big and needs splitting.

**Sizing:** `XS` <2h · `S` half day · `M` 1 day · `L` 2–3 days

**Rule:** do not start a milestone until the previous one's done-conditions all pass. The ordering is not arbitrary — later milestones assume earlier ones are stable.

---

## M0 — Environment (3 days)

| # | Task | Done when | Size |
|---|---|---|---|
| 0.1 | `git init`, monorepo folder structure, `.gitignore` | Folders exist per architecture doc; nothing tracked that shouldn't be | XS |
| 0.2 | pnpm workspace config (`pnpm-workspace.yaml`) | `pnpm install` from root resolves all TS packages | XS |
| 0.3 | Turborepo config, `turbo.json` | `pnpm turbo build` runs (even if it builds nothing) | XS |
| 0.4 | Python service scaffold under `services/pipeline` with `uv` | `uv run python -c "print('ok')"` works | XS |
| 0.5 | `docker-compose.yml` — Postgres 16 | `psql` connects on localhost:5432 | XS |
| 0.6 | Add LocalStack (S3, SQS) to compose | `aws --endpoint-url=http://localhost:4566 s3 ls` responds | S |
| 0.7 | `Makefile` — `dev`, `down`, `test`, `migrate`, `reset` | `make dev` brings the stack up from cold | S |
| 0.8 | `.env.example` + config loader (both languages) | Switching `AWS_ENDPOINT_URL` moves between LocalStack and AWS with no code change | S |
| 0.9 | AWS Budgets: alerts at $50 and $120 | Test email received | XS |
| 0.10 | GitHub Actions skeleton — lint + test jobs | CI runs green on an empty repo | S |
| 0.11 | `README.md` with a cold-start runbook | A stranger could clone and run `make dev` | S |

---

## M1 — Schema (4 days)

| # | Task | Done when | Size |
|---|---|---|---|
| 1.1 | `dbmate` (or equivalent) wired into `make migrate` | Migrations run up and down cleanly | S |
| 1.2 | Migration: `companies` | Table exists; rollback works | XS |
| 1.3 | Migration: `instruments` | FK to companies enforced | XS |
| 1.4 | Migration: `documents` | Unique constraint on `sha256` | XS |
| 1.5 | Migration: `concepts` | Table exists with archetype field | XS |
| 1.6 | Migration: `company_line_items` | FKs to company and concept | XS |
| 1.7 | Migration: `facts` — core columns, provenance NOT NULL | Insert without `document_id` fails | S |
| 1.8 | Migration: `facts` — `knowledge_period tstzrange` + GiST exclusion constraint | Migration applies without error | M |
| 1.9 | **Test: exclusion constraint rejects overlaps** | Two overlapping facts → second insert raises | S |
| 1.10 | Test: `as_of` query returns correct version | Fact revised, historical query returns old value | S |
| 1.11 | Seed script — the 12 companies in `docs/jse_coverage_universe.md` | `SELECT * FROM companies` returns 12 rows matching that list | XS |
| 1.12 | Python DB helper module (connection, basic CRUD) | Unit tests pass against local Postgres | S |
| 1.13 | TS DB helper module | Same | S |

> **1.8 and 1.9 are the most important tasks in this document.** Bitemporality is the only thing that cannot be retrofitted without migrating live customer data. Prove it works before writing anything else.

---

## M2 — One company by hand (7 days, mostly not coding)

| # | Task | Done when | Size |
|---|---|---|---|
| 2.1 | Download Shoprite: 10 annual reports + 10 interims | ~20 PDFs on disk | S |
| 2.2 | Naming convention: `{code}_{type}_{period}_{published}.pdf` | All files renamed consistently | XS |
| 2.3 | Upload to LocalStack S3, record keys | `aws s3 ls` shows all files | XS |
| 2.4 | Hand-entry spreadsheet template (label, value, unit, scale, page) | Template ready | XS |
| 2.5 | Hand-type FY2025 income statement | Every line item captured with page number | M |
| 2.6 | Hand-type FY2025 balance sheet | Same | M |
| 2.7 | Hand-type FY2025 cash flow statement | Same | M |
| 2.8 | Hand-type FY2025 HEPS reconciliation | Every reconciling item captured | M |
| 2.9 | Hand-type FY2025 segment note | Same | M |
| 2.10 | Repeat 2.5–2.9 for FY2024 | Two years complete | L |
| 2.11 | Write taxonomy v0 — the concept list you just discovered | A document listing every concept, its statement, sign convention | M |
| 2.12 | Loader: spreadsheet → `facts` table | Rows land with correct provenance | S |
| 2.13 | Query: Shoprite revenue, all periods. Read the output. | Ten years returned, values correct | XS |

> Do this personally. It is your first golden dataset, your taxonomy source, and the only way to design concepts for documents you've actually read. Everyone wants to skip it.

---

## M3 — Document store (3 days)

| # | Task | Done when | Size |
|---|---|---|---|
| 3.1 | S3 client wrapper (endpoint-configurable) | Same code works against LocalStack and real S3 | S |
| 3.2 | SHA-256 hashing utility | Unit test on known input | XS |
| 3.3 | Ingest function: bytes → hash → S3 → `documents` row | Document retrievable by ID | S |
| 3.4 | Dedupe: re-ingesting identical bytes is a no-op | Second ingest returns existing ID, no duplicate row | S |
| 3.5 | Retrieve function: ID → bytes | Retrieved bytes hash-match the original | XS |
| 3.6 | Backfill all 20 Shoprite PDFs through ingest | 20 `documents` rows, 20 S3 objects | XS |

---

## M4 — Extraction (3 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 4.1 | PyMuPDF: open a PDF, dump one page's text. **Read it yourself.** | You understand what the text layer gives you | XS |
| 4.2 | Render a page to PNG at readable DPI. **Look at it.** | Image is legible | XS |
| 4.3 | LLM client wrapper (provider-swappable) | One call returns a response | S |
| 4.4 | Extraction schema as Pydantic models (line item, value, unit, scale, page, bbox) | Schema validates a hand-written example | M |
| 4.5 | First extraction call: text + image + schema → JSON | Structured output printed | M |
| 4.6 | **Disk cache keyed on `hash(doc, page, prompt_version)`** | Second identical run makes zero API calls | S |
| 4.7 | Comparison script: extraction vs hand-typed facts | Prints match count and mismatches | M |
| 4.8 | Accuracy metric written to a run report | A single percentage you can track over time | S |
| 4.9 | Iterate prompt/schema until income statement matches | ≥95% on FY2025 income statement | L |
| 4.10 | Extend to balance sheet | ≥95% | M |
| 4.11 | Extend to cash flow | ≥95% | M |
| 4.12 | Extend to HEPS reconciliation | ≥95% | M |
| 4.13 | Extend to segment note | ≥95% | M |
| 4.14 | Second verification pass (model checks its own output against the page) | Measurable accuracy improvement over single pass | M |
| 4.15 | Scale/sign normalisation (thousands vs millions, cost signs) | Facts stored in canonical units regardless of source presentation | M |
| 4.16 | Page segmentation: find statement pages automatically | Correct pages found on all 20 Shoprite docs | L |
| 4.17 | Classification: company, doc type, fiscal period from cover pages | Correct on all 20 | M |
| 4.18 | Bounding boxes captured for every extracted value | Every fact has a bbox; spot-check 10 against the page | M |

> 4.6 before 4.9. You will run extraction hundreds of times while iterating and without a cache you re-pay for identical work every run.

---

## M5 — Validation (2 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 5.1 | Rule interface: `(facts) -> RuleResult(passed, message, offending_facts)` | Interface defined, one dummy rule passes | S |
| 5.2 | Fixture format — known-good and known-bad fact sets | Fixtures load in tests | S |
| 5.3 | Rule: balance sheet balances | Passes on good fixture, fails on bad | S |
| 5.4 | Rule: cash flow ties to balance sheet cash movement | Same | M |
| 5.5 | Rule: revenue − cost of sales = printed gross profit | Same | S |
| 5.6 | Rule: HEPS reconciliation foots to printed HEPS | Same | M |
| 5.7 | Rule: segments sum to group totals | Same | M |
| 5.8 | Rule: units and scale internally consistent | Same | S |
| 5.9 | Rule: comparatives match prior-period stored facts | Detects a deliberately corrupted prior fact | M |
| 5.10 | Rule runner — execute all rules, aggregate results | Report lists every rule and outcome | S |
| 5.11 | Routing: pass → publish, fail → review queue | Facts land in the correct state | S |

---

## M6 — Pipeline assembly (1 week)

| # | Task | Done when | Size |
|---|---|---|---|
| 6.1 | Stage interface — pure functions, no orchestrator awareness | Each stage unit-testable in isolation | S |
| 6.2 | Local runner chaining ingest → classify → segment → extract → validate → publish | One command runs a PDF end to end | M |
| 6.3 | Run report: facts extracted, passed, failed, accuracy, cost | Report written to disk per run | M |
| 6.4 | Idempotency: re-running the same document produces no duplicates | Second run is a no-op | M |

---

## M7 — Review UI (2 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 7.1 | Next.js app scaffold under `apps/review` | Runs on localhost | XS |
| 7.2 | Endpoint: list facts awaiting review | Returns queue as JSON | S |
| 7.3 | Endpoint: serve page image with bbox coordinates | Image renders in browser | M |
| 7.4 | UI: fact value and source page side by side, bbox highlighted | You can visually verify a fact in <5 seconds | L |
| 7.5 | Approve action → fact published | State changes in DB | S |
| 7.6 | Correct action → corrected value published | Correction persisted with reviewer ID | S |
| 7.7 | Corrections write back to golden dataset | Corrected fact appears in the regression set | M |
| 7.8 | Queue metrics: depth, age, throughput | Visible on the page | S |
| 7.9 | Keyboard shortcuts for approve/reject | Reviewer can work without a mouse | S |

> 7.9 sounds trivial. It isn't — reviewers will process thousands of facts and mouse-driven review is roughly three times slower.

---

## M8 — Companies two and three (3 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 8.1 | Download and ingest Pick n Pay, 10 years | 20 documents stored | S |
| 8.2 | Run pipeline on PnP. Record every failure. | Failure list documented | M |
| 8.3 | Fix failures one at a time | PnP reaches ≥95% against a hand-verified sample | L |
| 8.4 | `company_line_items` mapping: PnP labels → concepts | Every extracted line item mapped or explicitly unmapped | M |
| 8.5 | Download, ingest and run Mr Price | Same | L |
| 8.6 | MRP mapping | Same | M |
| 8.7 | **Taxonomy v1 — reconcile all three companies' vocabularies** | One concept list serving all three; conflicts resolved and documented | L |
| 8.8 | Re-run all three end to end after taxonomy changes | No regressions; accuracy report for all three | M |
| 8.9 | Add bank concept placeholders to the taxonomy (NII, NIM, IFRS 9 staging, RWA) | Schema demonstrably accommodates them; no coverage required | M |

> 8.7 is the milestone most likely to force redesign. That's why it happens at three companies rather than twelve. Expect discomfort here; it's the system working.

---

## M9 — API (2 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 9.1 | API scaffold (Hono or Fastify) under `services/api` | Health endpoint responds | XS |
| 9.2 | `GET /v1/facts` — companies, concepts, periods, basis | Returns correct facts for a known query | M |
| 9.3 | `as_of` parameter | Historical query returns pre-restatement values | M |
| 9.4 | `GET /v1/companies`, `GET /v1/concepts` | Reference data served | S |
| 9.5 | `GET /v1/documents/{id}/page/{n}` — provenance image | Image served with bbox metadata | M |
| 9.6 | OpenAPI spec generated from route definitions | Spec validates | S |
| 9.7 | TS types generated from spec into `packages/schema` | Web and add-in import shared types | S |
| 9.8 | Auth stub (API key), swappable for WorkOS later | Unauthenticated requests rejected | S |
| 9.9 | **Golden regression as a blocking CI gate** | A deliberate accuracy regression fails the build | M |

---

## M10 — First AWS deploy (2 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 10.1 | CDK bootstrap, staging account/profile | `cdk deploy` works on an empty stack | S |
| 10.2 | S3 stack — versioned bucket, lifecycle rules | Bucket exists, versioning on | S |
| 10.3 | RDS `t4g.micro` (not Aurora yet) | Connectable from your machine | M |
| 10.4 | **Log retention 7 days on every log group** | No group set to never-expire | XS |
| 10.5 | VPC endpoints for S3 and SQS (avoid NAT Gateway) | No NAT Gateway in the account | M |
| 10.6 | ECR repo, image build and push in CI | Image lands in ECR on merge | M |
| 10.7 | Migrate local data to staging DB | Row counts match | S |
| 10.8 | Fargate task definition, event-triggered (not always-on) | Task runs on demand, scales to zero | M |
| 10.9 | Step Functions state machine replacing local runner | Same stages, same code, different caller | L |
| 10.10 | `waitForTaskToken` for human review step | Workflow pauses; approving in UI resumes it | L |
| 10.11 | API to App Runner or Lambda (no ALB) | Public endpoint responds | M |
| 10.12 | Review UI to Vercel, pointed at staging | Reviewers can work against staging | S |
| 10.13 | Smoke test: ingest a document in staging end to end | Facts appear in staging DB | S |
| 10.14 | Cost check against Budgets | Actual spend within forecast | XS |

---

## M11 — Excel add-in (6 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 11.1 | Office.js scaffold, manifest, sideload locally | Task pane opens in Excel | M |
| 11.2 | Task pane shows "connected" with auth | Authenticated call to API succeeds from Excel | M |
| 11.3 | Read active workbook: sheets, used ranges, cell types | Prints structure to console | M |
| 11.4 | Classify cells: typed number vs formula vs text | Correct classification on a test workbook | M |
| 11.5 | Detect time-series rows and period columns from headers | Correct on 3 real analyst models | L |
| 11.6 | Write a facts sheet from API data | Sheet appears with 10 years of history | M |
| 11.7 | **Batch all reads/writes; minimise `context.sync()`** | Full model refresh under 5 seconds | L |
| 11.8 | Fingerprint matcher (backend): value series → concept | Correct match on Shoprite revenue series | L |
| 11.9 | Scale and sign variant testing in matcher | Matches a model in millions against thousands-stored facts | M |
| 11.10 | `POST /v1/match` endpoint | Returns matched / discrepant / unmatched | M |
| 11.11 | Diagnostic UI: three categories, discrepancies linked to source page | Analyst can read and understand it unaided | L |
| 11.12 | Copy-and-diff: never modify the original file | Original untouched; diff previewed before write | L |
| 11.13 | Repoint operation: typed cells → `=Facts!X` references | Model recalculates identically after repointing | L |
| 11.14 | Refresh operation: update facts sheet, model recalculates | New period flows through to all dependents | M |
| 11.15 | Forecast formula parsing → assumption objects | 60–70% of assumptions extracted from a real model | L |
| 11.16 | Manifest for centralised M365 deployment + IT documentation | An IT admin could deploy it | M |

> 11.12 is the highest-risk task in the product. One mangled model spreads across the entire Sandton buy-side. Over-test it.

---

## M12 — Backfill to twelve (6 weeks)

Repeat per company: download → ingest → run → fix failures → map line items → verify sample → sign off.

| # | Company | Notes |
|---|---|---|
| 12.1 | Woolworths | Has Zimbabwe/Australia exposure — watch currency translation |
| 12.2 | Spar | Guild structure affects revenue presentation |
| 12.3 | Truworths | Credit book — partial bank-like disclosure |
| 12.4 | Foschini (TFG) | Multi-territory, credit book |
| 12.5 | Clicks | Clean reporter, expect fast |
| 12.6 | Dis-Chem | Shorter listed history |
| 12.7 | Pepkor | Complex group structure |
| 12.8 | Boxer | Only 3 years of public history (listed Nov 2024) — cannot reach the 10-year depth of the other 11; scope the extraction to what actually exists |
| 12.9 | AVI | Manufacturer, different cost structure |
| 12.10 | Full re-run, all 12, accuracy report | ≥99% against golden set |
| 12.11 | Load test: results-day simulation | Publication → verified in under 90 min |

---

## M13 — Design partners (4 weeks)

| # | Task | Done when | Size |
|---|---|---|---|
| 13.1 | Dashboard: coverage-scoped action feed | Shows results, breaches, restatements, stale models | L |
| 13.2 | Provenance viewer: three-pane with click-through | Any fact traceable to its page in one click | L |
| 13.3 | Results diff view | New/changed/restated concepts listed | M |
| 13.4 | WorkOS SSO replacing the auth stub | SAML login works | M |
| 13.5 | Onboard partner 1, import a real model | ≥1 genuine error found in their model | M |
| 13.6 | Onboard partners 2 and 3 | Same | M |
| 13.7 | Survive one full results season | All 12 companies through a reporting cycle | L |

---

## Cross-cutting, from day one

| Task | Why |
|---|---|
| Every fact carries provenance, enforced by NOT NULL | The trust foundation; unenforceable later |
| Golden dataset grows with every correction | Your regression suite and your moat |
| Extraction cache on disk | Prevents runaway dev-time LLM spend |
| Run reports written for every pipeline execution | You cannot improve accuracy you don't measure |
| Log retention set on every new log group | CloudWatch accumulates silently |

---

## The three tasks that decide the outcome

**1.8 / 1.9** — bitemporal constraint. The only thing that cannot be retrofitted without migrating live customer data.

**8.7** — taxonomy reconciliation across three companies. Do it at three, not twelve. Doing it late means re-mapping everything you've already extracted.

**11.12** — copy-and-diff safety in the add-in. The only task where failure loses you the market rather than a sprint.

Everything else is recoverable.
