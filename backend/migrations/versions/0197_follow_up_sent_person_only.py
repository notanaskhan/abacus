"""A follow-up is sent by a person, not by the system either (Q-03-T038; ED-081; DEC-452).

`audit_events_human_only()` (0097) refuses a human-only action written by an `agent` or `policy`
actor. SPEC-319 AC-19 and C5 §12 call `follow_up.sent` human-only in the database, which a
`system` actor could still write (DEC-220 "Open"). This redefines the trigger function so that
`follow_up.sent` is refused from any actor but a person (`human`); every other human-only action
keeps 0097's rule. The scheduled reminder (DEC-74) records its own action
(`follow_up.scheduled_sent`), never `follow_up.sent`. The action list stays
`abacus_human_only_actions()` (0129); the person-only list is inline, so no new function or
grant. `CREATE OR REPLACE` keeps the trigger.

Revision ID: 0197
Revises: 0196
"""

from __future__ import annotations

from alembic import op

revision = "0197"
down_revision = "0196"
branch_labels = None
depends_on = None

_RAISE = """
                RAISE EXCEPTION 'human_only_action'
                    USING ERRCODE = 'insufficient_privilege',
                          DETAIL = 'I-AGENT-NEVER: a person must take this action';"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION audit_events_human_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.action = ANY(abacus_human_only_actions())
               AND (NEW.actor_kind IN ('agent', 'policy')
                    OR (NEW.actor_kind <> 'human'
                        AND NEW.action = ANY(ARRAY['follow_up.sent']::text[]))) THEN{_RAISE}
            END IF;
            RETURN NEW;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION audit_events_human_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.actor_kind IN ('agent', 'policy')
               AND NEW.action = ANY(abacus_human_only_actions()) THEN{_RAISE}
            END IF;
            RETURN NEW;
        END $$
        """
    )
