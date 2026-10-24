"""Follow-ups v2 (P-06-T14; P-06 §4.2 `follow_ups_v2`; DEC-74, DEC-220).

- `follow_up_schedules` gain:
  - `binder_id` (the binder its requests come from, when there is one) and
    `recipient_contact_id` (the client contact, when known);
  - `kind` (`overdue` for the agent's P-4 drafts, `chase` for a person's, `screening_return`
    for an SHL-20 return); rows before this migration are `overdue`;
  - `template_key` (the C16 template it is composed from) and the edit: `body_sealed` holds the
    person's edited body, or the body as sent (sealed); `body_fingerprint` is the composed
    body's SHA-256 when it was drafted, `edit_fingerprint` the edited body's;
  - `drafted_by_kind` (`person` or `agent`; rows before this migration are `agent`);
  - the send: `sent_by`, `sent_at`, `not_before` (the end of the 10-s Undo window) and
    `undone_at`.
  The app may update the edit and send columns and the existing decision columns only. At most
  one `chase` draft waits per client contact per engagement (a partial unique index).
- `follow_up_items.sequence` takes 1..4 (POR-20: at most four).
- New `follow_up_returns`: the files a screening-return follow-up returns, with the reason.
  Insert-only.

Revision ID: 0128
Revises: 0127
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None

_INSERT_BEFORE = (
    "tenant_id",
    "engagement_id",
    "recipient_user_id",
    "status",
    "note",
    "agent_run_id",
)
_INSERT_NEW = (
    "binder_id",
    "recipient_contact_id",
    "kind",
    "template_key",
    "body_fingerprint",
    "drafted_by_kind",
)
_UPDATE_BEFORE = ("status", "note", "decided_by", "decided_at")
_UPDATE_NEW = (
    "body_sealed",
    "edit_fingerprint",
    "sent_by",
    "sent_at",
    "not_before",
    "undone_at",
)


def _sequence_check(upper: int, name: str) -> None:
    # The CHECK came from 0040 as `reminder_items_sequence_check`; 0087 renamed the table, not
    # the constraint, so it is found by its definition rather than its name.
    op.execute(
        """
        DO $$
        DECLARE found text;
        BEGIN
            SELECT conname INTO found FROM pg_constraint
             WHERE conrelid = 'follow_up_items'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%sequence%';
            IF found IS NOT NULL THEN
                EXECUTE format('ALTER TABLE follow_up_items DROP CONSTRAINT %I', found);
            END IF;
        END $$
        """
    )
    op.execute(
        f"ALTER TABLE follow_up_items ADD CONSTRAINT {name} CHECK (sequence BETWEEN 1 AND {upper})"
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE follow_up_schedules
            ADD COLUMN binder_id uuid NULL,
            ADD COLUMN recipient_contact_id uuid NULL,
            ADD COLUMN kind text NOT NULL DEFAULT 'overdue'
                CHECK (kind IN ('overdue', 'chase', 'screening_return')),
            ADD COLUMN template_key text NULL CHECK (length(template_key) BETWEEN 1 AND 200),
            ADD COLUMN body_sealed bytea NULL CHECK (octet_length(body_sealed) <= 32768),
            ADD COLUMN body_fingerprint text NULL CHECK (body_fingerprint ~ '^[0-9a-f]{64}$'),
            ADD COLUMN edit_fingerprint text NULL CHECK (edit_fingerprint ~ '^[0-9a-f]{64}$'),
            ADD COLUMN drafted_by_kind text NOT NULL DEFAULT 'agent'
                CHECK (drafted_by_kind IN ('person', 'agent')),
            ADD COLUMN sent_by uuid NULL,
            ADD COLUMN sent_at timestamptz NULL,
            ADD COLUMN not_before timestamptz NULL,
            ADD COLUMN undone_at timestamptz NULL,
            ADD CONSTRAINT follow_up_schedules_binder_fk
                FOREIGN KEY (tenant_id, binder_id) REFERENCES request_lists (tenant_id, id),
            ADD CONSTRAINT follow_up_schedules_contact_fk
                FOREIGN KEY (tenant_id, recipient_contact_id) REFERENCES contacts (tenant_id, id),
            ADD CONSTRAINT follow_up_schedules_edit_sealed
                CHECK (edit_fingerprint IS NULL OR body_sealed IS NOT NULL),
            ADD CONSTRAINT follow_up_schedules_sent_stamps
                CHECK ((sent_at IS NULL) = (sent_by IS NULL)
                       AND (sent_at IS NULL) = (not_before IS NULL)),
            ADD CONSTRAINT follow_up_schedules_sent_status
                CHECK (sent_at IS NULL OR status = 'sent')
        """
    )
    op.execute(
        "CREATE INDEX follow_up_schedules_waiting ON follow_up_schedules "
        "(tenant_id, recipient_user_id, status)"
    )
    # One open person-asked draft per client contact per engagement: two concurrent "Send
    # reminder…" requests can't both draft (the second joins the first, ON CONFLICT).
    op.execute(
        "CREATE UNIQUE INDEX follow_up_schedules_one_open_chase ON follow_up_schedules "
        "(tenant_id, engagement_id, recipient_user_id) "
        "WHERE status = 'drafted' AND kind = 'chase'"
    )
    insert_columns(op, "follow_up_schedules", _INSERT_BEFORE + _INSERT_NEW)
    op.execute(
        f"GRANT UPDATE ({', '.join(_UPDATE_BEFORE + _UPDATE_NEW)}) "
        "ON follow_up_schedules TO abacus_app"
    )
    _sequence_check(4, "follow_up_items_sequence_check")
    op.execute(
        """
        CREATE TABLE follow_up_returns (
            tenant_id uuid NOT NULL,
            follow_up_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            reason_code text NOT NULL CHECK (reason_code ~ '^[a-z_]{1,64}$'),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, follow_up_id, evidence_version_id),
            FOREIGN KEY (tenant_id, follow_up_id) REFERENCES follow_up_schedules (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "follow_up_returns")
    insert_only(op, "follow_up_returns")
    insert_columns(
        op,
        "follow_up_returns",
        ("tenant_id", "follow_up_id", "evidence_version_id", "reason_code"),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM follow_up_schedules WHERE kind = 'screening_return') THEN
                RAISE EXCEPTION 'screening-return follow-ups exist; downgrade refused';
            END IF;
        END $$
        """
    )
    op.execute("DROP TABLE follow_up_returns")
    _sequence_check(3, "reminder_items_sequence_check")
    op.execute(f"REVOKE UPDATE ({', '.join(_UPDATE_NEW)}) ON follow_up_schedules FROM abacus_app")
    insert_columns(op, "follow_up_schedules", _INSERT_BEFORE)
    op.execute("DROP INDEX follow_up_schedules_one_open_chase")
    op.execute("DROP INDEX follow_up_schedules_waiting")
    op.execute(
        """
        ALTER TABLE follow_up_schedules
            DROP CONSTRAINT follow_up_schedules_sent_status,
            DROP CONSTRAINT follow_up_schedules_sent_stamps,
            DROP CONSTRAINT follow_up_schedules_edit_sealed,
            DROP CONSTRAINT follow_up_schedules_contact_fk,
            DROP CONSTRAINT follow_up_schedules_binder_fk,
            DROP COLUMN undone_at,
            DROP COLUMN not_before,
            DROP COLUMN sent_at,
            DROP COLUMN sent_by,
            DROP COLUMN drafted_by_kind,
            DROP COLUMN edit_fingerprint,
            DROP COLUMN body_fingerprint,
            DROP COLUMN body_sealed,
            DROP COLUMN template_key,
            DROP COLUMN kind,
            DROP COLUMN recipient_contact_id,
            DROP COLUMN binder_id
        """
    )
