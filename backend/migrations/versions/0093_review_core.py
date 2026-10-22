"""The review grammar's core (P-04-T03; ADR-160, ADR-161; DEC-134).

`sign_offs` (0072, SPEC-308) and `reviewable_notes` with `reviewable_note_events` (0076, SPEC-313)
already hold live rows and code. They are extended in place rather than renamed (DEC-134):

- `sign_offs` gains:
  - `kind` (`ladder`, `field_tick` or `final_approval`) and `work_item_id`;
  - what was true at signing: `initials`, `engagement_role_at_sign`, `function_at_sign`,
    `version_no` and `statement_version`;
  - `adopted_run_id`, `independence_checked_at` and `bulk_request_id`;
  - `actor_kind` and `actor_id`, defaulting to the transaction's actor. A human-only CHECK binds
    new rows to the `app.actor_*` settings (INV-1). It is NOT VALID for the SPEC-308 rows, which
    are backfilled as human and their signer.

  `level` stays 1 to 5: L1 preparer, L2 reviewer, L3 manager, L4 partner, L5 EQR. There is no
  stale column: staleness is `content_hash` ≠ the target's hash.
- `reviewable_notes` gains `status` (`open`, `responded`, `cleared`, `closed` or `withdrawn`),
  `assignee_user_id`, `anchor_ref` (cell, field key or region) and `body_sealed`.
- `reviewable_note_events` gains `raised`, `closed` and `withdrawn`, plus `actor_kind`. A
  `cleared` event must be a human's.
- New `field_value_versions`: insert-only, with no UPDATE or DELETE for any role. The
  `fvv_policy_dormant` CHECK keeps the `policy` value source and actor locked off until an
  accepted ADR P-08 (DEC-53), and a human edit needs a sealed citation note.
- New `human_gates`: the rebuildable projection Home reads (DF-25 kinds), idempotent on
  `source_event_id`. Only the projector writes it.

Revision ID: 0093
Revises: 0092
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None

_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind IN ('human', 'agent', 'system', 'policy'))"
)
_SIGN_OFF_COLUMNS = (
    "tenant_id",
    "engagement_id",
    "target_type",
    "target_id",
    "level",
    "content_hash",
    "signed_by",
    "kind",
    "work_item_id",
    "initials",
    "engagement_role_at_sign",
    "function_at_sign",
    "version_no",
    "statement_version",
    "adopted_run_id",
    "independence_checked_at",
    "bulk_request_id",
)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE sign_offs
            ADD COLUMN kind text NOT NULL DEFAULT 'ladder'
                CHECK (kind IN ('ladder', 'field_tick', 'final_approval')),
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN initials text NULL CHECK (initials ~ '^[A-Z]{{1,4}}$'),
            ADD COLUMN engagement_role_at_sign text NULL
                CHECK (engagement_role_at_sign ~ '^[a-z][a-z_]{{0,39}}$'),
            ADD COLUMN function_at_sign text NULL
                CHECK (function_at_sign ~ '^[a-z][a-z_]{{0,39}}$'),
            ADD COLUMN version_no integer NULL CHECK (version_no >= 1),
            ADD COLUMN statement_version text NULL CHECK (length(statement_version) <= 40),
            ADD COLUMN adopted_run_id uuid NULL,
            ADD COLUMN independence_checked_at timestamptz NULL,
            ADD COLUMN bulk_request_id uuid NULL,
            ADD COLUMN {_ACTOR},
            ADD COLUMN actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            ADD CONSTRAINT sign_offs_field_ticks_are_l1_l2
                CHECK (kind <> 'field_tick' OR level IN (1, 2))
        """
    )
    # Sign-offs are a person's (INV-1): bound to the transaction's actor. NOT VALID: SPEC-308
    # rows predate the actor columns and are backfilled as their signer.
    op.execute(
        "UPDATE sign_offs SET actor_kind = 'human', actor_id = signed_by::text "
        "WHERE actor_kind IS DISTINCT FROM 'human' OR actor_id IS NULL"
    )
    op.execute(
        "ALTER TABLE sign_offs ADD CONSTRAINT sign_offs_human_only CHECK ("
        "actor_kind = 'human' "
        "AND actor_kind = current_setting('app.actor_kind', true) "
        "AND actor_id = current_setting('app.actor_id', true)) NOT VALID"
    )
    op.execute(
        "CREATE INDEX sign_offs_by_target_time ON sign_offs "
        "(tenant_id, target_type, target_id, level, created_at)"
    )
    insert_columns(op, "sign_offs", _SIGN_OFF_COLUMNS)

    op.execute(
        """
        ALTER TABLE reviewable_notes
            ADD COLUMN status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'responded', 'cleared', 'closed', 'withdrawn')),
            ADD COLUMN assignee_user_id uuid NULL,
            ADD COLUMN anchor_ref jsonb NULL
                CHECK (anchor_ref IS NULL OR jsonb_typeof(anchor_ref) = 'object'),
            ADD COLUMN body_sealed bytea NULL CHECK (octet_length(body_sealed) <= 65536)
        """
    )
    # The status is the latest event's; backfill it from the SPEC-313 events.
    op.execute(
        """
        UPDATE reviewable_notes n SET status = CASE e.kind
            WHEN 'cleared' THEN 'cleared' WHEN 'responded' THEN 'responded' ELSE 'open' END
        FROM (
            SELECT DISTINCT ON (note_id) note_id, kind FROM reviewable_note_events
             ORDER BY note_id, created_at DESC, id DESC
        ) e
        WHERE e.note_id = n.id
        """
    )
    insert_columns(
        op,
        "reviewable_notes",
        (
            "tenant_id",
            "engagement_id",
            "target_type",
            "target_id",
            "anchor",
            "body",
            "raised_by",
            "assignee_user_id",
            "anchor_ref",
            "body_sealed",
        ),
    )
    op.execute("GRANT UPDATE (status, assignee_user_id) ON reviewable_notes TO abacus_app")
    op.execute(
        "ALTER TABLE reviewable_note_events DROP CONSTRAINT reviewable_note_events_kind_check"
    )
    op.execute(
        f"""
        ALTER TABLE reviewable_note_events
            ADD CONSTRAINT reviewable_note_events_kind_check CHECK (kind IN
                ('raised', 'responded', 'cleared', 'closed', 'withdrawn', 'reopened')),
            ADD COLUMN {_ACTOR},
            ADD CONSTRAINT reviewable_note_events_cleared_by_a_person
                CHECK (kind <> 'cleared' OR actor_kind = 'human') NOT VALID
        """
    )
    op.execute("UPDATE reviewable_note_events SET actor_kind = 'human'")
    op.execute(
        "ALTER TABLE reviewable_note_events "
        "VALIDATE CONSTRAINT reviewable_note_events_cleared_by_a_person"
    )

    op.execute(
        f"""
        CREATE TABLE field_value_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            target_type text NOT NULL CHECK (target_type ~ '^[a-z][a-z_]{{0,39}}$'),
            target_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[A-Za-z0-9_.!:-]{{1,80}}$'),
            seq integer NOT NULL CHECK (seq >= 1),
            value jsonb NOT NULL CHECK (jsonb_typeof(value) = 'object' AND value ? 't'),
            value_kind text NOT NULL CHECK (value_kind IN ('exact', 'estimate')),
            value_source text NOT NULL CHECK (value_source IN
                ('agent_suggested', 'human', 'formula', 'tb_linked', 'engine_import', 'policy')),
            cause text NOT NULL CHECK (cause IN ('edit', 'suggestion_adopted', 'recompute',
                'import', 'restore', 'template_update', 'relink')),
            {_ACTOR},
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            on_behalf_of_user_id uuid NULL,
            suggestion_id uuid NULL,
            checkpoint_id uuid NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            citation_note_sealed bytea NULL CHECK (octet_length(citation_note_sealed) <= 65536),
            issue_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, target_type, target_id, field_key, seq),
            CONSTRAINT fvv_policy_dormant
                CHECK (value_source <> 'policy' AND actor_kind <> 'policy'),
            CONSTRAINT fvv_human_edits_cite
                CHECK (value_source <> 'human' OR citation_note_sealed IS NOT NULL),
            CONSTRAINT fvv_actor_is_transaction_actor CHECK (
                actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)
            ),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    tenant_table(op, "field_value_versions")
    op.execute("REVOKE UPDATE, DELETE ON field_value_versions FROM abacus_app")
    insert_columns(
        op,
        "field_value_versions",
        (
            "tenant_id",
            "engagement_id",
            "target_type",
            "target_id",
            "field_key",
            "seq",
            "value",
            "value_kind",
            "value_source",
            "cause",
            "on_behalf_of_user_id",
            "suggestion_id",
            "checkpoint_id",
            "citation_ids",
            "citation_note_sealed",
            "issue_id",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION field_value_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'field value versions are insert-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER field_value_versions_immutable BEFORE UPDATE OR DELETE "
        "ON field_value_versions FOR EACH ROW EXECUTE FUNCTION field_value_versions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER field_value_versions_no_truncate BEFORE TRUNCATE "
        "ON field_value_versions FOR EACH STATEMENT "
        "EXECUTE FUNCTION field_value_versions_immutable()"
    )

    op.execute(
        """
        CREATE TABLE human_gates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('decision', 'sign_off_request', 'proposal', 'send',
                'final_approval', 'export', 'release')),
            subject_ref jsonb NOT NULL CHECK (jsonb_typeof(subject_ref) = 'object'),
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            client_id uuid NULL,
            assignee_user_id uuid NULL,
            role text NULL CHECK (role ~ '^[a-z][a-z_]{0,39}$'),
            due_on date NULL,
            state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'done', 'voided')),
            source_event_id uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            CONSTRAINT human_gates_once UNIQUE (tenant_id, source_event_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX human_gates_open ON human_gates (tenant_id, assignee_user_id, state, due_on)"
    )
    tenant_table(op, "human_gates")
    op.execute("REVOKE UPDATE, DELETE ON human_gates FROM abacus_app")
    insert_columns(
        op,
        "human_gates",
        (
            "tenant_id",
            "kind",
            "subject_ref",
            "engagement_id",
            "work_item_id",
            "client_id",
            "assignee_user_id",
            "role",
            "due_on",
            "state",
            "source_event_id",
        ),
    )
    op.execute(
        "GRANT UPDATE (state, assignee_user_id, due_on, updated_at) ON human_gates TO abacus_app"
    )


