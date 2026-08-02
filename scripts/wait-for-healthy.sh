#!/usr/bin/env bash
# Waits until every given docker-compose SERVICE (not container name) reports
# healthy. Container names depend on COMPOSE_PROJECT_NAME (derived from the
# directory name by default), so we resolve them via `docker compose ps -q`
# instead of assuming a fixed "valora-<service>-1" pattern.
set -euo pipefail

TIMEOUT="${WAIT_FOR_HEALTHY_TIMEOUT:-120}"

if [ "$#" -eq 0 ]; then
  echo "wait-for-healthy.sh: no services given" >&2
  exit 1
fi

deadline=$(( $(date +%s) + TIMEOUT ))

for service in "$@"; do
  while true; do
    container_id="$(docker compose ps -q "$service")"

    if [ -z "$container_id" ]; then
      status="no container"
    else
      status="$(docker inspect -f '{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "no healthcheck")"
    fi

    [ "$status" = "healthy" ] && break

    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "ERROR: service '$service' did not become healthy within ${TIMEOUT}s (last status: $status)" >&2
      docker compose ps
      exit 1
    fi

    sleep 1
  done
done
