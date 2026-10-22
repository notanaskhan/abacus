"""Approval grants (P-04-T10; ADR-126, ADR-161; DEC-24), owned by `identity`.

An approval grant holds an external effect of a human decision (a client-visible notice, a send)
until a named approver's grant is consumed at delivery. It is single use. It can't be consumed
before `not_before` or after `expires_at`, and it can't be consumed once voided (an Undo). It is
bound to the SHA-256 of the effect's payload, and to a consumer reference, so a retried delivery of
the same effect stays consumed while any other is refused.

- The app inserts the issue columns and may update only `used_at`, `consumer_ref` and
  `voided_at`. A trigger refuses any other change, and any change once a grant is used or voided.
- Business time (`abacus_now()`) stamps and compares, as the Undo window does.
- The Undo trigger on `proposal_decisions` gains its grant half (0095 left it for this
  migration): an undo is refused once the undone decision's grant has been consumed.

Revision ID: 0102
Revises: 0101
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None

_INSERT = (
    "tenant_id",
    "subject_type",
    "subject_id",
    "action",
    "approver_user_id",
    "engagement_id",
    "work_item_id",
    "payload_sha256",
    "not_before",
    "expires_at",
)
# 0095's Undo window for `proposal_decisions`, with and without the grant half.
_UNDO = """
CREATE OR REPLACE FUNCTION proposal_decisions_undo_window() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_original record;
BEGIN
    IF NEW.decision <> 'undone' THEN
        RETURN NEW;
    END IF;
    SELECT d.proposal_id AS subject, d.decision, d.created_at, d.approval_grant_id
      INTO v_original
      FROM proposal_decisions d
     WHERE d.tenant_id = NEW.tenant_id AND d.id = NEW.undoes_decision_id;
    IF v_original IS NULL OR v_original.subject <> NEW.proposal_id
       OR v_original.decision = 'undone'
       OR abacus_now() - v_original.created_at > interval '10 seconds'
       OR EXISTS (SELECT 1 FROM proposal_decisions u
                   WHERE u.tenant_id = NEW.tenant_id
                     AND u.undoes_decision_id = NEW.undoes_decision_id)
       __GRANT__ THEN
        RAISE EXCEPTION 'undo_window_closed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$
"""
_GRANT_HALF = """OR EXISTS (SELECT 1 FROM approval_grants g
                   WHERE g.tenant_id = NEW.tenant_id
                     AND g.id = v_original.approval_grant_id
                     AND g.used_at IS NOT NULL)"""


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE approval_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            subject_type text NOT NULL CHECK (subject_type ~ '^[a-z][a-z_]{0,39}$'),
            subject_id uuid NOT NULL,
            action text NOT NULL CHECK (action ~ '^[a-z][a-z_]{0,59}\\.[a-z][a-z_]{0,59}$'),
            approver_user_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
            not_before timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            used_at timestamptz NULL,
            consumer_ref uuid NULL,
            voided_at timestamptz NULL,
            CHECK (expires_at > not_before),
            CHECK ((used_at IS NULL) = (consumer_ref IS NULL)),
            CHECK (used_at IS NULL OR voided_at IS NULL),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX approval_grants_by_subject ON approval_grants "
        "(tenant_id, subject_type, subject_id)"
    )
    op.execute(
        """
        CREATE FUNCTION approval_grants_settle_once() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.used_at IS NOT NULL OR OLD.voided_at IS NOT NULL THEN
                RAISE EXCEPTION 'approval grant already settled'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF (NEW.id, NEW.tenant_id, NEW.subject_type, NEW.subject_id, NEW.action,
                NEW.approver_user_id, NEW.engagement_id, NEW.work_item_id, NEW.payload_sha256,
                NEW.not_before, NEW.expires_at, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.tenant_id, OLD.subject_type, OLD.subject_id, OLD.action,
                OLD.approver_user_id, OLD.engagement_id, OLD.work_item_id, OLD.payload_sha256,
                OLD.not_before, OLD.expires_at, OLD.created_at) THEN
                RAISE EXCEPTION 'an approval grant changes only when it is used or voided'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER approval_grants_settle_once BEFORE UPDATE ON approval_grants "
        "FOR EACH ROW EXECUTE FUNCTION approval_grants_settle_once()"
    )
    tenant_table(op, "approval_grants")
    op.execute("REVOKE UPDATE, DELETE ON approval_grants FROM abacus_app")
    insert_columns(op, "approval_grants", _INSERT)
    op.execute("GRANT UPDATE (used_at, consumer_ref, voided_at) ON approval_grants TO abacus_app")
    op.execute(_UNDO.replace("__GRANT__", _GRANT_HALF))


def downgrade() -> None:
    op.execute(_UNDO.replace("__GRANT__", ""))
    op.execute("DROP TABLE approval_grants")
    op.execute("DROP FUNCTION approval_grants_settle_once()")
