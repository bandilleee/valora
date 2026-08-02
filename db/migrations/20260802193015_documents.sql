-- migrate:up

create table documents (
  id bigint generated always as identity primary key,

  -- Known at ingest time, before classification, derived from the raw bytes
  -- with no parsing required. NOT NULL: the row is created at ingest so
  -- sha256-based dedupe (M3.4) can look up existing rows before
  -- classification ever runs, and an ingested PDF that later fails
  -- classification still has a durable record instead of being lost.
  s3_key text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  ingested_at timestamptz not null default now(),

  -- Requires successfully opening the PDF (PyMuPDF, first appears M4.1) —
  -- unlike s3_key/sha256, this is not a pure function of the raw bytes.
  -- Nullable: a corrupt file, truncated download, HTML error page saved as
  -- .pdf, or encrypted document must still get a durable ingest row. NULL
  -- means the document has not been successfully parsed yet.
  page_count integer,

  -- Determined by classification, which runs after ingest and can fail or
  -- be delayed. NULL means "not yet classified", not "unknown forever".
  company_id bigint references companies (id) on delete restrict,
  doc_type text check (doc_type in (
    'annual_report', 'interim_results', 'results_presentation', 'excel_databook'
  )),
  fiscal_period text,
  published_at date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint documents_s3_key_key unique (s3_key),
  constraint documents_sha256_key unique (sha256)
);

comment on column documents.published_at is
  'The date the COMPANY published this filing (day precision only, from the document itself). Not the same as ingested_at.';
comment on column documents.ingested_at is
  'The exact instant Valora first stored this document. Not the same as published_at.';
comment on column documents.fiscal_period is
  'Human-readable label for the period the document AS A WHOLE covers (e.g. FY2025, H1 2025). Distinct from facts.period_start/period_end/period_type, which give exact per-fact period boundaries since one document can contain comparative-period facts.';
comment on column documents.page_count is
  'NULL means the document has not been successfully parsed yet (e.g. corrupt file, truncated download, encrypted PDF) — not that it has zero pages.';

create index documents_company_id_idx on documents (company_id);

create trigger documents_set_updated_at
  before update on documents
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger documents_set_updated_at on documents;
drop table documents;
