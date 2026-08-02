# Valora

Valora turns JSE-listed company filings into a verified, source-linked
database of financial and operational facts, and delivers those facts
directly into the Excel models that equity analysts already use.

Full specification: [`docs/valora_mvp.md`](docs/valora_mvp.md).
Plan of record: [`docs/valora_build_backlog.md`](docs/valora_build_backlog.md)
— work proceeds through it in order, one milestone at a time.

This README gets a human running the project locally. For AI coding session
context, working agreements, and cross-cutting rules, see
[`CLAUDE.md`](CLAUDE.md).

---

## Prerequisites

Development happens **inside WSL2 (Ubuntu 24.04)**, not Windows. The repo
must live on the **Linux filesystem** (e.g. `~/projects/valora`) — never
under `/mnt/c` — because Docker's bind-mount I/O to `/mnt/c` is slow enough
to make the Postgres and LocalStack containers noticeably sluggish, and
because production runs on Linux (Fargate), so developing on the Linux
filesystem keeps dev/prod parity.

You'll need:

| Tool | Version |
|---|---|
| WSL2 | Ubuntu 24.04 |
| Docker Desktop | with WSL integration enabled for Ubuntu-24.04 |
| Node | 24 (LTS) |
| pnpm | 11.18.0 (via corepack) |
| Python | 3.12 |
| uv | 0.12+ |
| AWS CLI | v2 |
| make, gh, psql | |

## Cold start

1. **Clone the repo** onto the Linux filesystem inside WSL:
   ```bash
   git clone <repo-url> ~/projects/valora
   cd ~/projects/valora
   ```
   Success looks like: you're in the repo, and `pwd` does **not** start with `/mnt/`.

2. **Create your local environment file**:
   ```bash
   cp .env.example .env
   ```
   Success looks like: a `.env` file exists at the repo root. It's gitignored —
   `git status` should not show it.

3. **Install TypeScript dependencies**:
   ```bash
   pnpm install
   ```
   Success looks like: pnpm reports all workspace projects resolved, no errors.

4. **Install Python dependencies**:
   ```bash
   cd services/pipeline && uv sync && cd ../..
   ```
   Success looks like: a `.venv` appears under `services/pipeline`, `uv sync`
   exits cleanly.

5. **Bring up the local stack**:
   ```bash
   make dev
   ```
   Success looks like: the command blocks for a few seconds and then prints
   `postgres and localstack are healthy. Ready.` — not just "started."

## The make targets

| Target | Does |
|---|---|
| `make dev` | Brings up postgres + localstack and waits until both report healthy. |
| `make down` | Stops the containers. **Preserves** the data volumes. |
| `make test` | Runs the TypeScript suite (via turbo) and the Python suite (via uv). |
| `make migrate` | Stub — fails loudly until dbmate is wired up in M1.1. |
| `make reset` | **Destroys** the containers and their volumes, then brings up a clean stack. |

`make down` is safe to run between sessions. `make reset` is not — it deletes
your local database and any LocalStack state.

## Connecting to the local stack

Postgres, via the running container:
```bash
docker compose exec postgres psql -U valora -d valora
```

LocalStack, via the AWS CLI (dummy credentials — LocalStack accepts any value):
```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=af-south-1 \
  aws --endpoint-url=http://localhost:4566 s3 ls
```

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

## Known gotchas

- **Port 5432 conflicts.** Other projects on this machine may already be
  running Postgres on 5432. Stop their containers before `make dev`, or it
  will fail to bind the port.
- **Do not clone under `/mnt/c`.** Docker's bind-mount performance to the
  Windows filesystem is slow enough to be a real problem, not a theoretical
  one — keep the repo on the Linux filesystem.
- **`.env` must exist.** The Python and TypeScript config loaders read
  required variables from it (or your shell environment) and fail loudly if
  they're missing. If you skip `cp .env.example .env`, anything that loads
  config will refuse to start.
- **Compose service names are `postgres` and `localstack`.** Use those names
  with `docker compose exec` / `docker compose logs`, not container names.

---

See [`docs/valora_mvp.md`](docs/valora_mvp.md) for the full specification and
[`docs/valora_build_backlog.md`](docs/valora_build_backlog.md) — the plan of
record — for the complete task list.
