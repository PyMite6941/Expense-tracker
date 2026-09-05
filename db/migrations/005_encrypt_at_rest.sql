-- ============================================================================
-- Finance Kit — application-level encryption at rest
--
--   psql "$DATABASE_URL" -f db/migrations/005_encrypt_at_rest.sql
--
-- WHAT THIS DEFENDS AGAINST
--   A leaked or stolen database credential, a dumped backup, a snapshot copied
--   somewhere it should not be, or support staff with read access to the DB.
--   In every one of those the rows are ciphertext.
--
-- WHAT IT DOES NOT DEFEND AGAINST
--   The application itself. Finance Kit holds the key (from Secret Manager via
--   ET_ENCRYPTION_KEY) because the server has to compute net worth, forecasts
--   and anomalies for hosted users. This is encryption at rest, NOT
--   zero-knowledge. Anyone who has both the database AND the app's key can
--   read the data — that is the deliberate trade for keeping the analytics
--   working, and it is what "encrypt the stored data" means here.
--
--   The provider (Neon) also encrypts the underlying disk. This layer is on
--   top, so a credential leak is not enough on its own.
--
-- WHY A SINGLE COLUMN RATHER THAN ENCRYPTING EACH FIELD
--   `price numeric(14,2)` and `date date` cannot hold ciphertext without
--   becoming text and losing their types entirely. More importantly the app
--   never filters or aggregates on these values in SQL — every query is
--   `where org_id = %s` and `order by id`, and the maths happens in Python on
--   the whole snapshot. So moving the sensitive fields into one encrypted
--   payload costs nothing and keeps id/org_id/created_at in the clear for
--   indexing, joins, the audit trail and the concurrency check.
-- ============================================================================

-- Each finance table gains an encrypted payload. The plaintext columns stay in
-- place for now so an existing deployment can be migrated and verified before
-- they are dropped — see the commented-out step at the bottom.
do $$
declare
  t text;
begin
  foreach t in array array[
    'expenses','income','budgets','subscriptions','goals',
    'recurring_expenses','recurring_income','assets','liabilities'
  ]
  loop
    execute format('alter table %I add column if not exists enc bytea', t);
    execute format(
      'comment on column %I.enc is %L', t,
      'AES-256-GCM ciphertext of this row''s fields. Written by '
      'CLI/core/storage.py; the key lives in ET_ENCRYPTION_KEY, never in the DB.');
  end loop;
end $$;

-- The accounts blob gets the same treatment. It is jsonb today (004), so the
-- encrypted form goes in its own column rather than changing that one's type.
alter table organizations
  add column if not exists accounts_enc bytea;

comment on column organizations.accounts_enc is
  'AES-256-GCM ciphertext of accounts_data. When set, accounts_data is unused.';

-- Records which key version wrote a row, so a future key rotation can re-wrap
-- rows in batches instead of needing every row rewritten at once.
alter table organizations
  add column if not exists enc_key_version integer not null default 1;

-- ---------------------------------------------------------------------------
-- AFTER verifying that reads come back correct with ET_ENCRYPTION_KEY set,
-- drop the plaintext. Left commented because it is irreversible and should be
-- a deliberate, separate step once you have a backup you trust.
-- ---------------------------------------------------------------------------
-- alter table expenses            drop column price, drop column purchased,
--                                 drop column tags,  drop column date,
--                                 drop column currency, drop column notes;
-- ... and the equivalent for the other eight tables.
