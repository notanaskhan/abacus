"""The trust kit's records (P-03-T04; ADR-166 for P-48, ADR-004, ADR-066, ADR-110).

Owned by `evidence`.
Every table is tenant-scoped under row-level security and insert-only for every role (a trigger
refuses UPDATE, DELETE and TRUNCATE, as for `evidence_versions`):
- `citations`: one cited value, verified by code before anyone sees it. The quote text is never
  stored: only `quote_sha256`, and readers re-read the words from the (masked) word layer. An
  unverified row names its reason. Agents' rows carry their run, people's rows their user.
- `citation_events`: `moved`, `broken` or `relinked`. A citation's state is computed from its
  latest event (`citation_current`), never updated. Only a person relinks.
- `evidence_pages`: one page of a version's (or inbox file's) word layer, with its geometry. The
  layer itself is a sealed object in storage.
- `pii_scan_runs`, `pii_regions`: what the detector scanned, and each personal-data region found,
  with the value sealed (Restricted) and its last four digits.
- `pii_reveals`: every reveal of a region, by a person (never an agent or the system).
- `evidence_derivations`: what an unlock derived from a password-protected file. The evidence
  object itself is never touched.
- `upload_extractions` and `upload_previews` gain `derivation_id`, and `upload_previews` gains
  `mask_version`. Their one-per-source unique indexes now include the derivation.

Revision ID: 0109
Revises: 0108
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None

_KINDS = (
    "'document_text', 'sheet_cell', 'ledger_line', 'workpaper_cell', 'methodology_step', "
    "'policy_rule', 'record_field', 'tax_form_line', 'artifact_cell', 'request_item'"
)
_REASONS = (
    "'page_not_found', 'cell_not_found', 'quote_not_found', 'value_mismatch', 'bbox_mismatch', "
    "'source_not_found', 'source_not_visible', 'locator_invalid'"
)
_PII = "'ssn', 'itin', 'ein', 'bank_account', 'routing_number', 'dob'"
# A page, scan or region belongs to exactly one version or inbox file, optionally derived.
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
_TABLES = (
    "evidence_derivations",
    "citations",
    "citation_events",
    "evidence_pages",
    "pii_scan_runs",
    "pii_regions",
    "pii_reveals",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_derivations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('password_unlock')),
            created_by_user_id uuid NOT NULL,
            extractor_version text NOT NULL CHECK (length(extractor_version) BETWEEN 1 AND 40),
            renderer_version text NOT NULL CHECK (length(renderer_version) BETWEEN 1 AND 40),
            detector_version text NOT NULL CHECK (length(detector_version) BETWEEN 1 AND 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE citations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            client_id uuid NULL,
            cited_from_type text NOT NULL CHECK (cited_from_type ~ '^[a-z][a-z_]{{0,39}}$'),
            cited_from_id uuid NOT NULL,
            cited_from_ref text NULL CHECK (length(cited_from_ref) BETWEEN 1 AND 120),
            cited_from_locator jsonb NULL
                CHECK (cited_from_locator IS NULL OR jsonb_typeof(cited_from_locator) = 'object'),
            n smallint NOT NULL CHECK (n >= 1),
            kind text NOT NULL CHECK (kind IN ({_KINDS})),
            source_type text NOT NULL CHECK (source_type ~ '^[a-z][a-z_]{{0,39}}$'),
            source_id uuid NOT NULL,
            source_version text NULL CHECK (length(source_version) BETWEEN 1 AND 60),
            locator jsonb NOT NULL CHECK (jsonb_typeof(locator) = 'object'),
            match_id text NULL CHECK (match_id ~ '^[A-Za-z0-9._:-]{{1,80}}$'),
            quote_sha256 bytea NULL CHECK (octet_length(quote_sha256) = 32),
            value_text text NULL CHECK (length(value_text) BETWEEN 1 AND 200),
            verified boolean NOT NULL,
            verification_reason text NULL CHECK (verification_reason IN ({_REASONS})),
            verifier_version text NOT NULL CHECK (length(verifier_version) BETWEEN 1 AND 40),
            supersedes_id uuid NULL,
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('agent', 'human', 'system')),
            created_by_user_id uuid NULL,
            created_by_run_id uuid NULL,
            on_behalf_of_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (verified OR verification_reason IS NOT NULL),
            CHECK (NOT verified OR verification_reason IS NULL),
            CHECK (created_by_kind <> 'agent' OR created_by_run_id IS NOT NULL),
            CHECK (created_by_kind <> 'human' OR created_by_user_id IS NOT NULL),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES citations (tenant_id, id)
        )
        """
    )
    for name, columns in (
        ("citations_by_anchor", "tenant_id, cited_from_type, cited_from_id, n"),
        ("citations_by_source", "tenant_id, source_type, source_id"),
        ("citations_by_match", "tenant_id, match_id"),
    ):
        op.execute(f"CREATE INDEX {name} ON citations ({columns})")
    op.execute(
        """
        CREATE TABLE citation_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            citation_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('moved', 'broken', 'relinked')),
            cause_ref text NULL CHECK (length(cause_ref) BETWEEN 1 AND 120),
            successor_citation_id uuid NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (kind <> 'relinked' OR actor_kind = 'human'),
            CHECK ((actor_kind = 'human') = (actor_user_id IS NOT NULL)),
            CHECK ((kind = 'relinked') = (successor_citation_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, citation_id) REFERENCES citations (tenant_id, id),
            FOREIGN KEY (tenant_id, successor_citation_id) REFERENCES citations (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX citation_events_by_citation ON citation_events (tenant_id, citation_id, at)"
    )
    # A citation's state, computed from its latest event: valid, moved, broken or relinked.
    op.execute(
        """
        CREATE VIEW citation_current WITH (security_invoker = true) AS
        SELECT c.id, c.tenant_id,
               coalesce((SELECT e.kind FROM citation_events e
                          WHERE e.tenant_id = c.tenant_id AND e.citation_id = c.id
                          ORDER BY e.at DESC, e.id DESC LIMIT 1), 'valid') AS state
          FROM citations c
        """
    )
    op.execute(
        f"""
        CREATE TABLE evidence_pages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            page_no integer NOT NULL CHECK (page_no >= 1),
            width_pt numeric(8, 2) NOT NULL CHECK (width_pt > 0),
            height_pt numeric(8, 2) NOT NULL CHECK (height_pt > 0),
            rotation smallint NOT NULL DEFAULT 0 CHECK (rotation IN (0, 90, 180, 270)),
            has_text_layer boolean NOT NULL,
            word_count integer NOT NULL DEFAULT 0 CHECK (word_count >= 0),
            text_layer_key text NULL CHECK (length(text_layer_key) BETWEEN 1 AND 1024),
            text_layer_version_id text NULL CHECK (length(text_layer_version_id) <= 1024),
            text_layer_fingerprint text NULL CHECK (text_layer_fingerprint ~ '^[0-9a-f]{{64}}$'),
            ocr_used boolean NOT NULL DEFAULT false,
            extractor_version text NOT NULL CHECK (length(extractor_version) BETWEEN 1 AND 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((text_layer_key IS NULL) = (text_layer_fingerprint IS NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX evidence_pages_one_per_source ON evidence_pages (tenant_id, "
        "evidence_version_id, inbox_file_id, derivation_id, page_no, extractor_version) "
        "NULLS NOT DISTINCT"
    )
    op.execute(
        f"""
        CREATE TABLE pii_scan_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            detector_version text NOT NULL CHECK (length(detector_version) BETWEEN 1 AND 40),
            pages_scanned integer[] NOT NULL DEFAULT '{{}}',
            pages_not_scannable integer[] NOT NULL DEFAULT '{{}}',
            region_count integer NOT NULL DEFAULT 0 CHECK (region_count >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX pii_scan_runs_one_per_source ON pii_scan_runs (tenant_id, "
        "evidence_version_id, inbox_file_id, derivation_id, detector_version) NULLS NOT DISTINCT"
    )
    op.execute(
        f"""
        CREATE TABLE pii_regions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,{_SOURCE},
            page_no integer NOT NULL CHECK (page_no >= 1),
            bbox numeric(10, 2)[] NOT NULL CHECK (array_length(bbox, 1) = 4),
            kind text NOT NULL CHECK (kind IN ({_PII})),
            value_sealed bytea NOT NULL CHECK (octet_length(value_sealed) <= 1024),
            last4 text NULL CHECK (last4 ~ '^[0-9]{{2,4}}$'),
            label_anchored boolean NOT NULL,
            detector_version text NOT NULL CHECK (length(detector_version) BETWEEN 1 AND 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX pii_regions_by_source ON pii_regions "
        "(tenant_id, evidence_version_id, inbox_file_id, page_no)"
    )
    op.execute(
        """
        CREATE TABLE pii_reveals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            region_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            user_id uuid NOT NULL,
            reason_code text NOT NULL DEFAULT 'source_review'
                CHECK (reason_code ~ '^[a-z][a-z_]{0,39}$'),
            context_ref text NULL CHECK (length(context_ref) BETWEEN 1 AND 120),
            mfa_at timestamptz NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            revealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            UNIQUE (tenant_id, id),
            CHECK (expires_at > revealed_at),
            FOREIGN KEY (tenant_id, region_id) REFERENCES pii_regions (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX pii_reveals_by_user ON pii_reveals (tenant_id, user_id, revealed_at)")

    op.execute(
        """
        CREATE FUNCTION trust_kit_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION trust_kit_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION trust_kit_immutable()"
        )
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(
        op,
        "evidence_derivations",
        (
            "id",
            "tenant_id",
            "evidence_version_id",
            "kind",
            "created_by_user_id",
            "extractor_version",
            "renderer_version",
            "detector_version",
        ),
    )
    insert_columns(
        op,
        "citations",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "client_id",
            "cited_from_type",
            "cited_from_id",
            "cited_from_ref",
            "cited_from_locator",
            "n",
            "kind",
            "source_type",
            "source_id",
            "source_version",
            "locator",
            "match_id",
            "quote_sha256",
            "value_text",
            "verified",
            "verification_reason",
            "verifier_version",
            "supersedes_id",
            "created_by_kind",
            "created_by_user_id",
            "created_by_run_id",
            "on_behalf_of_user_id",
        ),
    )
    insert_columns(
        op,
        "citation_events",
        (
            "tenant_id",
            "citation_id",
            "kind",
            "cause_ref",
            "successor_citation_id",
            "actor_kind",
            "actor_user_id",
        ),
    )
    insert_columns(
        op,
        "evidence_pages",
        (
            "tenant_id",
            *_SOURCE_COLUMNS,
            "page_no",
            "width_pt",
            "height_pt",
            "rotation",
            "has_text_layer",
            "word_count",
            "text_layer_key",
            "text_layer_version_id",
            "text_layer_fingerprint",
            "ocr_used",
            "extractor_version",
        ),
    )
    insert_columns(
        op,
        "pii_scan_runs",
        (
            "tenant_id",
            *_SOURCE_COLUMNS,
            "detector_version",
            "pages_scanned",
            "pages_not_scannable",
            "region_count",
        ),
    )
    insert_columns(
        op,
        "pii_regions",
        (
            "id",
            "tenant_id",
            *_SOURCE_COLUMNS,
            "page_no",
            "bbox",
            "kind",
            "value_sealed",
            "last4",
            "label_anchored",
            "detector_version",
        ),
    )
    insert_columns(
        op,
        "pii_reveals",
        (
            "tenant_id",
            "region_id",
            "evidence_version_id",
            "user_id",
            "reason_code",
            "context_ref",
            "mfa_at",
            "expires_at",
        ),
    )

    for table, version in (("upload_extractions", "extractor"), ("upload_previews", "renderer")):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN derivation_id uuid NULL, "
            f"ADD CONSTRAINT {table}_derivation FOREIGN KEY (tenant_id, derivation_id) "
            "REFERENCES evidence_derivations (tenant_id, id)"
        )
        op.execute(f"GRANT INSERT (derivation_id) ON {table} TO abacus_app")
        for source in ("version", "inbox_file"):
            column = "evidence_version_id" if source == "version" else "inbox_file_id"
            index = f"{table}_one_per_{source}"
            op.execute(f"DROP INDEX {index}")
            op.execute(
                f"CREATE UNIQUE INDEX {index} ON {table} "
                f"(tenant_id, {column}, {version}_version, derivation_id) NULLS NOT DISTINCT "
                f"WHERE {column} IS NOT NULL"
            )
    op.execute(
        "ALTER TABLE upload_previews ADD COLUMN mask_version text NULL "
        "CHECK (length(mask_version) BETWEEN 1 AND 40)"
    )
    op.execute("GRANT INSERT (mask_version) ON upload_previews TO abacus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE upload_previews DROP COLUMN mask_version")
    for table, version in (("upload_previews", "renderer"), ("upload_extractions", "extractor")):
        for source in ("version", "inbox_file"):
            column = "evidence_version_id" if source == "version" else "inbox_file_id"
            index = f"{table}_one_per_{source}"
            op.execute(f"DROP INDEX {index}")
            op.execute(
                f"CREATE UNIQUE INDEX {index} ON {table} "
                f"(tenant_id, {column}, {version}_version) WHERE {column} IS NOT NULL"
            )
        op.execute(f"ALTER TABLE {table} DROP COLUMN derivation_id")
    op.execute("DROP VIEW citation_current")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION trust_kit_immutable()")
