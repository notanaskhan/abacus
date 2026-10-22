"""The binder engine (P-06-T05; P-06 §4.2; C5).

- `request_lists` (binders) gain:
  - unpublish stamps, with a sealed reason;
  - `created_from` (blank, template, prior-year binder or engine import) and `template_ref`;
  - a follow-up override (`every_days` 1..30, `max` 1..4);
  - close stamps.
  The app may update the stamps only.
- New `binder_recipients`: insert-only. A removal is a new row with `removed_at`.
- `request_items` gain:
  - `title`, `category_id`, `firm_owner_user_id`;
  - the period (`period_start` ≤ `period_end`), `wave`, `kind` and `source_tag`;
  - `supports_ref` and `linked_ref`;
  - the drafted-wording provenance. A run, its source and its fingerprint are all set or all
    null.
  - `sent_by`, and the soft delete. A sent request can never be deleted: only a draft never
    sent.
- `request_categories` gain `glyph` and `family`.
- New `request_delegations`: a request handed to a client contact under a grant.
- New UNLOGGED `request_upload_intents`: a 90-second portal hint, swept and never authoritative.
- New `binder_activity`: a projection updated by subscribers, with indexes for the binder lists.

Revision ID: 0100
Revises: 0099
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None

_LIST_STAMPS = (
    "unpublished_at, unpublished_by, unpublish_reason_sealed, follow_up_override, closed_at, "
    "closed_reason"
)
_ITEM_NEW = (
    "title",
    "category_id",
    "firm_owner_user_id",
    "period_start",
    "period_end",
    "wave",
    "kind",
    "source_tag",
    "supports_ref",
    "linked_ref",
    "drafted_by_run_id",
    "drafted_wording_source",
    "drafted_wording_fingerprint",
)
_ITEM_BEFORE = (
    "id",
    "tenant_id",
    "engagement_id",
    "request_list_id",
    "description",
    "audit_area",
    "created_by",
    "retrievability_tier",
    "dataset",
    "tier_source",
    "tier_rule",
    "document_kind",
    "document_kind_source",
    "why",
    "good_looks_like",
    "blocks_fieldwork",
    "effort",
    "guidance_source",
    "guidance_approved_by",
)
_LIST_BEFORE = (
    "id",
    "tenant_id",
    "engagement_id",
    "work_item_id",
    "name",
    "kind",
    "part",
    "status",
    "prior_year_source_ref",
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE request_lists
            ADD COLUMN unpublished_at timestamptz NULL,
            ADD COLUMN unpublished_by uuid NULL,
            ADD COLUMN unpublish_reason_sealed bytea NULL
                CHECK (octet_length(unpublish_reason_sealed) <= 4096),
            ADD COLUMN created_from text NOT NULL DEFAULT 'blank'
                CHECK (created_from IN
                    ('blank', 'template', 'prior_year_binder', 'engine_import')),
            ADD COLUMN template_ref text NULL CHECK (length(template_ref) BETWEEN 1 AND 200),
            ADD COLUMN follow_up_override jsonb NULL CHECK (
                follow_up_override IS NULL OR (
                    (follow_up_override->>'every_days')::int BETWEEN 1 AND 30
                    AND (follow_up_override->>'max')::int BETWEEN 1 AND 4
                )
            ),
            ADD COLUMN closed_at timestamptz NULL,
            ADD COLUMN closed_reason text NULL CHECK (closed_reason ~ '^[a-z][a-z_]{0,39}$')
        """
    )
    op.execute(f"GRANT UPDATE ({_LIST_STAMPS}) ON request_lists TO abacus_app")
    insert_columns(op, "request_lists", (*_LIST_BEFORE, "created_from", "template_ref"))

    op.execute(
        """
        CREATE TABLE binder_recipients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            binder_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            added_by uuid NOT NULL,
            added_at timestamptz NOT NULL DEFAULT abacus_now(),
            removed_at timestamptz NULL,
            FOREIGN KEY (tenant_id, binder_id) REFERENCES request_lists (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX binder_recipients_by_binder ON binder_recipients (tenant_id, binder_id)"
    )

    op.execute(
        """
        ALTER TABLE request_categories
            ADD COLUMN glyph text NULL CHECK (glyph ~ '^[A-Za-z0-9]{1,40}$'),
            ADD COLUMN family text NULL CHECK (family IN ('tax_portal', 'audit_area', 'close'))
        """
    )
    op.execute(
        """
        ALTER TABLE request_items
            ADD COLUMN title text NULL CHECK (length(title) BETWEEN 1 AND 200),
            ADD COLUMN category_id uuid NULL REFERENCES request_categories (id),
            ADD COLUMN firm_owner_user_id uuid NULL,
            ADD COLUMN period_start date NULL,
            ADD COLUMN period_end date NULL,
            ADD COLUMN wave text NULL CHECK (wave IN ('planning', 'year_end', 'sample')),
            ADD COLUMN kind text NOT NULL DEFAULT 'client_upload'
                CHECK (kind IN ('client_upload', 'firm_provided')),
            ADD COLUMN source_tag text NULL CHECK (source_tag IN ('prior_year')),
            ADD COLUMN supports_ref text NULL CHECK (length(supports_ref) BETWEEN 1 AND 200),
            ADD COLUMN linked_ref jsonb NULL
                CHECK (linked_ref IS NULL OR jsonb_typeof(linked_ref) = 'object'),
            ADD COLUMN drafted_by_run_id uuid NULL,
            ADD COLUMN drafted_wording_source text NULL
                CHECK (drafted_wording_source IN ('template', 'model')),
            ADD COLUMN drafted_wording_fingerprint text NULL
                CHECK (drafted_wording_fingerprint ~ '^[0-9a-f]{64}$'),
            ADD COLUMN sent_by uuid NULL,
            ADD COLUMN deleted_at timestamptz NULL,
            ADD COLUMN deleted_by uuid NULL,
            ADD CONSTRAINT request_items_period_in_order
                CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end),
            ADD CONSTRAINT request_items_drafted_wording_whole CHECK (
                (drafted_by_run_id IS NULL) = (drafted_wording_source IS NULL)
                AND (drafted_by_run_id IS NULL) = (drafted_wording_fingerprint IS NULL)
            ),
            ADD CONSTRAINT request_items_only_unsent_drafts_deleted
                CHECK (deleted_at IS NULL OR (status = 'draft' AND sent_at IS NULL))
        """
    )
    insert_columns(op, "request_items", (*_ITEM_BEFORE, *_ITEM_NEW))
    op.execute(
        "GRANT UPDATE (title, category_id, firm_owner_user_id, period_start, period_end, wave, "
        "supports_ref, linked_ref, sent_by, deleted_at, deleted_by) ON request_items TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE request_delegations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            grant_id uuid NULL,
            granted_by uuid NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT abacus_now(),
            revoked_at timestamptz NULL,
            FOREIGN KEY (tenant_id, request_item_id) REFERENCES request_items (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX request_delegations_by_item ON request_delegations "
        "(tenant_id, request_item_id)"
    )
    op.execute(
        """
        CREATE UNLOGGED TABLE request_upload_intents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            request_item_id uuid NOT NULL,
            user_id uuid NOT NULL,
            files_expected integer NOT NULL CHECK (files_expected BETWEEN 1 AND 100),
            started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL DEFAULT clock_timestamp() + interval '90 seconds'
        )
        """
    )
    op.execute(
        "CREATE INDEX request_upload_intents_live ON request_upload_intents "
        "(tenant_id, request_item_id, expires_at)"
    )
    op.execute(
        """
        CREATE TABLE binder_activity (
            tenant_id uuid NOT NULL,
            binder_id uuid NOT NULL,
            work_item_id uuid NULL,
            status text NOT NULL,
            open_count integer NOT NULL DEFAULT 0 CHECK (open_count >= 0),
            last_client_activity_at timestamptz NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, binder_id),
            FOREIGN KEY (tenant_id, binder_id) REFERENCES request_lists (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX binder_activity_by_work_item ON binder_activity "
        "(tenant_id, work_item_id, status)"
    )
    op.execute(
        "CREATE INDEX binder_activity_by_client_activity ON binder_activity "
        "(tenant_id, status, last_client_activity_at)"
    )

    for table in ("binder_recipients", "request_delegations", "request_upload_intents"):
        tenant_table(op, table)
    tenant_table(op, "binder_activity")
    op.execute("REVOKE UPDATE, DELETE ON binder_recipients FROM abacus_app")
    insert_columns(
        op, "binder_recipients", ("tenant_id", "binder_id", "contact_id", "added_by", "removed_at")
    )
    op.execute("REVOKE UPDATE, DELETE ON request_delegations FROM abacus_app")
    insert_columns(
        op,
        "request_delegations",
        ("tenant_id", "request_item_id", "contact_id", "grant_id", "granted_by"),
    )
    op.execute("GRANT UPDATE (revoked_at) ON request_delegations TO abacus_app")
    op.execute("REVOKE UPDATE ON request_upload_intents FROM abacus_app")
    insert_columns(
        op, "request_upload_intents", ("tenant_id", "request_item_id", "user_id", "files_expected")
    )
    op.execute("REVOKE DELETE ON binder_activity FROM abacus_app")
    op.execute("REVOKE UPDATE ON binder_activity FROM abacus_app")
    insert_columns(
        op,
        "binder_activity",
        (
            "tenant_id",
            "binder_id",
            "work_item_id",
            "status",
            "open_count",
            "last_client_activity_at",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, open_count, last_client_activity_at, updated_at) "
        "ON binder_activity TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE binder_activity")
    op.execute("DROP TABLE request_upload_intents")
    op.execute("DROP TABLE request_delegations")
    op.execute(
        "REVOKE UPDATE (title, category_id, firm_owner_user_id, period_start, period_end, wave, "
        "supports_ref, linked_ref, sent_by, deleted_at, deleted_by) ON request_items "
        "FROM abacus_app"
    )
    insert_columns(op, "request_items", _ITEM_BEFORE)
    op.execute(
        "ALTER TABLE request_items DROP CONSTRAINT request_items_only_unsent_drafts_deleted, "
        "DROP CONSTRAINT request_items_drafted_wording_whole, "
        "DROP CONSTRAINT request_items_period_in_order, DROP COLUMN deleted_by, "
        "DROP COLUMN deleted_at, DROP COLUMN sent_by, DROP COLUMN drafted_wording_fingerprint, "
        "DROP COLUMN drafted_wording_source, DROP COLUMN drafted_by_run_id, "
        "DROP COLUMN linked_ref, DROP COLUMN supports_ref, DROP COLUMN source_tag, "
        "DROP COLUMN kind, DROP COLUMN wave, DROP COLUMN period_end, DROP COLUMN period_start, "
        "DROP COLUMN firm_owner_user_id, DROP COLUMN category_id, DROP COLUMN title"
    )
    op.execute("ALTER TABLE request_categories DROP COLUMN family, DROP COLUMN glyph")
    op.execute("DROP TABLE binder_recipients")
    insert_columns(op, "request_lists", _LIST_BEFORE)
    op.execute(f"REVOKE UPDATE ({_LIST_STAMPS}) ON request_lists FROM abacus_app")
    op.execute(
        "ALTER TABLE request_lists DROP COLUMN closed_reason, DROP COLUMN closed_at, "
        "DROP COLUMN follow_up_override, DROP COLUMN template_ref, DROP COLUMN created_from, "
        "DROP COLUMN unpublish_reason_sealed, DROP COLUMN unpublished_by, "
        "DROP COLUMN unpublished_at"
    )
