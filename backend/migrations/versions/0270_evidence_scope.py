"""Client-scoped evidence and same-client fulfilment (N-01-T06; ADR-158, P-40; SPEC-380 Story 8).

`evidence_items` gains `client_id` (NOT NULL, backfilled from the engagement), `work_item_id`
(backfilled from the fulfilling request list's work item, else the engagement's first work
item), `scope` (`engagement` | `client`) with `CHECK ((scope = 'client') = (engagement_id IS
NULL))`, and `folder_kind`; `engagement_id` becomes nullable. `evidence_versions` gains
`channel` (backfilled from `source` and `method`), `supersedes_version_id` (same item, lower
version), the virtual-split columns (`parent_version_id`, `page_range`, `virtual_label`,
`virtual_amount`; no new bytes), `display_name` and `classification_id`; its `engagement_id`
becomes nullable and must equal its item's (trigger).

The composite fulfilment foreign key to `evidence_versions (tenant_id, engagement_id, id)` is
replaced by a plain one and the trigger `fulfilment_same_client`: a fulfilment's evidence must
belong to the request's client (it may come from another engagement of that client, or be
client-scoped). The request-item key stays.

Existing code keeps working unchanged: a BEFORE INSERT trigger fills `client_id`, `work_item_id`
and `scope` from the engagement, and `channel` from `source` and `method`, when the insert leaves
them out. Only N-01-T19 writes client-scoped rows; every current path reads through
engagement-scoped queries, which never return them.

Before Jun 1, 2027 one reversible migration may change shape (ADR-135/P-38). The downgrade
refuses while any client-scoped item or cross-engagement fulfilment exists.

Revision ID: 0270
Revises: 0244 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

from alembic import op

revision = "0270"
down_revision = "0244"
branch_labels = None
depends_on = None

_FOLDER_KINDS = (
    "'source_documents', 'workpapers', 'correspondence', 'deliverables', 'signed_authorizations'"
)
_CHANNELS = (
    "'portal', 'email', 'firm_upload', 'retrieval', 'import', 'mobile', 'internal_handoff', "
    "'generated', 'confirmation_response'"
)
# The channel an existing version arrived by, from what it recorded (code, not a guess at
# intent): retrieved by a connector; a portal or drop source; a generated export; else the
# firm's own upload.
_CHANNEL_OF = """
    CASE
        WHEN {m} = 'retrieved' THEN 'retrieval'
        WHEN {s} LIKE '%portal%' OR {s} LIKE '%drop%' THEN 'portal'
        WHEN {s} LIKE '%export%' THEN 'generated'
        WHEN {s} LIKE '%import%' THEN 'import'
        ELSE 'firm_upload'
    END
