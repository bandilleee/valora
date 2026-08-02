-- migrate:up

-- Reusable trigger function for updated_at. Created once here; later tables'
-- migrations reference this same function rather than redefining it.
create function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table companies (
  id bigint generated always as identity primary key,
  name text not null,
  jse_code text not null,
  sector text,
  archetype text not null check (archetype in ('retail', 'bank')),
  fye_month smallint not null check (fye_month between 1 and 12),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint companies_jse_code_key unique (jse_code)
);

create trigger companies_set_updated_at
  before update on companies
  for each row
  execute function set_updated_at();

-- migrate:down

drop trigger companies_set_updated_at on companies;
drop table companies;
drop function set_updated_at();
