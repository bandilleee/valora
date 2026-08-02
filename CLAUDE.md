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
