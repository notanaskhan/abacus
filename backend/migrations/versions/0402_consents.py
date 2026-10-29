"""§7216 consents (T-01-T08; T-01 §4.2 `00NN_consents`; SPEC-501 AC-15, AC-16).

One purpose per signed document (Treas. Reg. §301.7216-3; DF-31). No consent text or template is
inserted here: templates are counsel-approved database content imported by the firm (T-01-T11).

- `consent_sets` (forced RLS): the `use` and `ai_disclosure` consents requested together for a
  filing unit and its tax years (`use_ai_disclosure`), or one consent on its own (`single`).
- `consents` (forced RLS): one row per purpose, with at least one tax year, its scope and
  recipients, the template version and the signed text's SHA-256, the source (a C7 envelope or a
  record), its status and dates. A partial unique index refuses a second open request, or a new
  request while a decline stands, for the same entity, purpose and years.
- `consent_signers` (forced RLS): who must sign and who did, how and with what evidence.
- `consent_events` (forced RLS, insert-only, immutable): every change, with the actor.

The app inserts and updates the listed columns; it never deletes a consent, a signer or an event.

Revision ID: 0402
Revises: 0401
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0402"
down_revision = "0401"
branch_labels = None
depends_on = None

_PURPOSES = (
    "('use', 'ai_disclosure', 'offshore_disclosure', 'third_party_disclosure', "
    "'other_services_use', 'firm_defined')"
)
_STATUSES = "('requested', 'signed', 'declined', 'revoked', 'superseded', 'expired')"
_TABLES = ("consent_sets", "consents", "consent_signers", "consent_events")
SET_INSERT = (
    "id",
    "tenant_id",
    "client_id",
    "filing_unit_entity_id",
    "kind",
    "tax_years",
    "created_by",
)
CONSENT_INSERT = (
    "id",
    "tenant_id",
    "client_id",
    "client_entity_id",
    "consent_set_id",
    "purpose",
    "tax_years",
    "scope",
    "recipients",
    "provider_terms_version",
    "template_version_id",
    "text_sha256",
    "source",
    "envelope_id",
    "status",
    "requested_at",
    "renewal_of_id",
    "created_by",
)
CONSENT_UPDATE = (
    "status",
    "signed_at",
    "expires_at",
    "declined_at",
    "revoked_at",
    "copy_delivered_at",
    "copy_delivered_channel",
    "row_version",
)
SIGNER_INSERT = (
    "id",
    "tenant_id",
    "consent_id",
    "contact_id",
    "user_id",
    "signer_role",
    "required",
)
SIGNER_UPDATE = ("signed_at", "method", "evidence_version_id")
EVENT_INSERT = ("tenant_id", "consent_id", "kind", "actor_kind", "actor_id", "facts")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE consent_sets (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_id uuid NOT NULL,
            filing_unit_entity_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('use_ai_disclosure', 'single')),
            tax_years integer[] NOT NULL CHECK (cardinality(tax_years) > 0),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, filing_unit_entity_id)
                REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE consents (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            client_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            consent_set_id uuid NULL,
            purpose text NOT NULL CHECK (purpose IN {_PURPOSES}),
            tax_years integer[] NOT NULL CHECK (cardinality(tax_years) > 0),
            scope jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(scope) = 'object'),
            recipients jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(recipients) = 'array'),
            provider_terms_version text NOT NULL
                CHECK (char_length(provider_terms_version) BETWEEN 1 AND 40),
            template_version_id uuid NOT NULL,
            text_sha256 bytea NOT NULL CHECK (octet_length(text_sha256) = 32),
            source text NOT NULL CHECK (source IN ('envelope', 'record')),
            envelope_id uuid NULL,
            status text NOT NULL DEFAULT 'requested' CHECK (status IN {_STATUSES}),
            requested_at timestamptz NOT NULL DEFAULT abacus_now(),
            signed_at timestamptz NULL,
            expires_at timestamptz NULL,
            declined_at timestamptz NULL,
            revoked_at timestamptz NULL,
            copy_delivered_at timestamptz NULL,
            copy_delivered_channel text NULL
                CHECK (copy_delivered_channel IN ('portal', 'email', 'paper')),
            renewal_of_id uuid NULL,
            created_by uuid NOT NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, consent_set_id) REFERENCES consent_sets (tenant_id, id),
            FOREIGN KEY (tenant_id, renewal_of_id) REFERENCES consents (tenant_id, id),
            -- an envelope-sourced consent names its envelope; a record never does
            CHECK ((source = 'envelope') = (envelope_id IS NOT NULL)),
            CHECK (status <> 'signed' OR signed_at IS NOT NULL),
            CHECK (status <> 'declined' OR declined_at IS NOT NULL),
            CHECK (status <> 'revoked' OR revoked_at IS NOT NULL)
        )
        """
    )
    # One open request, or one standing decline, per entity, purpose and years: a declined
    # purpose is not requested again until the decline is superseded (T-01 §3.1; 409
    # `consent_declined`).
    op.execute(
        "CREATE UNIQUE INDEX consents_one_open ON consents "
        "(tenant_id, client_entity_id, purpose, tax_years) "
        "WHERE status IN ('requested', 'declined')"
    )
    op.execute(
        "CREATE INDEX consents_in_force ON consents (tenant_id, client_entity_id, purpose) "
        "WHERE status = 'signed'"
    )
    op.execute(
        """
        CREATE TABLE consent_signers (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            consent_id uuid NOT NULL,
            contact_id uuid NULL,
            user_id uuid NULL,
            signer_role text NOT NULL
                CHECK (signer_role IN ('taxpayer', 'spouse', 'officer', 'fiduciary', 'partner')),
            required boolean NOT NULL DEFAULT true,
            signed_at timestamptz NULL,
            method text NULL CHECK (method IN ('email_code', 'kba', 'wet', 'record')),
            evidence_version_id uuid NULL,
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, consent_id) REFERENCES consents (tenant_id, id),
            CHECK (contact_id IS NOT NULL OR user_id IS NOT NULL),
            CHECK ((signed_at IS NULL) = (method IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE consent_events (
            id bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            consent_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('requested', 'signer_signed', 'signed',
                'recorded', 'declined', 'revoked', 'expired', 'superseded', 'copy_delivered',
                'renewal_drafted')),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_id text NOT NULL CHECK (char_length(actor_id) BETWEEN 1 AND 200),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            facts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(facts) = 'object'),
            PRIMARY KEY (tenant_id, id),
            FOREIGN KEY (tenant_id, consent_id) REFERENCES consents (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION consent_events_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'consent_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER consent_events_immutable BEFORE UPDATE OR DELETE ON consent_events "
        "FOR EACH ROW EXECUTE FUNCTION consent_events_immutable()"
    )
    op.execute(
        "CREATE TRIGGER consent_events_no_truncate BEFORE TRUNCATE ON consent_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION consent_events_immutable()"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, "consent_sets", SET_INSERT)
    insert_columns(op, "consents", CONSENT_INSERT)
    op.execute(f"GRANT UPDATE ({', '.join(CONSENT_UPDATE)}) ON consents TO abacus_app")
    insert_columns(op, "consent_signers", SIGNER_INSERT)
    op.execute(f"GRANT UPDATE ({', '.join(SIGNER_UPDATE)}) ON consent_signers TO abacus_app")
    insert_only(op, "consent_events")
    insert_columns(op, "consent_events", EVENT_INSERT)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION consent_events_immutable()")
