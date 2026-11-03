-- ============================================================================
-- GRID Expense Tracker — accounts (hosted mode)
--
-- Run with:
--   psql "$DATABASE_URL" -f db/migrations/004_accounts.sql
--   (or paste into the Neon SQL editor)
--
-- Accounts are the second half of the data blob that `open_file` returns:
--
--     {"finance_data": {<the nine lists>}, "accounts_data": {...}}
--
-- Stored as a single jsonb column rather than a normalized `accounts` table,
-- ON PURPOSE and FOR NOW:
--
--   * The account record shape is still being designed — whether accounts are
--     one object or a keyed collection, and which fields each `type` carries,
--     are open questions. A normalized table would need a fresh migration (and
--     a backfill of live tenant data) on every one of those changes.
--   * jsonb round-trips whatever shape the app writes, so the model can move
--     without the hosted deployment lagging behind the local one.
--   * It costs nothing to normalize later: read the column, write the rows,
--     drop the column. Doing it now would cost a migration per iteration.
--
-- The tradeoff is real and worth stating: until this is a table, accounts
-- cannot be queried, indexed, joined or constrained in SQL, and the whole blob
-- is rewritten on every save. That is acceptable while an org's accounts are a
-- handful of small records. Revisit when the shape settles, or when anything
-- needs to query across accounts server-side.
--
-- Concurrency is unchanged: `accounts_data` is written inside the same
-- transaction and the same `data_version` check as the finance tables, so a
-- stale writer still loses cleanly (see 003_concurrency.sql).
-- ============================================================================

alter table organizations
  add column if not exists accounts_data jsonb not null default '{}'::jsonb;

comment on column organizations.accounts_data is
  'The accounts_data half of the app data blob. Deliberately schemaless while '
  'the account record shape is in flux — see db/migrations/004_accounts.sql.';
