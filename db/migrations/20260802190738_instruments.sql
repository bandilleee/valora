-- migrate:up

create table instruments (
  id bigint generated always as identity primary key,
  company_id bigint not null references companies (id) on delete restrict,
  isin text not null,
  share_code text not null,
  class text not null check (class in ('ordinary', 'n_ordinary', 'preference')),
  listed_from date not null,
  listed_to date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint instruments_isin_key unique (isin),
  constraint instruments_share_code_key unique (share_code),
  constraint instruments_listed_to_after_listed_from
    check (listed_to is null or listed_to > listed_from)
);

comment on column instruments.listed_to is
  'NULL means the instrument is currently listed.';

create index instruments_company_id_idx on instruments (company_id);

create trigger instruments_set_updated_at
  before update on instruments
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger instruments_set_updated_at on instruments;
drop table instruments;
