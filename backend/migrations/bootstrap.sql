-- Database roles and privileges (ADR-014; TASK-005 design §1). PROTECTED.
-- Run once per environment as a superuser or the managed-database admin, before any migration:
-- locally by the compose `db` init and the test fixtures, in staging by the operator (TASK-014).
-- Idempotent: safe to run again. Passwords are set separately, per environment.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'abacus_owner') THEN
    CREATE ROLE abacus_owner LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'abacus_app') THEN
    CREATE ROLE abacus_app LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'abacus_relay') THEN
    CREATE ROLE abacus_relay LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'abacus_identity') THEN
    CREATE ROLE abacus_identity LOGIN;
  END IF;
  -- Q-01-T19 (ADR-157): operator tasks run as this role: no table privileges, EXECUTE only on
  -- set_platform_control() and provision_firm() (granted in migration 0086).
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'abacus_ops') THEN
    CREATE ROLE abacus_ops LOGIN;
  END IF;
END
$$;

-- ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner (below) needs the admin to be a member of
-- abacus_owner; managed-Postgres admins are not superusers, so grant it explicitly.
DO $$
BEGIN
  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    EXECUTE format('GRANT abacus_owner TO %I', current_user);
  END IF;
END
$$;

-- Enforce attributes even if the roles already existed with others. A managed database's admin
-- (RDS `rds_superuser`) is not a superuser and may not touch SUPERUSER or REPLICATION at all; roles
-- it creates never have either, so there it sets only the attributes it may change (Q-01-T20).
DO $$
DECLARE
  super boolean := (SELECT rolsuper FROM pg_roles WHERE rolname = current_user);
  privileged text := CASE WHEN super THEN ' NOSUPERUSER NOREPLICATION' ELSE '' END;
BEGIN
  EXECUTE 'ALTER ROLE abacus_owner NOCREATEDB NOCREATEROLE NOBYPASSRLS' || privileged;
  EXECUTE 'ALTER ROLE abacus_app NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT' || privileged;
  -- The outbox relay reads every tenant's unpublished events (TASK-006, founder-approved): it
  -- bypasses row-level security, so it is granted privileges on `outbox` only (in migration 0002).
  EXECUTE 'ALTER ROLE abacus_relay NOCREATEDB NOCREATEROLE BYPASSRLS NOINHERIT' || privileged;
  -- Sign-in finds a user's memberships before any tenant is chosen (TASK-007, founder-approved): it
  -- bypasses row-level security, so it may only read users, memberships and firms (migration 0004).
  EXECUTE 'ALTER ROLE abacus_identity NOCREATEDB NOCREATEROLE BYPASSRLS NOINHERIT' || privileged;
  EXECUTE 'ALTER ROLE abacus_ops NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT' || privileged;
END
$$;
ALTER ROLE abacus_identity SET default_transaction_read_only = on;

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO abacus_owner', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO abacus_app, abacus_relay, abacus_identity, abacus_ops',
    current_database());
  EXECUTE format('REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
END
$$;

-- pgvector is not a trusted extension, so the admin creates it here, not a migration.
CREATE EXTENSION IF NOT EXISTS vector;
-- P-07-T07 (DEC-16): name search. Trusted, but the owner role has no CREATE on the database, so
-- the admin creates them here too; migration 0103 refuses to run without them.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO abacus_owner;
GRANT USAGE ON SCHEMA public TO abacus_app, abacus_relay, abacus_identity, abacus_ops;

-- Tables the owner creates are readable and writable by the app; row-level security decides which
-- rows. Insert-only tables revoke UPDATE and DELETE in their migration (kernel.db.migration).
ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO abacus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO abacus_app;
-- Functions the owner creates are not executable by everyone by default.
ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Large objects are not tenant-scoped (no row-level security), so nobody but the admin may use them.
DO $$
DECLARE f regprocedure;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure FROM pg_proc p
    WHERE p.pronamespace = 'pg_catalog'::regnamespace
      AND (p.proname LIKE 'lo\_%' OR p.proname IN ('loread', 'lowrite'))
  LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
  END LOOP;
END
$$;

-- The application has no business in the maintenance databases.
REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE template1 FROM PUBLIC;
