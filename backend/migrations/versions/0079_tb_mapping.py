"""Account mapping, first slice (SPEC-316; TASK-345; A-03).

Firm content (loaded through the import endpoint, never seeded):
- `grouping_sets`: a firm's taxonomy, by key.
- `grouping_set_versions`: a draft is imported with its problems; a person publishes it once
  (status and publication columns are the only updatable ones; a published version is frozen by
  a trigger).
- `groupings`, `fs_lines`, `fs_line_range_rules` (insert-only): the version's groupings (with
  their class), FS lines (with their normal balance) and account-number ranges.

Engagement work:
- `mapping_sets` (insert-only): one per trial balance of record, on a published version.
- `mapping_set_edits` (insert-only): a person's mapping of an account to an FS line, or back
  to the rules (`fs_line_id` NULL); the newest per account counts. Rule mappings are computed on
  read from the ranges, so a new trial balance version is mapped without writing anything.

Revision ID: 0079
Revises: 0078
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def _table(name: str, columns: tuple[str, ...], *, insert_only: bool = True) -> None:
    tenant_table(op, name)
    if insert_only:
        op.execute(f"REVOKE UPDATE, DELETE ON {name} FROM abacus_app")
    insert_columns(op, name, columns)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE grouping_sets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
            name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, key)
        )
        """
    )
    _table("grouping_sets", ("tenant_id", "key", "name", "created_by"))
    op.execute(
        """
        CREATE TABLE grouping_set_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            grouping_set_id uuid NOT NULL,
            version integer NOT NULL CHECK (version > 0),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
            payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
            problems jsonb NOT NULL DEFAULT '[]',
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            published_by uuid NULL,
            published_at timestamptz NULL,
            published_actor_kind text NULL CHECK (published_actor_kind = 'human'),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, grouping_set_id, version),
            CHECK ((status = 'published') = (published_by IS NOT NULL)),
            FOREIGN KEY (tenant_id, grouping_set_id) REFERENCES grouping_sets (tenant_id, id)
        )
        """
    )
    _table(
        "grouping_set_versions",
        ("tenant_id", "grouping_set_id", "version", "payload_hash", "problems", "created_by"),
        insert_only=False,
    )
    op.execute("REVOKE UPDATE, DELETE ON grouping_set_versions FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, published_by, published_at, published_actor_kind) "
        "ON grouping_set_versions TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION grouping_set_version_frozen() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'grouping set version % is published', OLD.id
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER grouping_set_version_frozen BEFORE UPDATE ON grouping_set_versions "
        "FOR EACH ROW EXECUTE FUNCTION grouping_set_version_frozen()"
    )
    op.execute(
        """
        CREATE TABLE groupings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            key text NOT NULL CHECK (length(key) BETWEEN 1 AND 40),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 120),
            class text NOT NULL
                CHECK (class IN ('assets', 'liabilities', 'equity', 'revenue', 'expenses')),
            position integer NOT NULL CHECK (position >= 0),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, key),
            FOREIGN KEY (tenant_id, version_id) REFERENCES grouping_set_versions (tenant_id, id)
        )
        """
    )
    _table("groupings", ("tenant_id", "version_id", "key", "label", "class", "position"))
    op.execute(
        """
        CREATE TABLE fs_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            grouping_id uuid NOT NULL,
            key text NOT NULL CHECK (length(key) BETWEEN 1 AND 40),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 160),
            normal_balance text NOT NULL CHECK (normal_balance IN ('debit', 'credit')),
            position integer NOT NULL CHECK (position >= 0),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, key),
            FOREIGN KEY (tenant_id, grouping_id) REFERENCES groupings (tenant_id, id)
        )
        """
    )
    _table(
        "fs_lines",
        ("tenant_id", "version_id", "grouping_id", "key", "label", "normal_balance", "position"),
    )
    op.execute(
        """
        CREATE TABLE fs_line_range_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_id uuid NOT NULL,
            position integer NOT NULL CHECK (position >= 0),
            account_from text NOT NULL CHECK (length(account_from) BETWEEN 1 AND 64),
            account_to text NOT NULL CHECK (length(account_to) BETWEEN 1 AND 64),
            fs_line_id uuid NOT NULL,
            CHECK (account_from <= account_to),
            FOREIGN KEY (tenant_id, fs_line_id) REFERENCES fs_lines (tenant_id, id)
        )
        """
    )
    _table(
        "fs_line_range_rules",
        ("tenant_id", "version_id", "position", "account_from", "account_to", "fs_line_id"),
    )
    op.execute(
        """
        CREATE TABLE mapping_sets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            trial_balance_id uuid NOT NULL,
            grouping_set_version_id uuid NOT NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, trial_balance_id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, trial_balance_id) REFERENCES trial_balances (tenant_id, id),
            FOREIGN KEY (tenant_id, grouping_set_version_id)
                REFERENCES grouping_set_versions (tenant_id, id)
        )
        """
    )
    _table(
        "mapping_sets",
        (
            "tenant_id",
            "engagement_id",
            "trial_balance_id",
            "grouping_set_version_id",
            "created_by",
        ),
    )
    op.execute(
        """
        CREATE TABLE mapping_set_edits (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            mapping_set_id uuid NOT NULL,
            account_code text NOT NULL CHECK (length(account_code) BETWEEN 1 AND 64),
            fs_line_id uuid NULL,
            edited_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, mapping_set_id) REFERENCES mapping_sets (tenant_id, id),
            FOREIGN KEY (tenant_id, fs_line_id) REFERENCES fs_lines (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX mapping_set_edits_newest ON mapping_set_edits "
        "(tenant_id, mapping_set_id, account_code, created_at DESC)"
    )
    _table(
        "mapping_set_edits",
        ("tenant_id", "mapping_set_id", "account_code", "fs_line_id", "edited_by", "actor_kind"),
    )


def downgrade() -> None:
    for table in (
        "mapping_set_edits",
        "mapping_sets",
        "fs_line_range_rules",
        "fs_lines",
        "groupings",
        "grouping_set_versions",
        "grouping_sets",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION grouping_set_version_frozen()")
