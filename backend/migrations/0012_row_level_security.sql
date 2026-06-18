-- 0012_row_level_security.sql
-- TRUE database-enforced tenant isolation.
--
-- Until now isolation depended on every query carrying "WHERE restaurant_id = %s".
-- This migration makes the database itself refuse cross-tenant access, so a missing
-- or wrong WHERE clause can no longer leak another restaurant's data.
--
-- Model:
--   * The app connects as role  order_app  (NOBYPASSRLS).
--   * Each request sets two session GUCs via db.py:
--       app.tenant_id   -> the resolved tenant id   (empty when none)
--       app.is_platform -> 'on' for super-admin / system operations
--   * Every tenant-owned table gets a policy:
--       USING (tenant_col = app.current_tenant() OR app.is_platform())
--     so with no tenant context and no platform flag, ZERO rows are visible.
--
-- Deploy notes:
--   * This migration is idempotent.
--   * After applying, give the role a password and point DATABASE_URL at it:
--       ALTER ROLE order_app WITH LOGIN PASSWORD '<strong-secret>';
--     The application code is a no-op when still connected as the owner/superuser
--     (RLS is bypassed), so you can deploy code first and cut over the role last.

-- ─────────────────────────────────────────────────────────────────────────────
-- Helper schema + context accessors
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_tenant() RETURNS integer
    LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')::integer
$$;

CREATE OR REPLACE FUNCTION app.is_platform() RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT COALESCE(current_setting('app.is_platform', true), 'off') = 'on'
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Application role (no BYPASSRLS). Created without LOGIN so no secret lives in
-- the repo; the operator enables login + password at deploy time.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'order_app') THEN
        CREATE ROLE order_app NOLOGIN NOBYPASSRLS;
    ELSE
        ALTER ROLE order_app NOBYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public, app TO order_app;
GRANT EXECUTE ON FUNCTION app.current_tenant(), app.is_platform() TO order_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO order_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO order_app;
-- Cover any tables/sequences created by later migrations too.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO order_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO order_app;

-- ─────────────────────────────────────────────────────────────────────────────
-- Tenant-scoped tables: enable forced RLS + standard policy, generated for every
-- table that has a restaurant_id or tenant_id column.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    r            record;
    tenant_col   text;
BEGIN
    FOR r IN
        SELECT t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
    LOOP
        -- Bootstrap / reference / non-tenant tables handled separately below.
        IF r.table_name IN (
            'restaurants','domains','platform_admins','plans','plan_entitlements',
            'feature_definitions','schema_migrations','auth_rate_windows','order_claims'
        ) THEN
            CONTINUE;
        END IF;

        SELECT c.column_name INTO tenant_col
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.table_name = r.table_name
          AND c.column_name IN ('restaurant_id','tenant_id')
        ORDER BY CASE c.column_name WHEN 'tenant_id' THEN 0 ELSE 1 END
        LIMIT 1;

        IF tenant_col IS NULL THEN
            CONTINUE;  -- no tenant column; not a tenant-owned table
        END IF;

        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', r.table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I', r.table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON public.%I '
            'USING (%I = app.current_tenant() OR app.is_platform()) '
            'WITH CHECK (%I = app.current_tenant() OR app.is_platform())',
            r.table_name, tenant_col, tenant_col
        );
    END LOOP;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Bootstrap / reference tables.
-- These must be readable BEFORE a tenant context exists (host->tenant resolution,
-- admin/platform login, entitlement lookups). Reads are open to the app role;
-- writes are restricted to platform/system operations.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'restaurants','domains','platform_admins','plans','plan_entitlements','feature_definitions'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', tbl);
        EXECUTE format('DROP POLICY IF EXISTS reference_read ON public.%I', tbl);
        EXECUTE format('DROP POLICY IF EXISTS reference_write ON public.%I', tbl);
        EXECUTE format('CREATE POLICY reference_read ON public.%I FOR SELECT USING (true)', tbl);
        EXECUTE format(
            'CREATE POLICY reference_write ON public.%I FOR ALL '
            'USING (app.is_platform()) WITH CHECK (app.is_platform())', tbl
        );
    END LOOP;
END $$;

-- order_claims has no tenant column; scope it through its parent order.
ALTER TABLE public.order_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_claims FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.order_claims;
CREATE POLICY tenant_isolation ON public.order_claims
    USING (
        app.is_platform()
        OR EXISTS (SELECT 1 FROM public.orders o
                   WHERE o.id = order_claims.order_id AND o.restaurant_id = app.current_tenant())
    )
    WITH CHECK (
        app.is_platform()
        OR EXISTS (SELECT 1 FROM public.orders o
                   WHERE o.id = order_claims.order_id AND o.restaurant_id = app.current_tenant())
    );

-- auth_rate_windows and schema_migrations are global infrastructure tables (no
-- tenant data); the app role may use them freely. No RLS.
