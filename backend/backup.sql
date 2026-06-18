--
-- PostgreSQL database dump
--

\restrict 9cPaowPYlIASR5tyUhDE8qx16tjmE8f7PQnzmNZXF7MihhjQryifxeSfXLkE0Ql

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA extensions;


--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql;


--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql_public;


--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA pgbouncer;


--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA realtime;


--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA storage;


--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA vault;


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


--
-- Name: oauth_authorization_status; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_authorization_status AS ENUM (
    'pending',
    'approved',
    'denied',
    'expired'
);


--
-- Name: oauth_client_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_client_type AS ENUM (
    'public',
    'confidential'
);


--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


--
-- Name: oauth_response_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_response_type AS ENUM (
    'code'
);


--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


--
-- Name: action; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in'
);


--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


--
-- Name: buckettype; Type: TYPE; Schema: storage; Owner: -
--

CREATE TYPE storage.buckettype AS ENUM (
    'STANDARD',
    'ANALYTICS',
    'VECTOR'
);


--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
begin
    if not exists (
        select 1
        from pg_event_trigger_ddl_commands() ev
        join pg_catalog.pg_extension e on ev.objid = e.oid
        where e.extname = 'pg_graphql'
    ) then
        return;
    end if;

    drop function if exists graphql_public.graphql;
    create or replace function graphql_public.graphql(
        "operationName" text default null,
        query text default null,
        variables jsonb default null,
        extensions jsonb default null
    )
        returns jsonb
        language sql
    as $$
        select graphql.resolve(
            query := query,
            variables := coalesce(variables, '{}'),
            "operationName" := "operationName",
            extensions := extensions
        );
    $$;

    -- Attach the wrapper to the extension so DROP EXTENSION cascades to it,
    -- which in turn triggers set_graphql_placeholder to reinstall the "not enabled" stub.
    alter extension pg_graphql add function graphql_public.graphql(text, text, jsonb, jsonb);

    grant usage on schema graphql to postgres, anon, authenticated, service_role;
    grant execute on function graphql.resolve to postgres, anon, authenticated, service_role;
    grant usage on schema graphql to postgres with grant option;
    grant usage on schema graphql_public to postgres with grant option;
end;
$_$;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_roles
      WHERE rolname = 'supabase_functions_admin'
    )
    THEN
      CREATE USER supabase_functions_admin NOINHERIT CREATEROLE LOGIN NOREPLICATION;
    END IF;

    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    IF EXISTS (
      SELECT FROM pg_extension
      WHERE extname = 'pg_net'
      -- all versions in use on existing projects as of 2025-02-20
      -- version 0.12.0 onwards don't need these applied
      AND extversion IN ('0.2', '0.6', '0.7', '0.7.1', '0.8', '0.10.0', '0.11.0')
    ) THEN
      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

      REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

      GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
      GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    END IF;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: graphql(text, text, jsonb, jsonb); Type: FUNCTION; Schema: graphql_public; Owner: -
--

CREATE FUNCTION graphql_public.graphql("operationName" text DEFAULT NULL::text, query text DEFAULT NULL::text, variables jsonb DEFAULT NULL::jsonb, extensions jsonb DEFAULT NULL::jsonb) RETURNS jsonb
    LANGUAGE plpgsql
    AS $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: -
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO ''
    AS $_$
  BEGIN
      RAISE DEBUG 'PgBouncer auth request: %', p_usename;

      RETURN QUERY
      SELECT
          rolname::text,
          CASE WHEN rolvaliduntil < now()
              THEN null
              ELSE rolpassword::text
          END
      FROM pg_authid
      WHERE rolname=$1 and rolcanlogin;
  END;
  $_$;


--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
-- Regclass of the table e.g. public.notes
entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

-- I, U, D, T: insert, update ...
action realtime.action = (
    case wal ->> 'action'
        when 'I' then 'INSERT'
        when 'U' then 'UPDATE'
        when 'D' then 'DELETE'
        else 'ERROR'
    end
);

-- Is row level security enabled for the table
is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

subscriptions realtime.subscription[] = array_agg(subs)
    from
        realtime.subscription subs
    where
        subs.entity = entity_
        -- Filter by action early - only get subscriptions interested in this action
        -- action_filter column can be: '*' (all), 'INSERT', 'UPDATE', or 'DELETE'
        and (subs.action_filter = '*' or subs.action_filter = action::text);

-- Subscription vars
roles regrole[] = array_agg(distinct us.claims_role::text)
    from
        unnest(subscriptions) us;

working_role regrole;
claimed_role regrole;
claims jsonb;

subscription_id uuid;
subscription_has_access bool;
visible_to_subscription_ids uuid[] = '{}';

-- structured info for wal's columns
columns realtime.wal_column[];
-- previous identity values for update/delete
old_columns realtime.wal_column[];

error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

-- Primary jsonb output for record
output jsonb;

begin
perform set_config('role', null, true);

columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'columns') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

old_columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'identity') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

for working_role in select * from unnest(roles) loop

    -- Update `is_selectable` for columns and old_columns
    columns =
        array_agg(
            (
                c.name,
                c.type_name,
                c.type_oid,
                c.value,
                c.is_pkey,
                pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
            )::realtime.wal_column
        )
        from
            unnest(columns) c;

    old_columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(old_columns) c;

    if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            -- subscriptions is already filtered by entity
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 400: Bad Request, no primary key']
        )::realtime.wal_rls;

    -- The claims role does not have SELECT permission to the primary key of entity
    elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 401: Unauthorized']
        )::realtime.wal_rls;

    else
        output = jsonb_build_object(
            'schema', wal ->> 'schema',
            'table', wal ->> 'table',
            'type', action,
            'commit_timestamp', to_char(
                ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
            ),
            'columns', (
                select
                    jsonb_agg(
                        jsonb_build_object(
                            'name', pa.attname,
                            'type', pt.typname
                        )
                        order by pa.attnum asc
                    )
                from
                    pg_attribute pa
                    join pg_type pt
                        on pa.atttypid = pt.oid
                where
                    attrelid = entity_
                    and attnum > 0
                    and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
            )
        )
        -- Add "record" key for insert and update
        || case
            when action in ('INSERT', 'UPDATE') then
                jsonb_build_object(
                    'record',
                    (
                        select
                            jsonb_object_agg(
                                -- if unchanged toast, get column name and value from old record
                                coalesce((c).name, (oc).name),
                                case
                                    when (c).name is null then (oc).value
                                    else (c).value
                                end
                            )
                        from
                            unnest(columns) c
                            full outer join unnest(old_columns) oc
                                on (c).name = (oc).name
                        where
                            coalesce((c).is_selectable, (oc).is_selectable)
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                    )
                )
            else '{}'::jsonb
        end
        -- Add "old_record" key for update and delete
        || case
            when action = 'UPDATE' then
                jsonb_build_object(
                        'old_record',
                        (
                            select jsonb_object_agg((c).name, (c).value)
                            from unnest(old_columns) c
                            where
                                (c).is_selectable
                                and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                        )
                    )
            when action = 'DELETE' then
                jsonb_build_object(
                    'old_record',
                    (
                        select jsonb_object_agg((c).name, (c).value)
                        from unnest(old_columns) c
                        where
                            (c).is_selectable
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                    )
                )
            else '{}'::jsonb
        end;

        -- Create the prepared statement
        if is_rls_enabled and action <> 'DELETE' then
            if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                deallocate walrus_rls_stmt;
            end if;
            execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
        end if;

        visible_to_subscription_ids = '{}';

        for subscription_id, claims in (
                select
                    subs.subscription_id,
                    subs.claims
                from
                    unnest(subscriptions) subs
                where
                    subs.entity = entity_
                    and subs.claims_role = working_role
                    and (
                        realtime.is_visible_through_filters(columns, subs.filters)
                        or (
                          action = 'DELETE'
                          and realtime.is_visible_through_filters(old_columns, subs.filters)
                        )
                    )
        ) loop

            if not is_rls_enabled or action = 'DELETE' then
                visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
            else
                -- Check if RLS allows the role to see the record
                perform
                    -- Trim leading and trailing quotes from working_role because set_config
                    -- doesn't recognize the role as valid if they are included
                    set_config('role', trim(both '"' from working_role::text), true),
                    set_config('request.jwt.claims', claims::text, true);

                execute 'execute walrus_rls_stmt' into subscription_has_access;

                if subscription_has_access then
                    visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
                end if;
            end if;
        end loop;

        perform set_config('role', null, true);

        return next (
            output,
            is_rls_enabled,
            visible_to_subscription_ids,
            case
                when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                else '{}'
            end
        )::realtime.wal_rls;

    end if;
end loop;

perform set_config('role', null, true);
end;
$$;


--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
declare
  res jsonb;
begin
  if type_::text = 'bytea' then
    return to_jsonb(val);
  end if;
  execute format('select to_jsonb(%L::'|| type_::text || ')', val) into res;
  return res;
end
$$;


--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
      /*
      Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
      */
      declare
          op_symbol text = (
              case
                  when op = 'eq' then '='
                  when op = 'neq' then '!='
                  when op = 'lt' then '<'
                  when op = 'lte' then '<='
                  when op = 'gt' then '>'
                  when op = 'gte' then '>='
                  when op = 'in' then '= any'
                  else 'UNKNOWN OP'
              end
          );
          res boolean;
      begin
          execute format(
              'select %L::'|| type_::text || ' ' || op_symbol
              || ' ( %L::'
              || (
                  case
                      when op = 'in' then type_::text || '[]'
                      else type_::text end
              )
              || ')', val_1, val_2) into res;
          return res;
      end;
      $$;


--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $_$
    /*
    Should the record be visible (true) or filtered out (false) after *filters* are applied
    */
        select
            -- Default to allowed when no filters present
            $2 is null -- no filters. this should not happen because subscriptions has a default
            or array_length($2, 1) is null -- array length of an empty array is null
            or bool_and(
                coalesce(
                    realtime.check_equality_op(
                        op:=f.op,
                        type_:=coalesce(
                            col.type_oid::regtype, -- null when wal2json version <= 2.4
                            col.type_name::regtype
                        ),
                        -- cast jsonb to text
                        val_1:=col.value #>> '{}',
                        val_2:=f.value
                    ),
                    false -- if null, filter does not match
                )
            )
        from
            unnest(filters) f
            join unnest(columns) col
                on f.column_name = col.name;
    $_$;


--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS TABLE(wal jsonb, is_rls_enabled boolean, subscription_ids uuid[], errors text[], slot_changes_count bigint)
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
    AS $$
  WITH pub AS (
    SELECT
      concat_ws(
        ',',
        CASE WHEN bool_or(pubinsert) THEN 'insert' ELSE NULL END,
        CASE WHEN bool_or(pubupdate) THEN 'update' ELSE NULL END,
        CASE WHEN bool_or(pubdelete) THEN 'delete' ELSE NULL END
      ) AS w2j_actions,
      coalesce(
        string_agg(
          realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
          ','
        ) filter (WHERE ppt.tablename IS NOT NULL AND ppt.tablename NOT LIKE '% %'),
        ''
      ) AS w2j_add_tables
    FROM pg_publication pp
    LEFT JOIN pg_publication_tables ppt ON pp.pubname = ppt.pubname
    WHERE pp.pubname = publication
    GROUP BY pp.pubname
    LIMIT 1
  ),
  -- MATERIALIZED ensures pg_logical_slot_get_changes is called exactly once
  w2j AS MATERIALIZED (
    SELECT x.*, pub.w2j_add_tables
    FROM pub,
         pg_logical_slot_get_changes(
           slot_name, null, max_changes,
           'include-pk', 'true',
           'include-transaction', 'false',
           'include-timestamp', 'true',
           'include-type-oids', 'true',
           'format-version', '2',
           'actions', pub.w2j_actions,
           'add-tables', pub.w2j_add_tables
         ) x
  ),
  -- Count raw slot entries before apply_rls/subscription filter
  slot_count AS (
    SELECT count(*)::bigint AS cnt
    FROM w2j
    WHERE w2j.w2j_add_tables <> ''
  ),
  -- Apply RLS and filter as before
  rls_filtered AS (
    SELECT xyz.wal, xyz.is_rls_enabled, xyz.subscription_ids, xyz.errors
    FROM w2j,
         realtime.apply_rls(
           wal := w2j.data::jsonb,
           max_record_bytes := max_record_bytes
         ) xyz(wal, is_rls_enabled, subscription_ids, errors)
    WHERE w2j.w2j_add_tables <> ''
      AND xyz.subscription_ids[1] IS NOT NULL
  )
  -- Real rows with slot count attached
  SELECT rf.wal, rf.is_rls_enabled, rf.subscription_ids, rf.errors, sc.cnt
  FROM rls_filtered rf, slot_count sc

  UNION ALL

  -- Sentinel row: always returned when no real rows exist so Elixir can
  -- always read slot_changes_count. Identified by wal IS NULL.
  SELECT null, null, null, null, sc.cnt
  FROM slot_count sc
  WHERE NOT EXISTS (SELECT 1 FROM rls_filtered)
$$;


