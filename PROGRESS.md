# Valora — Progress

Updated as tasks close. Plan of record is `docs/valora_build_backlog.md`.

**Status:** M1 (Schema) complete — M2 (One company by hand) not yet started
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

- [ ] 2.1–2.13

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
