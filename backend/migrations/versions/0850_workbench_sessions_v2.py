"""W-02 sessions v2: rename and delete attribution, list indexes, wider item kinds (W-02-T06;
W-02 §4.2; SPEC-653; DEC-4605).

Expand-only. `workbench_sessions` gains `title_source` (`auto` until the owner renames it, then
`manual`; AC-L4, AC-L6), `renamed_by`, `renamed_at` and `deleted_by` (soft delete stays the only
delete: items, runs and trace are kept, AC-L4). The owner list index of 0682 already serves
`(tenant_id, owner_user_id, last_item_at DESC) WHERE deleted_at IS NULL`; this adds a GIN on
`client_scope` (walled omission and locking, DEC-87) and a trigram GIN on `title` (title-only
search, AC-L3; `pg_trgm` comes from `migrations/bootstrap.sql`, as 0840). `session_items.kind`
widens with `context_added`, `context_removed` and `drill` (`notice` was already there); items
stay insert-only.

Classifications (the models tag them): `title` Confidential; `title_source`, `renamed_by`,
`renamed_at`, `deleted_by` Internal.

Revision ID: 0850
Revises: 0842
"""

from __future__ import annotations

from alembic import op

revision = "0850"
down_revision = "0842"
branch_labels = None
depends_on = None

OLD_KINDS = (
    "user_message", "agent_blocks", "plan", "question", "answer", "tool_card", "artifact",
    "notice",
)  # fmt: skip
NEW_KINDS = (*OLD_KINDS, "context_added", "context_removed", "drill")
NEW_UPDATES = ("title_source", "renamed_by", "renamed_at", "deleted_by")


def _kinds(kinds: tuple[str, ...]) -> str:
    return ", ".join(f"'{k}'" for k in kinds)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE workbench_sessions
            ADD COLUMN title_source text NOT NULL DEFAULT 'auto'
                CONSTRAINT workbench_sessions_title_source_check
                CHECK (title_source IN ('auto', 'manual')),
            ADD COLUMN renamed_by uuid NULL,
            ADD COLUMN renamed_at timestamptz NULL,
            ADD COLUMN deleted_by uuid NULL,
            ADD CONSTRAINT workbench_sessions_renamed_pair
                CHECK ((renamed_by IS NULL) = (renamed_at IS NULL)),
            ADD CONSTRAINT workbench_sessions_manual_renamed
                CHECK (title_source = 'auto' OR renamed_at IS NOT NULL),
            ADD CONSTRAINT workbench_sessions_deleted_pair
                CHECK (deleted_by IS NULL OR deleted_at IS NOT NULL)
        """
    )
    op.execute(
        "CREATE INDEX workbench_sessions_client_scope ON workbench_sessions "
        "USING gin (client_scope) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX workbench_sessions_title_trgm ON workbench_sessions "
        "USING gin (title gin_trgm_ops) WHERE deleted_at IS NULL"
    )
    op.execute("ALTER TABLE session_items DROP CONSTRAINT session_items_kind_check")
    op.execute(
        "ALTER TABLE session_items ADD CONSTRAINT session_items_kind_check "
        f"CHECK (kind IN ({_kinds(NEW_KINDS)}))"
    )
    op.execute(f"GRANT UPDATE ({', '.join(NEW_UPDATES)}) ON workbench_sessions TO abacus_app")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(NEW_UPDATES)}) ON workbench_sessions FROM abacus_app")
    op.execute("ALTER TABLE session_items DROP CONSTRAINT session_items_kind_check")
    op.execute(
        "ALTER TABLE session_items ADD CONSTRAINT session_items_kind_check "
        f"CHECK (kind IN ({_kinds(OLD_KINDS)})) NOT VALID"
    )
    op.execute("DROP INDEX workbench_sessions_title_trgm")
    op.execute("DROP INDEX workbench_sessions_client_scope")
    op.execute(
        """
        ALTER TABLE workbench_sessions
            DROP CONSTRAINT workbench_sessions_deleted_pair,
            DROP CONSTRAINT workbench_sessions_manual_renamed,
            DROP CONSTRAINT workbench_sessions_renamed_pair,
            DROP COLUMN deleted_by,
            DROP COLUMN renamed_at,
            DROP COLUMN renamed_by,
            DROP COLUMN title_source
        """
    )
