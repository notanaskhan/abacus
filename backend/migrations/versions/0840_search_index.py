"""P-02-T05 (S39; TASK-7505; P-02 §4.2; ADR-241, P-33): the firm search index, expand-only.

- `search_documents` (owner `platform`): one metadata-only row per `(tenant_id, object_type,
  object_id)`, upserted by the indexer from the owner's registered C15 builder and rebuildable from
  scratch. Not insert-only: it is a projection, never a record. Walls are evaluated at query time
  on `client_id` (never stored here), so `client_id` is required unless the scope is `firm` or
  `own`. `tsv` is written by the indexer in the same upsert (title A, identifiers B, related names
  C, context D, config `simple`): not a generated column, because `array_to_string` is not
  immutable. No TIN, amount, document text or comment body has a column here.
- `search_recents` (owner `platform`, scope `own`): a person's last opened records, identifiers
  only, trimmed to 20 per person by the service. Operational state (P-02 OQ-1).

Both tables force row-level security on `tenant_id` (ADR-014). `search_documents` is exempt from
`archived_guard()` (a rebuildable projection, like `home_activity_items`): a locked file's rows are
still rebuilt or deleted. `pg_trgm` and `btree_gin` are created by `migrations/bootstrap.sql`
(DEC-16); this revision only uses them.

Revision ID: 0840
Revises: 0832
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0840"
down_revision = "0832"
branch_labels = None
depends_on = None

_GROUPS = (
    "clients",
    "returns",
    "audits",
    "closes",
    "binders",
    "files",
    "inbox",
    "sessions",
    "todos",
    "saved_prompts",
    "agents",
)
_SCOPES = ("engagement", "work_item", "client", "client_entity", "firm", "own")
_CLASSES = ("internal", "confidential", "tri")


def _list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE search_documents (
            tenant_id uuid NOT NULL,
            object_type text NOT NULL CHECK (object_type ~ '^[a-z][a-z0-9_]{{1,39}}$'),
            object_id uuid NOT NULL,
            group_key text NOT NULL CHECK (group_key IN ({_list(_GROUPS)})),
            scope_kind text NOT NULL CHECK (scope_kind IN ({_list(_SCOPES)})),
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            client_id uuid NULL,
            owner_user_id uuid NULL,
            data_class text NOT NULL DEFAULT 'confidential'
                CHECK (data_class IN ({_list(_CLASSES)})),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 300),
            context text NULL CHECK (char_length(context) <= 300),
            identifiers_text text NOT NULL DEFAULT ''
                CHECK (char_length(identifiers_text) <= 2000),
            related jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(related) = 'array' AND jsonb_array_length(related) <= 20),
            related_text text NOT NULL DEFAULT '' CHECK (char_length(related_text) <= 4000),
            status_code text NULL CHECK (status_code ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            status_context text NULL CHECK (status_context ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            due_on date NULL,
            tag text NULL CHECK (tag IN ('firm', 'service_line', 'personal')),
            use_count integer NULL CHECK (use_count >= 0),
            target_params jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(target_params) = 'object'),
            tsv tsvector NOT NULL,
            source_updated_at timestamptz NOT NULL,
            indexed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, object_type, object_id),
            CONSTRAINT search_documents_client_scoped CHECK (
                client_id IS NOT NULL OR scope_kind IN ('firm', 'own')),
            CONSTRAINT search_documents_engagement_scoped CHECK (
                engagement_id IS NOT NULL OR scope_kind NOT IN ('engagement', 'work_item')),
            CONSTRAINT search_documents_owner_scoped CHECK (
                owner_user_id IS NOT NULL OR scope_kind <> 'own')
        )
        """
    )
    op.execute("CREATE INDEX search_documents_tsv ON search_documents USING gin (tsv)")
    for column in ("title", "identifiers_text", "related_text"):
        op.execute(
            f"CREATE INDEX search_documents_{column}_trgm ON search_documents "
            f"USING gin ({column} gin_trgm_ops)"
        )
    op.execute(
        "CREATE INDEX search_documents_freshness ON search_documents "
        "(tenant_id, object_type, source_updated_at DESC)"
    )
    op.execute("CREATE INDEX search_documents_client ON search_documents (tenant_id, client_id)")
    op.execute("CREATE INDEX search_documents_group ON search_documents (tenant_id, group_key)")
    tenant_table(op, "search_documents")
    op.execute("REVOKE TRUNCATE ON search_documents FROM abacus_app")

    op.execute(
        """
        CREATE TABLE search_recents (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            object_type text NOT NULL CHECK (object_type ~ '^[a-z][a-z0-9_]{1,39}$'),
            object_id uuid NOT NULL,
            opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, user_id, object_type, object_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX search_recents_newest ON search_recents (tenant_id, user_id, opened_at DESC)"
    )
    tenant_table(op, "search_recents")
    op.execute("REVOKE TRUNCATE ON search_recents FROM abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE search_recents")
    op.execute("DROP TABLE search_documents")
