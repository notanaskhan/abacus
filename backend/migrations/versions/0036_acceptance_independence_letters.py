"""Acceptance, independence and the engagement letter (SPEC-025 AC-4 to AC-7; TASK-044).

Recorded, not performed: where the firm documented them, and the engagement partner's decision
and conclusion. Each engagement's live acceptance row is the newest; rows are never changed. A
person's confirmation moves `requested` → `confirmed` or `declined`. Existing engagements are
marked "accepted, before Act 1" with their current staff "confirmed, before Act 1" (D3), with
forced row-level security lifted around the backfill (as 0012 does), so live work isn't blocked.

Revision ID: 0036
Revises: 0035
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engagement_acceptance (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('new_client', 'continuance')),
            decision text NOT NULL CHECK (decision IN ('accepted', 'declined')),
            decided_by text NOT NULL CHECK (length(decided_by) BETWEEN 1 AND 200),
            documented_at text NOT NULL CHECK (length(documented_at) BETWEEN 1 AND 300),
            predecessor_auditor text NULL CHECK (length(predecessor_auditor) BETWEEN 1 AND 200),
            predecessor_communicated_on date NULL,
            independence_concluded_by text NULL
                CHECK (length(independence_concluded_by) BETWEEN 1 AND 200),
            independence_concluded_at timestamptz NULL,
            independence_documented_at text NULL
                CHECK (length(independence_documented_at) BETWEEN 1 AND 300),
            file_key text NULL, file_version_id text NULL, file_fingerprint text NULL,
            file_size bigint NULL, file_media_type text NULL, file_name text NULL,
            before_act_1 boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            CHECK ((independence_concluded_by IS NULL) = (independence_concluded_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX engagement_acceptance_latest ON engagement_acceptance "
        "(tenant_id, engagement_id, created_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE independence_confirmations (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            user_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'requested'
                CHECK (status IN ('requested', 'confirmed', 'declined')),
            statement_version text NULL CHECK (length(statement_version) BETWEEN 1 AND 20),
            note text NULL CHECK (length(note) BETWEEN 1 AND 1000),
            before_act_1 boolean NOT NULL DEFAULT false,
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            answered_at timestamptz NULL,
            PRIMARY KEY (tenant_id, engagement_id, user_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id),
            CHECK ((status = 'requested') = (answered_at IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE engagement_letters (
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            status text NOT NULL CHECK (
                status IN ('not_started', 'sent', 'signed', 'not_required_this_year')
            ),
            letter_date date NULL,
            reason text NULL CHECK (length(reason) BETWEEN 1 AND 500),
            link text NULL CHECK (link ~ '^https://' AND length(link) <= 2000),
            file_key text NULL, file_version_id text NULL, file_fingerprint text NULL,
            file_size bigint NULL, file_media_type text NULL, file_name text NULL,
            recorded_by text NOT NULL CHECK (length(recorded_by) BETWEEN 1 AND 200),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, engagement_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            CHECK (status <> 'not_required_this_year' OR reason IS NOT NULL)
        )
        """
    )
    for table in ("engagement_acceptance", "independence_confirmations", "engagement_letters"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON engagement_acceptance FROM abacus_app")
    insert_columns(
        op,
        "engagement_acceptance",
        (
            "tenant_id",
            "engagement_id",
            "kind",
            "decision",
            "decided_by",
            "documented_at",
            "predecessor_auditor",
            "predecessor_communicated_on",
            "independence_concluded_by",
            "independence_concluded_at",
            "independence_documented_at",
            "file_key",
            "file_version_id",
            "file_fingerprint",
            "file_size",
            "file_media_type",
            "file_name",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON independence_confirmations FROM abacus_app")
    insert_columns(op, "independence_confirmations", ("tenant_id", "engagement_id", "user_id"))
    op.execute(
        "GRANT UPDATE (status, statement_version, note, answered_at) "
        "ON independence_confirmations TO abacus_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON engagement_letters FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, letter_date, reason, link, recorded_by, recorded_at, file_key, "
        "file_version_id, file_fingerprint, file_size, file_media_type, file_name) "
        "ON engagement_letters TO abacus_app"
    )
    op.execute("ALTER TABLE firms ADD COLUMN require_letter boolean NOT NULL DEFAULT false")
    op.execute("GRANT UPDATE (require_letter) ON firms TO abacus_app")
    # Engagements already in use: accepted and confirmed "before Act 1" (D3).
    for table in ("engagement_acceptance", "independence_confirmations"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE engagements NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE engagement_members NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        INSERT INTO engagement_acceptance (
            tenant_id, engagement_id, kind, decision, decided_by, documented_at,
            independence_concluded_by, independence_concluded_at, independence_documented_at,
            before_act_1
        )
        SELECT tenant_id, id, 'continuance', 'accepted', 'migration-0036',
               'Recorded before Act 1', 'migration-0036', clock_timestamp(),
               'Recorded before Act 1', true
          FROM engagements
        """
    )
    op.execute(
        """
        INSERT INTO independence_confirmations (
            tenant_id, engagement_id, user_id, status, statement_version, before_act_1,
            answered_at
        )
        SELECT tenant_id, engagement_id, user_id, 'confirmed', 'before-act-1', true,
               clock_timestamp()
          FROM engagement_members
         WHERE role IN ('engagement_partner', 'manager', 'senior', 'staff', 'reviewer')
        """
    )
    for table in (
        "engagement_acceptance",
        "independence_confirmations",
        "engagements",
        "engagement_members",
    ):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (require_letter) ON firms FROM abacus_app")
    op.execute("ALTER TABLE firms DROP COLUMN require_letter")
    op.execute("DROP TABLE engagement_letters")
    op.execute("DROP TABLE independence_confirmations")
    op.execute("DROP TABLE engagement_acceptance")
