"""Planning: materiality as the partner's decision, and the risk register (SPEC-300; TASK-301).

- `engagement_materiality` gains the basis the amounts were computed from, and a rationale.
- `materiality_decisions` (insert-only): the engagement partner deciding a materiality version.
- `risks` (insert-only): a risk on the engagement, numbered R1, R2… per engagement.
- `risk_versions` (insert-only): a risk's assessment; the newest counts.
- `risk_approvals` (insert-only): the partner approving a version's significant risk or rebuttal.

Revision ID: 0066
Revises: 0065
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE engagement_materiality
            ADD COLUMN basis_amount numeric(18, 2) NULL CHECK (basis_amount > 0),
            ADD COLUMN rate_pct numeric(6, 3) NULL CHECK (rate_pct > 0 AND rate_pct <= 100),
            ADD COLUMN performance_pct numeric(6, 3) NULL
                CHECK (performance_pct > 0 AND performance_pct <= 100),
            ADD COLUMN trivial_pct numeric(6, 3) NULL
                CHECK (trivial_pct > 0 AND trivial_pct <= 100),
            ADD COLUMN rationale text NULL CHECK (length(rationale) BETWEEN 1 AND 2000)
        """
    )
    op.execute("ALTER TABLE engagement_materiality ADD UNIQUE (tenant_id, id)")
    insert_columns(
        op,
        "engagement_materiality",
        (
            "tenant_id",
            "engagement_id",
            "overall",
            "performance",
            "trivial",
            "benchmark",
            "set_by",
            "basis_amount",
            "rate_pct",
            "performance_pct",
            "trivial_pct",
            "rationale",
        ),
    )
    op.execute(
        """
        CREATE TABLE materiality_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            materiality_id uuid NOT NULL,
            rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
            decided_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, materiality_id),
            FOREIGN KEY (tenant_id, materiality_id)
                REFERENCES engagement_materiality (tenant_id, id)
        )
        """
    )
    tenant_table(op, "materiality_decisions")
    op.execute("REVOKE UPDATE, DELETE ON materiality_decisions FROM abacus_app")
    insert_columns(
        op, "materiality_decisions", ("tenant_id", "materiality_id", "rationale", "decided_by")
    )
    op.execute(
        """
        CREATE TABLE risks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            number integer NOT NULL CHECK (number > 0),
            raised_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, number),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    tenant_table(op, "risks")
    op.execute("REVOKE UPDATE, DELETE ON risks FROM abacus_app")
    insert_columns(op, "risks", ("tenant_id", "engagement_id", "number", "raised_by"))
    op.execute(
        """
        CREATE TABLE risk_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            risk_id uuid NOT NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            area text NOT NULL CHECK (length(area) BETWEEN 1 AND 120),
            level text NOT NULL CHECK (level IN ('financial_statement', 'assertion')),
            assertions text[] NOT NULL DEFAULT '{}',
            inherent text NOT NULL CHECK (inherent IN ('low', 'moderate', 'high')),
            control text NOT NULL CHECK (control IN ('low', 'moderate', 'high', 'maximum')),
            significant boolean NOT NULL DEFAULT false,
            fraud text NOT NULL CHECK (fraud IN ('none', 'presumed', 'rebuttal')),
            rationale text NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
            recorded_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, risk_id) REFERENCES risks (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX risk_versions_by_risk ON risk_versions (tenant_id, risk_id, created_at DESC)"
    )
    tenant_table(op, "risk_versions")
    op.execute("REVOKE UPDATE, DELETE ON risk_versions FROM abacus_app")
    insert_columns(
        op,
        "risk_versions",
        (
            "tenant_id",
            "risk_id",
            "title",
            "area",
            "level",
            "assertions",
            "inherent",
            "control",
            "significant",
            "fraud",
            "rationale",
            "recorded_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE risk_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            risk_version_id uuid NOT NULL,
            rationale text NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
            approved_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, risk_version_id),
            FOREIGN KEY (tenant_id, risk_version_id) REFERENCES risk_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "risk_approvals")
    op.execute("REVOKE UPDATE, DELETE ON risk_approvals FROM abacus_app")
    insert_columns(
        op, "risk_approvals", ("tenant_id", "risk_version_id", "rationale", "approved_by")
    )


def downgrade() -> None:
    op.execute("DROP TABLE risk_approvals")
    op.execute("DROP TABLE risk_versions")
    op.execute("DROP TABLE risks")
    op.execute("DROP TABLE materiality_decisions")
    op.execute(
        "ALTER TABLE engagement_materiality "
        "DROP CONSTRAINT engagement_materiality_tenant_id_id_key"
    )
    op.execute(
        "ALTER TABLE engagement_materiality DROP COLUMN basis_amount, DROP COLUMN rate_pct, "
        "DROP COLUMN performance_pct, DROP COLUMN trivial_pct, DROP COLUMN rationale"
    )
