"""A-01-T05: the assurance profile facts and record-mode phases (A-01 §4.2 M1; SPEC-330 AC-9 to
AC-14; DEC-262).

`assurance_work_items` gains:
- `ebp_plan_kind` (`dc`, `403b`, `db`; health and welfare plans stay off until the BAA chain
  exists) and `limited_scope_103a3c`: the EBP label facts ("EBP DC · §103(a)(3)(C)");
- `phase_source` (`recorded` by a named person while the phase's gate has no provider, or
  `derived` from the gate's `gate.met`), `phase_changed_at` and `version` (optimistic
  concurrency for PATCH profile).
The `phase` CHECK already holds the C2 `audit_engagement` codes (0068) and is kept: SPEC-314's
release and archive write `released` and `archived`, and the backfill wrote `archived`.

New `assurance_phase_events` (insert-only: UPDATE and DELETE revoked and refused by a trigger):
one row per phase move. A `recorded` row is a human's (CHECK); a `derived` row is the system's
and names its gate. The optional reason is sealed under the tenant key (≤ 300 characters before
sealing, checked in the service). Indexed for the AUD-01 tiles and a work item's history.

Revision ID: 0134
Revises: 0133
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None

_PHASES = (
    "('planning', 'fieldwork', 'in_review', 'completion', 'ready_to_release', 'released', "
    "'archiving', 'archived')"
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE assurance_work_items
            ADD COLUMN ebp_plan_kind text NULL CHECK (ebp_plan_kind IN ('dc', '403b', 'db')),
            ADD COLUMN limited_scope_103a3c boolean NOT NULL DEFAULT false,
            ADD COLUMN phase_source text NOT NULL DEFAULT 'recorded'
                CHECK (phase_source IN ('recorded', 'derived')),
            ADD COLUMN phase_changed_at timestamptz NULL,
            ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1)
        """
    )
    op.execute(
        "GRANT UPDATE (ebp_plan_kind, limited_scope_103a3c, standards_set_id, phase_source, "
        "phase_changed_at, version) ON assurance_work_items TO abacus_app"
    )
    op.execute(
        "CREATE INDEX assurance_work_items_by_phase "
        "ON assurance_work_items (tenant_id, phase, work_item_id)"
    )
    op.execute(
        f"""
        CREATE TABLE assurance_phase_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            from_phase text NOT NULL CHECK (from_phase IN {_PHASES}),
            to_phase text NOT NULL CHECK (to_phase IN {_PHASES}),
            mode text NOT NULL CHECK (mode IN ('recorded', 'derived')),
            reason_sealed bytea NULL,
            gate_ref text NULL CHECK (gate_ref ~ '^G[1-9]$'),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            mfa_at timestamptz NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (from_phase <> to_phase),
            CHECK (mode <> 'recorded' OR (actor_kind = 'human' AND actor_user_id IS NOT NULL)),
            CHECK (mode <> 'derived' OR (actor_kind = 'system' AND gate_ref IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX assurance_phase_events_by_item "
        "ON assurance_phase_events (tenant_id, work_item_id, recorded_at)"
    )
    op.execute(
        """
        CREATE FUNCTION assurance_phase_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'assurance_phase_events is insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER assurance_phase_events_immutable "
        "BEFORE UPDATE OR DELETE ON assurance_phase_events "
        "FOR EACH ROW EXECUTE FUNCTION assurance_phase_events_immutable()"
    )
    tenant_table(op, "assurance_phase_events")
    op.execute("REVOKE UPDATE, DELETE ON assurance_phase_events FROM abacus_app")
    insert_columns(
        op,
        "assurance_phase_events",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "from_phase",
            "to_phase",
            "mode",
            "reason_sealed",
            "gate_ref",
            "actor_kind",
            "actor_user_id",
            "mfa_at",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE assurance_phase_events")
    op.execute("DROP FUNCTION assurance_phase_events_immutable()")
    op.execute("DROP INDEX assurance_work_items_by_phase")
    op.execute(
        "REVOKE UPDATE (ebp_plan_kind, limited_scope_103a3c, standards_set_id, phase_source, "
        "phase_changed_at, version) ON assurance_work_items FROM abacus_app"
    )
    op.execute(
        """
        ALTER TABLE assurance_work_items
            DROP COLUMN version,
            DROP COLUMN phase_changed_at,
            DROP COLUMN phase_source,
            DROP COLUMN limited_scope_103a3c,
            DROP COLUMN ebp_plan_kind
        """
    )
