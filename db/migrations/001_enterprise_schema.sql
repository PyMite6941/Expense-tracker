-- ============================================================================
-- GRID Expense Tracker — Enterprise (multi-tenant) schema
-- Target: Neon Postgres (any standard Postgres works). Run with:
--   psql "$DATABASE_URL" -f db/migrations/001_enterprise_schema.sql
--   (or paste into the Neon SQL editor)
--
-- Design:
--   * Every finance row is scoped to an organization (org_id).
--   * Tenancy is enforced in the BACKEND: only the FastAPI/Streamlit server and
--     the Cloudflare worker touch this DB (both server-side, with the connection
--     string) — no untrusted browser talks to it directly. So the app always
--     filters by the authenticated user's org_id. (Neon RLS can be layered on
--     later as defense-in-depth; it is intentionally NOT required here.)
--   * user ids are `text` so any auth provider fits — Clerk ('user_abc…'),
--     a UUID, or an email. Auth provider is a Phase-3 decision (Clerk recommended).
--   * Column names mirror the existing data.json record shapes so the
--     PostgresStore backend (de)serializes into the same dicts the app uses.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type member_role as enum ('admin', 'member', 'viewer');
exception when duplicate_object then null; end $$;

do $$ begin
  create type org_plan as enum ('free', 'pro', 'max');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- Core tenancy tables
-- ---------------------------------------------------------------------------
create table if not exists organizations (
  id          bigint generated always as identity primary key,
  name        text not null,
  plan        org_plan not null default 'free',
  license_jti text,                       -- links to the license JWT `jti` (paid features)
  created_by  text not null,              -- auth user id (Clerk id / uuid / email)
  created_at  timestamptz not null default now()
);

create table if not exists members (
  id        bigint generated always as identity primary key,
  org_id    bigint not null references organizations (id) on delete cascade,
  user_id   text   not null,              -- auth user id
  email     text,                         -- convenience copy for invites/joins
  role      member_role not null default 'member',
  joined_at timestamptz not null default now(),
  unique (org_id, user_id)
);

create index if not exists members_user_idx on members (user_id);
create index if not exists members_org_idx  on members (org_id);

create table if not exists org_invites (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  email      text not null,
  role       member_role not null default 'member',
  token      uuid not null default gen_random_uuid(),
  invited_by text not null,               -- auth user id of the inviter
  accepted   boolean not null default false,
  created_at timestamptz not null default now(),
  unique (org_id, email)
);

-- ---------------------------------------------------------------------------
-- Finance tables (one per data.json list). All org-scoped.
-- Shared columns: id, org_id, created_by, created_at, updated_at.
-- ---------------------------------------------------------------------------
create table if not exists expenses (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  price      numeric(14,2) not null,
  purchased  text,
  tags       text,
  date       date,
  currency   text not null default 'usd',
  notes      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists income (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  amount     numeric(14,2) not null,
  source     text,
  date       date,
  currency   text not null default 'usd',
  notes      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists budgets (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  category   text not null,
  amount     numeric(14,2) not null,
  currency   text not null default 'usd',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists subscriptions (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  name       text,
  price      numeric(14,2) not null,
  currency   text not null default 'usd',
  start_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists goals (
  id                 bigint generated always as identity primary key,
  org_id             bigint not null references organizations (id) on delete cascade,
  created_by         text,
  name               text,
  amount             numeric(14,2) not null,
  start_date         date,
  month_contribution numeric(14,2),
  currency           text not null default 'usd',
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create table if not exists recurring_expenses (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  amount     numeric(14,2) not null,
  purchased  text,
  tags       text,
  currency   text not null default 'usd',
  created_at timestamptz not null default now()
);

create table if not exists recurring_income (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  amount     numeric(14,2) not null,
  source     text,
  currency   text not null default 'usd',
  created_at timestamptz not null default now()
);

create table if not exists assets (
  id         bigint generated always as identity primary key,
  org_id     bigint not null references organizations (id) on delete cascade,
  created_by text,
  name       text not null,
  type       text,
  value      numeric(14,2) not null,
  currency   text not null default 'usd',
  notes      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists liabilities (
  id            bigint generated always as identity primary key,
  org_id        bigint not null references organizations (id) on delete cascade,
  created_by    text,
  name          text not null,
  type          text,
  balance       numeric(14,2) not null,
  currency      text not null default 'usd',
  interest_rate numeric(8,4) not null default 0,
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Index org_id on every finance table (the hot filter path for tenant queries).
do $$
declare t text;
begin
  foreach t in array array[
    'expenses','income','budgets','subscriptions','goals',
    'recurring_expenses','recurring_income','assets','liabilities'
  ] loop
    execute format('create index if not exists %I_org_idx on %I (org_id)', t, t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Audit log (append-only; every mutation on a finance row lands here)
-- ---------------------------------------------------------------------------
create table if not exists audit_log (
  id        bigint generated always as identity primary key,
  org_id    bigint not null references organizations (id) on delete cascade,
  actor     text,                 -- auth user id
  action    text not null,        -- 'create' | 'update' | 'delete'
  entity    text not null,        -- table name
  entity_id bigint,
  before    jsonb,
  after     jsonb,
  ts        timestamptz not null default now()
);
create index if not exists audit_org_idx on audit_log (org_id, ts desc);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

do $$
declare t text;
begin
  foreach t in array array[
    'expenses','income','budgets','subscriptions','goals','assets','liabilities'
  ] loop
    execute format(
      'drop trigger if exists %1$s_touch on %1$I;
       create trigger %1$s_touch before update on %1$I
         for each row execute function touch_updated_at()', t);
  end loop;
end $$;
