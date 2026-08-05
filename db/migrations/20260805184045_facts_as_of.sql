-- migrate:up

-- The canonical as_of query (spec §7: GET /v1/facts?as_of=). Lives in the
-- database, not in either language's codebase, because M1.12's DB helper is
-- Python and M9's API is TypeScript — a query constant in either language
-- is invisible to the other and guarantees eventual duplication. A SQL
-- function is the one form both can call identically, via plain SQL,
-- with zero duplication.
--
-- A function rather than a view: as_of is a genuine parameter. A view is a
-- fixed, unparameterised SELECT — a caller would have to add its own
-- `WHERE knowledge_period @> :as_of` on top, which is exactly the risk
-- this exists to close: a second, independently written boundary check
-- that can silently diverge from this one. A function makes the boundary
-- condition the only thing inside it; callers may layer company/concept/
-- period/basis filters on the result, but cannot redefine what "as of"
-- means without simply not calling it.
create function facts_as_of(p_as_of timestamptz default now())
returns setof facts
language sql
stable
as $$
  select *
  from facts
  where knowledge_period @> p_as_of
$$;

comment on function facts_as_of(timestamptz) is
  'Canonical as_of query (spec §7, GET /v1/facts?as_of=). Returns every fact row Valora believed as of the given instant (default now() — the current view). Uses knowledge_period''s containment operator directly, which already respects the [lower, upper) bound convention decided in M1.8: an as_of exactly at a restatement boundary instant t2 returns the NEW row, since [t1,t2) excludes t2 while [t2,t3) includes it. M9.3 (GET /v1/facts?as_of=) MUST call this function rather than reimplement the containment check in TypeScript — that is the entire reason it exists as a database function rather than a query embedded in either language. Company/concept/period/basis filtering belongs on top of this function''s output; it resolves only the bitemporal axis.';

-- migrate:down

drop function facts_as_of(timestamptz);
