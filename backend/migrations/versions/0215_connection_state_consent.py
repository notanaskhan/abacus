"""A started connection names its consent and its reconnect target; connections carry a version
(A-02-T16; TASK-1416; SPEC-333 AC-36, AC-37, AC-39, AC-42; C20 v1; DEC-514).

- `connection_states.consent_id`: the consent row POR-16's start wrote before the provider's
  sheet. The foreign key carries the client entity, so a state can only name a consent on its
  own entity; one state per consent (UNIQUE). Null for the legacy engagement flow (SPEC-020).
- `connection_states.connection_id`: the live connection a reconnect re-authorises, on the same
  entity (composite foreign key). Null for a new connection.
- `connection_states.category`: the catalogue category the connection will have (`ledger`,
  `bank_feed`, …), so completion applies one live ledger per entity. Null for the legacy flow,
  which only ever connects a ledger.
- `connection_states.verifier_sealed`: the PKCE code verifier (RFC 7636, S256), sealed with the
  tenant key bound to the state's hash; opened once, at completion (review L6).
- `connections.version`: optimistic concurrency for the portal's disconnect (`seen_version`,
  409 `stale_version`); every status change bumps it.
- `connection_grant_revocations` (review M1): a retired grant waiting to be revoked at the
  provider. A disconnect or a replaced grant moves the sealed blob here (the live secret row is
  deleted at once); the outbox consumer opens it, calls the connector's `revoke`, audits the
  result and deletes the row (the crypto-erase). Insert and delete only, never updated.

The new state columns are insert-only for the app, as the rest of the state is (only `used_at`
is ever updated). Expand-only; the downgrade drops the columns.

Revision ID: 0215
Revises: 0197
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0215"
down_revision = "0197"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE connection_states
            ADD COLUMN consent_id uuid NULL,
            ADD COLUMN connection_id uuid NULL,
            ADD COLUMN verifier_sealed bytea NULL
                CONSTRAINT connection_states_verifier_sealed_check
                CHECK (octet_length(verifier_sealed) BETWEEN 1 AND 4096),
            ADD COLUMN category text NULL
                CONSTRAINT connection_states_category_check CHECK (category IN (
                    'ledger', 'bank_feed', 'card_feed', 'sales', 'payroll', 'hr', 'ticketing',
                    'grc'
                )),
            ADD CONSTRAINT connection_states_portal_whole
                CHECK ((consent_id IS NULL) = (category IS NULL)),
            ADD CONSTRAINT connection_states_one_per_consent UNIQUE (consent_id),
            ADD CONSTRAINT connection_states_consent_entity
                FOREIGN KEY (tenant_id, client_entity_id, consent_id)
                REFERENCES connection_consents (tenant_id, client_entity_id, id),
            ADD CONSTRAINT connection_states_connection_entity
                FOREIGN KEY (tenant_id, client_entity_id, connection_id)
                REFERENCES connections (tenant_id, client_entity_id, id)
        """
    )
    op.execute(
        "GRANT INSERT (consent_id, connection_id, category, verifier_sealed) "
        "ON connection_states TO abacus_app"
    )
    op.execute(
        "ALTER TABLE connections ADD COLUMN version integer NOT NULL DEFAULT 1 "
        "CONSTRAINT connections_version_check CHECK (version >= 1)"
    )
    op.execute("GRANT UPDATE (version) ON connections TO abacus_app")
    op.execute(
        """
        CREATE TABLE connection_grant_revocations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            connection_id uuid NOT NULL,
            sealed bytea NOT NULL CHECK (octet_length(sealed) BETWEEN 1 AND 65536),
            reason text NOT NULL CHECK (reason IN ('disconnected', 'replaced')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, connection_id) REFERENCES connections (tenant_id, id)
        )
        """
    )
    tenant_table(op, "connection_grant_revocations")
    op.execute("REVOKE UPDATE ON connection_grant_revocations FROM abacus_app")
    insert_columns(
        op, "connection_grant_revocations", ("tenant_id", "connection_id", "sealed", "reason")
    )


def downgrade() -> None:
    op.execute("DROP TABLE connection_grant_revocations")
    op.execute("REVOKE UPDATE (version) ON connections FROM abacus_app")
    op.execute("ALTER TABLE connections DROP COLUMN version")
    op.execute(
        "REVOKE INSERT (consent_id, connection_id, category, verifier_sealed) "
        "ON connection_states FROM abacus_app"
    )
    op.execute(
        """
        ALTER TABLE connection_states
            DROP CONSTRAINT connection_states_connection_entity,
            DROP CONSTRAINT connection_states_consent_entity,
            DROP CONSTRAINT connection_states_one_per_consent,
            DROP CONSTRAINT connection_states_portal_whole,
            DROP COLUMN category,
            DROP COLUMN verifier_sealed,
            DROP COLUMN connection_id,
            DROP COLUMN consent_id
        """
    )
