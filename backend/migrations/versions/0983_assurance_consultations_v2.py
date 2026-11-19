"""Q-05-T09 (TASK-8716; DEC-5712; SPEC-711 AC-11 to AC-14; Q-05 §4.2): the consultations log v2,
expand-only, beside A-06's minimal record (dark until the Oct 24 train; P-29).

- `consultations` (0644) gains `facts_sealed` (the facts the consultee reads), `consulted_role`,
  `implemented` and `implemented_reference` (where the conclusion was carried out), `reopened_at`.
- `consultation_links` (insert-only): a consultation's links to findings, issues and documents.
- `consultation_positions` (insert-only, human-only): an EP's or EQR's recorded position, so a
  difference of opinion is on file.
- `consultation_resolutions` (insert-only, human-only): the QM owner's resolution of a
  difference; until one exists the consultation blocks release.

Revision ID: 0983
Revises: 0982
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0983"
down_revision = "0982"
branch_labels = None
depends_on = None

_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)),"
)
TABLES = {
    "consultation_links": (
        """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            consultation_id uuid NOT NULL,
            target_kind text NOT NULL CHECK (target_kind IN ('finding', 'issue', 'document',
                'workpaper', 'post_issuance_case')),
            target_id uuid NOT NULL,
            linked_by uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, consultation_id, target_kind, target_id),
            FOREIGN KEY (consultation_id) REFERENCES consultations (id)""",
        ("tenant_id", "consultation_id", "target_kind", "target_id", "linked_by"),
    ),
    "consultation_positions": (
        f"""
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            consultation_id uuid NOT NULL,
            role text NOT NULL CHECK (role IN ('engagement_partner', 'eqr_reviewer')),
            agrees boolean NOT NULL,
            position_sealed bytea NOT NULL CHECK (octet_length(position_sealed) <= 65536),
            recorded_by uuid NOT NULL,
            {_HUMAN}
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (consultation_id) REFERENCES consultations (id)""",
        ("tenant_id", "consultation_id", "role", "agrees", "position_sealed", "recorded_by"),
    ),
    "consultation_resolutions": (
        f"""
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            consultation_id uuid NOT NULL UNIQUE,
            resolution_sealed bytea NOT NULL CHECK (octet_length(resolution_sealed) <= 65536),
            resolved_by uuid NOT NULL,
            {_HUMAN}
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (consultation_id) REFERENCES consultations (id)""",
        ("tenant_id", "consultation_id", "resolution_sealed", "resolved_by"),
    ),
}


def upgrade() -> None:
    op.execute(
        "ALTER TABLE consultations "
        "ADD COLUMN facts_sealed bytea NULL CHECK (octet_length(facts_sealed) <= 65536), "
        "ADD COLUMN consulted_role text NULL CHECK (char_length(consulted_role) <= 40), "
        "ADD COLUMN implemented boolean NOT NULL DEFAULT false, "
        "ADD COLUMN implemented_reference text NULL "
        "CHECK (char_length(implemented_reference) <= 200), "
        "ADD COLUMN reopened_at timestamptz NULL"
    )
    op.execute(
        "GRANT UPDATE (implemented, implemented_reference, reopened_at) ON consultations "
        "TO abacus_app"
    )
    for table, (body, columns) in TABLES.items():
        op.execute(f"CREATE TABLE {table} ({body}\n        )")
        tenant_table(op, table)
        insert_columns(op, table, columns)
        insert_only(op, table)


def downgrade() -> None:
    for table in reversed(list(TABLES)):
        op.execute(f"DROP TABLE {table}")
    op.execute(
        "ALTER TABLE consultations DROP COLUMN reopened_at, DROP COLUMN implemented_reference, "
        "DROP COLUMN implemented, DROP COLUMN consulted_role, DROP COLUMN facts_sealed"
    )
