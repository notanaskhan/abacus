"""The human-only guard (Q-02-T17; I-AGENT-NEVER at the data layer; ADR-005).

`abacus_human_only_actions()` returns the audit actions listed in
`docs/architecture/human-only-actions.yaml` when this migration was written. A BEFORE INSERT
trigger on `audit_events` refuses any of them written by an `agent` or `policy` actor, before
commit, whatever the permission matrix says. A drift test holds this function, the YAML and the
generated `kernel._human_only_actions` together: changing the list needs a new migration that
redefines the function.

Revision ID: 0097
Revises: 0096
"""

from __future__ import annotations

from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None

_ACTIONS = """ARRAY[
        'engagement.accepted',
        'evidence.accepted',
        'firm.ai_client_data_opted_in',
        'firm_export.approved',
        'going_concern.decided',
        'guidance_draft.approved',
        'independence.confirmed',
        'legal_hold.placed',
        'materiality.decided',
        'procedure.concluded',
        'report.approved',
        'report.released',
        'review.decided',
        'review.released',
        'risk.approved',
        'sample.approved',
        'sign_off.recorded',
        'statement.approved'
    ]::text[]"""


def upgrade() -> None:
    op.execute(
        "CREATE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT {_ACTIONS} $$"
    )
    op.execute(
        """
        CREATE FUNCTION audit_events_human_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.actor_kind IN ('agent', 'policy')
               AND NEW.action = ANY(abacus_human_only_actions()) THEN
                RAISE EXCEPTION 'human_only_action'
                    USING ERRCODE = 'insufficient_privilege',
                          DETAIL = 'I-AGENT-NEVER: a person must take this action';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_human_only BEFORE INSERT ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_human_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_events_human_only ON audit_events")
    op.execute("DROP FUNCTION audit_events_human_only()")
    op.execute("DROP FUNCTION abacus_human_only_actions()")
