"""C-02-T28 (S52; TASK-8814; ADR-152): `generated_documents.kind` and `report_templates.family`
gain `close_package`, CLS-08's FS package composed by code (like `fs_package`). Expand-only.

Revision ID: 0993
Revises: 0992
"""

from __future__ import annotations

from alembic import op

revision = "0993"
down_revision = "0992"
branch_labels = None
depends_on = None

_OLD = (
    "engagement_letter", "consent_7216", "representation_letter", "governance_letter",
    "audit_report", "review_report", "compilation_report", "notice_response",
    "delivery_cover_letter", "k1_cover_letter", "fs_package", "run_trace_export",
    "ebp_supplemental_schedule", "client_entries_journal", "component_instructions",
)  # fmt: skip
_NEW = (*_OLD, "close_package")
_CHECKS = (
    ("generated_documents", "generated_documents_kind_check", "kind"),
    ("report_templates", "report_templates_family_check", "family"),
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    for table, check, column in _CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK ({column} IN ({_in(_NEW)}))")


def downgrade() -> None:
    for table, check, column in _CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK ({column} IN ({_in(_OLD)}))")
