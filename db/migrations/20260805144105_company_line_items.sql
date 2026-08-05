-- migrate:up

create table company_line_items (
  id bigint generated always as identity primary key,

  company_id bigint not null references companies (id) on delete restrict,

  -- Verbatim, as printed by the company. Never normalised or destroyed
  -- (spec §5.6, principle 3) — the standardized mapping lives in concept_id
  -- alongside it, not in place of it. No uniqueness constraint on this
  -- column: see the mapping_status/concept_id comment below for why.
  as_reported_label text not null,

  -- 'unreviewed': freshly discovered, nobody has looked at it (concept_id
  -- NULL). 'mapped': a standard concept equivalent has been confirmed
  -- (concept_id set). 'unmapped': explicitly reviewed and decided to have
  -- no standard equivalent (concept_id NULL) — a deliberate decision, not
  -- an absence of one. M8.4's done-condition ("every extracted line item
  -- mapped or explicitly unmapped") requires distinguishing the last two
  -- states, which a nullable concept_id alone cannot do.
  mapping_status text not null default 'unreviewed'
    check (mapping_status in ('unreviewed', 'mapped', 'unmapped')),
  concept_id bigint references concepts (id) on delete restrict,

  -- The row only exists because extraction discovered this label somewhere;
  -- that document is always known at creation time (unlike documents.
  -- company_id, there is no staged/pending case to accommodate).
  first_seen_doc_id bigint not null references documents (id) on delete restrict,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint company_line_items_mapping_status_consistency check (
    (mapping_status = 'mapped' and concept_id is not null)
    or (mapping_status in ('unreviewed', 'unmapped') and concept_id is null)
  )
);

comment on column company_line_items.as_reported_label is
  'Verbatim as printed by the company. Never normalised or destroyed. NOT unique per (company_id, as_reported_label): the same label (e.g. "Total") legitimately recurs across different statements/notes for one company, and no column here disambiguates those occurrences — see PROGRESS.md / migration history for M1.6.';

comment on column company_line_items.mapping_status is
  'unreviewed: not yet looked at (concept_id NULL). mapped: standard concept confirmed (concept_id set). unmapped: explicitly reviewed and decided to have no standard equivalent (concept_id NULL, but deliberately so, not by default).';

-- FK indexes for the two named consumers: the review queue (unreviewed
-- items, optionally scoped by company) and taxonomy reconciliation (a
-- company's full label catalog; all companies mapped to a given concept).
create index company_line_items_company_id_idx on company_line_items (company_id);
create index company_line_items_concept_id_idx on company_line_items (concept_id);

-- Partial: serves "what's still awaiting review", company-scoped or global,
-- without carrying the (majority, once mapped) resolved rows in the index.
create index company_line_items_unreviewed_idx on company_line_items (company_id)
  where mapping_status = 'unreviewed';

create trigger company_line_items_set_updated_at
  before update on company_line_items
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger company_line_items_set_updated_at on company_line_items;
drop table company_line_items;
