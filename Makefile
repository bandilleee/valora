.PHONY: help dev down test migrate reset

help:
	@echo "Valora - available commands:"
	@echo "  make dev      - bring up postgres + localstack, wait until healthy"
	@echo "  make down     - stop containers, preserve volumes"
	@echo "  make test     - run TS (turbo) and Python (uv) test suites"
	@echo "  make migrate  - run database migrations (stub until M1.1)"
	@echo "  make reset    - DESTROY containers and volumes, then bring up clean"

dev:
	docker compose up -d
	@echo "Waiting for postgres and localstack to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' valora-postgres-1 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' valora-localstack-1 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "postgres and localstack are healthy. Ready."

down:
	docker compose down

test:
	pnpm turbo test
	cd services/pipeline && uv run pytest

migrate:
	@echo "ERROR: 'make migrate' is not wired up yet."
	@echo "dbmate is introduced in M1.1 - there are no migrations to run."
	@echo "Do not treat this as success; this target intentionally fails until M1.1 lands."
	@exit 1

reset:
	@echo "WARNING: this destroys postgres and localstack volumes - all local data will be lost."
	docker compose down --volumes
	docker compose up -d
	@echo "Waiting for postgres and localstack to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' valora-postgres-1 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' valora-localstack-1 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "Reset complete. postgres and localstack are healthy, starting from empty state."
