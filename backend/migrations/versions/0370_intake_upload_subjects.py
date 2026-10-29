"""Intake attachments as upload subjects (N-01-T12; N-01 §4.4; DEC-1058).

The upload steps (extraction, previews, the word layer, the PII scan) run on communications'
intake attachments too. Each derived table gains `inbox_attachment_id` (a third subject beside
`evidence_version_id` and `inbox_file_id`; exactly one is set) and, where a row belongs to an
engagement, `engagement_id` becomes optional: an attachment belongs to none until it is filed.
An attachment row is never engagement-less in disguise: a row with no engagement must name an
attachment. The one-per-source indexes take the new subject.

Expand-only (Q-03-T081): a new nullable column, a relaxed NOT NULL and widened CHECKs.
"""

from __future__ import annotations

from alembic import op

revision = "0370"
down_revision = "0321"
branch_labels = None
depends_on = None

_TABLES = (
    "upload_extractions",
    "upload_previews",
    "evidence_pages",
    "pii_scan_runs",
    "pii_regions",
)
_ENGAGED = ("upload_extractions", "upload_previews")
_ONE = "num_nonnulls(evidence_version_id, inbox_file_id, inbox_attachment_id) = 1"


def _drop_subject_check(table: str) -> None:
    """The old CHECK that exactly one of a version and an inbox file is set, by its definition
    (0043, 0045 and 0109 left it unnamed)."""
    op.execute(
        f"""
        DO $$
        DECLARE c text;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = '{table}'::regclass AND contype = 'c'
                       AND pg_get_constraintdef(oid) LIKE '%evidence_version_id IS NULL%'
                       AND pg_get_constraintdef(oid) LIKE '%inbox_file_id IS NULL%'
            LOOP
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', c);
            END LOOP;
        END $$
        """  # noqa: S608 -- fixed SQL over this file's own table names, no input
    )


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN inbox_attachment_id uuid NULL, "
            f"ADD CONSTRAINT {table}_inbox_attachment "
            "FOREIGN KEY (tenant_id, inbox_attachment_id) "
            "REFERENCES inbox_attachments (tenant_id, id)"
        )
        _drop_subject_check(table)
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_one_subject CHECK ({_ONE})")
        op.execute(f"GRANT INSERT (inbox_attachment_id) ON {table} TO abacus_app")
    for table in _ENGAGED:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN engagement_id DROP NOT NULL")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_engaged_or_intake "
            "CHECK (engagement_id IS NOT NULL OR inbox_attachment_id IS NOT NULL)"
        )
    for table, version in (("upload_extractions", "extractor"), ("upload_previews", "renderer")):
        op.execute(
            f"CREATE UNIQUE INDEX {table}_one_per_inbox_attachment ON {table} "
            f"(tenant_id, inbox_attachment_id, {version}_version, derivation_id) "
            "NULLS NOT DISTINCT WHERE inbox_attachment_id IS NOT NULL"
        )
    op.execute("DROP INDEX evidence_pages_one_per_source")
    op.execute(
        "CREATE UNIQUE INDEX evidence_pages_one_per_source ON evidence_pages (tenant_id, "
        "evidence_version_id, inbox_file_id, inbox_attachment_id, derivation_id, page_no, "
        "extractor_version) NULLS NOT DISTINCT"
    )
    op.execute("DROP INDEX pii_scan_runs_one_per_source")
    op.execute(
        "CREATE UNIQUE INDEX pii_scan_runs_one_per_source ON pii_scan_runs (tenant_id, "
        "evidence_version_id, inbox_file_id, inbox_attachment_id, derivation_id, "
        "detector_version) NULLS NOT DISTINCT"
    )
    for table in _TABLES:
        op.execute(
            f"CREATE INDEX {table}_by_inbox_attachment ON {table} "
            "(tenant_id, inbox_attachment_id) WHERE inbox_attachment_id IS NOT NULL"
        )


def downgrade() -> None:
    # Refuses while any intake row exists (the dropped column would lose its subject).
    for table in _TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM {table} WHERE inbox_attachment_id IS NOT NULL) THEN
                    RAISE EXCEPTION '{table} holds intake rows: file or purge them first';
                END IF;
            END $$
            """  # noqa: S608 -- fixed SQL over this file's own table names, no input
        )
    op.execute("DROP INDEX pii_scan_runs_one_per_source")
    op.execute(
        "CREATE UNIQUE INDEX pii_scan_runs_one_per_source ON pii_scan_runs (tenant_id, "
        "evidence_version_id, inbox_file_id, derivation_id, detector_version) NULLS NOT DISTINCT"
    )
    op.execute("DROP INDEX evidence_pages_one_per_source")
    op.execute(
        "CREATE UNIQUE INDEX evidence_pages_one_per_source ON evidence_pages (tenant_id, "
        "evidence_version_id, inbox_file_id, derivation_id, page_no, extractor_version) "
        "NULLS NOT DISTINCT"
    )
    for table in ("upload_extractions", "upload_previews"):
        op.execute(f"DROP INDEX {table}_one_per_inbox_attachment")
    for table in _ENGAGED:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_engaged_or_intake")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN engagement_id SET NOT NULL")
    for table in _TABLES:
        op.execute(f"DROP INDEX {table}_by_inbox_attachment")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_one_subject")
        op.execute(
            f"ALTER TABLE {table} ADD CHECK "
            "((evidence_version_id IS NULL) <> (inbox_file_id IS NULL))"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN inbox_attachment_id")
