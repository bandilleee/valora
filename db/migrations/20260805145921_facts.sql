-- migrate:up

-- Core columns only. Deliberately does NOT include knowledge_period or the
-- GiST exclusion constraint (M1.8) — split so a misbehaving exclusion
-- constraint is debugged in isolation from everything else. This table is
-- designed so 1.8 is a pure ALTER TABLE ADD COLUMN + ADD CONSTRAINT: every
-- column the exclusion constraint keys on (company_id, concept_id,
-- period_start, period_type, basis) already exists below with types
-- compatible with btree_gist, so nothing here needs restructuring.
create table facts (
  id bigint generated always as identity primary key,

  company_id bigint not null references companies (id) on delete restrict,
  concept_id bigint not null references concepts (id) on delete restrict,

  -- Deviation from spec §7, which does not list this column (recorded in
  -- CLAUDE.md). company_id + concept_id alone cannot recover which
  -- as-reported label produced a given fact once a company's terminology
  -- for that concept changes across its filing history (e.g. "Sale of
  -- merchandise" -> "Revenue from contracts with customers" post-IFRS 15),
  -- and it is not derivable after the fact either — the same concept can
  -- appear as a group total and again in each segment note within one
  -- document, so (company_id, concept_id, document_id) does not identify a
  -- single line item. NOT part of 1.8's exclusion-constraint key: the same
  -- fact identity reached via a relabelled line item is still the same
  -- fact, so this column must never affect fact uniqueness.
  line_item_id bigint references company_line_items (id) on delete restrict,

  -- Precise dates, not a human label like documents.fiscal_period — a
  -- fiscal year (e.g. "FY2025") is derived by joining period_end against
  -- the owning company's fye_month, not stored here.
  period_start date not null,
  period_end date not null,
  -- JSE-listed companies report annual and interim results, not quarterly
  -- — do not import US (10-Q style) conventions.
  period_type text not null check (period_type in ('FY', 'H1')),

  -- as_reported: value as originally disclosed, in the filing that first
  -- reported this period. restated: a later filing's revised figure for a
  -- past period. These are parallel, coexisting fact series (not versions
  -- of each other) — an as_reported and a restated row for the identical
  -- period both exist simultaneously so their difference IS the
  -- restatement (§5.8 "free reconciliation"). This is why basis is one of
  -- 1.8's exclusion-constraint equality columns: uniqueness (via
  -- knowledge_period) is enforced within a basis, not across the two.
  basis text not null check (basis in ('as_reported', 'restated')),

  value numeric not null,
  -- ISO 4217 format enforced; value set not constrained. Not limited to
  -- ZAR — a JSE company can legitimately disclose a foreign-currency-
  -- denominated line item (e.g. an offshore facility), and the full
  -- ISO 4217 list is too large and too fluid to enumerate here.
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  -- Provenance only: what scale the SOURCE document printed this value in.
  -- value above is ALREADY the canonical number — never multiply value by
  -- scale. scale is text, not a numeric multiplier, specifically so that
  -- "value * scale" is a type error rather than a silent 1000x mistake.
  scale text not null check (scale in ('units', 'thousands', 'millions')),

  -- Provenance. NOT NULL: a fact without it cannot be published, enforced
  -- here rather than by convention (spec §5.7).
  document_id bigint not null references documents (id) on delete restrict,
  page integer not null check (page > 0),
  -- {x0,y0,x1,y1}, each normalised to [0,1] of page width/height, origin
  -- TOP-LEFT (matches image/screen convention, NOT raw PDF coordinates,
  -- which are bottom-left-origin in points). Chosen so a bbox rescales by
  -- plain multiplication against a page image served at any resolution/DPI,
  -- with no unit conversion. (x0,y0) is the top-left corner of the box,
  -- (x1,y1) the bottom-right.
  bbox jsonb not null check (
    bbox ?& array['x0', 'y0', 'x1', 'y1']
    and (bbox->>'x0')::numeric >= 0 and (bbox->>'x0')::numeric <= 1
    and (bbox->>'y0')::numeric >= 0 and (bbox->>'y0')::numeric <= 1
    and (bbox->>'x1')::numeric >= 0 and (bbox->>'x1')::numeric <= 1
    and (bbox->>'y1')::numeric >= 0 and (bbox->>'y1')::numeric <= 1
    and (bbox->>'x0')::numeric < (bbox->>'x1')::numeric
    and (bbox->>'y0')::numeric < (bbox->>'y1')::numeric
  ),

  -- NULL means no automated confidence score exists (e.g. a hand-typed
  -- golden-dataset fact, M2) — not a zero-confidence extraction.
  confidence numeric check (confidence >= 0 and confidence <= 1),

  -- No FK yet: neither the users table (M7) nor extraction_runs (M6.3)
  -- exist. Typed bigint to match this schema's uniform bigint-identity PK
  -- convention, so adding `references <table> (id)` later is a pure
  -- ALTER TABLE ADD CONSTRAINT, not a type migration. extraction_run_id is
  -- nullable because hand-typed golden-dataset facts (M2) have no
  -- extraction run behind them at all.
  verified_by bigint,
  verified_at timestamptz,
  extraction_run_id bigint,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint facts_period_end_after_period_start check (period_end > period_start),
  constraint facts_verification_consistency check (
    (verified_by is null) = (verified_at is null)
  )

  -- Deliberately NO unique constraint on the fact-identity columns
  -- (company_id, concept_id, period_start, period_type, basis). Uniqueness
  -- is 1.8's GiST exclusion constraint's job; adding one here would force
  -- 1.8 to drop it.
);

