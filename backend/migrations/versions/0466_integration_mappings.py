"""Integration mappings for the tax engine's file bridge (T-01-T20; T-01 §4.2
`integration_mappings`; ADM-08; DEC-1364; expand-only).

One row per (install, kind, source key): the return-ID template and client-code rule, the type
letters, the user and office mappings, the export rules and the workflow-status mirror. A firm
admin or security admin writes them through ADM-08 (fresh MFA); `version` counts a row's saves.
Two Accrued statuses may not mirror onto one engine status: a partial unique index refuses it
(409 `mapping_conflict`). Targets are internal names and engine codes, never client data; user
and office targets are the engine's staff and office codes (confidential).

Revision ID: 0466
Revises: 0430 (main's head when built; re-chain after the S18 lane's 0465 at the batch merge)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0466"
down_revision = "0430"
branch_labels = None
depends_on = None

_KINDS = (
    "'return_id_template', 'client_code_rule', 'type_letters', 'user', 'office', "
    "'export_rules', 'workflow_status'"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE integration_mappings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            firm_integration_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ({_KINDS})),
            source_key text NOT NULL CHECK (length(source_key) BETWEEN 1 AND 120),
            target_value text NOT NULL CHECK (length(target_value) BETWEEN 1 AND 200),
            direction text NULL CHECK (direction IN ('one_way', 'two_way')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT integration_mappings_one
                UNIQUE (tenant_id, firm_integration_id, kind, source_key),
            FOREIGN KEY (tenant_id, firm_integration_id)
                REFERENCES firm_integrations (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX integration_mappings_status_target ON integration_mappings "
        "(tenant_id, firm_integration_id, target_value) WHERE kind = 'workflow_status'"
    )
    tenant_table(op, "integration_mappings")
    insert_columns(
        op,
        "integration_mappings",
        (
            "tenant_id",
            "firm_integration_id",
            "kind",
            "source_key",
            "target_value",
            "direction",
            "updated_by",
        ),
    )
    op.execute("REVOKE UPDATE ON integration_mappings FROM abacus_app")
    op.execute(
        "GRANT UPDATE (target_value, direction, version, updated_by, updated_at) "
        "ON integration_mappings TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE integration_mappings")
