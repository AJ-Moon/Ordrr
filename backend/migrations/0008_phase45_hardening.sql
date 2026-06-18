CREATE TABLE IF NOT EXISTS intervention_request_windows (
    tenant_id integer NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    scope varchar(60) NOT NULL,
    window_start timestamptz NOT NULL,
    request_count integer NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, scope, window_start)
);
CREATE INDEX IF NOT EXISTS idx_intervention_windows_cleanup ON intervention_request_windows (window_start);
