"""Document classifications (N-01-T17; N-01 §3.4, §4.2 `00NN_document_classifications`).

`document_classifications` (evidence, forced RLS, insert-only, immutable): what a document is, by
rule now and by the matcher later (`proposed_by_kind`), for an intake attachment or an evidence
version (`subject_kind`): form family and code, tax year, issuer, kind, page count, the taxpayer
TIN's last four, whether it is a corrected form, per-field confidences, and the rules version
that produced it. A reclassification is a new row; the latest row for a subject is current.
`confirmed_by` and `confirmed_at` are written only with a row a person confirms.

Classification (ADR-031): `issuer_name` and `taxpayer_tin_last4` Confidential (the last four is
the masked form); `confidences` Internal.

Revision ID: 0404
Revises: 0403
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0404"
down_revision = "0403"
branch_labels = None
depends_on = None

_KINDS = "('tax_form', 'notice', 'receipt', 'census', 'invoice', 'statement', 'return', 'other')"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE document_classifications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            subject_kind text NOT NULL
                CHECK (subject_kind IN ('inbox_attachment', 'evidence_version')),
            subject_id uuid NOT NULL,
            form_family text NOT NULL CHECK (char_length(form_family) BETWEEN 1 AND 40),
            form_code text NULL CHECK (char_length(form_code) BETWEEN 1 AND 40),
            tax_year integer NULL CHECK (tax_year BETWEEN 1990 AND 2100),
            issuer_name text NULL CHECK (char_length(issuer_name) BETWEEN 1 AND 200),
            kind text NOT NULL CHECK (kind IN {_KINDS}),
            page_count integer NOT NULL CHECK (page_count >= 0),
            taxpayer_tin_last4 text NULL CHECK (taxpayer_tin_last4 ~ '^[0-9]{{4}}$'),
            corrected boolean NULL,
            confidences jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(confidences) = 'object'
                       AND octet_length(confidences::text) <= 1024),
            citation_ids uuid[] NULL,
            proposed_by_kind text NOT NULL CHECK (proposed_by_kind IN ('rule', 'agent')),
            agent_run_id uuid NULL,
            rules_version text NOT NULL CHECK (char_length(rules_version) BETWEEN 1 AND 40),
            confirmed_by uuid NULL,
            confirmed_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((proposed_by_kind = 'agent') = (agent_run_id IS NOT NULL)),
            CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX document_classifications_subject ON document_classifications "
        "(tenant_id, subject_kind, subject_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX document_classifications_family_year ON document_classifications "
        "(tenant_id, form_family, tax_year) WHERE subject_kind = 'evidence_version'"
    )
    tenant_table(op, "document_classifications")
    insert_only(op, "document_classifications")
    op.execute("REVOKE TRUNCATE ON document_classifications FROM abacus_app")
    # The trust kit's function (0109): insert-only, raised for any update, delete or truncate.
    op.execute(
        "CREATE TRIGGER document_classifications_immutable BEFORE UPDATE OR DELETE ON "
        "document_classifications FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
    )
    op.execute(
        "CREATE TRIGGER document_classifications_no_truncate BEFORE TRUNCATE ON "
        "document_classifications FOR EACH STATEMENT EXECUTE FUNCTION trust_kit_immutable()"
    )
    insert_columns(
        op,
        "document_classifications",
        (
            "tenant_id",
            "subject_kind",
            "subject_id",
            "form_family",
            "form_code",
            "tax_year",
            "issuer_name",
            "kind",
            "page_count",
            "taxpayer_tin_last4",
            "corrected",
            "confidences",
            "citation_ids",
            "proposed_by_kind",
            "agent_run_id",
            "rules_version",
            "confirmed_by",
            "confirmed_at",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE document_classifications")
