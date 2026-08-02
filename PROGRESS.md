# Valora — Progress

Updated as tasks close. Plan of record is `docs/valora_build_backlog.md`.

**Status:** M0 — Environment
**Started:** 2026-08-02

---

## Legend

`[ ]` not started · `[~]` in progress · `[x]` done, *done when* condition verified

---

## M0 — Environment

- [x] **Environment prerequisites** — WSL2 Ubuntu 24.04, Docker Desktop with WSL
      integration, Node v24.18.1, pnpm 11.18.0, Python 3.12.3, uv 0.12.1,
      AWS CLI 2.36.14, make 4.3, psql 16 client, gh 2.97.0, git identity set
- [~] **0.1** `git init`, monorepo folder structure, `.gitignore`
- [ ] **0.2** pnpm workspace config (`pnpm-workspace.yaml`)
- [ ] **0.3** Turborepo config, `turbo.json`
- [ ] **0.4** Python service scaffold under `services/pipeline` with `uv`
- [ ] **0.5** `docker-compose.yml` — Postgres 17
- [ ] **0.6** LocalStack (S3, SQS) added to compose
- [ ] **0.7** `Makefile` — `dev`, `down`, `test`, `migrate`, `reset`
- [ ] **0.8** `.env.example` + config loader (both languages)
- [ ] **0.9** AWS Budgets: alerts at $50 and $120
- [ ] **0.10** GitHub Actions skeleton — lint + test jobs
- [ ] **0.11** `README.md` with a cold-start runbook

## M1 — Schema

- [ ] 1.1–1.13 — see backlog. **1.8 and 1.9 are the most important tasks in the project.**

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

- Host `psql` client is v16 against a v17 server. Works, but consider upgrading
  the client or using `docker compose exec db psql` for version-matched tooling.
