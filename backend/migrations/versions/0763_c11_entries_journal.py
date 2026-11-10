"""R-02-T14 remainder (S33 partials round 2; TASK-6572; SPEC-646; DEC-3172): C11's
`client_entries_journal` kind, POR-08's "Download entries".

A C18 item's entries journal is composed by code from the item's own lines (account, debit,
credit), like `fs_package` and `ebp_supplemental_schedule`, in the code-only `financial_statements`
layout. The CHECKs on `generated_documents.kind` and `report_templates.family` widen by that one
key, so the kind list stays one list. Expand only.

Revision ID: 0763
Revises: 0762
"""

from __future__ import annotations

from alembic import op

revision = "0763"
down_revision = "0762"
branch_labels = None
depends_on = None

_OLD = (
    "engagement_letter",
    "consent_7216",
    "representation_letter",
    "governance_letter",
    "audit_report",
    "review_report",
    "compilation_report",
    "notice_response",
    "delivery_cover_letter",
    "k1_cover_letter",
    "fs_package",
    "run_trace_export",
    "ebp_supplemental_schedule",
)
_NEW = (*_OLD, "client_entries_journal")
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
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} "
            f"CHECK ({column} IN ({_in(_OLD)})) NOT VALID"
        )
