"""Drop SPEC-025's `engagement_acceptance` (P-07-T59, part 2; DEC-905, DEC-906).

G1 reads CLI-07's decision (`acceptance_records` and `acceptance_decisions`, 0163) and G2
CLI-08's conclusion (`independence_conclusions`, 0175) and nothing else; SPEC-025's routes that
wrote this table retired with P-07-T59 part 1. The rows are not converted (DEC-372, DEC-906): a
v2 decision needs a template version, a partner-level decider, an MFA time and a sealed
rationale the legacy text cannot give. Only synthetic data exists (P-38), so the upgrade drops a
synthetic firm's rows with the table and refuses while any other firm holds one (the check
reads across tenants with the policies unforced for that one statement, as 0270 does).

The downgrade recreates the table empty, as 0036, 0085 and 0175 left it: its columns, index,
tenant policy, insert-only grants and the `legacy_g2` cut-off trigger.

Revision ID: 0321
Revises: 0320
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0321"
down_revision = "0320"
branch_labels = None
depends_on = None

_REFUSE_REAL_ROWS = """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM engagement_acceptance a
              LEFT JOIN firms f ON f.tenant_id = a.tenant_id
             WHERE NOT coalesce(f.synthetic, false)
        ) THEN
            RAISE EXCEPTION 'engagement_acceptance holds rows of a non-synthetic firm; '
                'record them through CLI-07 and CLI-08 before dropping the table (DEC-906)'
                USING ERRCODE = 'object_in_use';
        END IF;
    END $$
"""
_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)
_LEGACY_CUTOFF = f"""
    CREATE FUNCTION engagement_acceptance_written_by_app() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF {_BY_APP} THEN
            NEW.legacy_g2 := false;
        END IF;
        RETURN NEW;
    END $$
"""


def upgrade() -> None:
    for table in ("engagement_acceptance", "firms"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(_REFUSE_REAL_ROWS)
    op.execute("ALTER TABLE firms FORCE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER engagement_acceptance_written_by_app ON engagement_acceptance")
    op.execute("DROP FUNCTION engagement_acceptance_written_by_app()")
    op.execute("DROP TABLE engagement_acceptance")


def downgrade() -> None:
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
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            legacy_g2 boolean NOT NULL DEFAULT true,
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
    tenant_table(op, "engagement_acceptance")
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
    op.execute(_LEGACY_CUTOFF)
    op.execute(
        "CREATE TRIGGER engagement_acceptance_written_by_app BEFORE INSERT ON "
        "engagement_acceptance FOR EACH ROW EXECUTE FUNCTION "
        "engagement_acceptance_written_by_app()"
    )
