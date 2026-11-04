"""P-11 migration 3: OCR, extracted fields and tables (P-11-T24; P-11 §4.2; C4 v1.1; NOT-01,
TAX-03, INB-02, CLS-05; DEC-2235; expand-only, merged before Dec 24, 2027).

Every new table is tenant-scoped with forced RLS and insert-only for every role (0109's
`trust_kit_immutable` trigger), each row naming exactly one source (an evidence version, an
inbox file or a derivation, 0109's rule):
- `ocr_runs`: the audit and cost record of each Textract (or fake) call or refusal; the first
  failing gate condition is the refusal reason (P-11 AC7.2), never retried.
- `extracted_fields`: code's form-map values with a page, a box and a confidence; a TIN's value
  is sealed (restricted) with its last four, never held as text (CHECK).
- `extracted_tables` and `extracted_table_cells`: statement transaction tables with cell boxes.
- `evidence_pages` (0109) gains nullable `text_source`, `ocr_run_id`, `mean_confidence` and
  `low_conf_words`: an OCR result is a new page row with an OCR extractor version; earlier
  `not_scannable` rows stay as history.
- `document_classifications` (0404) gains `form_map_version` for rule-proposed rows (its
  `corrected` column exists).
`upload_extractions` already keys on `extractor_version` (0043), so OCR-derived rows need no
change.

Revision ID: 0666
Revises: 0665
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0666"
down_revision = "0665"
branch_labels = None
depends_on = None

_SOURCE = """
            evidence_version_id uuid NULL,
            inbox_file_id uuid NULL,
            derivation_id uuid NULL,
            CHECK ((evidence_version_id IS NULL) <> (inbox_file_id IS NULL)),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, inbox_file_id) REFERENCES inbox_files (tenant_id, id),
            FOREIGN KEY (tenant_id, derivation_id)
                REFERENCES evidence_derivations (tenant_id, id)"""
_SOURCE_COLUMNS = ("evidence_version_id", "inbox_file_id", "derivation_id")
_EXTRACTOR = (
    "extractor_version text NOT NULL CHECK (char_length(extractor_version) BETWEEN 1 AND 40)"
)
_BBOX = "bbox numeric(10, 2)[] NOT NULL CHECK (cardinality(bbox) = 4)"
_TABLES = ("ocr_runs", "extracted_fields", "extracted_tables", "extracted_table_cells")
_REFUSALS = (
    "'kill_switch', 'flag_off', 'terms_not_covering', 'boundary_basis', 'consent_missing', "
    "'scope_unknown', 'quota_exceeded', 'too_large', 'unsupported_format'"
)
INSERTS: dict[str, tuple[str, ...]] = {
    "ocr_runs": (
        "tenant_id", *_SOURCE_COLUMNS, "provider", "api", "pages", "status", "refused_reason",
        "register_version", "basis", "page_units", "provider_request_ids",
    ),
    "extracted_fields": (
        "tenant_id", *_SOURCE_COLUMNS, "ocr_run_id", "form_type", "tax_year", "form_map_version",
        "field_key", "label", "value_type", "value_text", "value_sealed", "last4", "page_no",
        "bbox", "confidence", "low_confidence", "extractor_kind", "extractor_version",
        "pii_region_id", "match_id",
    ),
    "extracted_tables": (
        "tenant_id", *_SOURCE_COLUMNS, "ocr_run_id", "page_no", "bbox", "row_count", "col_count",
        "extractor_version",
    ),
    "extracted_table_cells": (
        "tenant_id", "table_id", "row_no", "col_no", "text", "bbox", "confidence",
    ),
}  # fmt: skip
_PAGE_COLUMNS = ("text_source", "ocr_run_id", "mean_confidence", "low_conf_words")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE ocr_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            provider text NOT NULL CHECK (provider IN ('textract', 'fake')),
            api text NOT NULL CHECK (api IN ('detect_text', 'analyze_forms', 'analyze_tables')),
            pages integer[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(pages) <= 500),
            status text NOT NULL CHECK (status IN ('completed', 'refused', 'failed')),
            refused_reason text NULL CHECK (refused_reason IN ({_REFUSALS})),
            register_version text NULL CHECK (char_length(register_version) <= 40),
            basis text NOT NULL CHECK (basis IN ('synthetic', 'client_data')),
            page_units integer NOT NULL DEFAULT 0 CHECK (page_units >= 0),
            provider_request_ids text[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(provider_request_ids) <= 500),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT ocr_runs_refusal_has_reason
                CHECK ((status = 'refused') = (refused_reason IS NOT NULL)),
            CHECK (status <> 'refused' OR page_units = 0)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE extracted_fields (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            ocr_run_id uuid NULL,
            form_type text NOT NULL CHECK (form_type ~ '^[a-z0-9_]{{1,40}}$'),
            tax_year integer NULL CHECK (tax_year BETWEEN 1990 AND 2100),
            form_map_version text NOT NULL CHECK (char_length(form_map_version) BETWEEN 1 AND 40),
            field_key text NOT NULL CHECK (field_key ~ '^[a-z0-9_]+(\\.[a-z0-9_]+)+$'),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            value_type text NOT NULL CHECK (value_type IN ('money', 'date', 'text', 'tin',
                'percent', 'code', 'checkbox')),
            value_text text NULL CHECK (char_length(value_text) <= 2000),
            value_sealed bytea NULL,
            last4 text NULL CHECK (last4 ~ '^[0-9]{{4}}$'),
            page_no integer NOT NULL CHECK (page_no >= 1),
            {_BBOX},
            confidence numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            low_confidence boolean NOT NULL,
            extractor_kind text NOT NULL CHECK (extractor_kind IN ('form_map', 'textract_kv')),
            {_EXTRACTOR},
            pii_region_id uuid NULL,
            match_id text NOT NULL CHECK (match_id ~ '^ev:[0-9a-f-]{{36}}#field:[a-z0-9_.]+$'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT extracted_fields_tin_sealed CHECK ((value_type = 'tin')
                = (value_sealed IS NOT NULL AND value_text IS NULL)),
            CHECK (value_type <> 'tin' OR last4 IS NOT NULL),
            FOREIGN KEY (tenant_id, ocr_run_id) REFERENCES ocr_runs (tenant_id, id),
            FOREIGN KEY (tenant_id, pii_region_id) REFERENCES pii_regions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX extracted_fields_source ON extracted_fields "
        "(tenant_id, evidence_version_id, field_key) WHERE evidence_version_id IS NOT NULL"
    )
    op.execute(
        f"""
        CREATE TABLE extracted_tables (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            ocr_run_id uuid NULL,
            page_no integer NOT NULL CHECK (page_no >= 1),
            {_BBOX},
            row_count integer NOT NULL CHECK (row_count >= 0),
            col_count integer NOT NULL CHECK (col_count >= 0),
            {_EXTRACTOR},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, ocr_run_id) REFERENCES ocr_runs (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE extracted_table_cells (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            table_id uuid NOT NULL,
            row_no integer NOT NULL CHECK (row_no >= 0),
            col_no integer NOT NULL CHECK (col_no >= 0),
            text text NOT NULL CHECK (char_length(text) <= 2000),
            {_BBOX},
            confidence numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, table_id, row_no, col_no),
            FOREIGN KEY (tenant_id, table_id) REFERENCES extracted_tables (tenant_id, id)
        )
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        insert_only(op, table)
        op.execute(f"REVOKE TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION trust_kit_immutable()"
        )
    op.execute(
        """
        ALTER TABLE evidence_pages
            ADD COLUMN text_source text NULL CHECK (text_source IN ('text_layer', 'ocr', 'none')),
            ADD COLUMN ocr_run_id uuid NULL,
            ADD COLUMN mean_confidence numeric(4, 3) NULL CHECK (mean_confidence BETWEEN 0 AND 1),
            ADD COLUMN low_conf_words integer NULL CHECK (low_conf_words >= 0),
            ADD CONSTRAINT evidence_pages_ocr_run FOREIGN KEY (tenant_id, ocr_run_id)
                REFERENCES ocr_runs (tenant_id, id),
            ADD CONSTRAINT evidence_pages_ocr_source
                CHECK (text_source IS DISTINCT FROM 'ocr' OR ocr_run_id IS NOT NULL)
        """
    )
    # A plain column GRANT: insert_columns would revoke 0109's column grants with the table's.
    op.execute(f"GRANT INSERT ({', '.join(_PAGE_COLUMNS)}) ON evidence_pages TO abacus_app")
    op.execute(
        "ALTER TABLE document_classifications ADD COLUMN form_map_version text NULL "
        "CHECK (char_length(form_map_version) BETWEEN 1 AND 40)"
    )
    op.execute("GRANT INSERT (form_map_version) ON document_classifications TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE document_classifications DROP COLUMN form_map_version")
    op.execute(
        "ALTER TABLE evidence_pages DROP CONSTRAINT evidence_pages_ocr_source, "
        "DROP CONSTRAINT evidence_pages_ocr_run, "
        + ", ".join(f"DROP COLUMN {c}" for c in _PAGE_COLUMNS)
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
