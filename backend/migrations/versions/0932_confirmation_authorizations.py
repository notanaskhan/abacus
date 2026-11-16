"""Confirmation authorizations (A-08-T18; A-08 §3 F4; SPEC-657 AC-6.3; AUD-14; DEC-5324).

`confirmation_authorizations`: one C7 envelope (purpose `confirmation_authorization`) per
request, for the client's named signer, wrapping the firm's authorization letter (an evidence
version); `confirmation_authorization_items` names the confirmations it covers. The envelope's
completion stamps `completed_at` and moves its confirmations back to Draft, authorized; until
then none of them sends. `confirmation_events` gains `authorized` and the follow-up sweep's
prompts (`second_request_due`, `no_response_due`), each recorded once per confirmation.
`confirmation_attachments` (insert-only, A-08-T19) names the evidence versions a respondent's link
uploaded for its confirmation; the answer may cite only those. `confirmation_responses` gains the
answer's sealed IP and its user agent (the P-14 access record) and the respondent's own account
list for a bank confirmation (`accounts`, a JSON array of description, last four and balance).

Revision ID: 0932
Revises: 0931
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0932"
down_revision = "0931"
branch_labels = None
depends_on = None

INSERTS = (
    "tenant_id", "engagement_id", "work_item_id", "letter_evidence_version_id",
    "signer_contact_id", "requested_by",
)  # fmt: skip
UPDATES = ("envelope_id", "completed_at")
_KINDS_OLD = (
    "'sent', 'viewed', 'second_request', 'responded', 'revoked', 'authorization_requested'"
)
# `authorized` (the envelope completed); the follow-up's prompts, once each (the daily sweep).
_KINDS_NEW = f"{_KINDS_OLD}, 'authorized', 'second_request_due', 'no_response_due'"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE confirmation_authorizations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            letter_evidence_version_id uuid NOT NULL,
            signer_contact_id uuid NOT NULL,
            requested_by uuid NOT NULL,
            requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            envelope_id uuid NULL,
            completed_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CHECK (completed_at IS NULL OR envelope_id IS NOT NULL),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, requested_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "confirmation_authorizations")
    insert_columns(op, "confirmation_authorizations", INSERTS)
    op.execute("REVOKE UPDATE, DELETE ON confirmation_authorizations FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(UPDATES)}) ON confirmation_authorizations TO abacus_app")
    op.execute(
        """
        CREATE TABLE confirmation_authorization_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            authorization_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            UNIQUE (tenant_id, authorization_id, confirmation_id),
            FOREIGN KEY (tenant_id, authorization_id)
                REFERENCES confirmation_authorizations (tenant_id, id),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    tenant_table(op, "confirmation_authorization_items")
    insert_columns(
        op,
        "confirmation_authorization_items",
        ("tenant_id", "authorization_id", "confirmation_id"),
    )
    op.execute(
        "REVOKE UPDATE, DELETE, TRUNCATE ON confirmation_authorization_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE confirmation_events DROP CONSTRAINT confirmation_events_kind_check, "
        f"ADD CONSTRAINT confirmation_events_kind_check CHECK (kind IN ({_KINDS_NEW}))"
    )
    op.execute(
        """
        CREATE TABLE confirmation_attachments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, evidence_version_id),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    tenant_table(op, "confirmation_attachments")
    insert_columns(
        op,
        "confirmation_attachments",
        ("tenant_id", "confirmation_id", "evidence_version_id", "principal_id"),
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON confirmation_attachments FROM abacus_app")
    op.execute(
        "ALTER TABLE confirmation_responses ADD COLUMN ip_sealed bytea NULL, "
        "ADD COLUMN user_agent text NULL CHECK (length(user_agent) <= 400), "
        "ADD COLUMN accounts jsonb NOT NULL DEFAULT '[]'::jsonb "
        "CHECK (jsonb_typeof(accounts) = 'array' AND jsonb_array_length(accounts) <= 50)"
    )
    op.execute(
        "GRANT INSERT (ip_sealed, user_agent, accounts) ON confirmation_responses TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM confirmation_events "
        "WHERE kind IN ('authorized', 'second_request_due', 'no_response_due')"
    )
    op.execute(
        "ALTER TABLE confirmation_events DROP CONSTRAINT confirmation_events_kind_check, "
        f"ADD CONSTRAINT confirmation_events_kind_check CHECK (kind IN ({_KINDS_OLD}))"
    )
    op.execute(
        "ALTER TABLE confirmation_responses DROP COLUMN ip_sealed, DROP COLUMN user_agent, "
        "DROP COLUMN accounts"
    )
    op.execute("DROP TABLE confirmation_attachments")
    op.execute("DROP TABLE confirmation_authorization_items")
    op.execute("DROP TABLE confirmation_authorizations")
