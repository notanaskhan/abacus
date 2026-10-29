"""Reporting v1: the C11 generated-document tables (P-11-T05; P-11 §4.2 "Migration 1"; ADR-320;
SPEC-520 AC-33, AC-27, AC-15, AC-16; P-38 expand-only).

Six tables in `reporting`, every one tenant-scoped with forced RLS:

- `generated_documents`: one per consumer record and kind (an engagement letter, a notice
  response…), with the scope columns `visible()` reads. Its status is computed from the latest
  version and events, never stored.
- Insert-only (`REVOKE UPDATE, DELETE` plus a trigger that refuses UPDATE, DELETE and TRUNCATE
  for every role): `generated_document_versions` (a final version needs an `approval_ref` and a
  human requester; an agent's request is a draft that names its run), `generated_document_files`
  (one per format; its `render_hash` is the evidence fingerprint; a sample has no evidence),
  `generated_document_fields` (the field-region manifest) and `generated_document_events`
  (out of date, locked, render failed, superseded).
- `render_jobs`: the operational job behind Drafting; its state moves through the unit of work.

Classification (ADR-031): `value_text`, `label`, `snapshot_key` Confidential (the snapshot object
may hold Restricted values, sealed in storage); `approval_ref`, hashes and ids Internal. No data
is inserted: templates are database content loaded through P-11-T06's import, never here.

Revision ID: 0430
Revises: 0321 (main's head at P-11-T05; re-chained at the S17 merge)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0430"
down_revision = "0321"
branch_labels = None
depends_on = None

_KINDS = (
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
)
_LAYOUTS = ("letter", "consent_7216", "report", "notice_response", "package", "run_export")
_FAILURES = (
    "missing_variable",
    "final_requires_approval",
    "approval_hash_mismatch",
    "markup_not_allowed",
    "unknown_variable",
    "asset_not_allowed",
    "missing_glyph",
    "renderer_unavailable",
    "document_locked",
)
_INSERT_ONLY = (
    "generated_document_versions",
    "generated_document_files",
    "generated_document_fields",
    "generated_document_events",
)
_HEX64 = "'^[0-9a-f]{64}$'"


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _immutable(table: str) -> None:
    insert_only(op, table)
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION reporting_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION reporting_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION reporting_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )

    op.execute(
        f"""
        CREATE TABLE generated_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ({_in(_KINDS)})),
            owner_type text NOT NULL CHECK (owner_type ~ '^[a-z_]{{1,64}}$'),
            owner_id uuid NOT NULL,
            client_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            template_id uuid NULL,
            created_by_kind text NOT NULL
                CHECK (created_by_kind IN ('human', 'agent', 'system')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, owner_type, owner_id, kind),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX generated_documents_by_client ON generated_documents (tenant_id, client_id)"
    )
    op.execute(
        "CREATE INDEX generated_documents_by_engagement ON generated_documents "
        "(tenant_id, engagement_id) WHERE engagement_id IS NOT NULL"
    )
    tenant_table(op, "generated_documents")
    insert_columns(
        op,
        "generated_documents",
        (
            "id",
            "tenant_id",
            "kind",
            "owner_type",
            "owner_id",
            "client_id",
            "engagement_id",
            "work_item_id",
            "template_id",
            "created_by_kind",
        ),
    )
    op.execute("REVOKE UPDATE, DELETE ON generated_documents FROM abacus_app")

    op.execute(
        f"""
        CREATE TABLE generated_document_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            generated_document_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            mode text NOT NULL CHECK (mode IN ('draft', 'final', 'sample')),
            template_version_id uuid NULL,
            layout_key text NOT NULL CHECK (layout_key IN ({_in(_LAYOUTS)})),
            layout_version integer NOT NULL CHECK (layout_version >= 1),
            snapshot_key text NOT NULL CHECK (char_length(snapshot_key) BETWEEN 1 AND 512),
            snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 ~ {_HEX64}),
            content_hash text NOT NULL CHECK (content_hash ~ {_HEX64}),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 500),
            approval_ref jsonb NULL CHECK (
                approval_ref IS NULL OR (
                    jsonb_typeof(approval_ref) = 'object'
                    AND approval_ref ?& ARRAY['kind', 'id', 'content_hash', 'approver_user_id']
                )
            ),
            requested_by_kind text NOT NULL
                CHECK (requested_by_kind IN ('human', 'agent', 'system')),
            requested_by_user_id uuid NULL,
            requested_by_run_id uuid NULL,
            on_behalf_of_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, generated_document_id, version_no),
            -- AC-15: a final version is a person's, with the approval it rests on.
            CHECK (mode <> 'final' OR (approval_ref IS NOT NULL
                                       AND requested_by_kind = 'human'
                                       AND requested_by_user_id IS NOT NULL)),
            -- AC-16, INV-1: an agent asks for drafts only, and names its run.
            CHECK (requested_by_kind <> 'agent' OR (mode = 'draft'
                                                    AND requested_by_run_id IS NOT NULL)),
            CHECK (requested_by_kind <> 'human' OR requested_by_user_id IS NOT NULL),
            -- The approval names the version it approved by that version's content hash.
            CHECK (approval_ref IS NULL OR approval_ref ->> 'content_hash' = content_hash),
            FOREIGN KEY (tenant_id, generated_document_id)
                REFERENCES generated_documents (tenant_id, id),
            FOREIGN KEY (tenant_id, requested_by_user_id)
                REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, on_behalf_of_user_id)
                REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "generated_document_versions")
    insert_columns(
        op,
        "generated_document_versions",
        (
            "id",
            "tenant_id",
            "generated_document_id",
            "version_no",
            "mode",
            "template_version_id",
            "layout_key",
            "layout_version",
            "snapshot_key",
            "snapshot_sha256",
            "content_hash",
            "engine_version",
            "approval_ref",
            "requested_by_kind",
            "requested_by_user_id",
            "requested_by_run_id",
            "on_behalf_of_user_id",
        ),
    )

    op.execute(
        """
        CREATE TABLE generated_document_files (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            format text NOT NULL CHECK (format IN ('pdf', 'docx')),
            evidence_version_id uuid NULL,
            sample_object_key text NULL CHECK (char_length(sample_object_key) BETWEEN 1 AND 512),
            render_hash bytea NOT NULL CHECK (octet_length(render_hash) = 32),
            page_count integer NOT NULL CHECK (page_count >= 1),
            byte_size bigint NOT NULL CHECK (byte_size >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, format),
            -- Evidence, or a 7-day sample object: exactly one (AC-25).
            CHECK ((evidence_version_id IS NULL) <> (sample_object_key IS NULL)),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES generated_document_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "generated_document_files")
    insert_columns(
        op,
        "generated_document_files",
        (
            "id",
            "tenant_id",
            "version_id",
            "format",
            "evidence_version_id",
            "sample_object_key",
            "render_hash",
            "page_count",
            "byte_size",
        ),
    )

    op.execute(
        """
        CREATE TABLE generated_document_fields (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[a-z][a-z0-9_.]{0,79}$'),
            occurrence integer NOT NULL DEFAULT 1 CHECK (occurrence >= 1),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            page integer NOT NULL CHECK (page >= 1),
            rect_pt numeric[] NOT NULL CHECK (array_length(rect_pt, 1) = 4),
            value_text text NOT NULL CHECK (char_length(value_text) <= 4000),
            match_id text NOT NULL CHECK (match_id LIKE 'gd:%'),
            UNIQUE (tenant_id, version_id, field_key, occurrence),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES generated_document_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "generated_document_fields")
    insert_columns(
        op,
        "generated_document_fields",
        (
            "id",
            "tenant_id",
            "version_id",
            "field_key",
            "occurrence",
            "label",
            "page",
            "rect_pt",
            "value_text",
            "match_id",
        ),
    )

    op.execute(
        """
        CREATE TABLE generated_document_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            generated_document_id uuid NOT NULL,
            kind text NOT NULL
                CHECK (kind IN ('out_of_date', 'locked', 'render_failed', 'superseded')),
            cause_ref text NOT NULL CHECK (char_length(cause_ref) BETWEEN 1 AND 200),
            changed_keys text[] NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
            actor_user_id uuid NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (actor_kind <> 'human' OR actor_user_id IS NOT NULL),
            -- Out of date names the changed keys, never their values (DEC-60).
            CHECK (kind <> 'out_of_date' OR changed_keys IS NOT NULL),
            FOREIGN KEY (tenant_id, generated_document_id)
                REFERENCES generated_documents (tenant_id, id),
            FOREIGN KEY (tenant_id, actor_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX generated_document_events_by_document ON generated_document_events "
        "(tenant_id, generated_document_id, at)"
    )
    tenant_table(op, "generated_document_events")
    insert_columns(
        op,
        "generated_document_events",
        (
            "id",
            "tenant_id",
            "generated_document_id",
            "kind",
            "cause_ref",
            "changed_keys",
            "actor_kind",
            "actor_user_id",
        ),
    )

    op.execute(
        f"""
        CREATE TABLE render_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            generated_document_id uuid NOT NULL,
            target_version_no integer NOT NULL CHECK (target_version_no >= 1),
            workflow_id text NOT NULL CHECK (char_length(workflow_id) BETWEEN 1 AND 300),
            status text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
            failure_code text NULL CHECK (failure_code IN ({_in(_FAILURES)})),
            started_at timestamptz NULL,
            finished_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, generated_document_id, target_version_no),
            CHECK ((status = 'failed') = (failure_code IS NOT NULL)),
            CHECK (status NOT IN ('succeeded', 'failed') OR finished_at IS NOT NULL),
            FOREIGN KEY (tenant_id, generated_document_id)
                REFERENCES generated_documents (tenant_id, id)
        )
        """
    )
    tenant_table(op, "render_jobs")
    insert_columns(
        op,
        "render_jobs",
        ("id", "tenant_id", "generated_document_id", "target_version_no", "workflow_id"),
    )
    op.execute("REVOKE UPDATE, DELETE ON render_jobs FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, failure_code, started_at, finished_at) ON render_jobs TO abacus_app"
    )

    for table in _INSERT_ONLY:
        _immutable(table)


def downgrade() -> None:
    for table in (
        "render_jobs",
        "generated_document_events",
        "generated_document_fields",
        "generated_document_files",
        "generated_document_versions",
        "generated_documents",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION reporting_rows_immutable()")
