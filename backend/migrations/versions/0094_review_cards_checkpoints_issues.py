"""Decision cards, checkpoints and issues (P-04-T04; ADR-160, ADR-161).

- `decision_cards`: one question reserved to a role. A new card version supersedes the last.
- `decisions`: one per card, insert-only and human-only. The sealed rationale is required and the
  actor must be the transaction's (INV-1).
- `checkpoints`: saved states of a target. "Current" is a derived tag, never a status.
  - `checkpoint_diffs` (insert-only): code-computed field changes.
  - `checkpoint_decisions` (insert-only, human-only).
- `issues`: one cross-module issue service.
  - `issue_events` (insert-only): resolution events (resolved, verified, marked not applicable)
    must be a human's.
  - `issue_links`: what an issue points at.
  - Dedupe on `(tenant, work_item, source_ref)`.

Rows hold identifiers, codes and sealed bodies only.

Revision ID: 0094
Revises: 0093
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None

_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_HUMAN = (
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_TRANSACTION_ACTOR = (
    "CHECK (actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_INSERT_ONLY = ("decisions", "checkpoint_diffs", "checkpoint_decisions", "issue_events")


def _immutable(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION review_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION review_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION review_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE decision_cards (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z][a-z_]{0,39}$'),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            question_key text NOT NULL CHECK (question_key ~ '^[a-z][a-z0-9_.]{0,79}$'),
            reserved_role text NOT NULL
                CHECK (reserved_role IN
                    ('engagement_partner', 'manager', 'eqr_reviewer', 'signer')),
            reserved_user_id uuid NULL,
            options jsonb NOT NULL CHECK (jsonb_typeof(options) = 'array'),
            context jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(context) = 'array'),
            factors jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(factors) = 'array'),
            recommendation_suggestion_id uuid NULL,
            blocking_refs jsonb NOT NULL DEFAULT '[]'
                CHECK (jsonb_typeof(blocking_refs) = 'array'),
            status text NOT NULL DEFAULT 'awaiting_role'
                CHECK (status IN ('awaiting_role', 'decided', 'superseded')),
            supersedes_id uuid NULL,
            raised_by_kind text NOT NULL CHECK (raised_by_kind IN ('human', 'agent', 'system')),
            raised_by_id text NOT NULL,
            run_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES decision_cards (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX decision_cards_open ON decision_cards (tenant_id, engagement_id, status)"
    )
    op.execute(
        f"""
        CREATE TABLE decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            card_id uuid NOT NULL,
            option_key text NOT NULL CHECK (option_key ~ '^[a-z][a-z0-9_]{{0,39}}$'),
            rationale_sealed bytea NOT NULL
                CHECK (octet_length(rationale_sealed) BETWEEN 1 AND 65536),
            factors jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(factors) = 'array'),
            seen_card_version integer NOT NULL CHECK (seen_card_version >= 1),
            decided_by uuid NOT NULL,
            mfa_at timestamptz NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT decisions_one_per_card UNIQUE (tenant_id, card_id),
            CONSTRAINT decisions_human_only {_HUMAN},
            FOREIGN KEY (tenant_id, card_id) REFERENCES decision_cards (tenant_id, id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE checkpoints (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            target_type text NOT NULL CHECK (target_type ~ '^[a-z][a-z_]{0,39}$'),
            target_id uuid NOT NULL,
            seq integer NOT NULL CHECK (seq >= 1),
            name text NULL CHECK (length(name) BETWEEN 1 AND 120),
            starred boolean NOT NULL DEFAULT false,
            author_kind text NOT NULL CHECK (author_kind IN ('agent', 'person', 'import')),
            author_ref text NOT NULL CHECK (length(author_ref) BETWEEN 1 AND 200),
            cause text NOT NULL CHECK (cause IN ('agent_run', 'engine_import', 'human_edit',
                'restore', 'amendment', 'manual_save')),
            status text NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected', 'saved')),
            proposal_id uuid NULL,
            restored_from_id uuid NULL,
            engine_sync_event_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            run_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, target_type, target_id, seq),
            FOREIGN KEY (tenant_id, restored_from_id) REFERENCES checkpoints (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE checkpoint_diffs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            checkpoint_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[A-Za-z0-9_.!:-]{1,80}$'),
            old jsonb NULL,
            new jsonb NULL,
            cause text NOT NULL CHECK (cause ~ '^[a-z][a-z_]{0,39}$'),
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            delta_facts jsonb NULL
                CHECK (delta_facts IS NULL OR jsonb_typeof(delta_facts) = 'object'),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            FOREIGN KEY (tenant_id, checkpoint_id) REFERENCES checkpoints (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE checkpoint_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            checkpoint_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'rejected', 'restored')),
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z_]{{0,39}}$'),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            proposal_decision_id uuid NULL,
            decided_by uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT checkpoint_decisions_human_only {_HUMAN},
            FOREIGN KEY (tenant_id, checkpoint_id) REFERENCES checkpoints (tenant_id, id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE issues (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            record_ref jsonb NOT NULL CHECK (jsonb_typeof(record_ref) = 'object'),
            kind text NOT NULL CHECK (kind IN ('missing_information', 'action_required',
                'review_point', 'waiting_on_client', 'exception', 'engine_diagnostic')),
            priority text NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
            title_sealed bytea NOT NULL CHECK (octet_length(title_sealed) BETWEEN 1 AND 65536),
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress',
                'resolved', 'verified', 'reopened', 'not_applicable', 'under_evaluation',
                'converted_to_misstatement', 'converted_to_deficiency')),
            instructions_required boolean NOT NULL DEFAULT false,
            assignee_user_id uuid NULL,
            assignee_agent boolean NOT NULL DEFAULT false,
            client_contact_id uuid NULL,
            client_wording_sealed bytea NULL CHECK (octet_length(client_wording_sealed) <= 65536),
            internal_note_sealed bytea NULL CHECK (octet_length(internal_note_sealed) <= 65536),
            blocks text[] NOT NULL DEFAULT '{}'
                CHECK (blocks <@ ARRAY['final_approval', 'export', 'release', 'sign_off']::text[]),
            source_ref text NULL CHECK (length(source_ref) BETWEEN 1 AND 200),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX issues_source_once ON issues (tenant_id, work_item_id, source_ref) "
        "WHERE source_ref IS NOT NULL"
    )
    op.execute("CREATE INDEX issues_open ON issues (tenant_id, engagement_id, status)")
    op.execute(
        f"""
        CREATE TABLE issue_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('created', 'assigned', 'status_changed',
                'fix_instructions_set', 'sent_to_client', 'explained', 'resolved', 'verified',
                'reopened', 'marked_not_applicable')),
            fix_instructions_sealed bytea NULL
                CHECK (octet_length(fix_instructions_sealed) <= 65536),
            scope text NULL CHECK (scope IN ('this_issue', 'all_of_class')),
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT issue_events_actor_is_transaction_actor {_TRANSACTION_ACTOR},
            CONSTRAINT issue_events_resolution_by_a_person CHECK (
                event NOT IN ('resolved', 'verified', 'marked_not_applicable')
                OR actor_kind = 'human'
            ),
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE issue_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            issue_id uuid NOT NULL,
            link_kind text NOT NULL CHECK (link_kind IN
                ('cell_range', 'form_field', 'file', 'request_item', 'finding')),
            ref jsonb NOT NULL CHECK (jsonb_typeof(ref) = 'object'),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            FOREIGN KEY (tenant_id, issue_id) REFERENCES issues (tenant_id, id)
        )
        """
    )

    for table in (
        "decision_cards",
        "decisions",
        "checkpoints",
        "checkpoint_diffs",
        "checkpoint_decisions",
        "issues",
        "issue_events",
        "issue_links",
    ):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        _immutable(table)

    insert_columns(
        op,
        "decision_cards",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "kind",
            "version_no",
            "question_key",
            "reserved_role",
            "reserved_user_id",
            "options",
            "context",
            "factors",
            "recommendation_suggestion_id",
            "blocking_refs",
            "supersedes_id",
            "raised_by_kind",
            "raised_by_id",
            "run_id",
        ),
    )
    op.execute("GRANT UPDATE (status) ON decision_cards TO abacus_app")
    insert_columns(
        op,
        "decisions",
        (
            "tenant_id",
            "card_id",
            "option_key",
            "rationale_sealed",
            "factors",
            "seen_card_version",
            "decided_by",
            "mfa_at",
        ),
    )
    insert_columns(
        op,
        "checkpoints",
        (
            "tenant_id",
            "engagement_id",
            "target_type",
            "target_id",
            "seq",
            "name",
            "starred",
            "author_kind",
            "author_ref",
            "cause",
            "status",
            "proposal_id",
            "restored_from_id",
            "engine_sync_event_id",
            "content_hash",
            "run_id",
        ),
    )
    op.execute("GRANT UPDATE (name, starred, status) ON checkpoints TO abacus_app")
    insert_columns(
        op,
        "checkpoint_diffs",
        (
            "tenant_id",
            "checkpoint_id",
            "field_key",
            "old",
            "new",
            "cause",
            "citation_ids",
            "delta_facts",
        ),
    )
    insert_columns(
        op,
        "checkpoint_decisions",
        (
            "tenant_id",
            "checkpoint_id",
            "decision",
            "reason_code",
            "note_sealed",
            "proposal_decision_id",
            "decided_by",
        ),
    )
    insert_columns(
        op,
        "issues",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "record_ref",
            "kind",
            "priority",
            "title_sealed",
            "status",
            "instructions_required",
            "assignee_user_id",
            "assignee_agent",
            "client_contact_id",
            "client_wording_sealed",
            "internal_note_sealed",
            "blocks",
            "source_ref",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, assignee_user_id, assignee_agent, priority, kind, title_sealed, "
        "version) ON issues TO abacus_app"
    )
    insert_columns(
        op, "issue_events", ("tenant_id", "issue_id", "event", "fix_instructions_sealed", "scope")
    )
    insert_columns(op, "issue_links", ("tenant_id", "issue_id", "link_kind", "ref"))


def downgrade() -> None:
    for table in (
        "issue_links",
        "issue_events",
        "issues",
        "checkpoint_decisions",
        "checkpoint_diffs",
        "checkpoints",
        "decisions",
        "decision_cards",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION review_rows_immutable()")
