# Valora — Project Context

Context for AI coding sessions. Read this first.

---

## What this is

Valora turns JSE-listed company filings into a verified, source-linked database of
financial facts, delivered into the Excel models equity analysts already use.

MVP scope: 12 retail/consumer companies, 10 years, ~180,000 verified facts.

Full specification: `docs/valora_mvp.md`

---

## Plan of record

**`docs/valora_build_backlog.md` is the plan of record.** ~130 tasks across 14
milestones (M0–M13). Work through them **in order**. Do not skip ahead.

Every task has a *done when* condition. A task is not complete until that
condition has been demonstrably met — not until the code looks right.

Do not start a milestone until the previous milestone's done-conditions all pass.

### The three tasks that decide the outcome

- **M1.8 / M1.9** — bitemporal GiST exclusion constraint. The only thing that
  cannot be retrofitted without migrating live customer data.
- **M8.7** — taxonomy reconciliation across three companies. Done at three, not
  twelve, because doing it late means re-mapping everything already extracted.
- **M11.12** — copy-and-diff safety in the Excel add-in. The only task where
  failure loses the market rather than a sprint.

---

## Principles

These resolve most design arguments:

1. **Excel is the model; Valora is the data.** Never try to replace the spreadsheet.
2. **No fact without provenance.** Enforced in the schema, not by convention.
3. **As-reported is never destroyed.** Analysts will disagree with the
   standardization and need the escape hatch.
4. **Automate the typing, never the judgment.**
5. **The golden dataset is the company.** Extraction code can be rewritten in a
   month. Verified, provenance-linked history cannot be bought.

---

## Environment

Development happens **inside WSL2 (Ubuntu 24.04)**, not Windows.

- Repo lives at `~/projects/valora` on the **Linux filesystem** — never `/mnt/c`,
  for Docker I/O performance.
- Docker Desktop on Windows, WSL integration enabled for Ubuntu-24.04.
- VS Code connects via Remote-WSL.

### Toolchain

| Tool | Version | Notes |
|---|---|---|
| Node | v24 LTS | via nvm |
| pnpm | 11.x | via corepack |
| Python | 3.12 | system |
| uv | 0.12+ | Python packaging |
| Postgres | **17** | in Docker |
| AWS CLI | v2 | |
| make, gh, psql | | |

### Decisions that deviate from the backlog

- **M0.5 uses Postgres 17**, not the 16 written in the backlog. The schema will
  be lived with for years; 16 was already two majors behind at the start.
- **`db/schema.sql` is dumped via `pg_dump` inside the postgres container**
  (`scripts/dump-schema.sh`), not the host's `pg_dump`. The host client is
  16.14 and cannot dump a 17.10 server; installing a matching host client
  isn't currently possible (`apt.postgresql.org` fails with a persistent TLS
  handshake error). dbmate's own `--dump-schema` is disabled for the same
  reason — it shells out to the host client and was silently failing. The
  in-container client is version-matched to the server by construction.
- **`facts` carries `line_item_id`**, a nullable FK to `company_line_items`,
  although `docs/valora_mvp.md` §7's data model does not list it. A company's
  as-reported label for a concept can change across its filing history (e.g.
  "Sale of merchandise" → "Revenue from contracts with customers" post-IFRS
  15), and `company_id` + `concept_id` alone cannot recover which label
  produced a given fact — nor is it derivable after the fact, since the same
  concept can appear as a group total and again in each segment note within
  one document, so `(company_id, concept_id, document_id)` doesn't identify a
  single line item either. Without this column, principle 3 (as-reported
  never destroyed) and the as-reported pane of the provenance viewer (§5.7)
  would be silently unsatisfiable at the per-fact level. NULL means a derived
  fact with no printed source line. Deliberately **not** part of M1.8's GiST
  exclusion-constraint key — the same fact identity reached via a relabelled
  line item is still the same fact.
- **CI now provisions a real Postgres 17 and applies migrations** (the
  Python job in `.github/workflows/ci.yml`), earlier than the backlog
  implies — M0.10 said no database in CI until real migrations and tests
  exist, deferring that to whenever M1 finished. M1.9 changed the
  calculus: the GiST exclusion constraint on `facts.knowledge_period` is
  the one schema guarantee that cannot be retrofitted without migrating
  live customer data, and a test that mocks or skips the database cannot
  actually prove it holds. Migrations are applied via `scripts/dbmate.sh
  up` directly (not `make migrate`, which also runs `scripts/dump-
  schema.sh` — that script requires a `docker compose`-managed postgres and
  would fail against a plain CI service container) — same tool, same
  version pin, same migrations as local, no duplicated SQL.
