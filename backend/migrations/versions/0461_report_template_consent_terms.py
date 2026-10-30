"""§7216 consent terms on a report template version (T-01-T17; T-01 §3.1 Story 1.1, §4.1;
DF-16; SPEC-501 AC-28 to AC-31; P-38 expand-only).

A `consent_7216` template is a P-11 report template (0460) whose version also carries its consent
terms, imported in the same request and frozen with it:

- `report_template_consent_terms` (insert-only, one per version): the one purpose the document
  asks for (Rev. Proc. 2013-14 §5.05: one purpose per document), the mandatory-statement version
  the wording follows, who attested that counsel approved it and when, where the recipients come
  from (only the provider-terms register: the recipient block is rendered from it at render time,
  never fixed text, DF-16) and the stated expiry in months, if the wording states one (else one
  year from signing, conflict C-17).

No row is inserted here: consent wording is counsel-approved firm content, imported.

Revision ID: 0461
Revises: 0460
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0461"
down_revision = "0460"
branch_labels = None
depends_on = None

_PURPOSES = (
    "use",
    "ai_disclosure",
    "offshore_disclosure",
    "third_party_disclosure",
    "other_services_use",
    "firm_defined",
)


def upgrade() -> None:
    purposes = ", ".join(f"'{p}'" for p in _PURPOSES)
    op.execute(
        f"""
        CREATE TABLE report_template_consent_terms (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            template_version_id uuid NOT NULL,
            purpose text NOT NULL CHECK (purpose IN ({purposes})),
            statement_version text NOT NULL
                CHECK (statement_version ~ '^[A-Za-z0-9 ._-]{{1,40}}$'),
            counsel_attested_by_user_id uuid NOT NULL,
            counsel_attested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            recipients_source text NOT NULL DEFAULT 'provider_terms_register'
                CHECK (recipients_source = 'provider_terms_register'),
            expiry_months integer NULL CHECK (expiry_months BETWEEN 1 AND 36),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, template_version_id),
            FOREIGN KEY (tenant_id, template_version_id)
                REFERENCES report_template_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "report_template_consent_terms")
    insert_columns(
        op,
        "report_template_consent_terms",
        (
            "id",
            "tenant_id",
            "template_version_id",
            "purpose",
            "statement_version",
            "counsel_attested_by_user_id",
            "expiry_months",
        ),
    )
    insert_only(op, "report_template_consent_terms")
    op.execute(
        "CREATE TRIGGER report_template_consent_terms_immutable BEFORE UPDATE OR DELETE "
        "ON report_template_consent_terms FOR EACH ROW "
        "EXECUTE FUNCTION report_template_rows_immutable()"
    )
    op.execute(
        "CREATE TRIGGER report_template_consent_terms_no_truncate BEFORE TRUNCATE "
        "ON report_template_consent_terms FOR EACH STATEMENT "
        "EXECUTE FUNCTION report_template_rows_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE report_template_consent_terms")