comment on column facts.value is
  'Canonical value, already normalised to actual units regardless of how the source document presented it (M4.15). Never multiply this by scale — scale is provenance only, describing how the source printed it, not a multiplier to apply.';

comment on column facts.scale is
  'Provenance: the scale the SOURCE document used to print this value (e.g. a statement header reading "R''000"). value is already canonical at the actual-units scale; this column is never consumed to compute it.';

comment on column facts.bbox is
  'JSON object {x0,y0,x1,y1}: bounding box of the value on its source page, normalised to [0,1] of page width/height, origin top-left (image/screen convention, not raw PDF bottom-left-origin points). (x0,y0) top-left corner, (x1,y1) bottom-right.';

comment on column facts.basis is
  'as_reported: value as originally disclosed, in the filing that first reported this period. restated: a later filing''s revised figure for a past period. The two coexist as parallel rows for the same period — not versions of each other.';

comment on column facts.confidence is
  'Automated extraction confidence in [0,1]. NULL means no automated score exists (e.g. a hand-typed golden-dataset fact, M2), not zero confidence.';

comment on column facts.extraction_run_id is
  'References the extraction_runs table once it exists (M6.3) — no FK yet. NULL for facts with no extraction run behind them (e.g. hand-typed golden-dataset facts, M2).';

comment on column facts.verified_by is
  'Will reference a users/reviewers table once it exists (M7) — no FK yet. NULL means not yet human-verified.';

comment on column facts.line_item_id is
  'Which as-reported line item (company_line_items) produced this fact, so the exact company terminology used survives even as it changes across a filing history. NULL indicates a derived fact with no printed source line — not a data-quality gap.';

-- The one named query this indexes for: facts for a set of companies and
-- concepts over a period range (GET /v1/facts, spec §7). Not speculative —
-- no other index added. line_item_id is not indexed either: its consumer
-- ("which facts came through this line item", M8.7 taxonomy remapping) is
-- a batch/admin operation, not a hot path, and there is no real data yet to
-- plan an index against — add one if M8.7 shows it is actually needed.
create index facts_company_concept_period_idx on facts (company_id, concept_id, period_start);

create trigger facts_set_updated_at
  before update on facts
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger facts_set_updated_at on facts;
drop table facts;
