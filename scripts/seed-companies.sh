#!/usr/bin/env bash
# Seeds the 12 MVP coverage companies (M1.11). Values are transcribed
# verbatim from docs/jse_coverage_universe.md, the single source of truth
# for which companies and what fye_month — do not edit values here without
# updating that file first, and do not re-derive fye_month independently.
#
# Idempotent via ON CONFLICT (jse_code) DO NOTHING: re-running never
# duplicates and never errors on an existing row. Deliberately NOT
# ON CONFLICT ... DO UPDATE — that would silently overwrite a hand
# correction made directly in the database. Deliberately not silent either:
# after seeding, this script re-reads every row back and WARNS (does not
# fail, does not touch the row) on any field that differs from the
# coverage doc, so a genuine upstream change (or an accidental hand-edit)
# becomes visible instead of being silently masked either way.
#
# Not part of any migration and not run by the test suite: this is
# reference data, not schema and not fixtures.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -z "$(docker compose ps --status running -q postgres)" ]; then
  echo "ERROR: the 'postgres' compose service is not running. Run 'make dev' first." >&2
  exit 1
fi

psql_exec() {
  docker compose exec -T postgres psql -U "${POSTGRES_USER:-valora}" -d "${POSTGRES_DB:-valora}" "$@"
}

echo "Seeding companies (ON CONFLICT (jse_code) DO NOTHING)..."

# fye_month and sector sourcing: docs/jse_coverage_universe.md. Sector
# values are a general classification only, not verified to the same
# primary-source rigor as fye_month (see that document's own caveat) —
# seeded anyway since they carry no downstream labelling risk the way a
# wrong fye_month would, and a caveated value is more useful than NULL.
psql_exec -v ON_ERROR_STOP=1 <<'SQL'
insert into companies (name, jse_code, sector, archetype, fye_month) values
  ('Shoprite Holdings Limited',        'SHP', 'Food Retailers & Wholesalers',                    'retail', 6),
  ('Pick n Pay Stores Limited',        'PIK', 'Food Retailers & Wholesalers',                    'retail', 2),
  ('Boxer Retail Limited',             'BOX', 'Food Retailers & Wholesalers',                    'retail', 2),
  ('The SPAR Group Limited',           'SPP', 'Food Retailers & Wholesalers',                    'retail', 9),
  ('Woolworths Holdings Limited',      'WHL', 'General Retailers (food & fashion/beauty/home)',  'retail', 6),
  ('Mr Price Group Limited',           'MRP', 'Apparel/General Retailers',                       'retail', 3),
  ('Truworths International Limited',  'TRU', 'Apparel Retailers',                               'retail', 6),
  ('The Foschini Group Limited',       'TFG', 'Apparel/General Retailers',                       'retail', 3),
  ('Clicks Group Limited',             'CLS', 'Food & Drug Retailers / Health & Beauty',         'retail', 8),
  ('Dis-Chem Pharmacies Limited',      'DCP', 'Food & Drug Retailers / Health & Beauty',         'retail', 2),
  ('Pepkor Holdings Limited',          'PPH', 'General Retailers / Apparel & Merchandise',       'retail', 9),
  ('AVI Limited',                      'AVI', 'Food Producers / Branded Consumer Goods',         'retail', 6)
on conflict (jse_code) do nothing;
SQL

echo "Verifying..."

row_count="$(psql_exec -t -A -c 'select count(*) from companies;')"
if [ "$row_count" -ne 12 ]; then
  echo "ERROR: expected exactly 12 companies, found $row_count." >&2
  exit 1
fi
echo "  12 companies present."

invalid_fye="$(psql_exec -t -A -c \
  'select count(*) from companies where fye_month is null or fye_month < 1 or fye_month > 12;')"
if [ "$invalid_fye" -ne 0 ]; then
  echo "ERROR: $invalid_fye company row(s) have a null or out-of-range fye_month." >&2
  exit 1
fi
echo "  Every fye_month is non-null and in 1-12."

# Compare every seeded field against what is actually in the database.
# A mismatch is a WARNING, not a failure and not an overwrite: it means
# either a hand-correction (leave it) or docs/jse_coverage_universe.md
# has moved on without this script being updated (fix the script). Either
# way, a human decides — this only makes the divergence visible.
mismatches="$(psql_exec -t -A -F'|' -c "
  with expected (jse_code, name, sector, archetype, fye_month) as (
    values
      ('SHP', 'Shoprite Holdings Limited',       'Food Retailers & Wholesalers',                   'retail', 6),
      ('PIK', 'Pick n Pay Stores Limited',       'Food Retailers & Wholesalers',                   'retail', 2),
      ('BOX', 'Boxer Retail Limited',            'Food Retailers & Wholesalers',                   'retail', 2),
      ('SPP', 'The SPAR Group Limited',          'Food Retailers & Wholesalers',                   'retail', 9),
      ('WHL', 'Woolworths Holdings Limited',     'General Retailers (food & fashion/beauty/home)', 'retail', 6),
      ('MRP', 'Mr Price Group Limited',          'Apparel/General Retailers',                      'retail', 3),
      ('TRU', 'Truworths International Limited', 'Apparel Retailers',                              'retail', 6),
      ('TFG', 'The Foschini Group Limited',      'Apparel/General Retailers',                      'retail', 3),
      ('CLS', 'Clicks Group Limited',            'Food & Drug Retailers / Health & Beauty',        'retail', 8),
      ('DCP', 'Dis-Chem Pharmacies Limited',     'Food & Drug Retailers / Health & Beauty',        'retail', 2),
      ('PPH', 'Pepkor Holdings Limited',         'General Retailers / Apparel & Merchandise',      'retail', 9),
      ('AVI', 'AVI Limited',                     'Food Producers / Branded Consumer Goods',        'retail', 6)
  )
  select e.jse_code, e.name, c.name, e.sector, c.sector, e.archetype, c.archetype, e.fye_month, c.fye_month
  from expected e
  join companies c using (jse_code)
  where e.name != c.name or e.sector is distinct from c.sector
     or e.archetype != c.archetype or e.fye_month != c.fye_month;
")"

if [ -n "$mismatches" ]; then
  echo "WARNING: the following rows differ from docs/jse_coverage_universe.md (left of each pair is expected, right is what's in the database) — not modified, review and reconcile by hand:" >&2
  echo "$mismatches" >&2
else
  echo "  All 12 rows match docs/jse_coverage_universe.md exactly."
fi

echo "Done."
