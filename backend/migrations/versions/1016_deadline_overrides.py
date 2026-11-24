"""T-08-T44 (S53; TASK-8919; T-08 §4.2; DF-10; DEC-5921; amber): the firm's deadline overrides.
Expand-only.

- `firm_standards.kind` admits `deadline_overrides` (an add-only CHECK swap): the firm's DF-10
  rows (internal target offsets per form, closure days, the relief notices it tracks) on the
  K-02 lifecycle, owner-published and effective-dated; the platform's reference sets stay
  read-only beside them in KNW-04 section j.
- `postponement_applications` (practice, insert-only): a person applies a relief notice to one
  client by its notice id, naming the version it read (the platform's `disaster_postponements`
  set or the firm's `deadline_overrides`); only that client's dates move. The actor is a person
  (a CHECK against the session, as every human-only row); one application per client and notice.

Revision ID: 1016
Revises: 1015
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1016"
down_revision = "1015"
branch_labels = None
depends_on = None

_BEFORE = "('review_checklist', 'review_levels', 'return_approval_policy', 'ssars_cas_settings')"
_AFTER = (
    "('review_checklist', 'review_levels', 'return_approval_policy', 'ssars_cas_settings', "
    "'deadline_overrides')"
)
INSERT = (
    "tenant_id", "client_id", "notice_id", "source", "reference_set_version_id", "applied_by",
)  # fmt: skip


def _kinds(kinds: str) -> None:
    op.execute("ALTER TABLE firm_standards DROP CONSTRAINT firm_standards_kind_check")
    op.execute(
        "ALTER TABLE firm_standards ADD CONSTRAINT firm_standards_kind_check "
        f"CHECK (kind IN {kinds})"
    )


def upgrade() -> None:
    _kinds(_AFTER)
    op.execute(
        """
        CREATE TABLE postponement_applications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            notice_id text NOT NULL CHECK (notice_id ~ '^[A-Za-z0-9][A-Za-z0-9-]{1,39}$'),
            source text NOT NULL CHECK (source IN ('platform', 'firm')),
            reference_set_version_id uuid NOT NULL,
            applied_by uuid NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'
                       AND actor_kind = current_setting('app.actor_kind', true)),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_id, notice_id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX postponement_applications_client ON postponement_applications "
        "(tenant_id, client_id)"
    )
    tenant_table(op, "postponement_applications")
    insert_columns(op, "postponement_applications", list(INSERT))
    insert_only(op, "postponement_applications")


def downgrade() -> None:
    op.execute("DROP TABLE postponement_applications")
    # A firm that published overrides keeps them: the swap back fails rather than drop them.
    _kinds(_BEFORE)
