#!/usr/bin/env bash
# Thin wrapper around a pinned dbmate binary. Downloads it on first use
# (verified against a known sha256, so upstream shipping a new release never
# silently changes what CI or a developer runs) and points it at the repo's
# single DATABASE_URL, forcing sslmode=disable for the local container only.
set -euo pipefail

DBMATE_VERSION="2.34.1"
DBMATE_SHA256="b002d5249d53d0c6c482ed761b5a806c6fb9a364fcc5f9db3e8763c1d9e40e1d"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBMATE_BIN="${REPO_ROOT}/.bin/dbmate-${DBMATE_VERSION}"

if [ ! -x "$DBMATE_BIN" ]; then
  echo "Fetching dbmate v${DBMATE_VERSION}..." >&2
  mkdir -p "${REPO_ROOT}/.bin"
  curl -fsSL -o "$DBMATE_BIN" \
    "https://github.com/amacneil/dbmate/releases/download/v${DBMATE_VERSION}/dbmate-linux-amd64"
  echo "${DBMATE_SHA256}  ${DBMATE_BIN}" | sha256sum -c - >/dev/null
  chmod +x "$DBMATE_BIN"
fi

if [ -f "${REPO_ROOT}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${REPO_ROOT}/.env"
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set. Copy .env.example to .env first." >&2
  exit 1
fi

case "$DATABASE_URL" in
  *sslmode=*) url="$DATABASE_URL" ;;
  *\?*) url="${DATABASE_URL}&sslmode=disable" ;;
  *) url="${DATABASE_URL}?sslmode=disable" ;;
esac

exec "$DBMATE_BIN" --url "$url" --migrations-dir "${REPO_ROOT}/db/migrations" "$@"
