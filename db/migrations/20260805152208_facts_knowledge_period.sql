-- migrate:up

-- Required so the EXCLUDE constraint below can mix plain equality on
-- ordinary scalar columns (bigint, text, date) with range-overlap on
-- knowledge_period inside a single GiST index. GiST has no native operator
-- class for bigint/text/date equality; btree_gist supplies one. Without it,
-- `EXCLUDE USING gist (company_id WITH =, ...)` fails outright — there is
-- no other built-in way to combine equality-key columns and a range-overlap
-- column in one declarative exclusion constraint.
create extension if not exists btree_gist;

alter table facts add column knowledge_period tstzrange not null;

comment on column facts.knowledge_period is
  'The period during which Valora believed this fact (bitemporal axis, distinct from period_start/period_end which describe the fiscal period the fact is ABOUT). Bounds are always [lower, upper): lower inclusive, upper exclusive, so a closed-then-reopened pair of ranges at the same instant abut without gap or overlap. Unbounded upper (e.g. tstzrange(t, NULL)) means "believed from t, still currently believed" — this is how "current" is represented; there is no separate flag for it. No column default: the correct lower bound is the actual instant belief began (extraction completion, verification, or publish time, depending on the writer), which Postgres''s now() at INSERT time does not reliably represent — a wrong default here would be silently wrong, not loudly wrong, so every writer must compute and supply it explicitly.';

-- Belt-and-braces on top of the bound convention above: a caller passing a
-- differently-shaped range (e.g. inclusive upper, or unbounded lower) does
-- not get to redefine what "current" means for this table.
alter table facts add constraint facts_knowledge_period_shape check (
  -- A fact believed for zero duration (lower = upper under '[)') collapses
  -- to Postgres's canonical empty range. Must never be a valid current
  -- belief — reject it outright rather than let it exist unnoticed.
  not isempty(knowledge_period)
  -- Requirement: a lower bound must always be present. A fact with no
  -- start of belief is meaningless; an unbounded lower bound would mean
  -- exactly that.
  and not lower_inf(knowledge_period)
  -- Enforce the [) convention itself, not just document it.
  and lower_inc(knowledge_period)
  and not upper_inc(knowledge_period)
);

-- Per spec §7. period_end is deliberately NOT a key column: for a fixed
-- (period_start, period_type) it is functionally determined (a fiscal year
-- starting on a given date always has the same length for that
-- period_type), so including it would only let a data-entry inconsistency
-- between two rows' period_end silently create two "different" keys
-- instead of being caught as the bug it is. (Nothing here enforces that
-- consistency yet — a validation gap, not an exclusion-constraint-key gap;
-- out of scope for this migration.) line_item_id is deliberately NOT a key
-- column either (confirmed and exercised in M1.7): a company relabelling
-- an as-reported line does not create a new fact identity, so a
-- relabelled line item must compete for the same knowledge_period window
-- as the fact it relabels, not sit beside it unconstrained.
--
-- DEFERRABLE INITIALLY IMMEDIATE: checked immediately by default (same
-- debuggability as a plain constraint) for any writer that does nothing
-- special. A restatement's natural order — UPDATE the old row's
-- knowledge_period to close it, THEN INSERT the new row with an
-- open-ended one — already satisfies immediate checking cleanly, since
-- [t_old, t_new) and [t_new, ) do not overlap. Reversing that order (INSERT
-- before closing the old row) is rejected immediately, mid-transaction,
-- under this default. DEFERRABLE exists to give a future writer (M2.12's
-- loader, M6's publish stage) the option to `SET CONSTRAINTS
-- facts_no_overlapping_knowledge_periods DEFERRED` if its transaction
-- structure genuinely cannot guarantee per-statement ordering — but that
-- moves violation reporting to COMMIT time, harder to localise to the
-- offending row, so it should be opted into deliberately, not treated as
-- the default way to write this operation.
alter table facts add constraint facts_no_overlapping_knowledge_periods
  exclude using gist (
    company_id with =,
    concept_id with =,
    period_start with =,
    period_type with =,
    basis with =,
    knowledge_period with &&
  ) deferrable initially immediate;

-- migrate:down

alter table facts drop constraint facts_no_overlapping_knowledge_periods;
alter table facts drop constraint facts_knowledge_period_shape;
alter table facts drop column knowledge_period;
-- Safe to drop outright (no CASCADE) as long as this is the only migration
-- depending on it: nothing else in this schema uses btree_gist yet. If a
-- later migration adds another btree_gist-dependent object, rolling back
-- 1.8 out of order (without first rolling back that later migration) would
-- correctly fail loudly here rather than silently cascading it away.
drop extension btree_gist;
