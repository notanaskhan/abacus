"""Integrations W1 write operations, grants and switches (C-02-T05; C20 v2.1; SPEC-700 AC-15,
AC-17, AC-21, AC-23; ADR-344; DEC-5504). Expand-only.

- `write_operations`: one call to a client's system under a declared write, unique on
  `(tenant_id, capability_id, idempotency_key)`, always a person's (the grant's approver).
- `write_evidence` (insert-only, immutable): the request, response and read-back bodies' object
  keys and hashes (the bodies live in the evidence store under Object Lock).
- `connection_write_grants` (insert-only, immutable): the client owner's grant and revocation
  events; the current grant is the latest event. A trigger refuses a grant for an attest-flagged
  client (I-POLICY-NOT-ATTEST, ADR-164).
- `firm_write_capabilities` (insert-only, immutable): the firm switch's history (security admin,
  fresh MFA); the current state is the latest row.
- `connection_engagement_settings`: an engagement's `posting_enabled` switch for a connection
  (C-01 did not add the table).

Nothing here writes to a client system: W1 stays `enabled: false` (ADR-344 §10).

Revision ID: 0951
Revises: 0950
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0951"
down_revision = "0950"
branch_labels = None
depends_on = None

_CAPABILITY = "text NOT NULL CHECK (capability_id ~ '^[a-z][a-z_]{2,62}$')"
TABLES = (
    "write_operations",
    "write_evidence",
    "connection_write_grants",
    "firm_write_capabilities",
    "connection_engagement_settings",
)
IMMUTABLE = ("write_evidence", "connection_write_grants", "firm_write_capabilities")
INSERTS: dict[str, tuple[str, ...]] = {
    "write_operations": (
        "tenant_id", "capability_id", "client_entity_id", "connection_id", "subject_type",
        "subject_id", "operation", "idempotency_key", "approval_grant_id", "actor_user_id",
    ),
    "write_evidence": (
        "tenant_id", "write_operation_id", "kind", "object_key", "sha256", "bytes",
    ),
    "connection_write_grants": (
        "tenant_id", "connection_id", "client_entity_id", "capability_id",
        "consent_copy_version", "granted_by_client_user_id", "mfa_at", "event", "actor_id",
    ),
    "firm_write_capabilities": (
        "tenant_id", "capability_id", "enabled", "changed_by", "mfa_at", "reason",
    ),
    "connection_engagement_settings": (
        "tenant_id", "engagement_id", "connection_id", "posting_enabled", "posting_enabled_by",
        "posting_enabled_at",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "write_operations": (
        "status", "provider_request_id", "external_ref", "attempt", "started_at", "finished_at",
    ),
    "connection_engagement_settings": (
        "posting_enabled", "posting_enabled_by", "posting_enabled_at", "version",
    ),
}  # fmt: skip


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE write_operations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            capability_id {_CAPABILITY},
            client_entity_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            subject_type text NOT NULL CHECK (subject_type ~ '^[a-z][a-z_]{{2,40}}$'),
            subject_id uuid NOT NULL,
            operation text NOT NULL
                CHECK (operation IN ('create_journal_entry', 'set_closing_date')),
            idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 8 AND 200),
            approval_grant_id uuid NOT NULL,
            actor_user_id uuid NOT NULL,
            actor_kind text NOT NULL DEFAULT 'human' CHECK (actor_kind = 'human'),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'dry_run_ok',
                'dry_run_failed', 'sent', 'verified', 'failed', 'verify_mismatch')),
            provider_request_id text NULL CHECK (char_length(provider_request_id) <= 100),
            external_ref text NULL CHECK (char_length(external_ref) <= 64),
            attempt integer NOT NULL DEFAULT 1 CHECK (attempt >= 1),
            started_at timestamptz NULL,
            finished_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, capability_id, idempotency_key),
            CHECK (status <> 'verified' OR external_ref IS NOT NULL),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id),
            FOREIGN KEY (tenant_id, actor_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE write_evidence (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            write_operation_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('request', 'response', 'readback')),
            object_key text NOT NULL CHECK (char_length(object_key) BETWEEN 1 AND 512),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            bytes bigint NOT NULL CHECK (bytes >= 0),
            captured_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, write_operation_id, kind),
            FOREIGN KEY (tenant_id, write_operation_id) REFERENCES write_operations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE connection_write_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            capability_id {_CAPABILITY},
            consent_copy_version text NOT NULL
                CHECK (consent_copy_version ~ '^[a-z0-9_.]{{3,80}}$'),
            granted_by_client_user_id uuid NOT NULL,
            mfa_at timestamptz NOT NULL,
            event text NOT NULL CHECK (event IN ('granted', 'revoked')),
            actor_id text NOT NULL CHECK (char_length(actor_id) BETWEEN 1 AND 64),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id)
        )
        """
    )
    # A grant is refused for an attest client (ADR-164, ADR-344 §4); a revocation always goes in.
    op.execute(
        """
        CREATE FUNCTION connection_write_grants_not_attest() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.event = 'granted' AND EXISTS (
                SELECT 1 FROM public.client_entities ce
                  JOIN public.clients c ON c.tenant_id = ce.tenant_id AND c.id = ce.client_id
                 WHERE ce.tenant_id = NEW.tenant_id AND ce.id = NEW.client_entity_id
                   AND c.is_attest_client
            ) THEN
                RAISE EXCEPTION 'attest_client_posting_refused' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION connection_write_grants_not_attest() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER connection_write_grants_not_attest BEFORE INSERT "
        "ON connection_write_grants FOR EACH ROW "
        "EXECUTE FUNCTION connection_write_grants_not_attest()"
    )
    op.execute(
        f"""
        CREATE TABLE firm_write_capabilities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            capability_id {_CAPABILITY},
            enabled boolean NOT NULL,
            changed_by uuid NOT NULL,
            changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            mfa_at timestamptz NOT NULL,
            reason text NULL CHECK (char_length(reason) <= 500),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'
                    AND actor_kind = current_setting('app.actor_kind', true)),
            UNIQUE (tenant_id, id),
            CHECK (changed_by::text = current_setting('app.actor_id', true)),
            FOREIGN KEY (tenant_id, changed_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE connection_engagement_settings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            posting_enabled boolean NOT NULL DEFAULT false,
            posting_enabled_by uuid NULL,
            posting_enabled_at timestamptz NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, connection_id),
            CHECK (NOT posting_enabled
                OR (posting_enabled_by IS NOT NULL AND posting_enabled_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX connection_write_grants_latest ON connection_write_grants "
        "(tenant_id, connection_id, capability_id, at DESC)"
    )
    op.execute(
        "CREATE INDEX firm_write_capabilities_latest ON firm_write_capabilities "
        "(tenant_id, capability_id, changed_at DESC)"
    )
    for table in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, INSERTS[table])
    for table in IMMUTABLE:
        insert_only(op, table)
        _immutable(table)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in (
        "connection_engagement_settings",
        "firm_write_capabilities",
        "connection_write_grants",
        "write_evidence",
        "write_operations",
    ):
        op.execute(f"DROP TABLE {table}")
    for table in IMMUTABLE:
        op.execute(f"DROP FUNCTION {table}_immutable()")
    op.execute("DROP FUNCTION connection_write_grants_not_attest()")
