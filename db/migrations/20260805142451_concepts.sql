-- migrate:up

create table concepts (
  id bigint generated always as identity primary key,

  -- Stable, human-readable identifier ('revenue', 'gross_profit'). Facts
  -- (1.7) will reference concepts by id, not code, so renaming code does not
  -- break FK integrity — but code is expected to appear in the public API
  -- (e.g. ?concepts=revenue,gross_margin per spec §7) and in analyst-facing
  -- tooling, so it should be treated as immutable once used anywhere
  -- outside this table. Not enforced by a constraint here: there is nothing
  -- yet (no facts table) for a trigger to check usage against.
  code text not null check (code ~ '^[a-z][a-z0-9_]*$'),
  label text not null,

  -- Every archetype this concept applies to. Not a normalized entity
  -- elsewhere in the schema (companies.archetype is a plain CHECK-
  -- constrained column, not a lookup table), so a text[] here matches that
  -- shape rather than introducing a join table for a two-value domain.
  -- Must stay in sync with companies' archetype CHECK by hand — there is no
  -- single source of truth for the allowed values across the two tables.
  archetype_set text[] not null check (
    cardinality(archetype_set) > 0
    and archetype_set <@ array['retail', 'bank']::text[]
  ),

  -- NULL means this concept does not belong to one of the three primary
  -- financial statements (e.g. a note-level reconciling item or an
  -- operating KPI like store count or trading space) rather than forcing
  -- it into a bucket it does not honestly belong to.
  statement text check (statement in ('income_statement', 'balance_sheet', 'cash_flow')),

  sign_convention text not null check (sign_convention in ('natural', 'signed')),
  unit_type text not null check (unit_type in (
    'currency', 'currency_per_share', 'count', 'percentage', 'ratio', 'density'
  )),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint concepts_code_key unique (code)
);

comment on column concepts.sign_convention is
  'How this concept''s value is signed in canonical storage. ''natural'': always a positive magnitude regardless of whether the concept adds or subtracts in its parent total (e.g. cost_of_sales stored as 50000; consuming code must apply the correct sign based on the concept''s role). ''signed'': stored with the sign it contributes to its parent total (e.g. cost_of_sales stored as -50000, so gross_profit = revenue + cost_of_sales works by plain summation).';

comment on column concepts.unit_type is
  'The unit family this concept''s value is denominated in: currency (absolute monetary value), currency_per_share (e.g. HEPS, NAV per share), count (e.g. store count, headcount), percentage (e.g. like-for-like growth, margins), ratio (non-percentage ratios, e.g. gearing), density (area-denominated measures, e.g. trading density as currency per square metre).';

comment on column concepts.statement is
  'Which primary financial statement this concept belongs to. NULL means it does not belong to one of the three (e.g. a note-level or operating-KPI concept such as store count or trading space).';

create index concepts_archetype_set_gin_idx on concepts using gin (archetype_set);

create trigger concepts_set_updated_at
  before update on concepts
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger concepts_set_updated_at on concepts;
drop table concepts;
