"""Sealed TINs, client descriptors, entity relationships and name search (P-07-T07; DEC-52).

- `client_entities` gains a TIN that is never stored in plaintext:
  - `tin_sealed` (an envelope under the firm's key);
  - `tin_last4`, the only digits any payload shows;
  - `tin_kind` (`ssn`, `ein`, `itin`) and `tin_status` (`none`, `on_file`, `applied_for`);
  - `tin_fingerprint`, an HMAC-SHA256 under a per-firm key, unique within the firm, so the same
    TIN can't be on file twice and a match is found without opening any envelope.
  The app may update these columns (P-07-T10 seals and writes them); an on-file TIN has all of
  them, and no other status has any.
- `clients.descriptor`: a short free-text line (120 characters at most).
- New `entity_relationships`: how two entities of a firm relate (spouse, owner of, trustee of,
  ...). A relationship ends by setting `effective_to`; it is never deleted.
- Name search: GIN trigram indexes on client, entity and contact names, with `tenant_id` first
  through btree_gin. `contacts` gains a generated `normalised_name`. The extensions are created by
  the protected bootstrap (the owner role can't create them); this migration fails clearly
  without them.

No column is named `tin`, `ssn` or `ein`; schema_check refuses one.

Revision ID: 0103
Revises: 0102
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None

_TIN = ("tin_sealed", "tin_last4", "tin_kind", "tin_status", "tin_fingerprint")
_KINDS = (
    "'spouse', 'owner_of', 'trustee_of', 'beneficiary_of', 'sponsor_of', 'upper_tier_of', "
    "'executor_of', 'gp_of', 'lp_of', 'estate_of'"
)
# A person's name: lower case, anything but letters and digits as a space, spaces collapsed
# (no legal suffixes to drop, unlike 0035's client and entity names).
_PERSON = "btrim(regexp_replace(lower(display_name), '[^a-z0-9]+', ' ', 'g'))"


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')
               OR NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'btree_gin') THEN
                RAISE EXCEPTION 'pg_trgm and btree_gin are missing: apply bootstrap.sql first';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE client_entities
            ADD COLUMN tin_sealed bytea NULL CHECK (octet_length(tin_sealed) <= 1024),
            ADD COLUMN tin_last4 text NULL CHECK (tin_last4 ~ '^[0-9]{4}$'),
            ADD COLUMN tin_kind text NULL CHECK (tin_kind IN ('ssn', 'ein', 'itin')),
            ADD COLUMN tin_status text NOT NULL DEFAULT 'none'
                CHECK (tin_status IN ('none', 'on_file', 'applied_for')),
            ADD COLUMN tin_fingerprint bytea NULL CHECK (octet_length(tin_fingerprint) = 32),
            ADD CONSTRAINT client_entities_tin_whole CHECK (
                (tin_sealed IS NULL) = (tin_last4 IS NULL)
                AND (tin_sealed IS NULL) = (tin_kind IS NULL)
                AND (tin_sealed IS NULL) = (tin_fingerprint IS NULL)
                AND (tin_sealed IS NOT NULL) = (tin_status = 'on_file')
            )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX client_entities_one_tin ON client_entities "
        "(tenant_id, tin_fingerprint) WHERE tin_fingerprint IS NOT NULL"
    )
    op.execute(f"GRANT UPDATE ({', '.join(_TIN)}) ON client_entities TO abacus_app")

    op.execute(
        "ALTER TABLE clients ADD COLUMN descriptor text NULL "
        "CHECK (char_length(descriptor) BETWEEN 1 AND 120)"
    )
    op.execute("GRANT UPDATE (descriptor) ON clients TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE entity_relationships (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            from_entity_id uuid NOT NULL,
            to_entity_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ({_KINDS})),
            percent numeric(9, 6) NULL CHECK (percent > 0 AND percent <= 100),
            effective_from date NOT NULL,
            effective_to date NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CHECK (from_entity_id <> to_entity_id),
            CHECK (effective_to IS NULL OR effective_to >= effective_from),
            FOREIGN KEY (tenant_id, from_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, to_entity_id) REFERENCES client_entities (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX entity_relationships_from ON entity_relationships "
        "(tenant_id, from_entity_id)"
    )
    op.execute(
        "CREATE INDEX entity_relationships_to ON entity_relationships (tenant_id, to_entity_id)"
    )
    tenant_table(op, "entity_relationships")
    op.execute("REVOKE UPDATE, DELETE ON entity_relationships FROM abacus_app")
    insert_columns(
        op,
        "entity_relationships",
        (
            "tenant_id",
            "from_entity_id",
            "to_entity_id",
            "kind",
            "percent",
            "effective_from",
            "effective_to",
            "created_by",
        ),
    )
    op.execute("GRANT UPDATE (effective_to) ON entity_relationships TO abacus_app")

    op.execute(
        f"ALTER TABLE contacts ADD COLUMN normalised_name text GENERATED ALWAYS AS ({_PERSON}) "
        "STORED"
    )
    for table in ("clients", "client_entities", "contacts"):
        op.execute(
            f"CREATE INDEX {table}_name_trgm ON {table} "
            "USING gin (tenant_id, normalised_name gin_trgm_ops)"
        )


def downgrade() -> None:
    for table in ("contacts", "client_entities", "clients"):
        op.execute(f"DROP INDEX {table}_name_trgm")
    op.execute("ALTER TABLE contacts DROP COLUMN normalised_name")
    op.execute("DROP TABLE entity_relationships")
    op.execute("ALTER TABLE clients DROP COLUMN descriptor")
    op.execute("DROP INDEX client_entities_one_tin")
    op.execute(
        "ALTER TABLE client_entities DROP CONSTRAINT client_entities_tin_whole, "
        "DROP COLUMN tin_fingerprint, DROP COLUMN tin_status, DROP COLUMN tin_kind, "
        "DROP COLUMN tin_last4, DROP COLUMN tin_sealed"
    )
