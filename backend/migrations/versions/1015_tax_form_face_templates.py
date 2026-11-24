"""T-06-T43 (S53; TASK-8912; SPEC-702 F7; TAX-11; amber): C11's `tax_form_face` templates.
Expand-only.

A form face is a report template whose layout is drawn from a field manifest (the form's pages and
fields with their boxes, formats, bindings and TIN masks), never from blocks. The CHECKs on
`generated_documents.kind` and `report_templates.family` widen by `tax_form_face`, the layout
CHECKs on `report_template_versions` and `generated_document_versions` by the `tax_form_face`
layout, and a version gains `field_manifest` (a JSON object, present exactly for that layout).
The faces themselves are firm-visible content loaded through P-11's import endpoint, never seed.

Revision ID: 1015
Revises: 1014
"""

from __future__ import annotations

from alembic import op

revision = "1015"
down_revision = "1014"
branch_labels = None
depends_on = None

_KINDS_OLD = (
    "engagement_letter", "consent_7216", "representation_letter", "governance_letter",
    "audit_report", "review_report", "compilation_report", "notice_response",
    "delivery_cover_letter", "k1_cover_letter", "fs_package", "run_trace_export",
    "ebp_supplemental_schedule", "client_entries_journal", "component_instructions",
    "close_package",
)  # fmt: skip
_KINDS_NEW = (*_KINDS_OLD, "tax_form_face")
_KIND_CHECKS = (
    ("generated_documents", "generated_documents_kind_check", "kind"),
    ("report_templates", "report_templates_family_check", "family"),
)
_LAYOUTS_OLD = ("letter", "consent_7216", "report", "notice_response", "package", "run_export")
_LAYOUT_CHECKS = (
    ("report_template_versions", "report_template_versions_layout_key_check", _LAYOUTS_OLD),
    ("generated_document_versions", "generated_document_versions_layout_key_check",
     (*_LAYOUTS_OLD, "financial_statements")),
)  # fmt: skip


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    for table, check, column in _KIND_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK ({column} IN ({_in(_KINDS_NEW)}))"
        )
    for table, check, old in _LAYOUT_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} "
            f"CHECK (layout_key IN ({_in((*old, 'tax_form_face'))}))"
        )
    op.execute(
        "ALTER TABLE report_template_versions ADD COLUMN field_manifest jsonb NULL, "
        "ADD CONSTRAINT report_template_versions_field_manifest CHECK ("
        "(field_manifest IS NOT NULL) = (layout_key = 'tax_form_face') "
        "AND (field_manifest IS NULL OR jsonb_typeof(field_manifest) = 'object'))"
    )
    op.execute("GRANT INSERT (field_manifest) ON report_template_versions TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE report_template_versions DROP COLUMN field_manifest")
    for table, check, old in _LAYOUT_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK (layout_key IN ({_in(old)})) "
            "NOT VALID"
        )
    for table, check, column in _KIND_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check} CHECK ({column} IN ({_in(_KINDS_OLD)})) "
            "NOT VALID"
        )
