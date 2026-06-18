-- 0013_chat_sessions.sql
-- The AI chatbot (routers/chatbot.py) and the chat retention job
-- (services/analytics_jobs.py) both read/write chat_sessions, but no migration ever
-- created it — so the chatbot cannot run on a freshly migrated database. This adds
-- the table, its RLS policy, and preserves chatbot access for existing tenants.
--
-- Idempotent and safe to re-run.

CREATE TABLE IF NOT EXISTS chat_sessions (
    -- Non-guessable session id: a customer resumes their own chat only via this
    -- token, and RLS scopes it to the tenant.
    id text PRIMARY KEY DEFAULT gen_random_uuid()::text,
    restaurant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    user_id text,
    cart jsonb NOT NULL DEFAULT '[]'::jsonb,
    stage varchar(40) NOT NULL DEFAULT 'browsing',
    guest_info jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_tenant_updated
    ON chat_sessions (restaurant_id, updated_at DESC);

-- Row-Level Security (matches the model established in migration 0012).
-- Guarded so this migration still works if 0012's app role/schema are absent.
DO $$
BEGIN
    IF to_regprocedure('app.current_tenant()') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON chat_sessions';
        EXECUTE 'CREATE POLICY tenant_isolation ON chat_sessions '
                'USING (restaurant_id = app.current_tenant() OR app.is_platform()) '
                'WITH CHECK (restaurant_id = app.current_tenant() OR app.is_platform())';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'order_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON chat_sessions TO order_app';
    END IF;
END $$;

-- Preserve current behaviour: tenants that exist today keep chatbot access even
-- though the chatbot is now plan-gated. New tenants follow their plan entitlements.
INSERT INTO tenant_feature_overrides (tenant_id, feature_key, enabled, reason)
SELECT r.id, 'ai.chatbot', true, 'preserved on 0013 (chatbot was ungated before)'
FROM restaurants r
WHERE EXISTS (SELECT 1 FROM feature_definitions f WHERE f.feature_key = 'ai.chatbot')
ON CONFLICT (tenant_id, feature_key) DO NOTHING;
