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
END
$$;

-- Enforce attributes even if the roles already existed with others.
ALTER ROLE abacus_owner NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION;
ALTER ROLE abacus_app   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION NOINHERIT;

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO abacus_owner', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO abacus_app', current_database());
  EXECUTE format('REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
END
$$;

-- pgvector is not a trusted extension, so the admin creates it here, not a migration.
CREATE EXTENSION IF NOT EXISTS vector;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO abacus_owner;
GRANT USAGE ON SCHEMA public TO abacus_app;

-- Tables the owner creates are readable and writable by the app; row-level security decides which
-- rows. Insert-only tables revoke UPDATE and DELETE in their migration (kernel.db.migration).
ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO abacus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE abacus_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO abacus_app;
