-- ============================================================================
-- GRID Expense Tracker — optimistic concurrency control
--
-- The app's data flow is read-modify-write over the whole dataset
-- (open_file -> mutate -> write_file). With multiple employees in one org that
-- is a lost-update hazard: A and B both load, both save, and A's changes vanish.
--
-- `data_version` is bumped on every write and checked against the version the
-- writer loaded. A stale write is REJECTED rather than silently clobbering —
-- PostgresStore raises ConcurrentModificationError so the UI can reload+retry.
-- ============================================================================

alter table organizations
  add column if not exists data_version bigint not null default 0;
