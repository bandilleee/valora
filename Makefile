.PHONY: help dev down test migrate migrate-down migrate-new reset seed upload-documents

help:
	@echo "Valora - available commands:"
	@echo "  make dev              - bring up postgres + localstack, wait until healthy"
	@echo "  make down             - stop containers, preserve volumes"
	@echo "  make test             - run TS (turbo) and Python (uv) test suites"
	@echo "  make migrate          - apply all pending migrations (dbmate up)"
	@echo "  make migrate-down     - roll back the most recent migration (dbmate rollback)"
	@echo "  make migrate-new name=<name> - create a new migration file"
	@echo "  make reset            - DESTROY containers and volumes, then bring up clean"
	@echo "  make seed             - seed the 12 MVP coverage companies (idempotent)"
	@echo "  make upload-documents - upload data/pdfs/*.pdf to LocalStack S3 (idempotent)"

dev:
	docker compose up -d
	@echo "Waiting for postgres and localstack to report healthy..."
	@./scripts/wait-for-healthy.sh postgres localstack
	@echo "postgres and localstack are healthy. Ready."

down:
	docker compose down

test:
	pnpm turbo test
	cd services/pipeline && uv run pytest

migrate:
	@./scripts/dbmate.sh up
	@./scripts/dump-schema.sh

migrate-down:
	@./scripts/dbmate.sh rollback
	@./scripts/dump-schema.sh

migrate-new:
	@if [ -z "$(name)" ]; then \
		echo "ERROR: usage: make migrate-new name=<migration_name>"; \
		exit 1; \
	fi
	@./scripts/dbmate.sh new $(name)

reset:
	@echo "WARNING: this destroys postgres and localstack volumes - all local data will be lost."
	docker compose down --volumes
	docker compose up -d
	@echo "Waiting for postgres and localstack to report healthy..."
	@./scripts/wait-for-healthy.sh postgres localstack
	@echo "Reset complete. postgres and localstack are healthy, starting from empty state."

seed:
	@./scripts/seed-companies.sh

upload-documents:
	@cd services/pipeline && uv run python scripts/upload_documents.py
