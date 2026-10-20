"""Request status v2 (F-03-T15; plan migration "0059_request_status_v2"; chapter 09 §9.5.6).

Codes rewritten: `open` → `draft` when firm-only, else `requested`; `received` and
`ready_for_review` → `uploaded` (the screening sub-state lives with the screening);
`needs_revision` → `returned`; `accepted` → `received`. `not_applicable` is new; `overdue` is
derived, never stored. A trigger keeps `draft` and `requested` in step with client visibility
and stamps `requested_at` the first time an item is asked of the client.

Also: `requested_at`, `sent_at`, the not-applicable facts (`na_reason`, `na_note`, `na_by`,
`na_at`), `client_ignored_at`, `incorporation_state` (+ by/at); review reasons `wrong_document`
and `wrong_year`.

Revision ID: 0071
Revises: 0070
"""

from __future__ import annotations

from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

_NEW = "('draft', 'requested', 'uploaded', 'received', 'returned', 'not_applicable')"
_OLD = "('open', 'received', 'ready_for_review', 'needs_revision', 'accepted')"


def upgrade() -> None:
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_status_check")
    op.execute("ALTER TABLE request_items NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE request_items SET status = CASE status
            WHEN 'open' THEN CASE WHEN client_visible THEN 'requested' ELSE 'draft' END
            WHEN 'received' THEN 'uploaded'
            WHEN 'ready_for_review' THEN 'uploaded'
            WHEN 'needs_revision' THEN 'returned'
            WHEN 'accepted' THEN 'received'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE request_items
            ALTER COLUMN status SET DEFAULT 'draft',
            ADD COLUMN requested_at timestamptz NULL,
            ADD COLUMN sent_at timestamptz NULL,
            ADD COLUMN na_reason text NULL CHECK (na_reason IN
                ('not_applicable_this_year', 'already_sent', 'dont_have', 'firm_waived')),
            ADD COLUMN na_note text NULL CHECK (length(na_note) BETWEEN 1 AND 1000),
            ADD COLUMN na_by uuid NULL,
            ADD COLUMN na_at timestamptz NULL,
            ADD COLUMN client_ignored_at timestamptz NULL,
            ADD COLUMN incorporation_state text NOT NULL DEFAULT 'none' CHECK
                (incorporation_state IN ('none', 'matched', 'pending_incorporation',
                                         'incorporated')),
            ADD COLUMN incorporated_by uuid NULL,
            ADD COLUMN incorporated_at timestamptz NULL
        """
    )
    op.execute(
        "UPDATE request_items SET requested_at = created_at WHERE status <> 'draft' "
        "AND client_visible"
    )
    op.execute("ALTER TABLE request_items FORCE ROW LEVEL SECURITY")
    op.execute(
        f"ALTER TABLE request_items ADD CONSTRAINT request_items_status_check "
        f"CHECK (status IN {_NEW})"
    )
    op.execute(
        "ALTER TABLE request_items ADD CONSTRAINT request_items_na_whole CHECK "
        "((status = 'not_applicable') = (na_reason IS NOT NULL))"
    )
    op.execute(
        """
        CREATE FUNCTION request_item_requested() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.status IN ('draft', 'requested') THEN
                NEW.status := CASE WHEN NEW.client_visible THEN 'requested' ELSE 'draft' END;
            END IF;
            IF NEW.status = 'requested' AND NEW.requested_at IS NULL THEN
                NEW.requested_at := clock_timestamp();
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER request_items_requested BEFORE INSERT OR UPDATE OF status, "
        "client_visible ON request_items FOR EACH ROW EXECUTE FUNCTION request_item_requested()"
    )
    op.execute(
        "GRANT UPDATE (sent_at, na_reason, na_note, na_by, na_at, client_ignored_at, "
        "incorporation_state, incorporated_by, incorporated_at) ON request_items TO abacus_app"
    )
    op.execute(
        """
        INSERT INTO review_reason_codes (code, applies_to, label, description, requires_note)
        SELECT code, applies_to, label, description, false
        FROM (VALUES
            ('wrong_document', 'Wrong document', 'Not the document the request asks for.'),
            ('wrong_year', 'Wrong year', 'A document for another year.')
        ) AS r(code, label, description)
        CROSS JOIN (VALUES ('reject'), ('send_back')) AS a(applies_to)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM review_reason_codes WHERE code IN ('wrong_document', 'wrong_year')")
    op.execute(
        "REVOKE UPDATE (sent_at, na_reason, na_note, na_by, na_at, client_ignored_at, "
        "incorporation_state, incorporated_by, incorporated_at) ON request_items FROM abacus_app"
    )
    op.execute("DROP TRIGGER request_items_requested ON request_items")
    op.execute("DROP FUNCTION request_item_requested()")
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_na_whole")
    op.execute("ALTER TABLE request_items DROP CONSTRAINT request_items_status_check")
    op.execute("ALTER TABLE request_items NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE request_items SET status = CASE status
            WHEN 'draft' THEN 'open'
            WHEN 'requested' THEN 'open'
            WHEN 'uploaded' THEN 'received'
            WHEN 'returned' THEN 'needs_revision'
            WHEN 'received' THEN 'accepted'
            WHEN 'not_applicable' THEN 'open'
        END
        """
    )
    op.execute("ALTER TABLE request_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE request_items ALTER COLUMN status SET DEFAULT 'open', "
        "DROP COLUMN requested_at, DROP COLUMN sent_at, DROP COLUMN na_reason, "
        "DROP COLUMN na_note, DROP COLUMN na_by, DROP COLUMN na_at, "
        "DROP COLUMN client_ignored_at, DROP COLUMN incorporation_state, "
        "DROP COLUMN incorporated_by, DROP COLUMN incorporated_at"
    )
    op.execute(
        f"ALTER TABLE request_items ADD CONSTRAINT request_items_status_check "
        f"CHECK (status IN {_OLD})"
    )