def downgrade() -> None:
    op.execute("DROP TABLE human_gates")
    op.execute("DROP TABLE field_value_versions")
    op.execute("DROP FUNCTION field_value_versions_immutable()")
    op.execute(
        "ALTER TABLE reviewable_note_events "
        "DROP CONSTRAINT reviewable_note_events_cleared_by_a_person, DROP COLUMN actor_kind, "
        "DROP CONSTRAINT reviewable_note_events_kind_check"
    )
    op.execute(
        "DELETE FROM reviewable_note_events WHERE kind NOT IN ('responded', 'cleared', 'reopened')"
    )
    op.execute(
        "ALTER TABLE reviewable_note_events ADD CONSTRAINT reviewable_note_events_kind_check "
        "CHECK (kind IN ('responded', 'cleared', 'reopened'))"
    )
    op.execute("REVOKE UPDATE (status, assignee_user_id) ON reviewable_notes FROM abacus_app")
    insert_columns(
        op,
        "reviewable_notes",
        ("tenant_id", "engagement_id", "target_type", "target_id", "anchor", "body", "raised_by"),
    )
    op.execute(
        "ALTER TABLE reviewable_notes DROP COLUMN body_sealed, DROP COLUMN anchor_ref, "
        "DROP COLUMN assignee_user_id, DROP COLUMN status"
    )
    insert_columns(op, "sign_offs", _SIGN_OFF_COLUMNS[:7])
    op.execute("DROP INDEX sign_offs_by_target_time")
    op.execute(
        "ALTER TABLE sign_offs DROP CONSTRAINT sign_offs_human_only, "
        "DROP CONSTRAINT sign_offs_field_ticks_are_l1_l2, "
        "DROP COLUMN actor_id, DROP COLUMN actor_kind, DROP COLUMN bulk_request_id, "
        "DROP COLUMN independence_checked_at, DROP COLUMN adopted_run_id, "
        "DROP COLUMN statement_version, DROP COLUMN version_no, DROP COLUMN function_at_sign, "
        "DROP COLUMN engagement_role_at_sign, DROP COLUMN initials, DROP COLUMN work_item_id, "
        "DROP COLUMN kind"
    )
