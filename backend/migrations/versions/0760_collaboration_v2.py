"""P-05-T04 (S33; TASK-6505; SPEC-650; P-05 §4.2; ADR-236 proposed; DEC-3105): comments v2 and
to-dos, expand-only.

Eight new tables owned by `collaboration`; no existing table changes (the SPEC-032 `comments`,
`comment_mentions`, `comment_redactions` and `comment_reads` of 0048 stay live and untouched until
CL-1, which is why the v2 body tables are named `thread_*`). Every table goes through
`tenant_table()` (forced RLS, `tenant_isolation`, `archived_guard`), and the app role inserts only
the columns it may supply.

- `comment_threads`: one per anchor and normalised locator (per version only under a `pin`
  provider), `open` or `resolved`; the app may update only the status projection, visibility,
  share scope and timestamps, each change written with its event.
- `comment_thread_events`, `thread_comments`, `thread_comment_mentions`,
  `thread_comment_redactions`: insert-only (grants and a trigger); events and comments are a
  person's (`actor_kind = 'human'`, INV-1). A client author only on a shared thread (trigger,
  as `comments_client_shared` in 0048). Bodies are sealed bytes with a fingerprint.
- `comment_thread_reads`: per person, `last_read_at` and `muted_at` only.
- `todos`: engagement or firm scope; `open`/`done` (Overdue is derived, never stored); no DELETE
  grant (soft delete); row text sealed. `todo_checklist_items`: at most 8 per to-do, a mutable
  sub-list (every change audited by the service).

Runs in the pipeline after 8 pm CT (P-29). Downgrade drops only what this revision created.

Revision ID: 0760
Revises: 0751
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0760"
down_revision = "0751"
branch_labels = None
depends_on = None

IMMUTABLE = (
    "comment_thread_events",
    "thread_comments",
    "thread_comment_mentions",
    "thread_comment_redactions",
)
TABLES = (
    "comment_threads",
    *IMMUTABLE,
    "comment_thread_reads",
    "todos",
    "todo_checklist_items",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "comment_threads": (
        "id",
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "client_id",
        "anchor_kind",
        "anchor_id",
        "anchor_locator",
        "anchor_locator_key",
        "opened_on_version_no",
        "pinned_version_no",
        "status",
        "visibility",
        "shared_scope_kind",
        "shared_scope_id",
        "created_by",
        "last_comment_at",
    ),
    "comment_thread_events": (
        "id",
        "tenant_id",
        "engagement_id",
        "thread_id",
        "kind",
        "actor_user_id",
        "actor_kind",
        "ref_type",
        "ref_id",
    ),
    "thread_comments": (
        "id",
        "tenant_id",
        "engagement_id",
        "thread_id",
        "author_user_id",
        "author_side",
        "body_sealed",
        "body_fingerprint",
        "corrects_comment_id",
        "citation_ids",
    ),
    "thread_comment_mentions": ("tenant_id", "comment_id", "user_id", "via_team"),
    "thread_comment_redactions": ("tenant_id", "comment_id", "redacted_by", "reason"),
    "comment_thread_reads": ("tenant_id", "user_id", "thread_id", "last_read_at", "muted_at"),
    "todos": (
        "id",
        "tenant_id",
        "scope_kind",
        "engagement_id",
        "work_item_id",
        "client_id",
        "title",
        "status",
        "assignee_user_id",
        "due_on",
        "anchor_kind",
        "anchor_id",
        "anchor_locator",
        "row_text_sealed",
        "row_text_fingerprint",
        "source_thread_id",
        "created_by",
    ),
    "todo_checklist_items": ("id", "tenant_id", "todo_id", "position", "text"),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "comment_threads": (
        "status",
        "visibility",
        "shared_scope_kind",
        "shared_scope_id",
        "last_comment_at",
        "updated_at",
    ),
    "comment_thread_reads": ("last_read_at", "muted_at"),
    "todos": (
        "title",
        "status",
        "assignee_user_id",
        "due_on",
        "anchor_kind",
        "anchor_id",
        "anchor_locator",
        "work_item_id",
        "done_by",
        "done_at",
        "assignee_seen_at",
        "deleted_at",
        "deleted_by",
        "version",
        "updated_at",
    ),
    "todo_checklist_items": ("position", "text", "done", "done_by", "done_at"),
}

_ANCHOR_KIND = "anchor_kind ~ '^[a-z][a-z0-9_]*$' AND length(anchor_kind) <= 40"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE comment_threads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NULL,
            client_id uuid NOT NULL,
            anchor_kind text NOT NULL CHECK ({_ANCHOR_KIND}),
            anchor_id uuid NOT NULL,
            anchor_locator jsonb NULL
                CHECK (anchor_locator IS NULL OR octet_length(anchor_locator::text) <= 2048),
            anchor_locator_key text NOT NULL DEFAULT '' CHECK (length(anchor_locator_key) <= 400),
            opened_on_version_no integer NULL CHECK (opened_on_version_no >= 1),
            pinned_version_no integer NULL CHECK (pinned_version_no >= 1),
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
            visibility text NOT NULL DEFAULT 'internal'
                CHECK (visibility IN ('internal', 'shared')),
            shared_scope_kind text NULL CHECK (length(shared_scope_kind) <= 40),
            shared_scope_id uuid NULL,
            created_by uuid NOT NULL REFERENCES users (id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            last_comment_at timestamptz NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT comment_threads_shared_scope CHECK (
                (visibility = 'shared') = (shared_scope_kind IS NOT NULL)
                AND (shared_scope_kind IS NULL) = (shared_scope_id IS NULL)
            ),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id)
        )
        """
    )
    # One thread per anchor and locator, and per version only for a `pin` provider (DEC-29).
    op.execute(
        "CREATE UNIQUE INDEX comment_threads_one_per_anchor ON comment_threads "
        "(tenant_id, anchor_kind, anchor_id, anchor_locator_key, pinned_version_no) "
        "NULLS NOT DISTINCT"
    )
    op.execute(
        "CREATE INDEX comment_threads_anchor ON comment_threads "
        "(tenant_id, anchor_kind, anchor_id)"
    )
    op.execute(
        "CREATE INDEX comment_threads_engagement ON comment_threads "
        "(tenant_id, engagement_id, last_comment_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE comment_thread_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            thread_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN (
                'opened', 'resolved', 'reopened', 'muted', 'unmuted', 'converted', 'shared',
                'unshared'
            )),
            actor_user_id uuid NOT NULL REFERENCES users (id),
            -- INV-1 layer 3: a thread event is always a person's (ADR-236 decision 5).
            actor_kind text NOT NULL DEFAULT 'human' CHECK (actor_kind = 'human'),
            ref_type text NULL CHECK (ref_type IN ('todo', 'review_note')),
            ref_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT comment_thread_events_ref CHECK ((ref_type IS NULL) = (ref_id IS NULL)),
            CONSTRAINT comment_thread_events_converted
                CHECK ((kind = 'converted') = (ref_type IS NOT NULL)),
            FOREIGN KEY (tenant_id, engagement_id, thread_id)
                REFERENCES comment_threads (tenant_id, engagement_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX comment_thread_events_thread ON comment_thread_events "
        "(tenant_id, thread_id, created_at)"
    )
    op.execute(
        """
        CREATE TABLE thread_comments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            thread_id uuid NOT NULL,
            author_user_id uuid NOT NULL REFERENCES users (id),
            author_side text NOT NULL CHECK (author_side IN ('firm', 'client')),
            body_sealed bytea NOT NULL,
            body_fingerprint text NOT NULL CHECK (body_fingerprint ~ '^[0-9a-f]{64}$'),
            corrects_comment_id uuid NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{}'
                CHECK (cardinality(citation_ids) <= 20),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, thread_id, id),
            FOREIGN KEY (tenant_id, engagement_id, thread_id)
                REFERENCES comment_threads (tenant_id, engagement_id, id),
            -- A correction stays in the thread it corrects.
            FOREIGN KEY (tenant_id, thread_id, corrects_comment_id)
                REFERENCES thread_comments (tenant_id, thread_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX thread_comments_thread ON thread_comments (tenant_id, thread_id, created_at)"
    )
    # A client author only on a shared thread: a CHECK cannot read the thread row (0048's rule,
    # `comments_client_shared`, as a trigger).
    op.execute(
        """
        CREATE FUNCTION thread_comments_client_shared() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.author_side = 'client' AND NOT EXISTS (
                SELECT 1 FROM comment_threads t
                 WHERE t.tenant_id = NEW.tenant_id AND t.id = NEW.thread_id
                   AND t.visibility = 'shared'
            ) THEN
                RAISE EXCEPTION 'a client comments only on a shared thread'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION thread_comments_client_shared() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER thread_comments_client_shared BEFORE INSERT ON thread_comments "
        "FOR EACH ROW EXECUTE FUNCTION thread_comments_client_shared()"
    )
    op.execute(
        """
        CREATE TABLE thread_comment_mentions (
            tenant_id uuid NOT NULL,
            comment_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            via_team boolean NOT NULL DEFAULT false,
            PRIMARY KEY (tenant_id, comment_id, user_id),
            FOREIGN KEY (tenant_id, comment_id) REFERENCES thread_comments (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE thread_comment_redactions (
            tenant_id uuid NOT NULL,
            comment_id uuid NOT NULL,
            redacted_by uuid NOT NULL REFERENCES users (id),
            reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, comment_id),
            FOREIGN KEY (tenant_id, comment_id) REFERENCES thread_comments (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE comment_thread_reads (
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL REFERENCES users (id),
            thread_id uuid NOT NULL,
            last_read_at timestamptz NULL,
            muted_at timestamptz NULL,
            UNIQUE (tenant_id, user_id, thread_id),
            FOREIGN KEY (tenant_id, thread_id) REFERENCES comment_threads (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE todos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            scope_kind text NOT NULL CHECK (scope_kind IN ('engagement', 'firm')),
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            client_id uuid NULL,
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
            -- People only: the agent principal is not a user row (AC-19).
            assignee_user_id uuid NOT NULL REFERENCES users (id),
            due_on date NULL,
            anchor_kind text NULL CHECK (anchor_kind IS NULL OR ({_ANCHOR_KIND})),
            anchor_id uuid NULL,
            anchor_locator jsonb NULL
                CHECK (anchor_locator IS NULL OR octet_length(anchor_locator::text) <= 2048),
            row_text_sealed bytea NULL,
            row_text_fingerprint text NULL CHECK (row_text_fingerprint ~ '^[0-9a-f]{{64}}$'),
            source_thread_id uuid NULL,
            created_by uuid NOT NULL REFERENCES users (id),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            done_by uuid NULL REFERENCES users (id),
            done_at timestamptz NULL,
            assignee_seen_at timestamptz NULL,
            deleted_at timestamptz NULL,
            deleted_by uuid NULL REFERENCES users (id),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT todos_done CHECK (
                (status = 'done') = (done_at IS NOT NULL AND done_by IS NOT NULL)
            ),
            CONSTRAINT todos_scope CHECK (
                (scope_kind = 'engagement') = (engagement_id IS NOT NULL)
            ),
            CONSTRAINT todos_anchor CHECK ((anchor_kind IS NULL) = (anchor_id IS NULL)),
            CONSTRAINT todos_row_text CHECK (
                (row_text_sealed IS NULL) = (row_text_fingerprint IS NULL)
            ),
            CONSTRAINT todos_deleted CHECK ((deleted_at IS NULL) = (deleted_by IS NULL)),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, source_thread_id) REFERENCES comment_threads (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX todos_mine ON todos (tenant_id, assignee_user_id, status, due_on) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX todos_anchor ON todos (tenant_id, anchor_kind, anchor_id) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        """
        CREATE TABLE todo_checklist_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            todo_id uuid NOT NULL,
            position integer NOT NULL CHECK (position BETWEEN 1 AND 8),
            text text NOT NULL CHECK (length(text) BETWEEN 1 AND 200),
            done boolean NOT NULL DEFAULT false,
            done_by uuid NULL REFERENCES users (id),
            done_at timestamptz NULL,
            CONSTRAINT todo_checklist_items_done CHECK (
                done = (done_at IS NOT NULL AND done_by IS NOT NULL)
            ),
            CONSTRAINT todo_checklist_items_position
                UNIQUE (tenant_id, todo_id, position) DEFERRABLE INITIALLY IMMEDIATE,
            FOREIGN KEY (tenant_id, todo_id) REFERENCES todos (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION collaboration_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: comments, mentions, redactions and thread events '
                'never change (ADR-236)' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION collaboration_rows_immutable() FROM PUBLIC")
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table in IMMUTABLE:
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION collaboration_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION collaboration_rows_immutable()"
        )
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    # Threads and reads are never deleted; to-dos are soft-deleted only. Checklist items are a
    # mutable sub-list (P-05 §4.2), so they keep DELETE.
    for table in ("comment_threads", "comment_thread_reads", "todos"):
        op.execute(f"REVOKE DELETE ON {table} FROM abacus_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION collaboration_rows_immutable()")
    op.execute("DROP FUNCTION thread_comments_client_shared()")
