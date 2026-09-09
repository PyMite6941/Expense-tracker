-- ============================================================================
-- Finance Kit — charge a transaction to an account
--
--   psql "$DATABASE_URL" -f db/migrations/006_account_links.sql
--
-- Nullable on purpose: every existing row stays valid, and assigning an account
-- remains optional. A transaction with no account still counts towards your
-- totals, it just does not move any account's balance.
--
-- ON DELETE SET NULL rather than CASCADE: deleting an account must never delete
-- the spending that went through it. You lose the link, not the history.
-- ============================================================================

alter table expenses add column if not exists account_id bigint;
alter table income   add column if not exists account_id bigint;

comment on column expenses.account_id is
  'Account this was charged to. NULL = unassigned. Also carried inside `enc` '
  'when encryption at rest is on.';
comment on column income.account_id is
  'Account this was paid into. NULL = unassigned.';

-- Accounts live in organizations.accounts_data / accounts_enc rather than their
-- own table, so this cannot be a real foreign key yet. The app enforces it, and
-- normalize_blob drops a link whose account no longer exists.
create index if not exists expenses_account_idx on expenses (org_id, account_id);
create index if not exists income_account_idx   on income   (org_id, account_id);
