-- ============================================================================
-- GRID Expense Tracker — Purchase → access hand-off
-- Target: Neon Postgres. Depends on 001_enterprise_schema.sql.
--
-- Flow:
--   1. Buyer pays on the GRID web-store. The grid-store-worker (Cloudflare)
--      verifies the USDC payment, mints the license JWT (unchanged), and ALSO
--      upserts a row into `entitlements` here via the Neon serverless driver.
--   2. Entitlements are keyed by EMAIL, not user id, because at purchase time
--      the buyer has no account yet.
--   3. On first sign-in the backend calls claim_entitlements(user_id, email);
--      it creates/updates the buyer's organization to the purchased plan and
--      links the row.
-- ============================================================================

create table if not exists entitlements (
  id          bigint generated always as identity primary key,
  email       text not null,                       -- lowercased buyer email (join key)
  product     text not null default 'expense_tracker_hosted',
  plan        org_plan not null,                   -- what they bought: pro | max
  license_jti text,                                -- jti of the minted license JWT
  order_id    text unique,                         -- tx hash — idempotency key from the worker
  status      text not null default 'active',      -- active | lapsed | revoked
  expires_at  timestamptz,                         -- end of the paid window (e.g. +31d)
  org_id      bigint references organizations (id),-- filled once claimed
  claimed_at  timestamptz,
  granted_at  timestamptz not null default now()
);

create index if not exists entitlements_email_idx on entitlements (lower(email));

-- ---------------------------------------------------------------------------
-- claim_entitlements(user_id, email): called by the backend right after login.
-- For each active, unclaimed entitlement matching the user's email:
--   * if they already admin an org, upgrade that org's plan;
--   * otherwise create a workspace org and make them its admin;
-- then link + mark the entitlement claimed. Idempotent; safe to call every login.
-- ---------------------------------------------------------------------------
create or replace function claim_entitlements(p_user_id text, p_email text)
returns jsonb
language plpgsql
as $$
declare
  v_email   text := lower(p_email);
  ent       record;
  v_org     bigint;
  n_claimed int := 0;
begin
  if p_user_id is null or v_email is null then
    return jsonb_build_object('error', 'user_id and email required');
  end if;

  for ent in
    select * from entitlements
    where lower(email) = v_email
      and status = 'active'
      and claimed_at is null
    order by granted_at
  loop
    -- Reuse an org the user already administers; else create one.
    select org_id into v_org
      from members
      where user_id = p_user_id and role = 'admin'
      order by org_id
      limit 1;

    if v_org is null then
      insert into organizations (name, plan, license_jti, created_by)
      values (split_part(v_email, '@', 1) || '''s workspace',
              ent.plan, ent.license_jti, p_user_id)
      returning id into v_org;

      insert into members (org_id, user_id, email, role)
      values (v_org, p_user_id, v_email, 'admin');
    else
      update organizations
        set plan = ent.plan, license_jti = ent.license_jti
        where id = v_org;
    end if;

    update entitlements
      set claimed_at = now(), org_id = v_org
      where id = ent.id;

    n_claimed := n_claimed + 1;
  end loop;

  -- Always resolve the caller's org, even when nothing new was claimed — the
  -- app calls this on every login and needs the org_id back each time.
  if v_org is null then
    select org_id into v_org
      from members
      where user_id = p_user_id
      order by (role = 'admin') desc, org_id
      limit 1;
  end if;

  return jsonb_build_object('claimed', n_claimed, 'org_id', v_org);
end $$;

-- ---------------------------------------------------------------------------
-- revert_lapsed_entitlements(): downgrade orgs whose paid window ended.
-- Schedule from a Cloudflare cron or pg_cron (Neon supports pg_cron).
-- ---------------------------------------------------------------------------
create or replace function revert_lapsed_entitlements()
returns integer
language plpgsql
as $$
declare n int;
begin
  with lapsed as (
    update entitlements
      set status = 'lapsed'
      where status = 'active'
        and expires_at is not null
        and expires_at < now()
      returning org_id
  )
  update organizations o
    set plan = 'free'
    from lapsed l
    where o.id = l.org_id;
  get diagnostics n = row_count;
  return n;
end $$;
