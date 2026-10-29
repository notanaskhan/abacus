"""Firm standards and threshold policies (K-02-T04; K-02 §4.2 M-B; SPEC-500 AC-11, AC-12).

Per-tenant, versioned rules that sort agent output and govern review (KNW-04). Two parents follow
the glossary, with one version table each:
- `firm_standards` (kinds review_checklist, review_levels, return_approval_policy,
  ssars_cas_settings) and `threshold_policies` (aje_thresholds, variance_thresholds,
  materiality_ranges, document_confidence): forced RLS; one per (tenant, key); a named owner.
- `firm_standard_versions` and `threshold_policy_versions`: forced RLS; versions numbered
  1, 2, 3 … per parent (a trigger refuses any other number); one `draft` per parent (a partial
  unique index); a published version has its effective date, publisher and `published_actor_kind
  = 'human'` (a CHECK); a trigger refuses any change to a published or discarded version,
  refuses publishing outside a person's session, refuses every DELETE and TRUNCATE, and lets a
  draft move only to `published` or `discarded`. "Superseded" is computed at read time, never
  stored.

The app inserts parents and drafts and updates only the listed columns; it never deletes. No
standard is inserted here (rule 16): content arrives through the import endpoints (K-02-T11).

Revision ID: 0401
Revises: 0400
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0401"
down_revision = "0400"
branch_labels = None
depends_on = None

_PAIRS = (
    (
        "firm_standards",
        "firm_standard_versions",
        "('review_checklist', 'review_levels', 'return_approval_policy', 'ssars_cas_settings')",
    ),
    (
        "threshold_policies",
        "threshold_policy_versions",
        "('aje_thresholds', 'variance_thresholds', 'materiality_ranges', 'document_confidence')",
    ),
)
PARENT_INSERT = ("id", "tenant_id", "kind", "key", "name", "owner_id", "applies_to", "created_by")
PARENT_UPDATE = ("name", "owner_id", "applies_to", "row_version")
VERSION_INSERT = (
    "id",
    "tenant_id",
    "parent_id",
    "version",
    "payload",
    "payload_schema_version",
    "payload_hash",
    "change_summary",
    "drafted_from_version_id",
    "drafted_by",
)
VERSION_UPDATE = (
    "status",
    "effective_from",
    "payload",
    "payload_hash",
    "change_summary",
    "published_by",
    "published_actor_kind",
    "published_at",
    "row_version",
)

_GUARD = """
    CREATE FUNCTION standard_versions_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    DECLARE
        v_next integer;
    BEGIN
        IF TG_OP = 'TRUNCATE' THEN
            RAISE EXCEPTION 'standard versions cannot be truncated'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'draft' THEN
                RAISE EXCEPTION 'not_draft' USING ERRCODE = 'check_violation';
            END IF;
            EXECUTE format('SELECT coalesce(max(version), 0) + 1 FROM public.%I '
                           'WHERE tenant_id = $1 AND parent_id = $2', TG_TABLE_NAME)
               INTO v_next USING NEW.tenant_id, NEW.parent_id;
            IF NEW.version <> v_next THEN
                RAISE EXCEPTION 'version_not_next' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END IF;
        -- UPDATE: a published or discarded version never changes.
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.parent_id <> OLD.parent_id
           OR NEW.version <> OLD.version OR NEW.drafted_by <> OLD.drafted_by
           OR NEW.drafted_at <> OLD.drafted_at
           OR NEW.drafted_from_version_id IS DISTINCT FROM OLD.drafted_from_version_id THEN
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- INV-1: a publish happens in a person's session, whatever the service writes.
        IF NEW.status = 'published'
           AND coalesce(current_setting('app.actor_kind', true), '') <> 'human' THEN
            RAISE EXCEPTION 'publisher_not_human' USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


def _parent(table: str, kinds: str) -> str:
    return f"""
        CREATE TABLE {table} (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            kind text NOT NULL CHECK (kind IN {kinds}),
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_.-]{{2,79}}$'),
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
            owner_id uuid NOT NULL,
            applies_to jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(applies_to) = 'object'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, key),
            FOREIGN KEY (tenant_id, owner_id) REFERENCES memberships (tenant_id, user_id)
        )
    """


def _versions(table: str, parent: str) -> str:
    return f"""
        CREATE TABLE {table} (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            parent_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'discarded')),
            effective_from date NULL,
            payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
            payload_schema_version integer NOT NULL DEFAULT 1 CHECK (payload_schema_version >= 1),
            payload_hash text NOT NULL CHECK (payload_hash ~ '^sha256:[0-9a-f]{{64}}$'),
            change_summary text NULL CHECK (char_length(change_summary) BETWEEN 1 AND 500),
            drafted_from_version_id uuid NULL,
            drafted_by uuid NOT NULL,
            drafted_at timestamptz NOT NULL DEFAULT abacus_now(),
            published_by uuid NULL,
            published_actor_kind text NULL CHECK (published_actor_kind = 'human'),
            published_at timestamptz NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, parent_id, version),
            FOREIGN KEY (tenant_id, parent_id) REFERENCES {parent} (tenant_id, id),
            FOREIGN KEY (tenant_id, drafted_from_version_id) REFERENCES {table} (tenant_id, id),
            CHECK (status <> 'published' OR (effective_from IS NOT NULL
                                             AND published_by IS NOT NULL
                                             AND published_actor_kind IS NOT NULL
                                             AND published_at IS NOT NULL)),
            CHECK (status = 'published' OR (published_by IS NULL AND published_at IS NULL
                                            AND published_actor_kind IS NULL))
        )
    """


def upgrade() -> None:
    op.execute(_GUARD)
    for parent, versions, kinds in _PAIRS:
        op.execute(_parent(parent, kinds))
        op.execute(_versions(versions, parent))
        op.execute(
            f"CREATE UNIQUE INDEX {versions}_one_draft ON {versions} (tenant_id, parent_id) "
            "WHERE status = 'draft'"
        )
        for table in (parent, versions):
            tenant_table(op, table)
            op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, parent, PARENT_INSERT)
        op.execute(f"GRANT UPDATE ({', '.join(PARENT_UPDATE)}) ON {parent} TO abacus_app")
        insert_columns(op, versions, VERSION_INSERT)
        op.execute(f"GRANT UPDATE ({', '.join(VERSION_UPDATE)}) ON {versions} TO abacus_app")
        op.execute(
            f"CREATE TRIGGER {versions}_guard BEFORE INSERT OR UPDATE OR DELETE ON {versions} "
            "FOR EACH ROW EXECUTE FUNCTION standard_versions_guard()"
        )
        op.execute(
            f"CREATE TRIGGER {versions}_no_truncate BEFORE TRUNCATE ON {versions} "
            "FOR EACH STATEMENT EXECUTE FUNCTION standard_versions_guard()"
        )
    op.execute("REVOKE ALL ON FUNCTION standard_versions_guard() FROM PUBLIC")


def downgrade() -> None:
    for parent, versions, _kinds in reversed(_PAIRS):
        op.execute(f"DROP TABLE {versions}")
        op.execute(f"DROP TABLE {parent}")
    op.execute("DROP FUNCTION standard_versions_guard()")
