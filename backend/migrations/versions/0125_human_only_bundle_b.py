"""Protected bundle B (Q-02-T30): three more human-only audit actions.

`legal_hold.lifted`, `firm_export.declined` and `retention_policy.updated` join the human-only
register (`docs/architecture/human-only-actions.yaml`), so the `audit_events_human_only` trigger
of 0097 refuses them from an `agent` or `policy` actor before commit. This redefines
`abacus_human_only_actions()` with the register's list; `CREATE OR REPLACE` keeps 0098's EXECUTE
grant. The drift test holds the function, the YAML and the generated module together.

Revision ID: 0125
Revises: 0115
"""

from __future__ import annotations

from alembic import op

revision = "0125"
down_revision = "0120"
branch_labels = None
depends_on = None

_BEFORE = (
    "engagement.accepted",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.confirmed",
    "legal_hold.placed",
    "materiality.decided",
    "procedure.concluded",
    "report.approved",
    "report.released",
    "review.decided",
    "review.released",
    "risk.approved",
    "sample.approved",
    "sign_off.recorded",
    "statement.approved",
)
_ADDED = ("firm_export.declined", "legal_hold.lifted", "retention_policy.updated")


def _define(actions: tuple[str, ...]) -> None:
    listed = ",\n        ".join(f"'{a}'" for a in sorted(actions))
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[\n        {listed}\n    ]::text[] $$"
    )


def upgrade() -> None:
    _define((*_BEFORE, *_ADDED))


def downgrade() -> None:
    _define(_BEFORE)