--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
      select
        (
          select string_agg('' || ch,'')
          from unnest(string_to_array(nsp.nspname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
        )
        || '.'
        || (
          select string_agg('' || ch,'')
          from unnest(string_to_array(pc.relname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
          )
      from
        pg_class pc
        join pg_namespace nsp
          on pc.relnamespace = nsp.oid
      where
        pc.oid = entity
    $$;


--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  generated_id uuid;
  final_payload jsonb;
BEGIN
  BEGIN
    -- Generate a new UUID for the id
    generated_id := gen_random_uuid();

    -- Check if payload has an 'id' key, if not, add the generated UUID
    IF payload ? 'id' THEN
      final_payload := payload;
    ELSE
      final_payload := jsonb_set(payload, '{id}', to_jsonb(generated_id));
    END IF;

    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    -- Attempt to insert the message
    INSERT INTO realtime.messages (id, payload, event, topic, private, extension)
    VALUES (generated_id, final_payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      -- Capture and notify the error
      RAISE WARNING 'ErrorSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    /*
    Validates that the user defined filters for a subscription:
    - refer to valid columns that the claimed role may access
    - values are coercable to the correct column type
    */
    declare
        col_names text[] = coalesce(
                array_agg(c.column_name order by c.ordinal_position),
                '{}'::text[]
            )
            from
                information_schema.columns c
            where
                format('%I.%I', c.table_schema, c.table_name)::regclass = new.entity
                and pg_catalog.has_column_privilege(
                    (new.claims ->> 'role'),
                    format('%I.%I', c.table_schema, c.table_name)::regclass,
                    c.column_name,
                    'SELECT'
                );
        filter realtime.user_defined_filter;
        col_type regtype;

        in_val jsonb;
    begin
        for filter in select * from unnest(new.filters) loop
            -- Filtered column is valid
            if not filter.column_name = any(col_names) then
                raise exception 'invalid column for filter %', filter.column_name;
            end if;

            -- Type is sanitized and safe for string interpolation
            col_type = (
                select atttypid::regtype
                from pg_catalog.pg_attribute
                where attrelid = new.entity
                      and attname = filter.column_name
            );
            if col_type is null then
                raise exception 'failed to lookup type for column %', filter.column_name;
            end if;

            -- Set maximum number of entries for in filter
            if filter.op = 'in'::realtime.equality_op then
                in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
                if coalesce(jsonb_array_length(in_val), 0) > 100 then
                    raise exception 'too many values for `in` filter. Maximum 100';
                end if;
            else
                -- raises an exception if value is not coercable to type
                perform realtime.cast(filter.value, col_type);
            end if;

        end loop;

        -- Apply consistent order to filters so the unique constraint on
        -- (subscription_id, entity, filters) can't be tricked by a different filter order
        new.filters = coalesce(
            array_agg(f order by f.column_name, f.op, f.value),
            '{}'
        ) from unnest(new.filters) f;

        return new;
    end;
    $$;


--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


--
-- Name: allow_any_operation(text[]); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.allow_any_operation(expected_operations text[]) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
  WITH current_operation AS (
    SELECT storage.operation() AS raw_operation
  ),
  normalized AS (
    SELECT CASE
      WHEN raw_operation LIKE 'storage.%' THEN substr(raw_operation, 9)
      ELSE raw_operation
    END AS current_operation
    FROM current_operation
  )
  SELECT EXISTS (
    SELECT 1
    FROM normalized n
    CROSS JOIN LATERAL unnest(expected_operations) AS expected_operation
    WHERE expected_operation IS NOT NULL
      AND expected_operation <> ''
      AND n.current_operation = CASE
        WHEN expected_operation LIKE 'storage.%' THEN substr(expected_operation, 9)
        ELSE expected_operation
      END
  );
$$;


--
-- Name: allow_only_operation(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.allow_only_operation(expected_operation text) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
  WITH current_operation AS (
    SELECT storage.operation() AS raw_operation
  ),
  normalized AS (
    SELECT
      CASE
        WHEN raw_operation LIKE 'storage.%' THEN substr(raw_operation, 9)
        ELSE raw_operation
      END AS current_operation,
      CASE
        WHEN expected_operation LIKE 'storage.%' THEN substr(expected_operation, 9)
        ELSE expected_operation
      END AS requested_operation
    FROM current_operation
  )
  SELECT CASE
    WHEN requested_operation IS NULL OR requested_operation = '' THEN FALSE
    ELSE COALESCE(current_operation = requested_operation, FALSE)
  END
  FROM normalized;
$$;


--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


--
-- Name: enforce_bucket_name_length(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.enforce_bucket_name_length() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
    if length(new.name) > 100 then
        raise exception 'bucket name "%" is too long (% characters). Max is 100.', new.name, length(new.name);
    end if;
    return new;
end;
$$;


--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
    _filename text;
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Get the last path segment (the actual filename)
    SELECT _parts[array_length(_parts, 1)] INTO _filename;
    -- Extract extension: reverse, split on '.', then reverse again
    RETURN reverse(split_part(reverse(_filename), '.', 1));
END
$$;


--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Return everything except the last segment
    RETURN _parts[1 : array_length(_parts,1) - 1];
END
$$;


--
-- Name: get_common_prefix(text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_common_prefix(p_key text, p_prefix text, p_delimiter text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
SELECT CASE
    WHEN position(p_delimiter IN substring(p_key FROM length(p_prefix) + 1)) > 0
    THEN left(p_key, length(p_prefix) + position(p_delimiter IN substring(p_key FROM length(p_prefix) + 1)))
    ELSE NULL
END;
$$;


--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::bigint)::bigint as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_objects_with_delimiter(_bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_peek_name TEXT;
    v_current RECORD;
    v_common_prefix TEXT;

    -- Configuration
    v_is_asc BOOLEAN;
    v_prefix TEXT;
    v_start TEXT;
    v_upper_bound TEXT;
    v_file_batch_size INT;

    -- Seek state
    v_next_seek TEXT;
    v_count INT := 0;

    -- Dynamic SQL for batch query only
    v_batch_query TEXT;

BEGIN
    -- ========================================================================
    -- INITIALIZATION
    -- ========================================================================
    v_is_asc := lower(coalesce(sort_order, 'asc')) = 'asc';
    v_prefix := coalesce(prefix_param, '');
    v_start := CASE WHEN coalesce(next_token, '') <> '' THEN next_token ELSE coalesce(start_after, '') END;
    v_file_batch_size := LEAST(GREATEST(max_keys * 2, 100), 1000);

    -- Calculate upper bound for prefix filtering (bytewise, using COLLATE "C")
    IF v_prefix = '' THEN
        v_upper_bound := NULL;
    ELSIF right(v_prefix, 1) = delimiter_param THEN
        v_upper_bound := left(v_prefix, -1) || chr(ascii(delimiter_param) + 1);
    ELSE
        v_upper_bound := left(v_prefix, -1) || chr(ascii(right(v_prefix, 1)) + 1);
    END IF;

    -- Build batch query (dynamic SQL - called infrequently, amortized over many rows)
    IF v_is_asc THEN
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" >= $2 ' ||
                'AND o.name COLLATE "C" < $3 ORDER BY o.name COLLATE "C" ASC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" >= $2 ' ||
                'ORDER BY o.name COLLATE "C" ASC LIMIT $4';
        END IF;
    ELSE
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" < $2 ' ||
                'AND o.name COLLATE "C" >= $3 ORDER BY o.name COLLATE "C" DESC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND o.name COLLATE "C" < $2 ' ||
                'ORDER BY o.name COLLATE "C" DESC LIMIT $4';
        END IF;
    END IF;

    -- ========================================================================
    -- SEEK INITIALIZATION: Determine starting position
    -- ========================================================================
    IF v_start = '' THEN
        IF v_is_asc THEN
            v_next_seek := v_prefix;
        ELSE
            -- DESC without cursor: find the last item in range
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_prefix AND o.name COLLATE "C" < v_upper_bound
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix <> '' THEN
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_next_seek FROM storage.objects o
                WHERE o.bucket_id = _bucket_id
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            END IF;

            IF v_next_seek IS NOT NULL THEN
                v_next_seek := v_next_seek || delimiter_param;
            ELSE
                RETURN;
            END IF;
        END IF;
    ELSE
        -- Cursor provided: determine if it refers to a folder or leaf
        IF EXISTS (
            SELECT 1 FROM storage.objects o
            WHERE o.bucket_id = _bucket_id
              AND o.name COLLATE "C" LIKE v_start || delimiter_param || '%'
            LIMIT 1
        ) THEN
            -- Cursor refers to a folder
            IF v_is_asc THEN
                v_next_seek := v_start || chr(ascii(delimiter_param) + 1);
            ELSE
                v_next_seek := v_start || delimiter_param;
            END IF;
        ELSE
            -- Cursor refers to a leaf object
            IF v_is_asc THEN
                v_next_seek := v_start || delimiter_param;
            ELSE
                v_next_seek := v_start;
            END IF;
        END IF;
    END IF;

    -- ========================================================================
    -- MAIN LOOP: Hybrid peek-then-batch algorithm
    -- Uses STATIC SQL for peek (hot path) and DYNAMIC SQL for batch
    -- ========================================================================
    LOOP
        EXIT WHEN v_count >= max_keys;

        -- STEP 1: PEEK using STATIC SQL (plan cached, very fast)
        IF v_is_asc THEN
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_next_seek AND o.name COLLATE "C" < v_upper_bound
                ORDER BY o.name COLLATE "C" ASC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" >= v_next_seek
                ORDER BY o.name COLLATE "C" ASC LIMIT 1;
            END IF;
        ELSE
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix <> '' THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek AND o.name COLLATE "C" >= v_prefix
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = _bucket_id AND o.name COLLATE "C" < v_next_seek
                ORDER BY o.name COLLATE "C" DESC LIMIT 1;
            END IF;
        END IF;

        EXIT WHEN v_peek_name IS NULL;

        -- STEP 2: Check if this is a FOLDER or FILE
        v_common_prefix := storage.get_common_prefix(v_peek_name, v_prefix, delimiter_param);

        IF v_common_prefix IS NOT NULL THEN
            -- FOLDER: Emit and skip to next folder (no heap access needed)
            name := rtrim(v_common_prefix, delimiter_param);
            id := NULL;
            updated_at := NULL;
            created_at := NULL;
            last_accessed_at := NULL;
            metadata := NULL;
            RETURN NEXT;
            v_count := v_count + 1;

            -- Advance seek past the folder range
            IF v_is_asc THEN
                v_next_seek := left(v_common_prefix, -1) || chr(ascii(delimiter_param) + 1);
            ELSE
                v_next_seek := v_common_prefix;
            END IF;
        ELSE
            -- FILE: Batch fetch using DYNAMIC SQL (overhead amortized over many rows)
            -- For ASC: upper_bound is the exclusive upper limit (< condition)
            -- For DESC: prefix is the inclusive lower limit (>= condition)
            FOR v_current IN EXECUTE v_batch_query USING _bucket_id, v_next_seek,
                CASE WHEN v_is_asc THEN COALESCE(v_upper_bound, v_prefix) ELSE v_prefix END, v_file_batch_size
            LOOP
                v_common_prefix := storage.get_common_prefix(v_current.name, v_prefix, delimiter_param);

                IF v_common_prefix IS NOT NULL THEN
                    -- Hit a folder: exit batch, let peek handle it
                    v_next_seek := v_current.name;
                    EXIT;
                END IF;

                -- Emit file
                name := v_current.name;
                id := v_current.id;
                updated_at := v_current.updated_at;
                created_at := v_current.created_at;
                last_accessed_at := v_current.last_accessed_at;
                metadata := v_current.metadata;
                RETURN NEXT;
                v_count := v_count + 1;

                -- Advance seek past this file
                IF v_is_asc THEN
                    v_next_seek := v_current.name || delimiter_param;
                ELSE
                    v_next_seek := v_current.name;
                END IF;

                EXIT WHEN v_count >= max_keys;
            END LOOP;
        END IF;
    END LOOP;
END;
$_$;


--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


--
-- Name: protect_delete(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.protect_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Check if storage.allow_delete_query is set to 'true'
    IF COALESCE(current_setting('storage.allow_delete_query', true), 'false') != 'true' THEN
        RAISE EXCEPTION 'Direct deletion from storage tables is not allowed. Use the Storage API instead.'
            USING HINT = 'This prevents accidental data loss from orphaned objects.',
                  ERRCODE = '42501';
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_peek_name TEXT;
    v_current RECORD;
    v_common_prefix TEXT;
    v_delimiter CONSTANT TEXT := '/';

    -- Configuration
    v_limit INT;
    v_prefix TEXT;
    v_prefix_lower TEXT;
    v_is_asc BOOLEAN;
    v_order_by TEXT;
    v_sort_order TEXT;
    v_upper_bound TEXT;
    v_file_batch_size INT;

    -- Dynamic SQL for batch query only
    v_batch_query TEXT;

    -- Seek state
    v_next_seek TEXT;
    v_count INT := 0;
    v_skipped INT := 0;
BEGIN
    -- ========================================================================
    -- INITIALIZATION
    -- ========================================================================
    v_limit := LEAST(coalesce(limits, 100), 1500);
    v_prefix := coalesce(prefix, '') || coalesce(search, '');
    v_prefix_lower := lower(v_prefix);
    v_is_asc := lower(coalesce(sortorder, 'asc')) = 'asc';
    v_file_batch_size := LEAST(GREATEST(v_limit * 2, 100), 1000);

    -- Validate sort column
    CASE lower(coalesce(sortcolumn, 'name'))
        WHEN 'name' THEN v_order_by := 'name';
        WHEN 'updated_at' THEN v_order_by := 'updated_at';
        WHEN 'created_at' THEN v_order_by := 'created_at';
        WHEN 'last_accessed_at' THEN v_order_by := 'last_accessed_at';
        ELSE v_order_by := 'name';
    END CASE;

    v_sort_order := CASE WHEN v_is_asc THEN 'asc' ELSE 'desc' END;

    -- ========================================================================
    -- NON-NAME SORTING: Use path_tokens approach (unchanged)
    -- ========================================================================
    IF v_order_by != 'name' THEN
        RETURN QUERY EXECUTE format(
            $sql$
            WITH folders AS (
                SELECT path_tokens[$1] AS folder
                FROM storage.objects
                WHERE objects.name ILIKE $2 || '%%'
                  AND bucket_id = $3
                  AND array_length(objects.path_tokens, 1) <> $1
                GROUP BY folder
                ORDER BY folder %s
            )
            (SELECT folder AS "name",
                   NULL::uuid AS id,
                   NULL::timestamptz AS updated_at,
                   NULL::timestamptz AS created_at,
                   NULL::timestamptz AS last_accessed_at,
                   NULL::jsonb AS metadata FROM folders)
            UNION ALL
            (SELECT path_tokens[$1] AS "name",
                   id, updated_at, created_at, last_accessed_at, metadata
             FROM storage.objects
             WHERE objects.name ILIKE $2 || '%%'
               AND bucket_id = $3
               AND array_length(objects.path_tokens, 1) = $1
             ORDER BY %I %s)
            LIMIT $4 OFFSET $5
            $sql$, v_sort_order, v_order_by, v_sort_order
        ) USING levels, v_prefix, bucketname, v_limit, offsets;
        RETURN;
    END IF;

    -- ========================================================================
    -- NAME SORTING: Hybrid skip-scan with batch optimization
    -- ========================================================================

    -- Calculate upper bound for prefix filtering
    IF v_prefix_lower = '' THEN
        v_upper_bound := NULL;
    ELSIF right(v_prefix_lower, 1) = v_delimiter THEN
        v_upper_bound := left(v_prefix_lower, -1) || chr(ascii(v_delimiter) + 1);
    ELSE
        v_upper_bound := left(v_prefix_lower, -1) || chr(ascii(right(v_prefix_lower, 1)) + 1);
    END IF;

    -- Build batch query (dynamic SQL - called infrequently, amortized over many rows)
    IF v_is_asc THEN
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" >= $2 ' ||
                'AND lower(o.name) COLLATE "C" < $3 ORDER BY lower(o.name) COLLATE "C" ASC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" >= $2 ' ||
                'ORDER BY lower(o.name) COLLATE "C" ASC LIMIT $4';
        END IF;
    ELSE
        IF v_upper_bound IS NOT NULL THEN
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" < $2 ' ||
                'AND lower(o.name) COLLATE "C" >= $3 ORDER BY lower(o.name) COLLATE "C" DESC LIMIT $4';
        ELSE
            v_batch_query := 'SELECT o.name, o.id, o.updated_at, o.created_at, o.last_accessed_at, o.metadata ' ||
                'FROM storage.objects o WHERE o.bucket_id = $1 AND lower(o.name) COLLATE "C" < $2 ' ||
                'ORDER BY lower(o.name) COLLATE "C" DESC LIMIT $4';
        END IF;
    END IF;

    -- Initialize seek position
    IF v_is_asc THEN
        v_next_seek := v_prefix_lower;
    ELSE
        -- DESC: find the last item in range first (static SQL)
        IF v_upper_bound IS NOT NULL THEN
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_prefix_lower AND lower(o.name) COLLATE "C" < v_upper_bound
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        ELSIF v_prefix_lower <> '' THEN
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_prefix_lower
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        ELSE
            SELECT o.name INTO v_peek_name FROM storage.objects o
            WHERE o.bucket_id = bucketname
            ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
        END IF;

        IF v_peek_name IS NOT NULL THEN
            v_next_seek := lower(v_peek_name) || v_delimiter;
        ELSE
            RETURN;
        END IF;
    END IF;

    -- ========================================================================
    -- MAIN LOOP: Hybrid peek-then-batch algorithm
    -- Uses STATIC SQL for peek (hot path) and DYNAMIC SQL for batch
    -- ========================================================================
    LOOP
        EXIT WHEN v_count >= v_limit;

        -- STEP 1: PEEK using STATIC SQL (plan cached, very fast)
        IF v_is_asc THEN
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_next_seek AND lower(o.name) COLLATE "C" < v_upper_bound
                ORDER BY lower(o.name) COLLATE "C" ASC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" >= v_next_seek
                ORDER BY lower(o.name) COLLATE "C" ASC LIMIT 1;
            END IF;
        ELSE
            IF v_upper_bound IS NOT NULL THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek AND lower(o.name) COLLATE "C" >= v_prefix_lower
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            ELSIF v_prefix_lower <> '' THEN
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek AND lower(o.name) COLLATE "C" >= v_prefix_lower
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            ELSE
                SELECT o.name INTO v_peek_name FROM storage.objects o
                WHERE o.bucket_id = bucketname AND lower(o.name) COLLATE "C" < v_next_seek
                ORDER BY lower(o.name) COLLATE "C" DESC LIMIT 1;
            END IF;
        END IF;

        EXIT WHEN v_peek_name IS NULL;

        -- STEP 2: Check if this is a FOLDER or FILE
        v_common_prefix := storage.get_common_prefix(lower(v_peek_name), v_prefix_lower, v_delimiter);

        IF v_common_prefix IS NOT NULL THEN
            -- FOLDER: Handle offset, emit if needed, skip to next folder
            IF v_skipped < offsets THEN
                v_skipped := v_skipped + 1;
            ELSE
                name := split_part(rtrim(storage.get_common_prefix(v_peek_name, v_prefix, v_delimiter), v_delimiter), v_delimiter, levels);
                id := NULL;
                updated_at := NULL;
                created_at := NULL;
                last_accessed_at := NULL;
                metadata := NULL;
                RETURN NEXT;
                v_count := v_count + 1;
            END IF;

            -- Advance seek past the folder range
            IF v_is_asc THEN
                v_next_seek := lower(left(v_common_prefix, -1)) || chr(ascii(v_delimiter) + 1);
            ELSE
                v_next_seek := lower(v_common_prefix);
            END IF;
        ELSE
            -- FILE: Batch fetch using DYNAMIC SQL (overhead amortized over many rows)
            -- For ASC: upper_bound is the exclusive upper limit (< condition)
            -- For DESC: prefix_lower is the inclusive lower limit (>= condition)
            FOR v_current IN EXECUTE v_batch_query
                USING bucketname, v_next_seek,
                    CASE WHEN v_is_asc THEN COALESCE(v_upper_bound, v_prefix_lower) ELSE v_prefix_lower END, v_file_batch_size
            LOOP
                v_common_prefix := storage.get_common_prefix(lower(v_current.name), v_prefix_lower, v_delimiter);

                IF v_common_prefix IS NOT NULL THEN
                    -- Hit a folder: exit batch, let peek handle it
                    v_next_seek := lower(v_current.name);
                    EXIT;
                END IF;

                -- Handle offset skipping
                IF v_skipped < offsets THEN
                    v_skipped := v_skipped + 1;
                ELSE
                    -- Emit file
                    name := split_part(v_current.name, v_delimiter, levels);
                    id := v_current.id;
                    updated_at := v_current.updated_at;
                    created_at := v_current.created_at;
                    last_accessed_at := v_current.last_accessed_at;
                    metadata := v_current.metadata;
                    RETURN NEXT;
                    v_count := v_count + 1;
                END IF;

                -- Advance seek past this file
                IF v_is_asc THEN
                    v_next_seek := lower(v_current.name) || v_delimiter;
                ELSE
                    v_next_seek := lower(v_current.name);
                END IF;

                EXIT WHEN v_count >= v_limit;
            END LOOP;
        END IF;
    END LOOP;
END;
$_$;


--
-- Name: search_by_timestamp(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search_by_timestamp(p_prefix text, p_bucket_id text, p_limit integer, p_level integer, p_start_after text, p_sort_order text, p_sort_column text, p_sort_column_after text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    v_cursor_op text;
    v_query text;
    v_prefix text;
BEGIN
    v_prefix := coalesce(p_prefix, '');

    IF p_sort_order = 'asc' THEN
        v_cursor_op := '>';
    ELSE
        v_cursor_op := '<';
    END IF;

    v_query := format($sql$
        WITH raw_objects AS (
            SELECT
                o.name AS obj_name,
                o.id AS obj_id,
                o.updated_at AS obj_updated_at,
                o.created_at AS obj_created_at,
                o.last_accessed_at AS obj_last_accessed_at,
                o.metadata AS obj_metadata,
                storage.get_common_prefix(o.name, $1, '/') AS common_prefix
            FROM storage.objects o
            WHERE o.bucket_id = $2
              AND o.name COLLATE "C" LIKE $1 || '%%'
        ),
        -- Aggregate common prefixes (folders)
        -- Both created_at and updated_at use MIN(obj_created_at) to match the old prefixes table behavior
        aggregated_prefixes AS (
            SELECT
                rtrim(common_prefix, '/') AS name,
                NULL::uuid AS id,
                MIN(obj_created_at) AS updated_at,
                MIN(obj_created_at) AS created_at,
                NULL::timestamptz AS last_accessed_at,
                NULL::jsonb AS metadata,
                TRUE AS is_prefix
            FROM raw_objects
            WHERE common_prefix IS NOT NULL
            GROUP BY common_prefix
        ),
        leaf_objects AS (
            SELECT
                obj_name AS name,
                obj_id AS id,
                obj_updated_at AS updated_at,
                obj_created_at AS created_at,
                obj_last_accessed_at AS last_accessed_at,
                obj_metadata AS metadata,
                FALSE AS is_prefix
            FROM raw_objects
            WHERE common_prefix IS NULL
        ),
        combined AS (
            SELECT * FROM aggregated_prefixes
            UNION ALL
            SELECT * FROM leaf_objects
        ),
        filtered AS (
            SELECT *
            FROM combined
            WHERE (
                $5 = ''
                OR ROW(
                    date_trunc('milliseconds', %I),
                    name COLLATE "C"
                ) %s ROW(
                    COALESCE(NULLIF($6, '')::timestamptz, 'epoch'::timestamptz),
                    $5
                )
            )
        )
        SELECT
            split_part(name, '/', $3) AS key,
            name,
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
        FROM filtered
        ORDER BY
            COALESCE(date_trunc('milliseconds', %I), 'epoch'::timestamptz) %s,
            name COLLATE "C" %s
        LIMIT $4
    $sql$,
        p_sort_column,
        v_cursor_op,
        p_sort_column,
        p_sort_order,
        p_sort_order
    );

    RETURN QUERY EXECUTE v_query
    USING v_prefix, p_bucket_id, p_level, p_limit, p_start_after, p_sort_column_after;
END;
$_$;


--
-- Name: search_v2(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer DEFAULT 100, levels integer DEFAULT 1, start_after text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text, sort_column text DEFAULT 'name'::text, sort_column_after text DEFAULT ''::text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    v_sort_col text;
    v_sort_ord text;
    v_limit int;
BEGIN
    -- Cap limit to maximum of 1500 records
    v_limit := LEAST(coalesce(limits, 100), 1500);

    -- Validate and normalize sort_order
    v_sort_ord := lower(coalesce(sort_order, 'asc'));
    IF v_sort_ord NOT IN ('asc', 'desc') THEN
        v_sort_ord := 'asc';
    END IF;

    -- Validate and normalize sort_column
    v_sort_col := lower(coalesce(sort_column, 'name'));
    IF v_sort_col NOT IN ('name', 'updated_at', 'created_at') THEN
        v_sort_col := 'name';
    END IF;

    -- Route to appropriate implementation
    IF v_sort_col = 'name' THEN
        -- Use list_objects_with_delimiter for name sorting (most efficient: O(k * log n))
        RETURN QUERY
        SELECT
            split_part(l.name, '/', levels) AS key,
            l.name AS name,
            l.id,
            l.updated_at,
            l.created_at,
            l.last_accessed_at,
            l.metadata
        FROM storage.list_objects_with_delimiter(
            bucket_name,
            coalesce(prefix, ''),
            '/',
            v_limit,
            start_after,
            '',
            v_sort_ord
        ) l;
    ELSE
        -- Use aggregation approach for timestamp sorting
        -- Not efficient for large datasets but supports correct pagination
        RETURN QUERY SELECT * FROM storage.search_by_timestamp(
            prefix, bucket_name, v_limit, levels, start_after,
            v_sort_ord, v_sort_col, sort_column_after
        );
    END IF;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: custom_oauth_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.custom_oauth_providers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    provider_type text NOT NULL,
    identifier text NOT NULL,
    name text NOT NULL,
    client_id text NOT NULL,
    client_secret text NOT NULL,
    acceptable_client_ids text[] DEFAULT '{}'::text[] NOT NULL,
    scopes text[] DEFAULT '{}'::text[] NOT NULL,
    pkce_enabled boolean DEFAULT true NOT NULL,
    attribute_mapping jsonb DEFAULT '{}'::jsonb NOT NULL,
    authorization_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    email_optional boolean DEFAULT false NOT NULL,
    issuer text,
    discovery_url text,
    skip_nonce_check boolean DEFAULT false NOT NULL,
    cached_discovery jsonb,
    discovery_cached_at timestamp with time zone,
    authorization_url text,
    token_url text,
    userinfo_url text,
    jwks_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT custom_oauth_providers_authorization_url_https CHECK (((authorization_url IS NULL) OR (authorization_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_authorization_url_length CHECK (((authorization_url IS NULL) OR (char_length(authorization_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_client_id_length CHECK (((char_length(client_id) >= 1) AND (char_length(client_id) <= 512))),
    CONSTRAINT custom_oauth_providers_discovery_url_length CHECK (((discovery_url IS NULL) OR (char_length(discovery_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_identifier_format CHECK ((identifier ~ '^[a-z0-9][a-z0-9:-]{0,48}[a-z0-9]$'::text)),
    CONSTRAINT custom_oauth_providers_issuer_length CHECK (((issuer IS NULL) OR ((char_length(issuer) >= 1) AND (char_length(issuer) <= 2048)))),
    CONSTRAINT custom_oauth_providers_jwks_uri_https CHECK (((jwks_uri IS NULL) OR (jwks_uri ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_jwks_uri_length CHECK (((jwks_uri IS NULL) OR (char_length(jwks_uri) <= 2048))),
    CONSTRAINT custom_oauth_providers_name_length CHECK (((char_length(name) >= 1) AND (char_length(name) <= 100))),
    CONSTRAINT custom_oauth_providers_oauth2_requires_endpoints CHECK (((provider_type <> 'oauth2'::text) OR ((authorization_url IS NOT NULL) AND (token_url IS NOT NULL) AND (userinfo_url IS NOT NULL)))),
    CONSTRAINT custom_oauth_providers_oidc_discovery_url_https CHECK (((provider_type <> 'oidc'::text) OR (discovery_url IS NULL) OR (discovery_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_oidc_issuer_https CHECK (((provider_type <> 'oidc'::text) OR (issuer IS NULL) OR (issuer ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_oidc_requires_issuer CHECK (((provider_type <> 'oidc'::text) OR (issuer IS NOT NULL))),
    CONSTRAINT custom_oauth_providers_provider_type_check CHECK ((provider_type = ANY (ARRAY['oauth2'::text, 'oidc'::text]))),
    CONSTRAINT custom_oauth_providers_token_url_https CHECK (((token_url IS NULL) OR (token_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_token_url_length CHECK (((token_url IS NULL) OR (char_length(token_url) <= 2048))),
    CONSTRAINT custom_oauth_providers_userinfo_url_https CHECK (((userinfo_url IS NULL) OR (userinfo_url ~~ 'https://%'::text))),
    CONSTRAINT custom_oauth_providers_userinfo_url_length CHECK (((userinfo_url IS NULL) OR (char_length(userinfo_url) <= 2048)))
);


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text,
    code_challenge_method auth.code_challenge_method,
    code_challenge text,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone,
    invite_token text,
    referrer text,
    oauth_client_state_id uuid,
    linking_target_id uuid,
    email_optional boolean DEFAULT false NOT NULL
);


--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.flow_state IS 'Stores metadata for all OAuth/SSO login flows';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid,
    last_webauthn_challenge_data jsonb
);


--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: COLUMN mfa_factors.last_webauthn_challenge_data; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.mfa_factors.last_webauthn_challenge_data IS 'Stores the latest WebAuthn challenge data including attestation/assertion for customer verification';


--
-- Name: oauth_authorizations; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_authorizations (
    id uuid NOT NULL,
    authorization_id text NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    redirect_uri text NOT NULL,
    scope text NOT NULL,
    state text,
    resource text,
    code_challenge text,
    code_challenge_method auth.code_challenge_method,
    response_type auth.oauth_response_type DEFAULT 'code'::auth.oauth_response_type NOT NULL,
    status auth.oauth_authorization_status DEFAULT 'pending'::auth.oauth_authorization_status NOT NULL,
    authorization_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:03:00'::interval) NOT NULL,
    approved_at timestamp with time zone,
    nonce text,
    CONSTRAINT oauth_authorizations_authorization_code_length CHECK ((char_length(authorization_code) <= 255)),
    CONSTRAINT oauth_authorizations_code_challenge_length CHECK ((char_length(code_challenge) <= 128)),
    CONSTRAINT oauth_authorizations_expires_at_future CHECK ((expires_at > created_at)),
    CONSTRAINT oauth_authorizations_nonce_length CHECK ((char_length(nonce) <= 255)),
    CONSTRAINT oauth_authorizations_redirect_uri_length CHECK ((char_length(redirect_uri) <= 2048)),
    CONSTRAINT oauth_authorizations_resource_length CHECK ((char_length(resource) <= 2048)),
    CONSTRAINT oauth_authorizations_scope_length CHECK ((char_length(scope) <= 4096)),
    CONSTRAINT oauth_authorizations_state_length CHECK ((char_length(state) <= 4096))
);


--
-- Name: oauth_client_states; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_client_states (
    id uuid NOT NULL,
    provider_type text NOT NULL,
    code_verifier text,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: TABLE oauth_client_states; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.oauth_client_states IS 'Stores OAuth states for third-party provider authentication flows where Supabase acts as the OAuth client.';


--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_secret_hash text,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    client_type auth.oauth_client_type DEFAULT 'confidential'::auth.oauth_client_type NOT NULL,
    token_endpoint_auth_method text NOT NULL,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048)),
    CONSTRAINT oauth_clients_token_endpoint_auth_method_check CHECK ((token_endpoint_auth_method = ANY (ARRAY['client_secret_basic'::text, 'client_secret_post'::text, 'none'::text])))
);


--
-- Name: oauth_consents; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    client_id uuid NOT NULL,
    scopes text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT oauth_consents_revoked_after_granted CHECK (((revoked_at IS NULL) OR (revoked_at >= granted_at))),
    CONSTRAINT oauth_consents_scopes_length CHECK ((char_length(scopes) <= 2048)),
    CONSTRAINT oauth_consents_scopes_not_empty CHECK ((char_length(TRIM(BOTH FROM scopes)) > 0))
);


--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text,
    oauth_client_id uuid,
    refresh_token_hmac_key text,
    refresh_token_counter bigint,
    scopes text,
    CONSTRAINT sessions_scopes_length CHECK ((char_length(scopes) <= 4096))
);


--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: COLUMN sessions.refresh_token_hmac_key; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sessions.refresh_token_hmac_key IS 'Holds a HMAC-SHA256 key used to sign refresh tokens for this session.';


--
-- Name: COLUMN sessions.refresh_token_counter; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sessions.refresh_token_counter IS 'Holds the ID (counter) of the last issued refresh token.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: webauthn_challenges; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.webauthn_challenges (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    challenge_type text NOT NULL,
    session_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT webauthn_challenges_challenge_type_check CHECK ((challenge_type = ANY (ARRAY['signup'::text, 'registration'::text, 'authentication'::text])))
);


--
-- Name: webauthn_credentials; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.webauthn_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    credential_id bytea NOT NULL,
    public_key bytea NOT NULL,
    attestation_type text DEFAULT ''::text NOT NULL,
    aaguid uuid,
    sign_count bigint DEFAULT 0 NOT NULL,
    transports jsonb DEFAULT '[]'::jsonb NOT NULL,
    backup_eligible boolean DEFAULT false NOT NULL,
    backed_up boolean DEFAULT false NOT NULL,
    friendly_name text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone
);


--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_users (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    restaurant_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(200) DEFAULT ''::character varying,
    role character varying(50) DEFAULT 'employee'::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: branches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.branches (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying(200) NOT NULL,
    address character varying(300) DEFAULT ''::character varying,
    city character varying(200) DEFAULT ''::character varying,
    phone character varying(50) DEFAULT ''::character varying,
    hours character varying(200) DEFAULT ''::character varying,
    maps_url text DEFAULT ''::text,
    is_open boolean DEFAULT true,
    is_default boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: branches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.branches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: branches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.branches_id_seq OWNED BY public.branches.id;


--
-- Name: contact_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact_messages (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying(200) NOT NULL,
    email character varying(255) NOT NULL,
    phone character varying(50) DEFAULT ''::character varying,
    subject character varying(300) DEFAULT ''::character varying,
    message text NOT NULL,
    is_read boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: contact_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contact_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contact_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_messages_id_seq OWNED BY public.contact_messages.id;


--
-- Name: content_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_pages (
    restaurant_id integer NOT NULL,
    slug character varying(100) NOT NULL,
    title character varying(200) DEFAULT ''::character varying,
    content text DEFAULT ''::text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: domains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.domains (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    domain character varying(255) NOT NULL,
    is_primary boolean DEFAULT false,
    verified boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: domains_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: domains_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.domains_id_seq OWNED BY public.domains.id;


--
-- Name: faqs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.faqs (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    question text NOT NULL,
    answer text NOT NULL,
    category character varying(100) DEFAULT 'General'::character varying,
    order_index integer DEFAULT 0
);


--
-- Name: faqs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.faqs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: faqs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.faqs_id_seq OWNED BY public.faqs.id;


--
-- Name: menu_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.menu_items (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    category character varying(100) DEFAULT ''::character varying,
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text,
    price numeric(10,2) NOT NULL,
    sale_price numeric(10,2),
    image text DEFAULT ''::text,
    rating numeric(3,1) DEFAULT 0,
    is_spicy boolean DEFAULT false,
    is_popular boolean DEFAULT false,
    is_featured boolean DEFAULT false,
    is_available boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: menu_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.menu_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: menu_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.menu_items_id_seq OWNED BY public.menu_items.id;


--
-- Name: order_claims; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_claims (
    id integer NOT NULL,
    order_id character varying(20) NOT NULL,
    user_id text NOT NULL,
    receipt_number character varying(100) NOT NULL,
    status character varying(50) DEFAULT 'success'::character varying,
    failure_reason text DEFAULT ''::text,
    claimed_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: order_claims_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.order_claims_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: order_claims_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.order_claims_id_seq OWNED BY public.order_claims.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    id character varying(20) NOT NULL,
    restaurant_id integer NOT NULL,
    user_id text,
    guest_name character varying(200) DEFAULT ''::character varying,
    guest_email character varying(255) DEFAULT ''::character varying,
    guest_phone character varying(50) DEFAULT ''::character varying,
    items jsonb DEFAULT '[]'::jsonb NOT NULL,
    subtotal numeric(10,2) DEFAULT 0,
    discount_amount numeric(10,2) DEFAULT 0,
    delivery_charge numeric(10,2) DEFAULT 0,
    total numeric(10,2) DEFAULT 0,
    status character varying(50) DEFAULT 'placed'::character varying,
    order_type character varying(50) DEFAULT 'delivery'::character varying,
    payment_method character varying(50) DEFAULT 'cash'::character varying,
    branch_id integer,
    address text DEFAULT ''::text,
    notes text DEFAULT ''::text,
    points_earned integer DEFAULT 0,
    points_redeemed integer DEFAULT 0,
    source character varying(50) DEFAULT 'online'::character varying,
    claim_code character varying(100),
    claimed_by_user_id text,
    claimed_at timestamp with time zone,
    claim_status character varying(50) DEFAULT 'unclaimed'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: platform_admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.platform_admins (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(200) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: points; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.points (
    user_id text NOT NULL,
    restaurant_id integer NOT NULL,
    points integer DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: restaurants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.restaurants (
    id integer NOT NULL,
    name character varying(200) DEFAULT 'My Restaurant'::character varying NOT NULL,
    slug character varying(100) DEFAULT 'default'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: restaurants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.restaurants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: restaurants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.restaurants_id_seq OWNED BY public.restaurants.id;


--
-- Name: reward_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reward_settings (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    mode character varying(50) DEFAULT 'points'::character varying,
    points_per_unit numeric(10,2) DEFAULT 1,
    unit_amount numeric(10,2) DEFAULT 100,
    min_redeem integer DEFAULT 100,
    max_discount numeric(10,2) DEFAULT 500,
    conversion_rate numeric(10,4) DEFAULT 1.0,
    eligible_category character varying(100) DEFAULT ''::character varying,
    eligible_item_id integer,
    required_count integer DEFAULT 10,
    free_item_id integer,
    auto_apply boolean DEFAULT false,
    claim_expiry_days integer DEFAULT 30,
    require_phone_match boolean DEFAULT false,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: reward_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reward_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reward_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reward_settings_id_seq OWNED BY public.reward_settings.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.settings (
    restaurant_id integer NOT NULL,
    key character varying(100) NOT NULL,
    value text DEFAULT ''::text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: theme_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.theme_settings (
    restaurant_id integer NOT NULL,
    primary_color character varying(20) DEFAULT '#e85d04'::character varying,
    secondary_color character varying(20) DEFAULT '#faa307'::character varying,
    accent_color character varying(20) DEFAULT '#f48c06'::character varying,
    logo_url text DEFAULT ''::text,
    favicon_url text DEFAULT ''::text,
    restaurant_name character varying(200) DEFAULT ''::character varying,
    hero_text character varying(300) DEFAULT ''::character varying,
    hero_subtext character varying(500) DEFAULT ''::character varying,
    font_family character varying(100) DEFAULT 'Inter'::character varying,
    updated_at timestamp with time zone DEFAULT now(),
    layout_style character varying(50) DEFAULT 'classic'::character varying,
    hero_image_url text DEFAULT ''::text,
    slogan character varying(80) DEFAULT ''::character varying
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    restaurant_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    first_name character varying(100) DEFAULT ''::character varying,
    last_name character varying(100) DEFAULT ''::character varying,
    phone character varying(50) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
)
PARTITION BY RANGE (inserted_at);


--
-- Name: messages_2026_05_22; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2026_05_22 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2026_05_23; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2026_05_23 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2026_05_24; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2026_05_24 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2026_05_25; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2026_05_25 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2026_05_26; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2026_05_26 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    action_filter text DEFAULT '*'::text,
    CONSTRAINT subscription_action_filter_check CHECK ((action_filter = ANY (ARRAY['*'::text, 'INSERT'::text, 'UPDATE'::text, 'DELETE'::text])))
);


--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: -
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text,
    type storage.buckettype DEFAULT 'STANDARD'::storage.buckettype NOT NULL
);


--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: buckets_analytics; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.buckets_analytics (
    name text NOT NULL,
    type storage.buckettype DEFAULT 'ANALYTICS'::storage.buckettype NOT NULL,
    format text DEFAULT 'ICEBERG'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: buckets_vectors; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.buckets_vectors (
    id text NOT NULL,
    type storage.buckettype DEFAULT 'VECTOR'::storage.buckettype NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: objects; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb
);


--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb,
    metadata jsonb
);


--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: vector_indexes; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.vector_indexes (
    id text DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    bucket_id text NOT NULL,
    data_type text NOT NULL,
    dimension integer NOT NULL,
    distance_metric text NOT NULL,
    metadata_configuration jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: messages_2026_05_22; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2026_05_22 FOR VALUES FROM ('2026-05-22 00:00:00') TO ('2026-05-23 00:00:00');


--
-- Name: messages_2026_05_23; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2026_05_23 FOR VALUES FROM ('2026-05-23 00:00:00') TO ('2026-05-24 00:00:00');


--
-- Name: messages_2026_05_24; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2026_05_24 FOR VALUES FROM ('2026-05-24 00:00:00') TO ('2026-05-25 00:00:00');


--
-- Name: messages_2026_05_25; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2026_05_25 FOR VALUES FROM ('2026-05-25 00:00:00') TO ('2026-05-26 00:00:00');


--
-- Name: messages_2026_05_26; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2026_05_26 FOR VALUES FROM ('2026-05-26 00:00:00') TO ('2026-05-27 00:00:00');


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: branches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches ALTER COLUMN id SET DEFAULT nextval('public.branches_id_seq'::regclass);


--
-- Name: contact_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_messages ALTER COLUMN id SET DEFAULT nextval('public.contact_messages_id_seq'::regclass);


--
-- Name: domains id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains ALTER COLUMN id SET DEFAULT nextval('public.domains_id_seq'::regclass);


--
-- Name: faqs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faqs ALTER COLUMN id SET DEFAULT nextval('public.faqs_id_seq'::regclass);


--
-- Name: menu_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items ALTER COLUMN id SET DEFAULT nextval('public.menu_items_id_seq'::regclass);


--
-- Name: order_claims id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_claims ALTER COLUMN id SET DEFAULT nextval('public.order_claims_id_seq'::regclass);


--
-- Name: restaurants id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants ALTER COLUMN id SET DEFAULT nextval('public.restaurants_id_seq'::regclass);


--
-- Name: reward_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reward_settings ALTER COLUMN id SET DEFAULT nextval('public.reward_settings_id_seq'::regclass);


--
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.audit_log_entries (instance_id, id, payload, created_at, ip_address) FROM stdin;
\.


--
-- Data for Name: custom_oauth_providers; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.custom_oauth_providers (id, provider_type, identifier, name, client_id, client_secret, acceptable_client_ids, scopes, pkce_enabled, attribute_mapping, authorization_params, enabled, email_optional, issuer, discovery_url, skip_nonce_check, cached_discovery, discovery_cached_at, authorization_url, token_url, userinfo_url, jwks_uri, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.flow_state (id, user_id, auth_code, code_challenge_method, code_challenge, provider_type, provider_access_token, provider_refresh_token, created_at, updated_at, authentication_method, auth_code_issued_at, invite_token, referrer, oauth_client_state_id, linking_target_id, email_optional) FROM stdin;
\.


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at, id) FROM stdin;
\.


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.instances (id, uuid, raw_base_config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_amr_claims (session_id, created_at, updated_at, authentication_method, id) FROM stdin;
\.


--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_challenges (id, factor_id, created_at, verified_at, ip_address, otp_code, web_authn_session_data) FROM stdin;
\.


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_factors (id, user_id, friendly_name, factor_type, status, created_at, updated_at, secret, phone, last_challenged_at, web_authn_credential, web_authn_aaguid, last_webauthn_challenge_data) FROM stdin;
\.


--
-- Data for Name: oauth_authorizations; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.oauth_authorizations (id, authorization_id, client_id, user_id, redirect_uri, scope, state, resource, code_challenge, code_challenge_method, response_type, status, authorization_code, created_at, expires_at, approved_at, nonce) FROM stdin;
\.


--
-- Data for Name: oauth_client_states; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.oauth_client_states (id, provider_type, code_verifier, created_at) FROM stdin;
\.


--
-- Data for Name: oauth_clients; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.oauth_clients (id, client_secret_hash, registration_type, redirect_uris, grant_types, client_name, client_uri, logo_uri, created_at, updated_at, deleted_at, client_type, token_endpoint_auth_method) FROM stdin;
\.


--
-- Data for Name: oauth_consents; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.oauth_consents (id, user_id, client_id, scopes, granted_at, revoked_at) FROM stdin;
\.


--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.one_time_tokens (id, user_id, token_type, token_hash, relates_to, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.refresh_tokens (instance_id, id, token, user_id, revoked, created_at, updated_at, parent, session_id) FROM stdin;
\.


--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.saml_providers (id, sso_provider_id, entity_id, metadata_xml, metadata_url, attribute_mapping, created_at, updated_at, name_id_format) FROM stdin;
\.


--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.saml_relay_states (id, sso_provider_id, request_id, for_email, redirect_to, created_at, updated_at, flow_state_id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.schema_migrations (version) FROM stdin;
20171026211738
20171026211808
20171026211834
20180103212743
20180108183307
20180119214651
20180125194653
00
20210710035447
20210722035447
20210730183235
20210909172000
20210927181326
20211122151130
20211124214934
20211202183645
20220114185221
20220114185340
20220224000811
20220323170000
20220429102000
20220531120530
20220614074223
20220811173540
20221003041349
20221003041400
20221011041400
20221020193600
20221021073300
20221021082433
20221027105023
20221114143122
20221114143410
20221125140132
20221208132122
20221215195500
20221215195800
20221215195900
20230116124310
20230116124412
20230131181311
20230322519590
20230402418590
20230411005111
20230508135423
20230523124323
20230818113222
20230914180801
20231027141322
20231114161723
20231117164230
20240115144230
20240214120130
20240306115329
20240314092811
20240427152123
20240612123726
20240729123726
20240802193726
20240806073726
20241009103726
20250717082212
20250731150234
20250804100000
20250901200500
20250903112500
20250904133000
20250925093508
20251007112900
20251104100000
20251111201300
20251201000000
20260115000000
20260121000000
20260219120000
20260302000000
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sessions (id, user_id, created_at, updated_at, factor_id, aal, not_after, refreshed_at, user_agent, ip, tag, oauth_client_id, refresh_token_hmac_key, refresh_token_counter, scopes) FROM stdin;
\.


--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sso_domains (id, sso_provider_id, domain, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sso_providers (id, resource_id, created_at, updated_at, disabled) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, invited_at, confirmation_token, confirmation_sent_at, recovery_token, recovery_sent_at, email_change_token_new, email_change, email_change_sent_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at, phone, phone_confirmed_at, phone_change, phone_change_token, phone_change_sent_at, email_change_token_current, email_change_confirm_status, banned_until, reauthentication_token, reauthentication_sent_at, is_sso_user, deleted_at, is_anonymous) FROM stdin;
\.


--
-- Data for Name: webauthn_challenges; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.webauthn_challenges (id, user_id, challenge_type, session_data, created_at, expires_at) FROM stdin;
\.


--
-- Data for Name: webauthn_credentials; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.webauthn_credentials (id, user_id, credential_id, public_key, attestation_type, aaguid, sign_count, transports, backup_eligible, backed_up, friendly_name, created_at, updated_at, last_used_at) FROM stdin;
\.


--
-- Data for Name: admin_users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.admin_users (id, restaurant_id, email, password_hash, name, role, created_at) FROM stdin;
f29ae87a-4d8d-4dc3-98be-701dfd549247	1	admin@test.com	$2b$12$q58276WkhCnmVZFXOQxCKO4ajzzJ2fOz9zHbiLlOlASymLy7yYDqO	Super Admin	admin	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: branches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.branches (id, restaurant_id, name, address, city, phone, hours, maps_url, is_open, is_default, created_at) FROM stdin;
1	1	Flavor Hub Downtown	123 Main Street	New York, NY 10001	(212) 555-0101	Mon–Sun: 10am – 11pm		t	f	2026-05-23 17:19:58.553869+00
2	1	Flavor Hub Midtown	456 5th Avenue	New York, NY 10018	(212) 555-0102	Mon–Sun: 10am – 12am		t	f	2026-05-23 17:19:58.553869+00
3	1	Flavor Hub Brooklyn	789 Atlantic Ave	Brooklyn, NY 11217	(718) 555-0103	Mon–Sun: 11am – 11pm		t	f	2026-05-23 17:19:58.553869+00
4	1	Flavor Hub Queens	321 Jamaica Ave	Queens, NY 11435	(718) 555-0104	Mon–Fri: 11am – 10pm, Sat–Sun: 11am – 11pm		f	f	2026-05-23 17:19:58.553869+00
5	1	Flavor Hub Bronx	654 Grand Concourse	Bronx, NY 10451	(718) 555-0105	Mon–Sun: 10am – 10pm		t	f	2026-05-23 17:19:58.553869+00
6	1	Flavor Hub Staten Island	987 Victory Blvd	Staten Island, NY 10301	(718) 555-0106	Mon–Sun: 11am – 10pm		t	f	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: contact_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.contact_messages (id, restaurant_id, name, email, phone, subject, message, is_read, created_at) FROM stdin;
\.


--
-- Data for Name: content_pages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.content_pages (restaurant_id, slug, title, content, updated_at) FROM stdin;
1	privacy	Privacy Policy	Update your privacy policy here...	2026-05-23 17:19:58.553869+00
1	terms	Terms of Service	Update your terms of service here...	2026-05-23 17:19:58.553869+00
1	about	About Us	Tell your story here...	2026-05-23 17:19:58.553869+00
1	refund	Refund Policy	Update your refund policy here...	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: domains; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.domains (id, restaurant_id, domain, is_primary, verified, created_at) FROM stdin;
1	1	localhost	f	t	2026-05-23 17:19:58.553869+00
2	1	127.0.0.1	f	t	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: faqs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.faqs (id, restaurant_id, question, answer, category, order_index) FROM stdin;
\.


--
-- Data for Name: menu_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.menu_items (id, restaurant_id, category, name, description, price, sale_price, image, rating, is_spicy, is_popular, is_featured, is_available, created_at) FROM stdin;
1	1	burgers	Classic Smash Burger	Beef patty, American cheese, pickles, onions, special sauce	9.99	\N	https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400&q=80	4.8	f	t	f	t	2026-05-23 17:19:58.553869+00
2	1	burgers	Bacon BBQ Burger	Beef patty, crispy bacon, BBQ sauce, cheddar, onion rings	12.99	\N	https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=400&q=80	4.9	f	t	f	t	2026-05-23 17:19:58.553869+00
3	1	burgers	Jalapeño Heat Burger	Beef patty, pepper jack, jalapeños, chipotle mayo	11.99	\N	https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=400&q=80	4.7	t	f	f	t	2026-05-23 17:19:58.553869+00
4	1	burgers	Mushroom Swiss Burger	Beef patty, sautéed mushrooms, Swiss cheese, truffle aioli	13.99	\N	https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=400&q=80	4.6	f	f	f	t	2026-05-23 17:19:58.553869+00
5	1	pizza	Margherita	Fresh tomatoes, mozzarella, basil, olive oil	14.99	\N	https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80	4.8	f	t	f	t	2026-05-23 17:19:58.553869+00
6	1	pizza	Pepperoni Supreme	Double pepperoni, mozzarella, tomato sauce	16.99	\N	https://images.unsplash.com/photo-1628840042765-356cda07504e?w=400&q=80	4.9	f	t	f	t	2026-05-23 17:19:58.553869+00
7	1	pizza	BBQ Chicken	Grilled chicken, BBQ sauce, red onions, cilantro	17.99	\N	https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400&q=80	4.7	f	f	f	t	2026-05-23 17:19:58.553869+00
8	1	pizza	Spicy Diavola	Spicy salami, chili flakes, olives, mozzarella	15.99	\N	https://images.unsplash.com/photo-1513104890138-7c749659a591?w=400&q=80	4.6	t	f	f	t	2026-05-23 17:19:58.553869+00
9	1	wraps	Chicken Caesar Wrap	Grilled chicken, romaine, parmesan, caesar dressing	9.99	\N	https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=400&q=80	4.7	f	f	f	t	2026-05-23 17:19:58.553869+00
10	1	wraps	Buffalo Chicken Wrap	Crispy chicken, buffalo sauce, ranch, lettuce	10.99	\N	https://images.unsplash.com/photo-1599785209707-a456fc1337bb?w=400&q=80	4.8	t	t	f	t	2026-05-23 17:19:58.553869+00
11	1	sides	Loaded Fries	Crispy fries, cheese sauce, bacon, green onions	6.99	\N	https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?w=400&q=80	4.7	f	t	f	t	2026-05-23 17:19:58.553869+00
12	1	sides	Onion Rings	Beer-battered onion rings with ranch dip	5.99	\N	https://images.unsplash.com/photo-1639024471283-03518883512d?w=400&q=80	4.6	f	f	f	t	2026-05-23 17:19:58.553869+00
13	1	drinks	Fresh Lemonade	House-made lemonade with fresh mint	3.99	\N	https://images.unsplash.com/photo-1621263764928-df1444c5e859?w=400&q=80	4.9	f	t	f	t	2026-05-23 17:19:58.553869+00
14	1	drinks	Chocolate Milkshake	Rich chocolate ice cream blended to perfection	5.99	\N	https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=400&q=80	4.8	f	f	f	t	2026-05-23 17:19:58.553869+00
15	1	desserts	Brownie Sundae	Warm brownie, vanilla ice cream, chocolate sauce	6.99	\N	https://images.unsplash.com/photo-1551024601-bec78aea704b?w=400&q=80	4.9	f	t	f	t	2026-05-23 17:19:58.553869+00
16	1	desserts	Churros	Crispy churros with chocolate dipping sauce	5.99	\N	https://images.unsplash.com/photo-1624371414361-e670cc507feb?w=400&q=80	4.8	f	f	f	t	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: order_claims; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.order_claims (id, order_id, user_id, receipt_number, status, failure_reason, claimed_at, created_at) FROM stdin;
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.orders (id, restaurant_id, user_id, guest_name, guest_email, guest_phone, items, subtotal, discount_amount, delivery_charge, total, status, order_type, payment_method, branch_id, address, notes, points_earned, points_redeemed, source, claim_code, claimed_by_user_id, claimed_at, claim_status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: platform_admins; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.platform_admins (id, email, password_hash, name, created_at) FROM stdin;
9a0c380d-8206-47fa-a920-1200621cf4fd	platform@test.com	$2b$12$UBLNGNayBZOf3.LZpqo9XO1dm9JSEuLN1v8oj7Qd.t3ygjdw.92Gy	Platform Admin	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: points; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.points (user_id, restaurant_id, points, updated_at) FROM stdin;
\.


--
-- Data for Name: restaurants; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.restaurants (id, name, slug, created_at) FROM stdin;
1	Flavor Hub	default	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: reward_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reward_settings (id, restaurant_id, mode, points_per_unit, unit_amount, min_redeem, max_discount, conversion_rate, eligible_category, eligible_item_id, required_count, free_item_id, auto_apply, claim_expiry_days, require_phone_match, updated_at) FROM stdin;
1	1	points	1.00	100.00	100	500.00	1.0000		\N	10	\N	f	30	f	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.settings (restaurant_id, key, value, updated_at) FROM stdin;
1	delivery_charge	0	2026-05-23 17:19:58.553869+00
1	min_order_amount	0	2026-05-23 17:19:58.553869+00
1	points_on_guest	false	2026-05-23 17:19:58.553869+00
1	restaurant_open	true	2026-05-23 17:19:58.553869+00
\.


--
-- Data for Name: theme_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.theme_settings (restaurant_id, primary_color, secondary_color, accent_color, logo_url, favicon_url, restaurant_name, hero_text, hero_subtext, font_family, updated_at, layout_style, hero_image_url, slogan) FROM stdin;
1	#2563eb	#faa307	#f48c06	data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAATcAAAC2CAIAAAAz212sAAAAAXNSR0IArs4c6QAAAQplWElmTU0AKgAAAAgABwESAAMAAAABAAEAAAEaAAUAAAABAAAAYgEbAAUAAAABAAAAagEoAAMAAAABAAIAAAExAAIAAAA5AAAAcgE7AAIAAAAQAAAArIdpAAQAAAABAAAAvAAAAAAAAABgAAAAAQAAAGAAAAABQ2FudmEgZG9jPURBSEhPR0pwdW9rIHVzZXI9VUFEa202RTY0YVUgYnJhbmQ9QkFEa215UjZpTzgAAEF5ZXNoYSBLaGFsZG9vbgAABpAAAAcAAAAEMDIxMJEBAAcAAAAEAQIDAKAAAAcAAAAEMDEwMKABAAMAAAABAAEAAKACAAQAAAABAAABN6ADAAQAAAABAAAAtgAAAAA0Rp8jAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAIjWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNi4wLjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczpleGlmPSJodHRwOi8vbnMuYWRvYmUuY29tL2V4aWYvMS4wLyIKICAgICAgICAgICAgeG1sbnM6ZGM9Imh0dHA6Ly9wdXJsLm9yZy9kYy9lbGVtZW50cy8xLjEvIgogICAgICAgICAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIKICAgICAgICAgICAgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIgogICAgICAgICAgICB4bWxuczpBdHRyaWI9Imh0dHA6Ly9ucy5hdHRyaWJ1dGlvbi5jb20vYWRzLzEuMC8iPgogICAgICAgICA8ZXhpZjpDb2xvclNwYWNlPjY1NTM1PC9leGlmOkNvbG9yU3BhY2U+CiAgICAgICAgIDxleGlmOlBpeGVsWERpbWVuc2lvbj4yMzA0PC9leGlmOlBpeGVsWERpbWVuc2lvbj4KICAgICAgICAgPGV4aWY6RXhpZlZlcnNpb24+MDIxMDwvZXhpZjpFeGlmVmVyc2lvbj4KICAgICAgICAgPGV4aWY6UGl4ZWxZRGltZW5zaW9uPjM0NTY8L2V4aWY6UGl4ZWxZRGltZW5zaW9uPgogICAgICAgICA8ZXhpZjpGbGFzaFBpeFZlcnNpb24+MDEwMDwvZXhpZjpGbGFzaFBpeFZlcnNpb24+CiAgICAgICAgIDxleGlmOkNvbXBvbmVudHNDb25maWd1cmF0aW9uPgogICAgICAgICAgICA8cmRmOlNlcT4KICAgICAgICAgICAgICAgPHJkZjpsaT4xPC9yZGY6bGk+CiAgICAgICAgICAgICAgIDxyZGY6bGk+MjwvcmRmOmxpPgogICAgICAgICAgICAgICA8cmRmOmxpPjM8L3JkZjpsaT4KICAgICAgICAgICAgICAgPHJkZjpsaT4wPC9yZGY6bGk+CiAgICAgICAgICAgIDwvcmRmOlNlcT4KICAgICAgICAgPC9leGlmOkNvbXBvbmVudHNDb25maWd1cmF0aW9uPgogICAgICAgICA8ZGM6dGl0bGU+CiAgICAgICAgICAgIDxyZGY6QWx0PgogICAgICAgICAgICAgICA8cmRmOmxpIHhtbDpsYW5nPSJ4LWRlZmF1bHQiPkhJUklRIC0gMjwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgIDwvZGM6dGl0bGU+CiAgICAgICAgIDxkYzpjcmVhdG9yPgogICAgICAgICAgICA8cmRmOlNlcT4KICAgICAgICAgICAgICAgPHJkZjpsaT5BeWVzaGEgS2hhbGRvb248L3JkZjpsaT4KICAgICAgICAgICAgPC9yZGY6U2VxPgogICAgICAgICA8L2RjOmNyZWF0b3I+CiAgICAgICAgIDx0aWZmOlJlc29sdXRpb25Vbml0PjI8L3RpZmY6UmVzb2x1dGlvblVuaXQ+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgICAgIDx0aWZmOlhSZXNvbHV0aW9uPjk2PC90aWZmOlhSZXNvbHV0aW9uPgogICAgICAgICA8dGlmZjpZUmVzb2x1dGlvbj45NjwvdGlmZjpZUmVzb2x1dGlvbj4KICAgICAgICAgPHhtcDpDcmVhdG9yVG9vbD5DYW52YSBkb2M9REFISE9HSnB1b2sgdXNlcj1VQURrbTZFNjRhVSBicmFuZD1CQURrbXlSNmlPODwveG1wOkNyZWF0b3JUb29sPgogICAgICAgICA8QXR0cmliOkFkcz4KICAgICAgICAgICAgPHJkZjpTZXE+CiAgICAgICAgICAgICAgIDxyZGY6bGkgcmRmOnBhcnNlVHlwZT0iUmVzb3VyY2UiPgogICAgICAgICAgICAgICAgICA8QXR0cmliOkZiSWQ+NTI1MjY1OTE0MTc5NTgwPC9BdHRyaWI6RmJJZD4KICAgICAgICAgICAgICAgICAgPEF0dHJpYjpUb3VjaFR5cGU+MjwvQXR0cmliOlRvdWNoVHlwZT4KICAgICAgICAgICAgICAgICAgPEF0dHJpYjpDcmVhdGVkPjIwMjYtMDQtMTk8L0F0dHJpYjpDcmVhdGVkPgogICAgICAgICAgICAgICAgICA8QXR0cmliOkV4dElkPmZhNTBmYzQwLTk2OGUtNGUyYy1hODU2LTRjY2E0OGFkZjJlZjwvQXR0cmliOkV4dElkPgogICAgICAgICAgICAgICAgICA8QXR0cmliOkRhdGE+eyJkb2MiOiJEQUhIT0dKcHVvayIsInVzZXIiOiJVQURrbTZFNjRhVSIsImJyYW5kIjoiQkFEa215UjZpTzgifTwvQXR0cmliOkRhdGE+CiAgICAgICAgICAgICAgIDwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpTZXE+CiAgICAgICAgIDwvQXR0cmliOkFkcz4KICAgICAgPC9yZGY6RGVzY3JpcHRpb24+CiAgIDwvcmRmOlJERj4KPC94OnhtcG1ldGE+CqCbBDQAAEAASURBVHgBnL1ZcyRJlqUHwB3uWAKIPdfKzNqm2dLTrB5pkeYIKST/Cn8qReaFL2yZHvZSrOmqzKrcImOPQGB1h8N5vnOuqpkjoppDGhxmqnc599yrqmbmCxzbe4f/23p9w+NmuV4v9w8PDw7vPHhw9+OP7z96dP/x4wf37h3t78329maT6c5kur29tbW93tJhW9vOljc1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		Flavor Hub	Welcome to Flavor Hub	Seeded check	Inter	2026-05-23 21:52:54.597511+00	modern		Seeded check
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, restaurant_id, email, password_hash, first_name, last_name, phone, created_at) FROM stdin;
792ab30f-c565-4e9c-9a62-a7d7ea06c38c	1	seeded_check_1779569906@test.com	$2b$12$Y8/kpivahev5evLsWvztR..cchSVRGyv.AZl3Mq8EUPMDn15kcfCC	Seed	Check		2026-05-23 20:58:31.881093+00
\.


--
-- Data for Name: messages_2026_05_22; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.messages_2026_05_22 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2026_05_23; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.messages_2026_05_23 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2026_05_24; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.messages_2026_05_24 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2026_05_25; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.messages_2026_05_25 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2026_05_26; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.messages_2026_05_26 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.schema_migrations (version, inserted_at) FROM stdin;
20211116024918	2026-05-19 17:04:33
20211116045059	2026-05-19 17:04:33
20211116050929	2026-05-19 17:04:33
20211116051442	2026-05-19 17:04:33
20211116212300	2026-05-19 17:04:33
20211116213355	2026-05-19 17:04:33
20211116213934	2026-05-19 17:04:33
20211116214523	2026-05-19 17:04:33
20211122062447	2026-05-19 20:24:57
20211124070109	2026-05-19 20:24:57
20211202204204	2026-05-19 20:24:57
20211202204605	2026-05-19 20:24:57
20211210212804	2026-05-19 20:24:58
20211228014915	2026-05-19 20:24:58
20220107221237	2026-05-19 20:24:58
20220228202821	2026-05-19 20:24:58
20220312004840	2026-05-19 20:24:58
20220603231003	2026-05-19 20:24:58
20220603232444	2026-05-19 20:24:58
20220615214548	2026-05-19 20:24:58
20220712093339	2026-05-19 20:24:58
20220908172859	2026-05-19 20:24:58
20220916233421	2026-05-19 20:24:58
20230119133233	2026-05-19 20:24:58
20230128025114	2026-05-19 20:24:58
20230128025212	2026-05-19 20:24:58
20230227211149	2026-05-19 20:24:58
20230228184745	2026-05-19 20:24:58
20230308225145	2026-05-19 20:24:58
20230328144023	2026-05-19 20:24:58
20231018144023	2026-05-19 20:24:58
20231204144023	2026-05-19 20:24:58
20231204144024	2026-05-19 20:24:58
20231204144025	2026-05-19 20:24:58
20240108234812	2026-05-19 20:24:58
20240109165339	2026-05-19 20:24:58
20240227174441	2026-05-19 20:24:58
20240311171622	2026-05-19 20:24:58
20240321100241	2026-05-19 20:24:58
20240401105812	2026-05-19 20:24:58
20240418121054	2026-05-19 20:24:58
20240523004032	2026-05-19 20:24:58
20240618124746	2026-05-19 20:24:58
20240801235015	2026-05-19 20:24:58
20240805133720	2026-05-19 20:24:58
20240827160934	2026-05-19 20:24:58
20240919163303	2026-05-19 20:24:58
20240919163305	2026-05-19 20:24:58
20241019105805	2026-05-19 20:24:58
20241030150047	2026-05-19 20:24:58
20241108114728	2026-05-19 20:24:58
20241121104152	2026-05-19 20:24:58
20241130184212	2026-05-19 20:24:58
20241220035512	2026-05-19 20:24:58
20241220123912	2026-05-19 20:24:58
20241224161212	2026-05-19 20:24:58
20250107150512	2026-05-19 20:24:58
20250110162412	2026-05-19 20:24:58
20250123174212	2026-05-19 20:24:58
20250128220012	2026-05-19 20:24:58
20250506224012	2026-05-19 20:24:58
20250523164012	2026-05-19 20:24:58
20250714121412	2026-05-19 20:24:58
20250905041441	2026-05-19 20:24:58
20251103001201	2026-05-19 20:24:58
20251120212548	2026-05-19 20:24:58
20251120215549	2026-05-19 20:24:58
20260218120000	2026-05-19 20:24:58
20260326120000	2026-05-19 20:24:58
\.


--
-- Data for Name: subscription; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.subscription (id, subscription_id, entity, filters, claims, created_at, action_filter) FROM stdin;
\.


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.buckets (id, name, owner, created_at, updated_at, public, avif_autodetection, file_size_limit, allowed_mime_types, owner_id, type) FROM stdin;
\.


--
-- Data for Name: buckets_analytics; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.buckets_analytics (name, type, format, created_at, updated_at, id, deleted_at) FROM stdin;
\.


--
-- Data for Name: buckets_vectors; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.buckets_vectors (id, type, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.migrations (id, name, hash, executed_at) FROM stdin;
0	create-migrations-table	e18db593bcde2aca2a408c4d1100f6abba2195df	2026-05-19 17:04:35.556499
1	initialmigration	6ab16121fbaa08bbd11b712d05f358f9b555d777	2026-05-19 17:04:35.610414
2	storage-schema	f6a1fa2c93cbcd16d4e487b362e45fca157a8dbd	2026-05-19 17:04:35.61594
3	pathtoken-column	2cb1b0004b817b29d5b0a971af16bafeede4b70d	2026-05-19 17:04:35.650799
4	add-migrations-rls	427c5b63fe1c5937495d9c635c263ee7a5905058	2026-05-19 17:04:35.663961
5	add-size-functions	79e081a1455b63666c1294a440f8ad4b1e6a7f84	2026-05-19 17:04:35.668443
6	change-column-name-in-get-size	ded78e2f1b5d7e616117897e6443a925965b30d2	2026-05-19 17:04:35.672287
7	add-rls-to-buckets	e7e7f86adbc51049f341dfe8d30256c1abca17aa	2026-05-19 17:04:35.676764
8	add-public-to-buckets	fd670db39ed65f9d08b01db09d6202503ca2bab3	2026-05-19 17:04:35.680463
9	fix-search-function	af597a1b590c70519b464a4ab3be54490712796b	2026-05-19 17:04:35.68387
10	search-files-search-function	b595f05e92f7e91211af1bbfe9c6a13bb3391e16	2026-05-19 17:04:35.687777
11	add-trigger-to-auto-update-updated_at-column	7425bdb14366d1739fa8a18c83100636d74dcaa2	2026-05-19 17:04:35.691108
12	add-automatic-avif-detection-flag	8e92e1266eb29518b6a4c5313ab8f29dd0d08df9	2026-05-19 17:04:35.695613
13	add-bucket-custom-limits	cce962054138135cd9a8c4bcd531598684b25e7d	2026-05-19 17:04:35.699397
14	use-bytes-for-max-size	941c41b346f9802b411f06f30e972ad4744dad27	2026-05-19 17:04:35.705009
15	add-can-insert-object-function	934146bc38ead475f4ef4b555c524ee5d66799e5	2026-05-19 17:04:35.739193
16	add-version	76debf38d3fd07dcfc747ca49096457d95b1221b	2026-05-19 17:04:35.742641
17	drop-owner-foreign-key	f1cbb288f1b7a4c1eb8c38504b80ae2a0153d101	2026-05-19 17:04:35.74988
18	add_owner_id_column_deprecate_owner	e7a511b379110b08e2f214be852c35414749fe66	2026-05-19 17:04:35.753901
19	alter-default-value-objects-id	02e5e22a78626187e00d173dc45f58fa66a4f043	2026-05-19 17:04:35.759387
20	list-objects-with-delimiter	cd694ae708e51ba82bf012bba00caf4f3b6393b7	2026-05-19 17:04:35.762774
21	s3-multipart-uploads	8c804d4a566c40cd1e4cc5b3725a664a9303657f	2026-05-19 17:04:35.767809
22	s3-multipart-uploads-big-ints	9737dc258d2397953c9953d9b86920b8be0cdb73	2026-05-19 17:04:35.780431
23	optimize-search-function	9d7e604cddc4b56a5422dc68c9313f4a1b6f132c	2026-05-19 17:04:35.790145
24	operation-function	8312e37c2bf9e76bbe841aa5fda889206d2bf8aa	2026-05-19 17:04:35.793863
25	custom-metadata	d974c6057c3db1c1f847afa0e291e6165693b990	2026-05-19 17:04:35.797242
26	objects-prefixes	215cabcb7f78121892a5a2037a09fedf9a1ae322	2026-05-19 17:04:35.800916
27	search-v2	859ba38092ac96eb3964d83bf53ccc0b141663a6	2026-05-19 17:04:35.805798
28	object-bucket-name-sorting	c73a2b5b5d4041e39705814fd3a1b95502d38ce4	2026-05-19 17:04:35.808787
29	create-prefixes	ad2c1207f76703d11a9f9007f821620017a66c21	2026-05-19 17:04:35.811895
30	update-object-levels	2be814ff05c8252fdfdc7cfb4b7f5c7e17f0bed6	2026-05-19 17:04:35.814847
31	objects-level-index	b40367c14c3440ec75f19bbce2d71e914ddd3da0	2026-05-19 17:04:35.818115
32	backward-compatible-index-on-objects	e0c37182b0f7aee3efd823298fb3c76f1042c0f7	2026-05-19 17:04:35.821046
33	backward-compatible-index-on-prefixes	b480e99ed951e0900f033ec4eb34b5bdcb4e3d49	2026-05-19 17:04:35.824039
34	optimize-search-function-v1	ca80a3dc7bfef894df17108785ce29a7fc8ee456	2026-05-19 17:04:35.827064
35	add-insert-trigger-prefixes	458fe0ffd07ec53f5e3ce9df51bfdf4861929ccc	2026-05-19 17:04:35.83005
36	optimise-existing-functions	6ae5fca6af5c55abe95369cd4f93985d1814ca8f	2026-05-19 17:04:35.833407
37	add-bucket-name-length-trigger	3944135b4e3e8b22d6d4cbb568fe3b0b51df15c1	2026-05-19 17:04:35.836348
38	iceberg-catalog-flag-on-buckets	02716b81ceec9705aed84aa1501657095b32e5c5	2026-05-19 17:04:35.8404
39	add-search-v2-sort-support	6706c5f2928846abee18461279799ad12b279b78	2026-05-19 17:04:35.848177
40	fix-prefix-race-conditions-optimized	7ad69982ae2d372b21f48fc4829ae9752c518f6b	2026-05-19 17:04:35.851261
41	add-object-level-update-trigger	07fcf1a22165849b7a029deed059ffcde08d1ae0	2026-05-19 17:04:35.854327
42	rollback-prefix-triggers	771479077764adc09e2ea2043eb627503c034cd4	2026-05-19 17:04:35.857836
43	fix-object-level	84b35d6caca9d937478ad8a797491f38b8c2979f	2026-05-19 17:04:35.860942
44	vector-bucket-type	99c20c0ffd52bb1ff1f32fb992f3b351e3ef8fb3	2026-05-19 17:04:35.864042
45	vector-buckets	049e27196d77a7cb76497a85afae669d8b230953	2026-05-19 17:04:35.867813
46	buckets-objects-grants	fedeb96d60fefd8e02ab3ded9fbde05632f84aed	2026-05-19 17:04:35.876548
47	iceberg-table-metadata	649df56855c24d8b36dd4cc1aeb8251aa9ad42c2	2026-05-19 17:04:35.881677
48	iceberg-catalog-ids	e0e8b460c609b9999ccd0df9ad14294613eed939	2026-05-19 17:04:35.884717
49	buckets-objects-grants-postgres	072b1195d0d5a2f888af6b2302a1938dd94b8b3d	2026-05-19 17:04:35.899594
50	search-v2-optimised	6323ac4f850aa14e7387eb32102869578b5bd478	2026-05-19 17:04:35.903421
51	index-backward-compatible-search	2ee395d433f76e38bcd3856debaf6e0e5b674011	2026-05-19 17:04:36.86942
52	drop-not-used-indexes-and-functions	5cc44c8696749ac11dd0dc37f2a3802075f3a171	2026-05-19 17:04:36.876365
53	drop-index-lower-name	d0cb18777d9e2a98ebe0bc5cc7a42e57ebe41854	2026-05-19 17:04:36.89921
54	drop-index-object-level	6289e048b1472da17c31a7eba1ded625a6457e67	2026-05-19 17:04:36.901689
55	prevent-direct-deletes	262a4798d5e0f2e7c8970232e03ce8be695d5819	2026-05-19 17:04:36.90281
56	fix-optimized-search-function	b823ed1e418101032fa01374edc9a436e54e3ed4	2026-05-19 17:04:36.907806
57	s3-multipart-uploads-metadata	f127886e00d1b374fadbc7c6b31e09336aad5287	2026-05-19 17:04:36.915539
58	operation-ergonomics	00ca5d483b3fe0d522133d9002ccc5df98365120	2026-05-19 17:04:36.918672
59	drop-unused-functions	38456f13e39691c2bbb4b5151d0d1cdbabd4a8c4	2026-05-19 17:04:36.92223
60	optimize-existing-functions-again	db35e1c91a9201e59f4fef8d972c2f277d68b157	2026-05-19 17:04:36.92562
\.


--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.objects (id, bucket_id, name, owner, created_at, updated_at, last_accessed_at, metadata, version, owner_id, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.s3_multipart_uploads (id, in_progress_size, upload_signature, bucket_id, key, version, owner_id, created_at, user_metadata, metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.s3_multipart_uploads_parts (id, upload_id, size, part_number, bucket_id, key, etag, owner_id, version, created_at) FROM stdin;
\.


--
-- Data for Name: vector_indexes; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.vector_indexes (id, name, bucket_id, data_type, dimension, distance_metric, metadata_configuration, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: secrets; Type: TABLE DATA; Schema: vault; Owner: -
--

COPY vault.secrets (id, name, description, secret, key_id, nonce, created_at, updated_at) FROM stdin;
\.


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.refresh_tokens_id_seq', 1, false);


--
-- Name: branches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.branches_id_seq', 6, true);


--
-- Name: contact_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.contact_messages_id_seq', 1, false);


--
-- Name: domains_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.domains_id_seq', 2, true);


--
-- Name: faqs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.faqs_id_seq', 1, false);


--
-- Name: menu_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.menu_items_id_seq', 16, true);


--
-- Name: order_claims_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.order_claims_id_seq', 1, false);


--
-- Name: restaurants_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.restaurants_id_seq', 1, true);


--
-- Name: reward_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.reward_settings_id_seq', 1, true);


--
-- Name: subscription_id_seq; Type: SEQUENCE SET; Schema: realtime; Owner: -
--

SELECT pg_catalog.setval('realtime.subscription_id_seq', 1, false);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: custom_oauth_providers custom_oauth_providers_identifier_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.custom_oauth_providers
    ADD CONSTRAINT custom_oauth_providers_identifier_key UNIQUE (identifier);


--
-- Name: custom_oauth_providers custom_oauth_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.custom_oauth_providers
    ADD CONSTRAINT custom_oauth_providers_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_code_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_code_key UNIQUE (authorization_code);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_id_key UNIQUE (authorization_id);


--
-- Name: oauth_authorizations oauth_authorizations_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_pkey PRIMARY KEY (id);


--
-- Name: oauth_client_states oauth_client_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_client_states
    ADD CONSTRAINT oauth_client_states_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_user_client_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_client_unique UNIQUE (user_id, client_id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: webauthn_challenges webauthn_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.webauthn_challenges
    ADD CONSTRAINT webauthn_challenges_pkey PRIMARY KEY (id);


--
-- Name: webauthn_credentials webauthn_credentials_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.webauthn_credentials
    ADD CONSTRAINT webauthn_credentials_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_restaurant_id_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_restaurant_id_email_key UNIQUE (restaurant_id, email);


--
-- Name: branches branches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_pkey PRIMARY KEY (id);


--
-- Name: contact_messages contact_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_messages
    ADD CONSTRAINT contact_messages_pkey PRIMARY KEY (id);


--
-- Name: content_pages content_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_pages
    ADD CONSTRAINT content_pages_pkey PRIMARY KEY (restaurant_id, slug);


--
-- Name: domains domains_domain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_domain_key UNIQUE (domain);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (id);


--
-- Name: faqs faqs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faqs
    ADD CONSTRAINT faqs_pkey PRIMARY KEY (id);


--
-- Name: menu_items menu_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_pkey PRIMARY KEY (id);


--
-- Name: order_claims order_claims_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_claims
    ADD CONSTRAINT order_claims_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: platform_admins platform_admins_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_admins
    ADD CONSTRAINT platform_admins_email_key UNIQUE (email);


--
-- Name: platform_admins platform_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.platform_admins
    ADD CONSTRAINT platform_admins_pkey PRIMARY KEY (id);


--
-- Name: points points_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.points
    ADD CONSTRAINT points_pkey PRIMARY KEY (user_id, restaurant_id);


--
-- Name: restaurants restaurants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_pkey PRIMARY KEY (id);


--
-- Name: restaurants restaurants_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.restaurants
    ADD CONSTRAINT restaurants_slug_key UNIQUE (slug);


--
-- Name: reward_settings reward_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reward_settings
    ADD CONSTRAINT reward_settings_pkey PRIMARY KEY (id);


--
-- Name: reward_settings reward_settings_restaurant_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reward_settings
    ADD CONSTRAINT reward_settings_restaurant_id_key UNIQUE (restaurant_id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (restaurant_id, key);


--
-- Name: theme_settings theme_settings_restaurant_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.theme_settings
    ADD CONSTRAINT theme_settings_restaurant_id_key UNIQUE (restaurant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_restaurant_id_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_restaurant_id_email_key UNIQUE (restaurant_id, email);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2026_05_22 messages_2026_05_22_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2026_05_22
    ADD CONSTRAINT messages_2026_05_22_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2026_05_23 messages_2026_05_23_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2026_05_23
    ADD CONSTRAINT messages_2026_05_23_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2026_05_24 messages_2026_05_24_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2026_05_24
    ADD CONSTRAINT messages_2026_05_24_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2026_05_25 messages_2026_05_25_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2026_05_25
    ADD CONSTRAINT messages_2026_05_25_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2026_05_26 messages_2026_05_26_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2026_05_26
    ADD CONSTRAINT messages_2026_05_26_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets_analytics buckets_analytics_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.buckets_analytics
    ADD CONSTRAINT buckets_analytics_pkey PRIMARY KEY (id);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: buckets_vectors buckets_vectors_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.buckets_vectors
    ADD CONSTRAINT buckets_vectors_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: vector_indexes vector_indexes_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.vector_indexes
    ADD CONSTRAINT vector_indexes_pkey PRIMARY KEY (id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: custom_oauth_providers_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX custom_oauth_providers_created_at_idx ON auth.custom_oauth_providers USING btree (created_at);


--
-- Name: custom_oauth_providers_enabled_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX custom_oauth_providers_enabled_idx ON auth.custom_oauth_providers USING btree (enabled);


--
-- Name: custom_oauth_providers_identifier_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX custom_oauth_providers_identifier_idx ON auth.custom_oauth_providers USING btree (identifier);


--
-- Name: custom_oauth_providers_provider_type_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX custom_oauth_providers_provider_type_idx ON auth.custom_oauth_providers USING btree (provider_type);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_oauth_client_states_created_at; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_oauth_client_states_created_at ON auth.oauth_client_states USING btree (created_at);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: idx_users_created_at_desc; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_created_at_desc ON auth.users USING btree (created_at DESC);


--
-- Name: idx_users_email; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_email ON auth.users USING btree (email);


--
-- Name: idx_users_last_sign_in_at_desc; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_last_sign_in_at_desc ON auth.users USING btree (last_sign_in_at DESC);


--
-- Name: idx_users_name; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_users_name ON auth.users USING btree (((raw_user_meta_data ->> 'name'::text))) WHERE ((raw_user_meta_data ->> 'name'::text) IS NOT NULL);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_auth_pending_exp_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_auth_pending_exp_idx ON auth.oauth_authorizations USING btree (expires_at) WHERE (status = 'pending'::auth.oauth_authorization_status);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: oauth_consents_active_client_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_active_client_idx ON auth.oauth_consents USING btree (client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_active_user_client_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_active_user_client_idx ON auth.oauth_consents USING btree (user_id, client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_user_order_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_user_order_idx ON auth.oauth_consents USING btree (user_id, granted_at DESC);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_oauth_client_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_oauth_client_id_idx ON auth.sessions USING btree (oauth_client_id);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: webauthn_challenges_expires_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX webauthn_challenges_expires_at_idx ON auth.webauthn_challenges USING btree (expires_at);


--
-- Name: webauthn_challenges_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX webauthn_challenges_user_id_idx ON auth.webauthn_challenges USING btree (user_id);


--
-- Name: webauthn_credentials_credential_id_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX webauthn_credentials_credential_id_key ON auth.webauthn_credentials USING btree (credential_id);


--
-- Name: webauthn_credentials_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX webauthn_credentials_user_id_idx ON auth.webauthn_credentials USING btree (user_id);


--
-- Name: idx_branches_restaurant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_branches_restaurant ON public.branches USING btree (restaurant_id);


--
-- Name: idx_contact_messages_rest; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contact_messages_rest ON public.contact_messages USING btree (restaurant_id);


--
-- Name: idx_faqs_restaurant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_faqs_restaurant ON public.faqs USING btree (restaurant_id);


--
-- Name: idx_menu_items_rest_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_menu_items_rest_category ON public.menu_items USING btree (restaurant_id, category);


--
-- Name: idx_menu_items_restaurant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_menu_items_restaurant ON public.menu_items USING btree (restaurant_id);


--
-- Name: idx_orders_claim_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_claim_status ON public.orders USING btree (restaurant_id, claim_status);


--
-- Name: idx_orders_restaurant_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_restaurant_created ON public.orders USING btree (restaurant_id, created_at DESC);


--
-- Name: idx_orders_restaurant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_restaurant_id ON public.orders USING btree (restaurant_id);


--
-- Name: idx_orders_restaurant_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_restaurant_status ON public.orders USING btree (restaurant_id, status);


--
-- Name: idx_orders_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_orders_user_id ON public.orders USING btree (user_id);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: messages_inserted_at_topic_index; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_inserted_at_topic_index ON ONLY realtime.messages USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2026_05_22_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2026_05_22_inserted_at_topic_idx ON realtime.messages_2026_05_22 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2026_05_23_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2026_05_23_inserted_at_topic_idx ON realtime.messages_2026_05_23 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2026_05_24_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2026_05_24_inserted_at_topic_idx ON realtime.messages_2026_05_24 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2026_05_25_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2026_05_25_inserted_at_topic_idx ON realtime.messages_2026_05_25 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2026_05_26_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2026_05_26_inserted_at_topic_idx ON realtime.messages_2026_05_26 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: subscription_subscription_id_entity_filters_action_filter_key; Type: INDEX; Schema: realtime; Owner: -
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_action_filter_key ON realtime.subscription USING btree (subscription_id, entity, filters, action_filter);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: buckets_analytics_unique_name_idx; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX buckets_analytics_unique_name_idx ON storage.buckets_analytics USING btree (name) WHERE (deleted_at IS NULL);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: idx_objects_bucket_id_name_lower; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_bucket_id_name_lower ON storage.objects USING btree (bucket_id, lower(name) COLLATE "C");


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: vector_indexes_name_bucket_id_idx; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX vector_indexes_name_bucket_id_idx ON storage.vector_indexes USING btree (name, bucket_id);


--
-- Name: messages_2026_05_22_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2026_05_22_inserted_at_topic_idx;


--
-- Name: messages_2026_05_22_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2026_05_22_pkey;


--
-- Name: messages_2026_05_23_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2026_05_23_inserted_at_topic_idx;


--
-- Name: messages_2026_05_23_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2026_05_23_pkey;


--
-- Name: messages_2026_05_24_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2026_05_24_inserted_at_topic_idx;


--
-- Name: messages_2026_05_24_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2026_05_24_pkey;


--
-- Name: messages_2026_05_25_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2026_05_25_inserted_at_topic_idx;


--
-- Name: messages_2026_05_25_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2026_05_25_pkey;


--
-- Name: messages_2026_05_26_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2026_05_26_inserted_at_topic_idx;


--
-- Name: messages_2026_05_26_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2026_05_26_pkey;


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: -
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: buckets enforce_bucket_name_length_trigger; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER enforce_bucket_name_length_trigger BEFORE INSERT OR UPDATE OF name ON storage.buckets FOR EACH ROW EXECUTE FUNCTION storage.enforce_bucket_name_length();


--
-- Name: buckets protect_buckets_delete; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER protect_buckets_delete BEFORE DELETE ON storage.buckets FOR EACH STATEMENT EXECUTE FUNCTION storage.protect_delete();


--
-- Name: objects protect_objects_delete; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER protect_objects_delete BEFORE DELETE ON storage.objects FOR EACH STATEMENT EXECUTE FUNCTION storage.protect_delete();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_oauth_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_oauth_client_id_fkey FOREIGN KEY (oauth_client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: webauthn_challenges webauthn_challenges_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.webauthn_challenges
    ADD CONSTRAINT webauthn_challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: webauthn_credentials webauthn_credentials_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.webauthn_credentials
    ADD CONSTRAINT webauthn_credentials_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: admin_users admin_users_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: branches branches_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: contact_messages contact_messages_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_messages
    ADD CONSTRAINT contact_messages_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: content_pages content_pages_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_pages
    ADD CONSTRAINT content_pages_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: domains domains_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: faqs faqs_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.faqs
    ADD CONSTRAINT faqs_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: menu_items menu_items_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: order_claims order_claims_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_claims
    ADD CONSTRAINT order_claims_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: orders orders_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: points points_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.points
    ADD CONSTRAINT points_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id);


--
-- Name: reward_settings reward_settings_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reward_settings
    ADD CONSTRAINT reward_settings_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: settings settings_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: theme_settings theme_settings_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.theme_settings
    ADD CONSTRAINT theme_settings_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: users users_restaurant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_restaurant_id_fkey FOREIGN KEY (restaurant_id) REFERENCES public.restaurants(id) ON DELETE CASCADE;


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: vector_indexes vector_indexes_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.vector_indexes
    ADD CONSTRAINT vector_indexes_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets_vectors(id);


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: -
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_analytics; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets_vectors; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets_vectors ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: vector_indexes; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.vector_indexes ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: -
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


--
-- Name: supabase_realtime_messages_publication; Type: PUBLICATION; Schema: -; Owner: -
--

CREATE PUBLICATION supabase_realtime_messages_publication WITH (publish = 'insert, update, delete, truncate');


--
-- Name: supabase_realtime_messages_publication messages; Type: PUBLICATION TABLE; Schema: realtime; Owner: -
--

ALTER PUBLICATION supabase_realtime_messages_publication ADD TABLE ONLY realtime.messages;


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


--
-- PostgreSQL database dump complete
--

\unrestrict 9cPaowPYlIASR5tyUhDE8qx16tjmE8f7PQnzmNZXF7MihhjQryifxeSfXLkE0Ql

