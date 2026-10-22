"""Agent suggestions and proposals (P-04-T05; ADR-161), owned by `agents`.

- `suggestions`: one proposed field value from an agent run. Its decisions are in
  `suggestion_decisions`, which is insert-only and human-only.
- `proposals`: an agent's change set, made of `proposal_rows` (insert-only). Its decisions are
  in `proposal_decisions`, which is insert-only and human-only.
- Undo (DEC-24): an `undone` decision names the decision it undoes. A trigger refuses it unless
  that decision is on the same subject, is not itself an undo, and is at most 10 seconds old in
  business time (`abacus_now()`, the same clock that stamped it). Undo by someone other than the
  decider is refused in the service. The approval-grant half ("and its grant is unconsumed")
  arrives with `approval_grants` (P-04-T10). Until then no decision carries a grant.

Revision ID: 0095
Revises: 0094
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0095"
down_revision = "0094"
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
_TABLES = (
    "suggestions",
    "suggestion_decisions",
    "proposals",
    "proposal_rows",
    "proposal_decisions",
)
_INSERT_ONLY = ("suggestion_decisions", "proposal_rows", "proposal_decisions")
# DEC-24 / ADR-161: Undo within 10 seconds of the decision it undoes, on the same subject, never
# an undo of an undo, and one undo per decision. Instantiated for both decision tables.
_UNDO_WINDOW = """
CREATE FUNCTION __TABLE___undo_window() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_original record;
BEGIN
    IF NEW.decision <> 'undone' THEN
        RETURN NEW;
    END IF;
    SELECT d.__SUBJECT__ AS subject, d.decision, d.created_at INTO v_original
      FROM __TABLE__ d
     WHERE d.tenant_id = NEW.tenant_id AND d.id = NEW.undoes_decision_id;
    IF v_original IS NULL OR v_original.subject <> NEW.__SUBJECT__
       OR v_original.decision = 'undone'
       OR abacus_now() - v_original.created_at > interval '10 seconds'
       OR EXISTS (SELECT 1 FROM __TABLE__ u
                   WHERE u.tenant_id = NEW.tenant_id
                     AND u.undoes_decision_id = NEW.undoes_decision_id) THEN
        RAISE EXCEPTION 'undo_window_closed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE suggestions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            target_type text NOT NULL CHECK (target_type ~ '^[a-z][a-z_]{0,39}$'),
            target_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key ~ '^[A-Za-z0-9_.!:-]{1,80}$'),
            proposed_value jsonb NOT NULL CHECK (jsonb_typeof(proposed_value) = 'object'),
            rationale_ref text NULL CHECK (length(rationale_ref) BETWEEN 1 AND 200),
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            confidence numeric(4, 3) NULL CHECK (confidence BETWEEN 0 AND 1),
            agent_run_id uuid NOT NULL,
            proposal_id uuid NULL,
            status text NOT NULL DEFAULT 'pending' CHECK (status IN
                ('pending', 'adopted', 'edited', 'dismissed', 'superseded', 'expired')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX suggestions_by_target ON suggestions "
        "(tenant_id, target_type, target_id, field_key, status)"
    )
    op.execute(
        f"""
        CREATE TABLE suggestion_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            suggestion_id uuid NOT NULL,
            decision text NOT NULL
                CHECK (decision IN ('adopted', 'edited', 'dismissed', 'undone')),
            edited_value jsonb NULL
                CHECK (edited_value IS NULL OR jsonb_typeof(edited_value) = 'object'),
            citation_note_sealed bytea NULL CHECK (octet_length(citation_note_sealed) <= 65536),
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z_]{{0,39}}$'),
            undoes_decision_id uuid NULL,
            decided_by uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT suggestion_decisions_human_only {_HUMAN},
            CONSTRAINT suggestion_decisions_undo_names_its_decision
                CHECK ((decision = 'undone') = (undoes_decision_id IS NOT NULL)),
            CONSTRAINT suggestion_decisions_edits_carry_a_value
                CHECK (decision <> 'edited' OR edited_value IS NOT NULL),
            FOREIGN KEY (tenant_id, suggestion_id) REFERENCES suggestions (tenant_id, id),
            FOREIGN KEY (tenant_id, undoes_decision_id)
                REFERENCES suggestion_decisions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE proposals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z][a-z_]{0,39}$'),
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
            reasoning_ref text NULL CHECK (length(reasoning_ref) BETWEEN 1 AND 200),
            policy_eval jsonb NULL
                CHECK (policy_eval IS NULL OR jsonb_typeof(policy_eval) = 'object'),
            routed_to_user_id uuid NULL,
            set_ref jsonb NULL CHECK (set_ref IS NULL OR jsonb_typeof(set_ref) = 'object'),
            checkpoint_id uuid NULL,
            state text NOT NULL DEFAULT 'pending' CHECK (state IN
                ('pending', 'approved', 'approved_with_edits', 'rejected', 'superseded')),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            agent_run_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute("CREATE INDEX proposals_routed ON proposals (tenant_id, routed_to_user_id, state)")
    op.execute(
        """
        CREATE TABLE proposal_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            proposal_id uuid NOT NULL,
            n integer NOT NULL CHECK (n >= 1),
            suggestion_id uuid NULL,
            field_ref jsonb NOT NULL CHECK (jsonb_typeof(field_ref) = 'object'),
            label text NOT NULL CHECK (length(label) BETWEEN 1 AND 200),
            before jsonb NULL,
            after jsonb NULL,
            cause text NOT NULL CHECK (cause ~ '^[a-z][a-z_]{0,39}$'),
            citation_ids uuid[] NOT NULL DEFAULT '{}',
            unsupported boolean NOT NULL DEFAULT false,
            UNIQUE (tenant_id, proposal_id, n),
            FOREIGN KEY (tenant_id, proposal_id) REFERENCES proposals (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE proposal_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            proposal_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'approved_with_edits',
                'rejected', 'routed', 'follow_up', 'undone')),
            reason_code text NULL CHECK (reason_code IN
                ('wrong_treatment', 'unsupported_value', 'needs_client_input', 'other')),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            edits jsonb NULL CHECK (edits IS NULL OR jsonb_typeof(edits) = 'array'),
            seen_version integer NOT NULL CHECK (seen_version >= 1),
            routed_to_user_id uuid NULL,
            undoes_decision_id uuid NULL,
            approval_grant_id uuid NULL,
            decided_by uuid NOT NULL,
            {_ACTOR},
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            CONSTRAINT proposal_decisions_human_only {_HUMAN},
            CONSTRAINT proposal_decisions_undo_names_its_decision
                CHECK ((decision = 'undone') = (undoes_decision_id IS NOT NULL)),
            CONSTRAINT proposal_decisions_rejections_have_a_reason
                CHECK (decision <> 'rejected' OR reason_code IS NOT NULL),
            CONSTRAINT proposal_decisions_routing_names_a_person
                CHECK (decision <> 'routed' OR routed_to_user_id IS NOT NULL),
            FOREIGN KEY (tenant_id, proposal_id) REFERENCES proposals (tenant_id, id),
            FOREIGN KEY (tenant_id, undoes_decision_id)
                REFERENCES proposal_decisions (tenant_id, id)
        )
        """
    )

    # DEC-24 / ADR-161: Undo within 10 seconds of the decision it undoes, on the same subject,
    # never an undo of an undo, and only one undo per decision.
    for table, subject in (
        ("suggestion_decisions", "suggestion_id"),
        ("proposal_decisions", "proposal_id"),
    ):
        op.execute(_UNDO_WINDOW.replace("__TABLE__", table).replace("__SUBJECT__", subject))
        op.execute(
            f"CREATE TRIGGER {table}_undo_window BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {table}_undo_window()"
        )

    op.execute(
        """
        CREATE FUNCTION agent_decisions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION agent_decisions_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION agent_decisions_immutable()"
        )

    insert_columns(
        op,
        "suggestions",
        (
            "tenant_id",
            "engagement_id",
            "target_type",
            "target_id",
            "field_key",
            "proposed_value",
            "rationale_ref",
            "citation_ids",
            "confidence",
            "agent_run_id",
            "proposal_id",
        ),
    )
    op.execute("GRANT UPDATE (status, version) ON suggestions TO abacus_app")
    insert_columns(
        op,
        "suggestion_decisions",
        (
            "tenant_id",
            "suggestion_id",
            "decision",
            "edited_value",
            "citation_note_sealed",
            "reason_code",
            "undoes_decision_id",
            "decided_by",
        ),
    )
    insert_columns(
        op,
        "proposals",
        (
            "tenant_id",
            "engagement_id",
            "kind",
            "title",
            "reasoning_ref",
            "policy_eval",
            "routed_to_user_id",
            "set_ref",
            "checkpoint_id",
            "agent_run_id",
        ),
    )
    op.execute("GRANT UPDATE (state, routed_to_user_id, version) ON proposals TO abacus_app")
    insert_columns(
        op,
        "proposal_rows",
        (
            "tenant_id",
            "proposal_id",
            "n",
            "suggestion_id",
            "field_ref",
            "label",
            "before",
            "after",
            "cause",
            "citation_ids",
            "unsupported",
        ),
    )
    insert_columns(
        op,
        "proposal_decisions",
        (
            "tenant_id",
            "proposal_id",
            "decision",
            "reason_code",
            "note_sealed",
            "edits",
            "seen_version",
            "routed_to_user_id",
            "undoes_decision_id",
            "approval_grant_id",
            "decided_by",
        ),
    )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION agent_decisions_immutable()")
    op.execute("DROP FUNCTION proposal_decisions_undo_window()")
    op.execute("DROP FUNCTION suggestion_decisions_undo_window()")
