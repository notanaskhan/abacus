"""A person's rejection of the matcher's proposal (P-04-T25 security review M6; DEC-609).

Rejecting an inbox match through SHL-10 was only an audit event, so the projection stayed pending
and the same match could be rejected again or approved later. `inbox_match_decisions` holds the
verdict: insert-only, human-only (bound to the transaction's actor, as 0095's decision tables),
one per match (a retry is refused), with its reason code and a sealed note. The file itself keeps
waiting in the inbox for a person to sort.

Revision ID: 0232
Revises: 0231
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0232"
down_revision = "0231"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE inbox_match_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            match_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('rejected')),
            reason_code text NOT NULL CHECK (reason_code IN
                ('wrong_treatment', 'unsupported_value', 'needs_client_input', 'other')),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            decided_by uuid NOT NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT inbox_match_decisions_once_per_match UNIQUE (tenant_id, match_id),
            CONSTRAINT inbox_match_decisions_human_only CHECK (
                actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)
            ),
            CONSTRAINT inbox_match_decisions_decider_is_the_actor
                CHECK (decided_by::text = actor_id),
            CONSTRAINT inbox_match_decisions_other_has_a_note
                CHECK (reason_code <> 'other' OR note_sealed IS NOT NULL),
            FOREIGN KEY (tenant_id, match_id) REFERENCES inbox_match_runs (tenant_id, id)
        )
        """
    )
    tenant_table(op, "inbox_match_decisions")
    op.execute("REVOKE UPDATE, DELETE ON inbox_match_decisions FROM abacus_app")
    op.execute(
        "CREATE TRIGGER inbox_match_decisions_immutable BEFORE UPDATE OR DELETE "
        "ON inbox_match_decisions FOR EACH ROW EXECUTE FUNCTION agent_decisions_immutable()"
    )
    op.execute(
        "CREATE TRIGGER inbox_match_decisions_no_truncate BEFORE TRUNCATE "
        "ON inbox_match_decisions FOR EACH STATEMENT EXECUTE FUNCTION agent_decisions_immutable()"
    )
    insert_columns(
        op,
        "inbox_match_decisions",
        ("id", "tenant_id", "match_id", "decision", "reason_code", "note_sealed", "decided_by"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE inbox_match_decisions")
