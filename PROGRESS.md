# Valora — Progress

Updated as tasks close. Plan of record is `docs/valora_build_backlog.md`.

**Status:** M1 (Schema) complete — M2 (One company by hand) in progress
**Started:** 2026-08-02

---

## Legend

`[ ]` not started · `[~]` in progress · `[x]` done, *done when* condition verified

---

## M0 — Environment

- [x] **Environment prerequisites** — WSL2 Ubuntu 24.04, Docker Desktop with WSL
      integration, Node v24.18.1, pnpm 11.18.0, Python 3.12.3, uv 0.12.1,
      AWS CLI 2.36.14, make 4.3, psql 16 client, gh 2.97.0, git identity set
- [x] **0.1** `git init`, monorepo folder structure, `.gitignore`
- [x] **0.2** pnpm workspace config (`pnpm-workspace.yaml`)
- [x] **0.3** Turborepo config, `turbo.json`
- [x] **0.4** Python service scaffold under `services/pipeline` with `uv`
- [x] **0.5** `docker-compose.yml` — Postgres 17
- [x] **0.6** LocalStack (S3, SQS) added to compose
- [x] **0.7** `Makefile` — `dev`, `down`, `test`, `migrate`, `reset`
- [x] **0.8** `.env.example` + config loader (both languages)
- [x] **0.9** AWS Budgets: alerts at $50 and $120
- [x] **0.10** GitHub Actions skeleton — lint + test jobs
- [x] **0.11** `README.md` with a cold-start runbook

**M0 complete.** All environment tasks (0.1–0.11) done and verified. M1
(schema) can begin.

## M1 — Schema

- [x] **1.1** `dbmate` wired into `make migrate` (+ `migrate-down`, `migrate-new`)
- [x] **1.2** `companies` migration — bigint identity PK, trigger-maintained
      `updated_at` (convention for later tables), `archetype` as `text` + CHECK
      (not enum), `jse_code` case-sensitive UNIQUE
- [x] **1.3** `instruments` migration — FK to `companies` (`ON DELETE
      RESTRICT`), indexed `company_id`, `isin`/`share_code` UNIQUE, `class`
      as `text` + CHECK, `listed_to > listed_from` CHECK, same PK/timestamp/
      trigger conventions as 1.2
- [x] **1.4** `documents` migration — row created at ingest time so hash
      dedupe (M3.4) works before classification; `s3_key`/`sha256`/
      `ingested_at` NOT NULL (pure functions of the raw bytes); `page_count`
      nullable (requires successfully parsing the PDF — a corrupt/truncated/
      encrypted file must still get a durable row); `company_id`/`doc_type`/
      `fiscal_period`/`published_at` nullable until classified; `sha256`
      UNIQUE + 64-hex-char CHECK; `s3_key` UNIQUE; `fiscal_period` is a plain
      label, distinct from facts' future `period_start`/`period_end`/
      `period_type`