- **The `as_of` query (spec §7, `GET /v1/facts?as_of=`) is a database
  function, `facts_as_of(p_as_of timestamptz default now())`** (migration
  `20260805184045_facts_as_of.sql`), not a query embedded in either
  language's codebase. M1.12's DB helper is Python and M9's API is
  TypeScript; a constant in either is invisible to the other and
  guarantees the two silently diverge. **M9.3 must call this function
  rather than reimplement the bitemporal containment check** — layer
  company/concept/period/basis filters on its result, do not rewrite
  `knowledge_period @> :as_of` in TypeScript. M1.10's tests
  (`services/pipeline/tests/test_facts_as_of.py`) are the only guarantee
  this function's boundary behaviour is correct; a second, independently
  written query has no such guarantee.
- **`@valora/db` (M1.13) is server-side only.** Its consumers are
  `services/api` and, potentially, `apps/review`'s server routes — code
  that already holds `DATABASE_URL` and runs somewhere Valora controls.
  **The Excel add-in must never import `@valora/db`.** It runs sandboxed
  inside Excel, with no network path to Postgres and no business holding
  database credentials on a user's machine. Per spec §7's "no privileged
  internal path," the add-in reaches data exclusively over the public REST
  API, the same as every other client — not via a direct database
  connection just because it happens to be written in TypeScript.
- **`pg` type parsing in `@valora/db` overrides two defaults, and both
  overrides are load-bearing — do not "clean them up":**
  - `date` columns (OID 1082) must never be parsed into JS `Date` objects.
    `pg`'s default parser treats the string as local midnight and
    re-serializes through UTC, which silently shifts the value by a day
    depending on the server's timezone — for a column like `period_start`
    or `period_end`, that is a silently corrupted period boundary, not a
    formatting quirk. `@valora/db` registers a custom type parser
    (`pg.types.setTypeParser(1082, ...)`) that returns the raw
    `"YYYY-MM-DD"` string unchanged. Any new code path that queries a
    `date` column must go through this, not a fresh `pg.Client`.
  - `numeric` values (`facts.value`) must never pass through a JavaScript
    `number`. IEEE 754 doubles lose precision on large Rand amounts;
    a verified financial fact silently rounding is exactly the failure
    principle 2 (no fact without provenance) exists to prevent even
    though provenance isn't the mechanism here — correctness of the value
    itself is. `facts.value` stays a string end-to-end in TypeScript.
    Arithmetic on it requires an explicit decimal library at the call
    site, not `Number(fact.value)`.

Record any further deviations here, with the reason.

### Local ports

| Port | Service |
|---|---|
| 5432 | Postgres (M0.5) |
| 4566 | LocalStack (M0.6) |

Other projects on this machine also use 5432. Stop their containers before
running `make dev`.

Compose service names: `postgres` and `localstack` (see root `docker-compose.yml`).
LocalStack runs S3 and SQS only, with no `PERSISTENCE` flag set — buckets and
queues do **not** survive `docker compose down`. This is expected and matters
for M0.7's `make reset`.

---

## Repository layout

```
apps/
  review/          M7  — Next.js review queue UI
services/
  pipeline/        M0.4, M4–M6 — Python extraction pipeline
  api/             M9  — TypeScript REST API
packages/
  schema/          M9.7 — shared TS types generated from OpenAPI
infra/             M10 — AWS CDK (TypeScript)
db/
  migrations/      M1  — dbmate migrations
docs/              specification, backlog, taxonomy
scripts/
data/              gitignored — PDFs, extraction cache, run reports
```

---

## Language split

- **Python** — extraction pipeline, PDF processing, validation rules,
  derivations. The document and LLM tooling ecosystems are Python-first.
- **TypeScript** — API, Next.js web app, Excel add-in (Office.js is JS/TS), auth,
  CDK.

The boundary is the queue and the API. Python services consume from SQS and write
to Postgres; they never serve the web app directly.

---

## Working agreement for AI sessions

- One milestone at a time, one task at a time, in backlog order.
- For coding tasks: provide the code, then state how to verify it.
- For manual tasks (AWS console, downloads, setup): step by step.
- Do not advance to the next task until the current *done when* condition has
  been confirmed as passing.
- Prompt for a commit after each meaningful piece of work.
- Update `PROGRESS.md` as tasks close.

---

## Cross-cutting rules, from day one

| Rule | Why |
|---|---|
| Every fact carries provenance, enforced by NOT NULL | The trust foundation; unenforceable later |
| Golden dataset grows with every correction | The regression suite and the moat |
| Extraction cache on disk, keyed on `hash(doc, page, prompt_version)` | Prevents runaway dev-time LLM spend |
| Run reports written for every pipeline execution | You cannot improve accuracy you don't measure |
| Log retention set on every new CloudWatch log group | Accumulates silently and costs money |
