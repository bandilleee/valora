# Valora — Progress

Updated as tasks close. Plan of record is `docs/valora_build_backlog.md`.

**Status:** M0 complete — M1 (Schema) in progress
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
- [ ] 1.11–1.13 — see backlog. **1.8 and 1.9 are the most important tasks in the project.**

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