- [x] **1.5** `concepts` migration — no concepts seeded (taxonomy comes in
      M2.11); `archetype_set text[]` + CHECK (not a join table — archetype
      isn't a normalized entity elsewhere), GIN-indexed; `code` UNIQUE +
      snake_case format CHECK; `sign_convention` ('natural'/'signed') and
      `unit_type` (6 values) fully documented via column comments;
      `statement` nullable — NULL means notes/operating-KPI, not forced into
      income/balance/cash-flow
- [x] **1.6** `company_line_items` migration — no mappings seeded; explicit
      `mapping_status` ('unreviewed'/'mapped'/'unmapped') with a CHECK tying
      it to `concept_id` nullability, satisfying M8.4's "mapped or
      explicitly unmapped" done-condition; FKs to `companies`/`concepts`/
      `documents` all `ON DELETE RESTRICT`; `first_seen_doc_id` NOT NULL
      (row only exists once extraction discovered the label somewhere);
      **no uniqueness constraint on `as_reported_label`** — the spec's own
      "Total" example (recurs across income statement/balance sheet/every
      segment note) proves `(company_id, as_reported_label)` can't be safely
      unique, and no given column disambiguates it; partial index on
      `mapping_status = 'unreviewed'` for the review queue, plain indexes on
      `company_id`/`concept_id` for taxonomy reconciliation
- [x] **1.7** `facts` migration — core columns, provenance NOT NULL
      (`document_id`/`page`/`bbox`; insert without `document_id` confirmed
      failing); `value` is already canonical (M4.15), `scale` is
      provenance-only and typed `text` (not numeric) so `value * scale` is a
      type error, not a silent 1000x bug; `bbox` is `jsonb`, [0,1]-normalised,
      origin top-left, CHECK-validated shape/ordering; `period_type` limited
      to `FY`/`H1` (no quarterly — JSE, not US); `basis` `as_reported`/
      `restated` coexist as parallel rows for the same period, not versions
      of each other, confirmed correct against 1.8's exclusion-constraint
      spec; `verified_by`/`extraction_run_id` are FK-less `bigint` (no
      users/extraction_runs tables yet) and nullable (hand-typed M2 facts
      have neither); **deliberately no unique constraint** — that is 1.8's
      job; designed so 1.8 (`knowledge_period` + GiST exclusion) is a pure
      addition, confirmed no restructuring needed; single composite index
      `(company_id, concept_id, period_start)` for the `GET /v1/facts`
      query shape, confirmed via `EXPLAIN`; **`line_item_id`** — nullable FK
      to `company_line_items`, `ON DELETE RESTRICT`, added after review
      (deviation from spec §7, recorded in CLAUDE.md) so the exact
      as-reported label survives even as a company's terminology changes
      across its filing history; NULL means a derived fact with no printed
      source line; not indexed (M8.7's remapping lookup is a batch/admin
      path, no data yet to plan against) and deliberately **not** part of
      1.8's exclusion-constraint key
- [x] **1.8** `facts.knowledge_period` + GiST exclusion constraint (new
      migration, does not amend the committed 1.7 file) — `tstzrange`,
      `[lower, upper)` bounds enforced by a CHECK (not just convention),
      unbounded upper = "currently believed", empty/zero-duration ranges
      and unbounded-lower ranges both explicitly rejected; **no column
      default** — a wrong default here would be silently wrong (recorded
      believed-since would not match reality), so every writer must
      compute and supply it; constraint is `DEFERRABLE INITIALLY
      IMMEDIATE` — immediate by default (same debuggability as
      non-deferrable), deferred checking available to a future writer that
      needs it; `btree_gist` enabled (required — GiST has no native
      equality operator class for bigint/text/date); key columns exactly
      per spec §7 — confirmed `period_end` and `line_item_id` both
      correctly excluded, reasoning in the migration; `migrate:down`
      confirmed to fully reverse, including dropping the extension (safe
      now — nothing else depends on it yet); write cost at 180,000 facts
      assessed as acceptable, no optimisation needed. Applies cleanly; no
      overlap test and no data inserted — that is 1.9, deliberately
      separate.
- [x] **1.9** Test: exclusion constraint rejects overlaps —
      `services/pipeline/tests/test_facts_knowledge_period_exclusion.py`,
      11 pytest cases against real Postgres via `psycopg` (new dev
      dependency). Every rejection case asserts the specific
      `psycopg.errors.ExclusionViolation` / SQLSTATE `23P01` (shape
      violations assert `CheckViolation` / `23514` instead) — a loose
      "raises" assertion would still pass with the constraint dropped
      entirely. **Proved this**: manually dropped
      `facts_no_overlapping_knowledge_periods`, reran — the 4 tests
      guarding it failed with "DID NOT RAISE", the other 7 (both-accepted
      cases, shape-check tests, restatement) still passed; restored via
      `make reset && make migrate`, reran — all 11 pass again. Restatement
      case genuinely commits (close old row, insert new, commit) and
      cleans up explicitly rather than relying on rollback, since it's the
      one test that can't just roll back. Every other test uses
      function-scoped rollback-per-test isolation. Confirmed a DB-
      unreachable run produces `1 failed, 10 errors` (exit code 1) with no
      skip logic anywhere in the file — a misconfigured CI database fails
      the job rather than silently going green. CI: added a Postgres 17
      service to the Python job, migrations applied via
      `scripts/dbmate.sh up` directly (not `make migrate`, which also
      triggers a docker-compose-dependent schema dump that would fail
      against a CI service container) — no secrets, no duplicated SQL.
      **For 1.12**: move `psycopg` from `dev` to a real dependency, create
      `valora_pipeline.db` with a `get_connection()` function, and swap
      this test's local `_connect()` for an import of it — a one-line
      change, no rewrite.
- [x] **1.10** Test: `as_of` query returns correct historical version —
      canonical query lives as a database function,
      `facts_as_of(p_as_of timestamptz default now())` (new migration
      `20260805184045_facts_as_of.sql`), not a Python or TypeScript
      constant — the only form both M1.12 (Python) and M9 (TypeScript) can
      call identically, via plain SQL, with zero duplication. A function
      rather than a view because `as_of` is a real parameter; a view would
      force every caller to bolt its own `WHERE knowledge_period @>
      :as_of` on top, reintroducing the exact risk this closes. **M9.3
      MUST call this function rather than reimplement the containment
      check** — stated in the function's own `COMMENT ON FUNCTION` and
      here. 7 pytest cases in
      `services/pipeline/tests/test_facts_as_of.py`: before/after a single
      revision, `as_of` defaulting to now, the exact boundary instant
      (`[t1,t2)`/`[t2,t3)` — asserts the SECOND row per M1.8's bound
      convention), before any knowledge existed (empty, not an error, not
      the earliest value), two successive revisions at four query points,
      and as_reported/restated both current unless basis is filtered.
      Revisions performed via a `_restate_fact` helper — close old window,
      insert new row, same transaction, same order as M1.9's proven
      restatement path (M2.12/M6 will do this same operation). The exact-
      boundary and before-any-knowledge tests fabricate `knowledge_period`
      directly instead, since they test query semantics, not the write
      path. Every assertion checks actual `(value, basis)` tuples, never
      bare row counts. **Proved the boundary test actually catches a
      wrong-boundary bug**: temporarily changed `facts_as_of` to
      inclusive-upper comparison (`upper(knowledge_period) >= p_as_of`
      instead of `@>`) — the exact-boundary test failed, returning BOTH
      rows at the shared instant instead of just the new one; restored via
      `make reset && make migrate`, reran — all 23 pipeline tests (11 from
      1.9 + 7 from 1.10 + 5 pre-existing) pass. No CI changes needed —
      M1.9 already generalised the workflow to apply all migrations and
      run the full `pytest` suite.
- [x] **1.11** Seed script for the 12 MVP companies —
      `scripts/seed-companies.sh` (matching `dump-schema.sh`'s conventions;
      not `db/`, which dbmate treats as its own migration-tracked
      territory), invoked via `make seed`. Values transcribed verbatim from
      `docs/jse_coverage_universe.md`, not restated as a second list and
      not re-derived. Idempotent via `ON CONFLICT (jse_code) DO NOTHING`
      (confirmed: second run is `INSERT 0 0`, still 12 rows) — deliberately
      not `DO UPDATE`, which would silently overwrite a hand correction.
      Not silent either: re-reads every row after seeding and **warns**
      (does not modify) on any field that differs from the coverage doc —
      confirmed live by hand-editing AVI's `fye_month` to 5, reseeding, and
      observing the warning fire while the hand-edited value stayed
      untouched. Verifies exactly 12 rows and every `fye_month` non-null
      and in 1–12 after seeding; confirmed the row-count check fails
      loudly (exit 2) with a 13th row present, and confirmed a
      constraint-violating value (`fye_month=13`) aborts the entire
      multi-row `INSERT` atomically (0 rows land, not 11) rather than
      skipping just the bad row. Sector values seeded despite the coverage
      doc's own lower-confidence caveat — carries no fact-labelling risk
      the way `fye_month` does, so a caveated value is more useful than
      NULL. No instruments seeded. Not run by any migration or test —
      confirmed `make migrate` alone leaves `companies` empty, and
      confirmed nothing under `db/migrations/` or
      `services/pipeline/tests/` references the seed script.
- [x] **1.12** Python DB helper module — `valora_pipeline.db`. Thin on
      purpose: `get_connection()` (reads `DATABASE_URL` via
      `valora_pipeline.config`, never the environment directly),
      `transaction()` (commit-on-success/rollback-on-exception context
      manager; nesting on the same connection raises `RuntimeError`
      immediately rather than silently letting an inner commit break the
      outer block's atomicity — confirmed live), `publish_fact()` (the
      bitemporal write: no current row → open-ended insert; current row
      exists → close at `effective_at` then insert, same cursor/
      transaction), and `get_facts_as_of()` (calls the canonical
      `facts_as_of()` DB function, never a hand-written containment
      query). `psycopg` moved from `dev` to real dependencies — it's
      production code now. `effective_at` is a required parameter, never
      `now()` inside the function — confirmed a value equal to or earlier
      than the current fact's `knowledge_period` lower bound raises
      `ValueError` before any SQL runs, with no partial state left behind
      either way (checked directly). Fact identity is exactly the
      exclusion constraint's key (`company_id`, `concept_id`,
      `period_start`, `period_type`, `basis`) — confirmed `line_item_id`
      changing supersedes rather than adding a third row. Concurrency:
      reasoned through explicitly, not asserted — two racing calls can
      never both succeed with corrupted/duplicated state (the closing
      `UPDATE`'s `rowcount` is checked and raises if a concurrent writer
      already closed the row; a racing double-insert is caught by the
      exclusion constraint), but this function does not retry — the loser
      gets an explicit exception and the caller decides. Both existing
      test files (`test_facts_knowledge_period_exclusion.py`,
      `test_facts_as_of.py`) now import `get_connection` from this module
      instead of a local `_connect()`, exactly as promised in M1.9/M1.10 —
      all 23 pre-existing tests still pass unchanged. 9 new tests in
      `test_db.py`, same rollback-per-test isolation, no skip logic;
      cover first publish, supersession, identity excluding
      `line_item_id`, the earlier/equal-instant rejection with a
      no-partial-state check, `get_facts_as_of` against the real DB
      function, transaction rollback leaving no partial state, transaction
      commit (verified via a second independent connection, not just the
      same session), and the nesting guard. 32 tests total, `ruff`/`mypy
      --strict` clean. Typing: a frozen `Fact` dataclass, not a TypedDict
      or tuple — the values come from constructing typed objects out of
      query results this code controls (not parsing untyped external
      data, which is TypedDict's strength), and named fields keep call
      sites self-documenting for a 19-column row a positional tuple could
      not. **Deliberately left out** (full reasoning in the module
      docstring): CRUD for companies/concepts/documents/instruments/
      company_line_items (no consumer needs it yet — the test suites'
      raw-SQL seed helpers are fixtures, not production call sites);
      connection pooling (M2.12/M3.3 are batch jobs, not a concurrent
      server); automatic retry on a write conflict (a caller policy
      decision, not this module's); filtering beyond `as_of` on the read
      side (no concrete consumer need yet — compose filters directly
      against `facts_as_of()` as designed); async support (nothing in this
      project runs an event loop). Add these in M2/M3 when a real need is
      concrete, rather than guessing at their shape now.
- [x] **1.13** TypeScript DB helper module — `@valora/db`, a new workspace
      package under `packages/`, not inside `services/api`. Justification:
      spec §7 gives TypeScript three consumers of this data — the API, the
      web app, and the Excel add-in — and `services/api` is only one of
      those three; a package sibling to `@valora/config` (which every
      TypeScript workspace already depends on) is reachable by all of them
      the same way. Flagging a real tension rather than deciding it
      silently: spec §7 also states every client, including Valora's own
      add-in, uses the public REST API with "no privileged internal path,"
      which argues the add-in should reach this data over HTTP, not via a
      direct Postgres connection through this package. `services/api`
      needing `@valora/db` directly is true regardless and is sufficient on
      its own to justify the `packages/` location; whether the add-in ever
      imports this package directly or only talks to the API is a decision
      for M11, left open here rather than assumed.
      **Explicitly not a mirror of `valora_pipeline.db`** — no
      `publishFact`, no bitemporal write path of any kind. A second
      implementation of that write logic, in a second language, called by
      nothing today, is exactly the liability M1.8/M1.9 exist to prevent:
      it would eventually get called, and then the boundary-safety
      guarantee has two versions that can diverge. Reads only:
      `getFactsAsOf(client, asOf?)` (calls the canonical `facts_as_of()` DB
      function, never a hand-written `knowledge_period` containment query —
      the specific risk that function was built in M1.10 to prevent),
      `getCompanies`, `getConcepts` (reference data for M9.4's
      `GET /v1/companies` / `GET /v1/concepts`). `createClient()` reads
      `DATABASE_URL` via `@valora/config`'s `getConfig()`, never
      `process.env` directly — same single-source-of-truth rule as the
      Python side. Types: hand-written interfaces (`Fact`, `Company`,
      `Concept`), kept in sync with `db/migrations` by hand, same discipline
      as `valora_pipeline.db`'s dataclass. M9.7 (not yet built) will
      generate shared types from the API's OpenAPI spec — a different,
      later layer (the API's public JSON contract), not a replacement for
      these internal DB-row types; no code generator was built here, since
      that is explicitly M9.7's job. Two type-parsing bugs caught live
      before they reached the module: `pg`'s default `DATE` parser
      (OID 1082) converts to a JS `Date` via local-midnight-then-UTC,
      silently shifting the calendar date backward depending on server
      timezone — confirmed with a throwaway query
      (`'2024-07-01'::date` → `2024-06-30T22:00:00.000Z`) before fixing it
      with a custom type parser that returns the raw string unchanged;
      `bigint`/`numeric` columns confirmed live to arrive as strings, not
      numbers — `value` is deliberately kept as a string end-to-end
      (floating-point could silently corrupt a verified financial value)
      while `id`/`company_id`/etc. are converted with `Number()` since IDs
      are safe at that magnitude. 6 tests against local Postgres, same
      rollback-per-test isolation and no-skip rule as the Python suite.
      One is a deliberate line-for-line port of
      `test_as_of_at_exact_boundary_instant_returns_second_row` from
      `test_facts_as_of.py` — same `t1`/`t2`/`t3` shape, same assertion
      that querying exactly at the shared boundary instant returns the
      second (not first) row. That cross-language agreement is the actual
      point: confirmed TypeScript and Python resolve the `[lower, upper)`
      boundary identically, rather than each merely testing itself. Also
      covers a revision (value before/after/current), before-any-knowledge
      returning no rows, `value` arriving as a string, and shape checks on
      `getCompanies`/`getConcepts`. Caught one bug in the test suite itself
      during verification: an early version of the `getCompanies` test
      asserted on M1.11's seeded reference data, which passed locally by
      accident (dev DB was already seeded) but would have failed in CI,
      which only runs migrations, never `make seed`. Caught by bypassing
      Turborepo's task cache (`pnpm turbo test` had silently replayed a
      stale cached pass against a since-reset database) and invoking
      `node --test` directly against a freshly migrated, unseeded database;
      fixed by making the test insert and assert on its own fixture row,
      matching every other test in the file. CI: added a `postgres:17`
      `services:` block to the `typescript` job, identical shape to the
      `python` job's (M1.9), plus the same `DATABASE_URL`/AWS env vars
      `@valora/config` requires, plus an `Apply migrations` step running
      `./scripts/dbmate.sh up` — the existing wrapper, not duplicated SQL —
      before `lint`/`test`. Runtime impact: one additional service
      container plus its health-check wait and one migration-apply step per
      CI run, the same magnitude already accepted for the `python` job in
      M1.9. **Deliberately left out** (reasoning above and in the module's
      own docstring): any write path (`publishFact` or otherwise); a code
      generator for types (M9.7's job); connection pooling, retry policy,
      or CRUD beyond the three read functions (no concrete consumer needs
      them yet — add in M9 when the API is the one calling this module).
      **Post-review fix:** first CI run failed while local `make test` had
      reported a pass — two Turborepo configuration bugs, not a bug in the
      module or tests. (1) Turbo runs tasks in a filtered environment; none
      of the five `@valora/config`-required env vars were declared in
      `turbo.json`, so CI's task saw them as missing even though the step
      set them — invisible locally only because a `.env` file papered over
      it. Fixed by declaring them under `env` (not `passThroughEnv`, since
      the latter forwards without hashing — a changed `DATABASE_URL` must
      invalidate the cache, not be silently ignored; confirmed live). (2)
      More seriously, turbo had cached `@valora/db`'s test results — a
      cache key derived from file contents cannot observe external
      Postgres state, so a stale pass replayed locally
      ("cache hit, replaying logs", six green) while CI executed the real
      tests and failed. A cached false-positive on the suite carrying the
      cross-language bitemporal boundary check is worse than no test at
      all. Fixed with a `@valora/db#test` override setting `cache: false`
      — this task always executes for real. `@valora/config`'s tests stay
      cacheable (no external dependency). Reproduced both failure modes
      live before fixing (removed `.env`, confirmed a stale cache hit
      despite missing env; `pnpm turbo test --force` reproduced the actual
      CI failure) and reproduced the fix live after (env change forces
      re-run; `@valora/db#test` never cache-hits across two consecutive
      runs; full `make test` green). Same reasoning flagged for M9: once
      `services/api` has tests hitting a real database, it needs the same
      `cache: false` override — the blanket `test` task's caching is not
      safe to assume for it. Recorded as a permanent decision in
      CLAUDE.md, not just a fix, since it is exactly the kind of thing a
      future "turbo.json cleanup" could silently reintroduce.

## M1 complete. All 13 tasks done. `facts` carries a NOT-NULL provenance
chain and a GiST-enforced bitemporal boundary that Python, SQL, and
TypeScript all agree on at the exact instant it matters.

## M2 — One company by hand

- [~] **2.1** Download Shoprite: 10 annual reports + 10 interims. PARTIAL.
      Ten annual documents covering FY2016–FY2025 downloaded to
      `data/pdfs/` (gitignored) — confirmed as eleven files by M2.2 (one
      duplicate rendering of FY2025; see below). Interim results NOT yet
      downloaded — 10 outstanding. FY2026 does not exist yet (year ends
      late June 2026, published ~October). Document type is NOT consistent
      across the ten years, which is a finding rather than an
      inconvenience: FY2016 is an integrated report (financial statements
      are a ~17-page section within a 78-page document); FY2017–FY2025 are
      all standalone annual financial statements. **Correction from M2.2's
      by-hand inspection:** the FY2021 vendor filename says "iafs"
      (integrated annual financial statements), but the document's own
      text never uses that term and is structurally identical to every
      other standalone-AFS year — the filename was not reliable evidence,
      exactly the risk this task flagged in advance. Relevant to M4.16
      (page segmentation) and M4.17 (classification).
- [x] **2.2** Naming convention. All ten fiscal-year documents renamed to
      `{code}_{type}_{period}_{published}.pdf`
      (e.g. `SHP_AFS_FY2025_20251001.pdf`) in `data/pdfs/` (gitignored;
      renames invisible to git). Every field — company, document type,
      fiscal period, publication date — read from each PDF's own text via
      PyMuPDF (`pymupdf`, added to `services/pipeline`'s `dev` dependency
      group only, not the extraction pipeline proper), never inferred from
      the original vendor filename. Full manifest with the evidence quote
      and page reference for every field:
      `docs/shoprite_pdf_manifest.md`. Two findings surfaced by opening
      the documents rather than trusting filenames: (1) the FY2021 "iafs"
      filename contradicts the document's own self-description (see 2.1);
      (2) **eleven files were present for ten fiscal years** — a second
      FY2025 copy (`Shoprite Holdings - Annual Financial Statements
      2025.pdf`, 79 pages) is the same report, same fiscal period, same
      1 October 2025 authorisation date as the renamed 156-page
      `SHP_AFS_FY2025_20251001.pdf`, just a different PDF rendering (each
      printed spread as one page vs. two — confirmed by comparing
      page-numbered content, not by filename or checksum, since checksums
      differ). Left unrenamed rather than deleted, per instruction not to
      take destructive action on a file without explicit confirmation.
      FY2020 and FY2021 both show an unusually late (~30 September, not
      the ~20 August of surrounding years) board-approval date — flagged
      as observed evidence, plausibly a COVID-era audit delay, not
      confirmed from the documents themselves. No field on any of the ten
      fiscal-year documents was unclassifiable.
- [x] **2.3** Upload to LocalStack S3, record keys.
      `services/pipeline/scripts/upload_documents.py`, invoked via
      `make upload-documents` — a new, separate Makefile target, deliberately
      NOT wired into `make dev`. Same precedent as `make seed`: bringing up
      healthy containers and populating them with data are different
      concerns, and `make seed`'s own target is already separate from `dev`
      for that reason. Repeatable, not one-off: LocalStack sets no
      `PERSISTENCE` flag (CLAUDE.md's local-ports table), so its state does
      not survive `make reset` — confirmed live by running `make reset`
      (which also destroys Postgres, so `make seed` was re-run too), then
      `make upload-documents`, which recreated the bucket from an empty
      LocalStack and restored all 11 objects. Bucket name (`S3_BUCKET`) read
      through `valora_pipeline.config.get_settings()`, never
      `os.environ` directly, matching M0.8's single-source-of-truth rule.
      `boto3` added to `services/pipeline` as a REAL dependency (not dev) —
      unlike M2.2's PyMuPDF, M3.3's ingest function will need a real S3
      client too, so this is not a throwaway tool; `boto3-stubs[s3]` added
      to `dev` for `mypy --strict` cleanliness (repo convention). Bucket
      versioning: enabled, confirmed live via `get_bucket_versioning`.
      Object lock: requested at creation
      (`ObjectLockEnabledForBucket=True`); **confirmed live that LocalStack
      community 3.8 (the pinned version) accepts the object-lock API and
      returns correct-looking retention metadata on read, but does not
      enforce it** — a `delete_object` against a key under active
      `GOVERNANCE` retention succeeded, when real S3 would have refused it.
      Stated plainly rather than assumed; real AWS (M10.2) enforces it for
      real. One S3-semantics surprise found and fixed by testing, not
      assumed: a bucket created with object lock is versioned implicitly,
      and S3 **rejects** an explicit `PutBucketVersioning` call afterward
      (`InvalidBucketState`) — confirmed live on the first run, which
      crashed; fixed by checking current versioning status first and only
      calling `PutBucketVersioning` when not already enabled.
      **Key scheme: content-addressed, `documents/{sha256}.pdf`.** M3.3
      defines ingest as bytes → sha256 → S3 → `documents` row, which means
      M3.3 independently computes the same sha256 from the same bytes and
      needs a key to store it under — using that hash as the key now means
      M3.3 derives the byte-identical key this script already used, not
      merely a compatible one. No filename embedded in the key:
      `documents.s3_key` and `documents.sha256` are two separately-unique
      columns in the schema (confirmed via `\d documents`), so the key
      itself does not need to carry human-readable identity. **M3.3 needs
      no migration of what this task uploaded.** All 11 files in
      `data/pdfs/` uploaded, including the FY2025 duplicate rendering
      flagged in M2.2 — retained deliberately as the only real fixture for
      the case M3.4's SHA-256 dedupe cannot catch (same report, two
      renderings, two different hashes), not an oversight; recorded as such
      in `docs/shoprite_pdf_manifest.md`. Keys and SHA-256 hashes for all 11
      files recorded in that manifest (extended, not replaced, since it
      already maps filename → document identity from M2.2).
      **Idempotent, verified three ways:** (1) re-running immediately is a
      clean no-op, exit 0, same 11 keys, new object version stacked under
      versioning rather than a duplicate object; (2) re-running after a full
      `make reset` restores all 11 objects from a genuinely empty bucket;
      (3) a key deliberately corrupted with different-length content causes
      a hard failure (`exit 2`) rather than a silent overwrite — the
      conflict check compares object size, not ETag, after a false-positive
      was caught live: `boto3.upload_file`'s multipart threshold (8 MiB)
      makes the S3 ETag `md5-of-part-md5s-N` rather than a plain MD5 above
      that size, which an earlier version of this check compared directly
      against a locally-computed MD5 and wrongly flagged the ~9 MB FY2022
      file as conflicting on ordinary re-upload. **Did not build:** the
      `documents` table row, any hashing inside the pipeline's ingest path,
      or any pipeline code — all reserved for M3.3, per instruction.
      `aws s3 ls s3://valora-documents-dev/documents/` confirmed showing
      all 11 files (backlog's done-when condition). `ruff`/`mypy --strict`
      clean on the new script; all 32 existing pytest tests still pass.
- [x] **2.4** Hand-entry template.
      `data/golden/shoprite_SHP_FY2025_hand_entry.xlsx`. Columns:
      `statement`, `note_ref`, `as_reported_label` (verbatim), `period`,
      `basis`, `value_as_printed`, `scale`, `unit`, `currency`, `page`,
      `verified`, `concept_suggestion`, `notes`. Values captured as
      printed with scale recorded separately; the M2.12 loader converts to
      canonical units rather than the template pre-converting.
- [x] **2.5–2.9** Shoprite FY2025 — income statement, balance sheet, cash
      flow, HEPS reconciliation (note 36), segment note (note 2.1).
      Source: Annual Financial Statements 2025, 52 weeks ended 29 June
      2025, authorised 1 October 2025. Verified against the source
      document. 12 validation checks pass, including balance sheet
      balances, gross profit, revenue components, cash flow ties,
      segments-plus-reconciling equals consolidated, and HEPS foots.
- [x] **2.10** Shoprite FY2024, from its own annual financial statements
      (`shp-afs-2024-print.pdf`, 152pp, year ended 30 June 2024) rather
      than from the FY2025 comparatives.
      `data/golden/shoprite_SHP_FY2024_hand_entry.xlsx`. Page numbers
      pre-filled from the PDF: income statement p21, balance sheet p20,
      cash flows p23, segments p50, HEPS p90–91 (PDF page indices, not
      printed page numbers — they differ). 12 checks pass. Includes a
      `Bitemporal_Pair` sheet holding 18 line items in both versions, and
      a `Structural_Changes` sheet cataloguing 10 differences between the
      FY2024 and FY2025 documents.
- [x] **2.11** Taxonomy v0 — `docs/taxonomy_v0.md`. A document, not a
      seed script: nothing here has been written to the `concepts` table —
      that is M2.12's job. 192 non-segment concepts (§3.1 income statement,
      §3.2 balance sheet, §3.3 cash flow, §3.4 HEPS reconciliation note 36)
      plus 7 segment-note concepts (§3.5), every one traceable to a line
      that actually appears in the FY2024 or FY2025 golden workbook — no
      concept imported from general accounting knowledge. Completeness
      check run programmatically, not eyeballed: every distinct
      `(statement, as_reported_label)` pair across both workbooks'
      `IncomeStatement`/`BalanceSheet`/`CashFlow`/`HEPS` sheets (205 pairs)
      exact-string-matches a row in the taxonomy document; the two
      bitemporal fixture sheets' 18 genuinely-fixture-only pairs and the
      segment sheet's 61 pairs (collapsing to 7 concepts) accounted for
      separately. 0 mismatches, 0 unmapped, 0 unnoticed — full arithmetic
      284 = 205 + 61 + 18 confirmed live. Caught and fixed one of my own
      errors during this verification: an early draft's completeness count
      (151, made by hand while drafting) undercounted the HEPS
      reconciliation table specifically; rerunning the check
      programmatically after §3 was complete found the real number, 205,
      and every subsequent count in the document was corrected to match
      before this was reported done. The six questions the task posed are
      resolved in §2, each with the decision, the reasoning, and what
      would change it — not just an answer. Closes the `PROGRESS.md` open
      question "Unlabelled subtotals ... Decide in M2.11": resolved as
      scope-per-concept (§2b) plus the existing `[unlabelled subtotal]
      ...` bracketed-label convention already used in the FY2024 golden
      workbook (§2c) — no new column on `company_line_items`, no scope
      qualifier on `facts`. §5 states which concepts are expected to
      generalise to banks (most of §3.1–3.2: cash, receivables/payables,
      PP&E, tax, leases, equity structure, EPS/HEPS mechanics — anything
      not retail-specific in its own wording) versus retail-only
      (`revenue`, `cost_of_sales`, `trading_profit`, the segment note, the
      capex expand/maintain split), without inventing any bank-specific
      concept — that stays M8.9's job. §6 names six decisions expected to
      be tested at M8.7 (the `revenue`/`revenue_total` split; company-
      defined-measure marking with no schema flag; the sign-flip HEPS
      adjustment lines kept as label-pairs rather than collapsed to one
      signed concept; segment scope via `company_line_items` labels;
      under-modelled hyperinflation; and the 192-concept count itself
      scaling with company count) with the reasoning for each so a future
      disagreement from Pick n Pay's actual AFS can be judged against a
      recorded decision, not reconstructed after the fact.
- [x] **2.12** Loader, golden spreadsheets → `facts`. Backlog condition
      ("rows land with correct provenance") verified live: 634 facts
      loaded from both Shoprite golden workbooks, every one carrying a
      real `document_id` (one of two real `documents` rows, sha256/s3_key
      from `docs/shoprite_pdf_manifest.md`, not placeholders), a real
      `page`, and a `bbox` that is either PyMuPDF-located against the
      actual PDF (430/634, 68%) or an honestly-recorded whole-page
      fallback (204/634, 32% — see "Bounding boxes" below; the schema's
      own `bbox` CHECK constraint would reject anything not shaped
      `{x0,y0,x1,y1}` normalised `[0,1]`, so every fallback is a real,
      valid, queryable box, not a null or a lie).

      **BLOCKING ISSUE resolved before building, per instruction: segments
      have nowhere to go.** `facts`' uniqueness (M1.8's exclusion-
      constraint key: `company_id, concept_id, period_start, period_type,
      basis`) allows exactly one current fact per concept per
      company/period/basis. Taxonomy v0's original design gave all
      6–7 values of one segment metric (e.g. `segment_trading_profit`) a
      SINGLE shared concept, with segment identity carried only in
      `company_line_items.as_reported_label`'s `Metric :: Segment`
      compound string — consistent with §2(b)'s general "scope lives in
      concepts/labels, not a `facts` column" principle, but wrong for
      this specific axis: loading 6 segment values under one concept
      would not create 6 coexisting facts, each `publish_fact` call after
      the first would silently supersede the previous one (a real
      "current" row genuinely exists to close every time — no error
      raised). **Decision: encode the segment into the concept code**
      (`segment_trading_profit_supermarkets_rsa`,
      `segment_trading_profit_consolidated`, etc.) — 49 concept codes (7
      metrics × 7 distinct segment values across the two years) instead
      of 7. `concepts` is the cheap table (CLAUDE.md), so this is exactly
      where the cost of a scope axis that must coexist as simultaneous
      facts should land — not a `facts` column, and not deferred (61 of
      634 facts, ~10% of the dataset, would have been silently missing
      with no record it was a deliberate exclusion, which is not a
      decision to make without asking). `docs/taxonomy_v0.md` §2(b) and
      §3.5 both updated to match, with the reasoning for the change and
      an explicit note on why the original mechanism doesn't generalise
      to this axis — not silently corrected, the prior reasoning is left
      visible with a correction note per the same discipline as every
      other decision in that document.

      **Prerequisite 1 — concepts.** `services/pipeline/scripts/
      seed_concepts.py`, `make seed-concepts`. Follows
      `scripts/seed-companies.sh`'s conventions exactly: idempotent
      (`ON CONFLICT (code) DO NOTHING`), warns rather than overwrites on
      divergence, not part of any migration. Does NOT restate the concept
      list — parses `docs/taxonomy_v0.md`'s own `§3.1`–`§3.5` markdown
      tables at runtime via the same row-regex verified during M2.11's
      completeness check, so the document remains the single source of
      truth. 241 concepts seeded (192 non-segment + 49 segment), 0
      divergence from the document on the confirmed idempotent re-run.

      **Prerequisite 2 — documents.** Two rows created directly from
      `docs/shoprite_pdf_manifest.md`'s recorded sha256/s3_key — real
      values, not placeholders (confirmed: both match the manifest table
      exactly). This is data, not M3.3's ingest function; no ingest code
      touched. **What M3.4's dedupe will do when it later meets these
      rows:** M3.4 is keyed on `documents.sha256`, computed from raw
      bytes. When M3.3's real ingest function processes these same two
      PDFs during a future backfill run, it computes the identical sha256
      from the identical bytes, looks it up via the existing unique
      constraint on `documents.sha256`, finds these exact rows already
      present, and — per M3.4's own "second ingest returns existing ID,
      no duplicate row" condition — treats them as already-ingested. No
      special-casing needed in M3.3 for facts M2.12 already loaded.

      **Prerequisite 3 — company_line_items.** 266 rows, one per distinct
      `(company_id, as_reported_label, concept_id)` triple actually
      present across both workbooks (matches M2.11's own 205 core + 61
      segment completeness-check total exactly). Keyed on the triple, not
      just `(company_id, as_reported_label)` — that pair is documented as
      NOT unique (M1.6: the same printed label can legitimately mean two
      different concepts in two different statements/notes), and one real
      case exists in this dataset ("Current assets" — confirmed resolved
      to the single canonical `total_current_assets_incl_hfs`, not the
      stray `total_current_assets` suggestion one workbook's
      `concept_suggestion` column carried). All 266 rows
      `mapping_status = 'mapped'` — taxonomy v0's own completeness check
      already established 0 unmapped labels exist in this dataset, so no
      `unmapped` branch was exercised. `first_seen_doc_id` is the document
      the label was actually first encountered in during the load (FY2024
      workbook processed before FY2025, so a label appearing in both is
      attributed to the FY2024 document).

      **Bounding boxes — located for real, not guessed.** PyMuPDF
      `page.get_text("dict")` word/line/span geometry, not a rendered-
      image OCR pass. Disambiguation, in order: (1) exact-line match
      against the printed label; (2) for the same visual row (same
      y-coordinate ±2pt), every numeric span checked against the target
      printed value; (3) if exactly one (label-row, value) pair survives
      across all candidate pages, that span's bbox is used, normalised to
      the schema's documented `[0,1]`-origin-top-left convention.
      **Three distinct PDF-rendering quirks found and fixed live, not
      assumed, before accepting the fallback rate as final:**
      (a) a footnote reference digit glued directly to a row label with
      no separating space (e.g. `"Trading profit/(loss)6"`) never equals
      the workbook's clean label — stripped before comparison, along with
      a trailing `"(note N[, note M])"` cross-reference clause found on
      most HEPS reconciliation rows; (b) a long row label wraps across
      two separate PDF line objects (e.g. `"Interest revenue included
      in"` / `"trading profit"`), with the row's numeric values sitting
      at the WRAPPED remainder's y-position, not the first line's —
      handled by shrinking the search string to progressively shorter
      word-suffixes (floor: 2 words, to bound the risk of a common short
      word over-matching elsewhere on the page) until a line match is
      found; (c) the workbook's own compound labels
      (`Metric :: Segment`, `Heading: sub-item`, `Label [gross/tax
      effect/net]`) are never printed verbatim — the PDF prints the
      metric/sub-item/label as its own row and the segment/column as a
      header, not inline — reduced to the actually-printed leaf text
      before searching, confirmed against the real PDF layout for every
      pattern before coding it, not assumed from the workbook's own
      column-naming convention. **HEPS gross/tax/net columns specifically
      cannot be disambiguated by value alone** (confirmed live: the same
      figure legitimately repeats across the gross and net columns of one
      row when the tax effect is nil, e.g. "Profit on disposal of assets
      classified as held for sale" FY2025: gross=-45, tax=0, net=-45) —
      resolved by column x-position instead (confirmed against the
      printed "Gross | Income tax effect | Net" header order on both
      years' note 36 pages), with the target value still used to pick the
      correct ROW when the same label legitimately appears twice on one
      page (current year vs. prior-year restated comparative, printed as
      two separate blocks on the same page). **Spot-checked 5 facts**
      (random sample, both documents, a mix of income statement, balance
      sheet, cash flow, and segment-note facts): every one confirmed by
      both direct PyMuPDF text extraction from the stored bbox AND a
      rendered, boxed crop of the source PDF page, all 5 exact matches —
      images and the extraction script's output kept in this session's
      scratch directory, not committed (ephemeral verification artifacts,
      not project data). **Remaining fallback rate: 204/634 (32%)**,
      reported honestly per instruction rather than hidden or rounded
      away — dominated by (i) genuine unlabelled rows (e.g. a "Total"
      segment subtotal printed with no row label at all — the segment
      note's own unlabelled-subtotal phenomenon, structurally the same
      finding as M2.11 §2(c)'s balance-sheet case), (ii) same-page
      multi-match ambiguity the value/position disambiguation correctly
      refuses to guess through (e.g. a headline figure repeated in both
      the primary statement and a note elsewhere on the same page), and
      (iii) wrapped labels whose remainder is a single common word below
      the 2-word shrink floor. Every fallback reason is queryable
      (`bbox = {"x0":0,"y0":0,"x1":1,"y1":1}` is the literal marker) and
      was reported by the loader's own run output, not inferred after the
      fact.

      **Knowledge period.** `effective_at` = each document's own board
      authorisation date from the manifest (FY2024: 2024-09-27; FY2025:
      2025-10-01), never `now()` — `publish_fact()` requires it
      explicitly, by design (M1.12). **Consequence confirmed live, not
      just asserted:** `select count(*) from facts_as_of('2025-01-01')`
      returns exactly 309 facts, all from a single `document_id` — the
      FY2024 AFS — and zero from the FY2025 AFS, because 2025-01-01
      predates the FY2025 AFS's 2025-10-01 authorisation date. Querying
      `facts_as_of()` (now) returns 574 facts across both documents,
      confirming the full current picture is visible once both
      documents' knowledge periods have opened.

      **Scale.** Every row in both workbooks is `scale='millions'`
      (confirmed by inspection — no row uses `units`/`thousands` except
      count/cents_per_share unit-type rows, which are a different axis).
      Canonical conversion: `value_as_printed × 1,000,000`. Confirmed
      against a known figure live: FY2025 `revenue_total` = 256,682 (Rm)
      in the workbook → `256682000000` in `facts.value`, queried back
      directly from the database.

      **Sheets loaded vs. skipped (do not double-load).** Loaded:
      `IncomeStatement`, `BalanceSheet`, `CashFlow`, `HEPS`, `Segments`,
      from both workbooks — including each sheet's prior-year comparative
      column (e.g. FY2024's workbook also yields FY2023-restated facts,
      genuinely new information with real page provenance, not available
      from any other loaded sheet). **Skipped: `Restatement_N45`
      (FY2025 workbook) and `Bitemporal_Pair` (FY2024 workbook)** —
      confirmed empirically, not assumed, that every row in both is a
      byte-for-byte duplicate of a value already present in a primary
      statement sheet (checked programmatically against both sheets'
      full row sets before writing the loader). Loading them would have
      attempted duplicate facts sourced from the WRONG document for half
      their rows (a value printed in the FY2024 AFS, claimed as sourced
      from the FY2025 AFS, or vice versa) for zero informational gain.
      `README`/`Checks`/`Concepts_Discovered`/`Structural_Changes` are
      non-data sheets, never loaded.

      **Idempotency — the subtlest requirement, proven, not just
      claimed.** `publish_fact()` always supersedes an existing current
      fact for a given identity; it has no built-in "is this actually
      different" check by design (that decision belongs to the caller,
      per M1.12's own docstring). Before calling it, the loader reads the
      current fact (if any) for that identity and skips the call entirely
      — not just skips inserting, skips CALLING `publish_fact` at all —
      when value/currency/scale/document_id/page/line_item_id are all
      unchanged. **A second, subtler case found live via an actual crash,
      not anticipated in advance:** a fact legitimately printed in BOTH
      documents (e.g. a balance-sheet comparative IFRS 5 does not require
      restating) is correctly superseded forward on first load (FY2025's
      later confirmation closes FY2024's knowledge period) — but
      reprocessing FY2024's own row on a SECOND run, after that
      supersession already exists, tried to publish at FY2024's EARLIER
      `effective_at`, which `publish_fact()` correctly refused
      (`ValueError`, "would corrupt the belief timeline"), crashing the
      loader with a clean transaction rollback (checksum of every fact's
      `(id, knowledge_period lower bound)` confirmed byte-identical before
      and after the crashed attempt). Fixed by skipping (not retrying,
      not erroring) whenever the new `effective_at` would not be strictly
      after the current fact's own knowledge-period start — that document
      genuinely has no new information to contribute at that point.
      **Proven, not just argued:** ran the loader three consecutive
      times; run 2 reports 0 published / 574 skipped-unchanged / 60
      skipped-superseded-by-later-document every time thereafter, and
      `md5(string_agg(id || ':' || lower(knowledge_period)))` over all
      634 facts is identical (`55d96ed4...`) across all three runs.

      **Verified column: 0/634 rows verified, recorded honestly.**
      Confirmed by direct inspection of both workbooks before writing the
      loader (not assumed) — `verified='Y'` appears on 0 of ~634 loadable
      rows in either workbook. Per instruction, loaded anyway
      (refusing would mean M2.12 loads nothing, stalling on M2.5–2.10's
      own unfinished hand-verification pass rather than solving a loader
      problem) with the distinction recorded, not silently upgraded:
      every fact's `verified_by`/`verified_at` are `NULL`, the schema's
      own documented meaning for "not yet human-verified" — confirmed
      live, 634/634. Hand verification against the review queue is M7's
      job, not this loader's.

      **Used `valora_pipeline.db`'s `publish_fact`/`transaction`
      throughout** — no raw bitemporal SQL written; the loader's only
      direct SQL is read-only lookups (current-fact check, concept/
      company/document ID resolution) and the two prerequisite tables'
      idempotent inserts. `ruff`/`mypy --strict` clean across the whole
      `services/pipeline` tree; all 32 existing pytest tests still pass
      unchanged. `make seed-concepts` and `make load-golden-shoprite`
      both new, separate Makefile targets, matching `make seed`'s own
      precedent (data-population steps are explicit, never wired into
      `make dev`).
- [ ] 2.13 Query Shoprite revenue, all periods — not started.

## M3 — Document store

- [ ] 3.1–3.6

## M4 — Extraction

- [ ] 4.1–4.18

## M5 — Validation

- [ ] 5.1–5.11

## M6 — Pipeline assembly

- [ ] 6.1–6.4

## M7 — Review UI

- [ ] 7.1–7.9

## M8 — Companies two and three

- [ ] 8.1–8.9

## M9 — API

- [ ] 9.1–9.9

## M10 — First AWS deploy

- [ ] 10.1–10.14

## M11 — Excel add-in

- [ ] 11.1–11.16

## M12 — Backfill to twelve

- [ ] 12.1–12.11

## M13 — Design partners

- [ ] 13.1–13.7

---

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-02 | Develop inside WSL2, repo on Linux filesystem | Dev/prod parity with Fargate; Docker I/O on `/mnt/c` is slow |
| 2026-08-02 | Postgres 17 rather than the backlog's 16 | Schema will be lived with for years; 16 already two majors behind |
| 2026-08-13 | `data/golden/` is tracked in git; `data/pdfs`, `data/cache`, `data/runs`, `data/models` remain ignored | The golden dataset is the regression baseline every extraction change is measured against (spec §8.1). Small (~43KB per workbook), and its version history is the record of how the baseline evolved. PDFs stay out — large, re-downloadable, and spec §6 is explicit that documents are stored for provenance and never redistributed. |

## Open questions

- Host `psql`/`pg_dump` client is v16 against a v17 server. **Resolved for
  schema dumps:** `scripts/dump-schema.sh` runs `pg_dump` inside the
  `postgres` container instead (see CLAUDE.md deviations). **Still open for
  ad-hoc `psql`:** interactive queries from the host still use the v16
  client; use `docker compose exec postgres psql -U valora -d valora` for
  version-matched tooling, or upgrade the host client if
  `apt.postgresql.org`'s TLS issue clears up.
- **`facts.document_id`/`page`/`bbox` are NOT NULL, but a *derived* fact
  (computed from other facts rather than extracted from a printed line) may
  have no printed source line at all, and arguably no meaningful bbox
  either.** MVP facts are all extracted, not derived, so this does not block
  M1.7. Flagged for M5 (validation, which may need to produce derived facts,
  e.g. computed ratios) and M6 (pipeline assembly) to resolve — likely
  either derived facts point provenance at the inputs they were computed
  from, or provenance NOT NULL needs a documented exception for them. Not
  solved here.
- **`companies.archetype` conflates "which concept set applies" with "what
  kind of business this is."** AVI (coverage universe, see
  `docs/jse_coverage_universe.md`) is a branded consumer-goods manufacturer,
  not a store operator — it has no trading space, no like-for-like sales,
  none of §5.6's retail-specific concepts. It is recorded as `archetype =
  'retail'` anyway, since the schema has no third value and the MVP concept
  set still mostly applies (revenue, margins, segment reporting). The
  retail-specific concepts simply go unused for AVI — an acceptable MVP
  answer, not a bug. Revisit if this conflation becomes a real problem in
  M8.7's taxonomy reconciliation (e.g. if AVI needs concepts that retail
  archetype-filtering would incorrectly hide or expose).
- **`companies` has no `parent_company_id`, and Pick n Pay consolidates
  Boxer at 65.6%** (see `docs/jse_coverage_universe.md`). Any future
  sector-level or group-level aggregation across companies double-counts
  Boxer's numbers (once under Boxer itself, once inside Pick n Pay's
  consolidated results) until this relationship is modelled. Nothing
  aggregates across companies before M13, so this is not currently
  blocking — but it is a change to the entity master (`companies`), which
  this project handles deliberately rather than adding opportunistically.
  Flagging now so it is a conscious decision when M13's cross-company
  features are designed, not a surprise.
- **Fiscal period labels must not be computed from `fye_month`.** Seven of
  the twelve companies (`docs/jse_coverage_universe.md`) use 52/53-week
  retail calendars whose year end floats across a month boundary:
  Truworths' FY2022 ended 3 July (`fye_month` 6), Mr Price's FY2021 ended
  3 April (`fye_month` 3), Pick n Pay's and Boxer's FY2025 both ended 2
  March (`fye_month` 2). Deriving a fiscal year by comparing `period_end`'s
  month against `fye_month` misclassifies every one of those filings by a
  full year, with no error raised — the comparison succeeds, it is just
  wrong. **M4.17** (classification: fiscal period from cover pages) must
  read the fiscal year the company states on the document itself and use
  `fye_month` only as a plausibility check on that reading, never as the
  source of truth for it. Not implemented — there is no classifier yet.
- **Validation rules cannot hardcode the composition of a total.** FY2024
  Revenue (246,082) = sale of merchandise + other operating income +
  interest revenue + insurance revenue — four components. FY2025 Revenue
  (256,682) = sale of merchandise + alternative revenue + interest revenue
  — three. The insurance revenue line (298 in FY2024) no longer appears on
  the face of the FY2025 statement. A rule written against one year's
  structure fails on another year of the same company, on a correct
  document — this was observed, not hypothesised: a revenue-components
  check written from FY2025 failed on FY2024 by exactly 298. M5.5 must
  read the component structure from the statement being validated.
- **Note numbers are not stable identifiers.** Inventories is note 17 in
  the FY2024 AFS and note 16 in FY2025. Stated capital 18 → 17. Lease
  liabilities 21 → 20. Provenance must never be keyed on a note reference.
- **Segment identity is not stable.** FY2024 reports four segments
  (Supermarkets RSA, Supermarkets Non-RSA, Furniture, Other); FY2025
  reports three — Furniture became a discontinued operation. The
  reconciling column was also renamed from "Hyperinflation effect" to
  "Hyperinflation effect and other reconciling items". M5.7 keys on that
  column.
- **Segments do not sum to consolidated.** A reconciling column absorbs
  the difference (FY2025: total operating segments trading profit 15,200
  vs consolidated 14,951, difference 249). M5.7's rule as written in the
  backlog ("segments sum to group totals") would fail on Shoprite's
  actual disclosure. The rule is segments PLUS reconciling items equals
  group, and the reconciling column must be captured as a fact.
- **Restatement detection cannot compare only headline totals.** The
  FY2025 restatement of FY2024 moved 9,754 of revenue between continuing
  and discontinued operations, yet profit for the year (6,221) and total
  HEPS (1,191.4 cents) are IDENTICAL before and after. Only the
  continuing/discontinued split moved (HEPS continuing 1,250.5 →
  1,185.3). A detector diffing bottom-line profit would see nothing.
  Relevant to §5.8's comparative reconciliation and M5.9.
- **Restatements have different causes and the cause matters.** The
  FY2024 AFS restated FY2023 for the adoption of IFRS 17 (Insurance
  Contracts). The FY2025 AFS restated FY2024 for IFRS 5 (discontinued
  operations). Two consecutive years, two unrelated reasons. The facts
  schema records `basis` (as_reported/restated) but not why. Consider
  whether the reason needs capturing before M5.9.
- **Basis is per-fact, not per-document.** In the FY2025 AFS the income
  statement comparative for FY2024 IS restated, but the balance sheet
  comparative is NOT — IFRS 5 does not require it. Two different bases
  for the same fiscal year within one document. Any pipeline setting
  basis per filing mislabels half the document.
- **RESOLVED by M2.11 (`docs/taxonomy_v0.md` §2b, §2c).** Unlabelled
  subtotals. Five figures in the Shoprite FY2025 balance sheet and cash
  flow are printed with no label at all (current assets excluding
  held-for-sale, equity attributable to owners, current liabilities
  excluding held-for-sale, and two in the cash reconciliation).
  `company_line_items.as_reported_label` is NOT NULL. Options considered:
  skip (rejected — two of these are load-bearing components of the totals
  M5.3 checks), sentinel (rejected — satisfies the schema without
  disambiguating anything), synthesise-and-flag (chosen). **Decision: no
  schema change.** Scope (held-for-sale included/excluded, and the other
  scope axes named below) is expressed as separate `concepts` rows, not a
  qualifier column on `facts` — `concepts` is cheap to extend, `facts` is
  the table CLAUDE.md names as expensive to migrate, and held-for-sale is
  only one of several scope axes (continuing vs total, segment vs
  consolidated) that a single column could not hold simultaneously without
  becoming a bitmask. The "no label at all" half of the problem is handled
  by the bracketed `[unlabelled subtotal] <description>` convention the
  FY2024 golden workbook had already independently adopted while
  transcribing — no new `label_provenance` column, since the bracket
  prefix carries that flag in-band in the same column every other row
  already uses. Full reasoning, including what would change this decision,
  in `docs/taxonomy_v0.md` §2b/§2c. **Known weakness, recorded not fixed**
  (§2c, added 2026-08-13): the bracket prefix is a convention, not a
  constraint — nothing in the schema enforces it, so any consumer needing
  to distinguish printed-as-reported labels from synthesised ones must
  parse the string (`LIKE '[unlabelled subtotal]%'`), which a legitimately
  bracketed printed label or a reviewer's typo silently defeats. Also in
  tension with principle 3: `as_reported_label` is documented as verbatim
  company wording, and a synthesised value in that column means the column
  no longer has one meaning. (d)'s company-defined-measure marking (free
  definition text, no schema flag) has the identical weakness for the
  identical reason. Both accepted for v0 because nothing downstream parses
  either signal yet. **Trigger to revisit: M7.4** (review UI) — if a
  reviewer needs to SEE that a label was synthesised or a concept is
  company-defined as first-class UI behaviour, that is a real consumer
  requirement, and `label_provenance` on `company_line_items` /
  `is_company_defined` on `concepts` are the columns to add at that point,
  not before.
- **The same label carries two different values in one statement.**
  "Current assets" is printed as 52,867 (FY2025) as a heading that
  INCLUDES assets held for sale, while the unlabelled subtotal directly
  above the held-for-sale line EXCLUDES them (47,279). Same for current
  liabilities. An extractor matching on label alone picks up the heading,
  sums the components, and reports a false failure. Note also that scope
  must be determined structurally, never by comparing the two values: in
  FY2024 the current liabilities heading (41,538) equals the subtotal
  exactly, because there were no held-for-sale liabilities that year.
- **Company-defined measures need flagging as such.** "Trading profit"
  and "items of a capital nature" are defined by Shoprite in accounting
  policy note 1.1.2, not by IFRS. Items of a capital nature is defined by
  reference to SAICA Circular 1/2023 — the same circular governing HEPS,
  and a circular version that can change between years. Analysts model
  trading profit heavily so it must be captured, but another retailer's
  "trading profit" may not mean the same thing. Directly relevant to
  M8.7.
- **HEPS validation needs a rounding tolerance derived from presentation
  scale.** Headline earnings / weighted average shares computed from
  figures presented in Rm gives 1,431.4 cents against a printed 1,431.6
  for FY2025 — the company computes from unrounded rand. M5.6's rule
  fails on a correct filing without a tolerance, and the tolerance must
  be derived from the scale of the presented figures rather than being a
  magic number.
- **Scale varies between a model and the source.** An analyst model built
  from this same filing was denominated in R billions while the AFS and
  the golden workbooks are in R millions. Observed instance of the
  condition M11.9 must handle.
- **SHA-256 dedupe cannot catch the same report in two renderings.**
  `data/pdfs/` holds two files for the FY2025 AFS:
  `SHP_AFS_FY2025_20251001.pdf` (print imposition, 156 PDF pages, each
  printed spread split across two) and "Shoprite Holdings - Annual
  Financial Statements 2025.pdf" (digital reader export, 79 PDF pages,
  one spread per page). Identical content, identical printed page range
  1–153, identical authorisation date, DIFFERENT checksums. M3.4's
  dedupe is keyed on `documents.sha256`, which is a pure function of the
  bytes — it will treat these as two distinct documents. Consequence: two
  `documents` rows for one filing, and facts extracted twice for the same
  period, which under the M1.8 exclusion constraint either collides or
  produces a false restatement signal. Hash dedupe catches re-downloads;
  it does not catch multiple publication formats, which is normal issuer
  behaviour. M3.4 likely needs a second, semantic dedupe layer — company
  + fiscal_period + doc_type + published_at — with the hash remaining the
  check for byte-identical re-ingestion. Flagged for M3.4, not solved
  here.
- **FY2016 may not provide a complete financial year.** Per
  `docs/shoprite_pdf_manifest.md`, the FY2016 document is an Integrated
  Report whose financial content is a "Summary Consolidated Financial
  Statements" section spanning pages 47–63 of 78 — summary statements,
  not full ones. Summary statements omit most notes, which likely means
  no full segment note (M2.9's equivalent) and no full headline earnings
  reconciliation (M2.8's equivalent) for that year. The MVP spec states
  10 financial years of history. Determine before M12 whether Shoprite
  published a separate full AFS for FY2016; if not, FY2016 is a partial
  year and the coverage claim needs qualifying in `docs/valora_mvp.md`.
- **Segment concepts are company-specific, not shared — a taxonomy design
  debt deliberately taken on at M2.12, to be repaid at M8.7.** Encoding
  segment identity into the concept code
  (`segment_trading_profit_supermarkets_rsa`, etc. — see M2.12's own
  entry above for why: `facts`' exclusion-constraint uniqueness allows
  only one current fact per concept per company/period/basis, so a
  shared concept across segments would silently supersede-and-destroy
  all but the last-loaded segment value) was the correct call for one
  company, but it does not generalise: `segment_trading_profit_
  supermarkets_rsa` is meaningless for any issuer other than Shoprite —
  no other retailer has a "Supermarkets RSA" segment. At twelve
  companies this is roughly 500 segment concepts (12 companies × ~7
  metrics × ~6 segments each, no two companies sharing a code), which
  directly contradicts the purpose of a shared taxonomy: one concept
  list serving all companies, per the backlog's own framing of M8.7
  ("One concept list serving all three; conflicts resolved and
  documented"). Segment concepts as built cannot be reconciled the way
  `revenue` or `cost_of_sales` can — there is no shared vocabulary to
  reconcile, because the codes were never meant to be shared in the
  first place.

  **Option set, for M8.7 to choose from — not decided here:**
  1. **A segment dimension on `facts`** (a nullable `segment` text/enum
     column, or a `segment_id` FK to a small new `segments` lookup
     table keyed by company). Restores one shared concept per metric
     (`segment_trading_profit`) across all companies. Cost: a migration
     on the table CLAUDE.md and the MVP spec both name as the one
     component where a mistake requires migrating live customer data —
     the exact cost M2.12 avoided by encoding into `concepts` instead.
     Would also need to decide whether `segment` participates in the
     M1.8 exclusion-constraint key (it must, or two segments' facts for
     the same concept/period/basis would collide exactly as company-
     specific concepts were built to avoid).
  2. **A separate `facts_by_segment` table** (or similar), parallel to
     `facts`, carrying its own segment dimension and provenance columns,
     leaving `facts` itself untouched. Avoids migrating the expensive
     table's existing rows, at the cost of a second fact-shaped table
     with its own bitemporal/provenance rules to build, test, and keep
     in sync with `facts`' own guarantees (M1.8's exclusion constraint
     would need to be re-derived for it, not inherited).
  3. **Keep company-specific segment concepts, accept the non-sharing.**
     No schema change, no migration. Costs the stated ~500-concept
     proliferation and forfeits any cross-company segment comparison
     (e.g. "supermarket segment trading margin across the sector") at
     the concept level — such a comparison would need to be built in
     application code that already knows which companies' concepts
     correspond to which segments, rather than being a plain `WHERE
     concept_id = X` query across companies.

  M2.12 chose the cost of option 3 deliberately, for one company, because
  the alternative (option 1 or 2) is a schema decision this task was
  explicitly told to stop and ask about rather than make unilaterally,
  and because the real shape of the problem — how much segment
  vocabulary actually overlaps across retailers, whether "Supermarkets"
  as a segment concept even makes sense for Pick n Pay or Woolworths —
  is not knowable from one company's disclosure. **M8.7 is where this
  must be resolved**, per the backlog's own reasoning for why taxonomy
  reconciliation happens at three companies rather than twelve: doing it
  late means re-mapping everything already extracted, and segment
  concepts are exactly the part of v0's taxonomy most likely to need
  that re-mapping.

## Observed baselines

Human transcription accuracy, first pass: 219/222 values correct (98.6%)
on Shoprite FY2025, transcribed carefully with no time pressure from the
cleanest reporter in the coverage universe. Errors were one transposed
digit, one sign error, and one wrong value — plus one structural error (a
subtotal formula pointing at the wrong range) which no value-level check
would catch. 222/222 after one review cycle. This is below the MVP's
≥99.0% accuracy bar and is the concrete justification for §8's
verification apparatus; it also argues that first-pass review catches
most but not all errors, supporting §5.5's two-person confirmation during
results windows.