"""


# The tables the backfill reads or writes. Each forces row-level security and the migration's
# role does not bypass it, so an UPDATE here would see no rows (and the NOT NULL that follows
# would fail on a populated database): FORCE is lifted for the backfill, as the tables' owner, and
# put back before anything else runs.
_BACKFILL_TABLES = (
    "evidence_items",
    "evidence_versions",
    "engagements",
    "fulfilments",
    "request_items",
    "request_lists",
    "work_items",
)


def _unforced(statement: str) -> None:
    for table in _BACKFILL_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(statement)
    for table in _BACKFILL_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # --- evidence_items ---------------------------------------------------------------------
    op.execute(
        f"""
        ALTER TABLE evidence_items
            ADD COLUMN client_id uuid NULL,
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN scope text NOT NULL DEFAULT 'engagement'
                CHECK (scope IN ('client', 'engagement')),
            ADD COLUMN folder_kind text NOT NULL DEFAULT 'source_documents'
                CHECK (folder_kind IN ({_FOLDER_KINDS}))
        """
    )
    _unforced(
        """
        UPDATE evidence_items i SET client_id = e.client_id
        FROM engagements e
        WHERE e.tenant_id = i.tenant_id AND e.id = i.engagement_id
        """
    )
    _unforced(
        """
        UPDATE evidence_items i SET work_item_id = coalesce(
            (SELECT rl.work_item_id
               FROM evidence_versions v
               JOIN fulfilments f
                 ON f.tenant_id = v.tenant_id AND f.evidence_version_id = v.id
               JOIN request_items ri
                 ON ri.tenant_id = f.tenant_id AND ri.id = f.request_item_id
               JOIN request_lists rl
                 ON rl.tenant_id = ri.tenant_id AND rl.id = ri.request_list_id
              WHERE v.tenant_id = i.tenant_id AND v.evidence_item_id = i.id
              ORDER BY f.created_at
              LIMIT 1),
            (SELECT w.id FROM work_items w
              WHERE w.tenant_id = i.tenant_id AND w.engagement_id = i.engagement_id
              ORDER BY w.created_at, w.id
              LIMIT 1))
        """
    )
    op.execute("ALTER TABLE evidence_items ALTER COLUMN client_id SET NOT NULL")
    op.execute("ALTER TABLE evidence_items ALTER COLUMN engagement_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE evidence_items ADD CONSTRAINT evidence_items_scope_engagement "
        "CHECK ((scope = 'client') = (engagement_id IS NULL))"
    )
    op.execute(
        "ALTER TABLE evidence_items ADD CONSTRAINT evidence_items_client_fkey "
        "FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE evidence_items ADD CONSTRAINT evidence_items_work_item_fkey "
        "FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id)"
    )
    op.execute(
        "ALTER TABLE evidence_items ADD CONSTRAINT evidence_items_client_unique "
        "UNIQUE (tenant_id, client_id, id)"
    )
    op.execute(
        "CREATE INDEX evidence_items_files ON evidence_items "
        "(tenant_id, client_id, work_item_id, folder_kind)"
    )
    # The item's client, work item and scope, from its engagement when the insert leaves them
    # out; an engagement-scoped item always carries its engagement's client (never another's).
    op.execute(
        """
        CREATE FUNCTION evidence_items_fill_scope() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            engagement_client uuid;
        BEGIN
            IF NEW.engagement_id IS NULL THEN
                NEW.scope := 'client';
                IF NEW.client_id IS NULL THEN
                    RAISE EXCEPTION 'a client-scoped evidence item needs its client (ADR-158)'
                        USING ERRCODE = 'not_null_violation';
                END IF;
                RETURN NEW;
            END IF;
            SELECT e.client_id INTO engagement_client FROM engagements e
             WHERE e.tenant_id = NEW.tenant_id AND e.id = NEW.engagement_id;
            IF NEW.client_id IS NULL THEN
                NEW.client_id := engagement_client;
            ELSIF NEW.client_id IS DISTINCT FROM engagement_client THEN
                RAISE EXCEPTION 'an evidence item belongs to its engagement''s client (ADR-158)'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.work_item_id IS NULL THEN
                SELECT w.id INTO NEW.work_item_id FROM work_items w
                 WHERE w.tenant_id = NEW.tenant_id AND w.engagement_id = NEW.engagement_id
                 ORDER BY w.created_at, w.id LIMIT 1;
            END IF;
            NEW.scope := 'engagement';
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_items_fill_scope BEFORE INSERT ON evidence_items "
        "FOR EACH ROW EXECUTE FUNCTION evidence_items_fill_scope()"
    )
    op.execute(
        "GRANT INSERT (client_id, work_item_id, scope, folder_kind) "
        "ON evidence_items TO abacus_app"
    )

    # --- evidence_versions ------------------------------------------------------------------
    op.execute(
        f"""
        ALTER TABLE evidence_versions
            ADD COLUMN channel text NULL CHECK (channel IN ({_CHANNELS})),
            ADD COLUMN supersedes_version_id uuid NULL,
            ADD COLUMN parent_version_id uuid NULL,
            ADD COLUMN page_range int4range NULL,
            ADD COLUMN virtual_label text NULL
                CHECK (virtual_label IS NULL OR length(virtual_label) BETWEEN 1 AND 200),
            ADD COLUMN virtual_amount numeric(20, 2) NULL,
            ADD COLUMN display_name text NULL
                CHECK (display_name IS NULL OR length(display_name) BETWEEN 1 AND 255),
            ADD COLUMN classification_id uuid NULL,
            ADD CONSTRAINT evidence_versions_virtual_split CHECK (
                (parent_version_id IS NULL) = (page_range IS NULL)
                AND (parent_version_id IS NOT NULL OR virtual_label IS NULL)
                AND (parent_version_id IS NOT NULL OR virtual_amount IS NULL)
            ),
            ADD CONSTRAINT evidence_versions_supersedes_fkey
                FOREIGN KEY (tenant_id, supersedes_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            ADD CONSTRAINT evidence_versions_parent_fkey
                FOREIGN KEY (tenant_id, parent_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            ADD CONSTRAINT evidence_versions_item_fkey
                FOREIGN KEY (tenant_id, evidence_item_id)
                REFERENCES evidence_items (tenant_id, id)
        """
    )
    # The backfill writes one new column on existing rows; ADR-004's trigger is off for this
    # statement only, inside the migration's transaction.
    op.execute(
        "ALTER TABLE evidence_versions DISABLE TRIGGER evidence_versions_no_update_or_delete"
    )
    _unforced(
        "UPDATE evidence_versions SET channel = "  # noqa: S608 -- fixed SQL, no input
        + _CHANNEL_OF.format(m="method", s="source")
    )
    op.execute(
        "ALTER TABLE evidence_versions ENABLE TRIGGER evidence_versions_no_update_or_delete"
    )
    op.execute("ALTER TABLE evidence_versions ALTER COLUMN engagement_id DROP NOT NULL")
    op.execute(
        f"""
        CREATE FUNCTION evidence_versions_fill_scope() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            item_engagement uuid;
            earlier record;
        BEGIN
            SELECT i.engagement_id INTO item_engagement FROM evidence_items i
             WHERE i.tenant_id = NEW.tenant_id AND i.id = NEW.evidence_item_id;
            IF NEW.engagement_id IS DISTINCT FROM item_engagement THEN
                RAISE EXCEPTION 'a version carries its item''s engagement (ADR-158)'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.channel IS NULL THEN
                NEW.channel := {_CHANNEL_OF.format(m="NEW.method", s="NEW.source")};
            END IF;
            IF NEW.supersedes_version_id IS NOT NULL THEN
                SELECT v.evidence_item_id, v.version_no INTO earlier FROM evidence_versions v
                 WHERE v.tenant_id = NEW.tenant_id AND v.id = NEW.supersedes_version_id;
                IF earlier.evidence_item_id IS DISTINCT FROM NEW.evidence_item_id
                   OR earlier.version_no >= NEW.version_no THEN
                    RAISE EXCEPTION 'a version supersedes an earlier version of its own item'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END
        $$
        """  # noqa: S608 -- fixed SQL, no input
    )
    op.execute(
        "CREATE TRIGGER evidence_versions_fill_scope BEFORE INSERT ON evidence_versions "
        "FOR EACH ROW EXECUTE FUNCTION evidence_versions_fill_scope()"
    )
    op.execute(
        "GRANT INSERT (channel, supersedes_version_id, parent_version_id, page_range, "
        "virtual_label, virtual_amount, display_name, classification_id) "
        "ON evidence_versions TO abacus_app"
    )
    op.execute(
        "CREATE INDEX evidence_versions_supersedes ON evidence_versions "
        "(tenant_id, supersedes_version_id) WHERE supersedes_version_id IS NOT NULL"
    )

    # --- fulfilments --------------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE c text;
        BEGIN
            SELECT conname INTO c FROM pg_constraint
             WHERE conrelid = 'fulfilments'::regclass
               AND confrelid = 'evidence_versions'::regclass AND contype = 'f';
            EXECUTE format('ALTER TABLE fulfilments DROP CONSTRAINT %I', c);
        END
        $$
        """
    )
    op.execute(
        "ALTER TABLE fulfilments ADD CONSTRAINT fulfilments_evidence_version_fkey "
        "FOREIGN KEY (tenant_id, evidence_version_id) REFERENCES evidence_versions (tenant_id, id)"
    )
    op.execute(
        """
        CREATE FUNCTION fulfilment_same_client() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            request_client uuid;
            evidence_client uuid;
        BEGIN
            SELECT e.client_id INTO request_client FROM request_items ri
              JOIN engagements e ON e.tenant_id = ri.tenant_id AND e.id = ri.engagement_id
             WHERE ri.tenant_id = NEW.tenant_id AND ri.id = NEW.request_item_id;
            SELECT i.client_id INTO evidence_client FROM evidence_versions v
              JOIN evidence_items i ON i.tenant_id = v.tenant_id AND i.id = v.evidence_item_id
             WHERE v.tenant_id = NEW.tenant_id AND v.id = NEW.evidence_version_id;
            IF request_client IS NULL OR evidence_client IS DISTINCT FROM request_client THEN
                RAISE EXCEPTION
                    'a fulfilment''s evidence belongs to the request''s client (ADR-158)'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER fulfilment_same_client BEFORE INSERT OR UPDATE ON fulfilments "
        "FOR EACH ROW EXECUTE FUNCTION fulfilment_same_client()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM evidence_items WHERE scope = 'client')
               OR EXISTS (
                   SELECT 1 FROM fulfilments f
                     JOIN evidence_versions v
                       ON v.tenant_id = f.tenant_id AND v.id = f.evidence_version_id
                    WHERE v.engagement_id IS DISTINCT FROM f.engagement_id)
               OR EXISTS (
                   SELECT 1 FROM evidence_versions
                    WHERE supersedes_version_id IS NOT NULL OR parent_version_id IS NOT NULL)
            THEN
                RAISE EXCEPTION 'client-scoped evidence, cross-engagement fulfilments or '
                    'version links exist: 0270 cannot be undone (ADR-004, ADR-158)';
            END IF;
        END
        $$
        """
    )
    op.execute("DROP TRIGGER fulfilment_same_client ON fulfilments")
    op.execute("DROP FUNCTION fulfilment_same_client()")
    op.execute("ALTER TABLE fulfilments DROP CONSTRAINT fulfilments_evidence_version_fkey")
    op.execute(
        "ALTER TABLE fulfilments ADD FOREIGN KEY (tenant_id, engagement_id, evidence_version_id) "
        "REFERENCES evidence_versions (tenant_id, engagement_id, id)"
    )

    op.execute("DROP INDEX evidence_versions_supersedes")
    op.execute("DROP TRIGGER evidence_versions_fill_scope ON evidence_versions")
    op.execute("DROP FUNCTION evidence_versions_fill_scope()")
    op.execute("ALTER TABLE evidence_versions ALTER COLUMN engagement_id SET NOT NULL")
    op.execute(
        """
        ALTER TABLE evidence_versions
            DROP CONSTRAINT evidence_versions_item_fkey,
            DROP CONSTRAINT evidence_versions_parent_fkey,
            DROP CONSTRAINT evidence_versions_supersedes_fkey,
            DROP CONSTRAINT evidence_versions_virtual_split,
            DROP COLUMN classification_id,
            DROP COLUMN display_name,
            DROP COLUMN virtual_amount,
            DROP COLUMN virtual_label,
            DROP COLUMN page_range,
            DROP COLUMN parent_version_id,
            DROP COLUMN supersedes_version_id,
            DROP COLUMN channel
        """
    )

    op.execute("DROP TRIGGER evidence_items_fill_scope ON evidence_items")
    op.execute("DROP FUNCTION evidence_items_fill_scope()")
    op.execute("DROP INDEX evidence_items_files")
    op.execute("ALTER TABLE evidence_items ALTER COLUMN engagement_id SET NOT NULL")
    op.execute(
        """
        ALTER TABLE evidence_items
            DROP CONSTRAINT evidence_items_client_unique,
            DROP CONSTRAINT evidence_items_work_item_fkey,
            DROP CONSTRAINT evidence_items_client_fkey,
            DROP CONSTRAINT evidence_items_scope_engagement,
            DROP COLUMN folder_kind,
            DROP COLUMN scope,
            DROP COLUMN work_item_id,
            DROP COLUMN client_id
        """
    )
