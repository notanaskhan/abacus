"""A-08-T16 (S46; TASK-8084; SPEC-657 F6; AU-C 505; ADR-146): `confirmations`, expand-only, amber.

External confirmations under the auditor's control (AUD-14):

- `confirmations`: one per respondent on a work item; positive form only (`form = 'positive'`;
  never negative alone, AU-C 505), its type, channel, status, number (C1, C2…), the address it goes
  to (sealed) and its SHA-256, the sample item it tests.
- `confirmation_lines`: the book amounts the respondent is asked to confirm.
- `address_verifications` (insert-only): how a person verified the address independently, with
  sources and citations; `independent` is true only with a non-client source.
- `confirmation_events` (insert-only): sent, viewed, second request, responded, revoked.
- `confirmation_responses` (insert-only), `reconciliation_items` (insert-only),
  `alternative_procedures` (insert-only) and `confirmation_decisions` (insert-only, a person's:
  `actor_kind = 'human'`).
- `confirmation_links`: the link principal a sent confirmation carries (A-08-T15).

No client principal ever reads these: the repository refuses a client context before any query
(I-CONFIRMATION-ISOLATION), and the tables are tenant-scoped. Amounts are confidential.

Revision ID: 0894
Revises: 0893
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0894"
down_revision = "0893"
branch_labels = None
depends_on = None

_MONEY = "numeric(18,2)"
_WI = (
    "engagement_id uuid NOT NULL, work_item_id uuid NOT NULL, "
    "FOREIGN KEY (tenant_id, engagement_id, work_item_id) "
    "REFERENCES work_items (tenant_id, engagement_id, id)"
)
_STATUS = (
    "'draft', 'authorization_requested', 'sent', 'responded', 'exception', "
    "'alternative_procedures', 'closed'"
)
TABLES = (
    "confirmations",
    "confirmation_lines",
    "address_verifications",
    "confirmation_events",
    "confirmation_responses",
    "reconciliation_items",
    "alternative_procedures",
    "confirmation_decisions",
    "confirmation_links",
)


def _lock(table: str, inserts: tuple[str, ...], updates: tuple[str, ...] = ()) -> None:
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    insert_columns(op, table, inserts)
    if updates:
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    else:
        insert_only(op, table)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE confirmations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            {_WI},
            number integer NOT NULL CHECK (number > 0),
            type text NOT NULL
                CHECK (type IN ('bank', 'accounts_receivable', 'accounts_payable', 'other')),
            form text NOT NULL DEFAULT 'positive' CHECK (form = 'positive'),
            channel text NOT NULL
                CHECK (channel IN ('accrued_link', 'network_recorded', 'mail_recorded')),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ({_STATUS})),
            respondent_name_sealed bytea NOT NULL,
            respondent_org text NOT NULL CHECK (length(respondent_org) BETWEEN 1 AND 200),
            address_sealed bytea NOT NULL,
            address_sha256 bytea NOT NULL CHECK (octet_length(address_sha256) = 32),
            sample_item_ref text NULL CHECK (length(sample_item_ref) <= 100),
            tb_account_refs text[] NOT NULL DEFAULT '{{}}',
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id, number)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE confirmation_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            position integer NOT NULL CHECK (position > 0),
            description text NOT NULL CHECK (length(description) BETWEEN 1 AND 200),
            account_last4 text NULL CHECK (account_last4 ~ '^[0-9]{{4}}$'),
            book_amount {_MONEY} NOT NULL,
            UNIQUE (confirmation_id, position),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE address_verifications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            method text NOT NULL CHECK (length(method) BETWEEN 1 AND 300),
            sources text[] NOT NULL CHECK (cardinality(sources) >= 1),
            independent boolean NOT NULL,
            citation_ids uuid[] NOT NULL CHECK (cardinality(citation_ids) >= 1),
            address_sha256 bytea NOT NULL CHECK (octet_length(address_sha256) = 32),
            verified_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (independent = (sources && ARRAY['prior_year', 'website', 'phone',
                'public_register', 'bank_published'])),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE confirmation_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('sent', 'viewed', 'second_request', 'responded',
                'revoked', 'authorization_requested')),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system', 'link_principal')),
            actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 100),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE confirmation_responses (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL UNIQUE,
            via text NOT NULL CHECK (via IN ('respondent_page', 'recorded')),
            agrees boolean NOT NULL,
            respondent_name_sealed bytea NOT NULL,
            confirmed_total {_MONEY} NOT NULL,
            explanation_sealed bytea NULL,
            attested boolean NOT NULL DEFAULT false,
            attachment_version_ids uuid[] NOT NULL DEFAULT '{{}}',
            submitted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE reconciliation_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            kind text NOT NULL CHECK (length(kind) BETWEEN 1 AND 60),
            amount {_MONEY} NOT NULL,
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE alternative_procedures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            procedure_sealed bytea NOT NULL,
            citation_ids uuid[] NOT NULL CHECK (cardinality(citation_ids) >= 1),
            performed_by uuid NOT NULL,
            performed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE confirmation_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            confirmation_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('accept_reconciliation', 'exception',
            'close')),
            decided_by uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE confirmation_links (
            confirmation_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, confirmation_id) REFERENCES confirmations (tenant_id, id),
            FOREIGN KEY (tenant_id, principal_id) REFERENCES link_principals (tenant_id, id)
        )
        """
    )
    _lock(
        "confirmations",
        (
            "tenant_id",
            "engagement_id",
            "work_item_id",
            "number",
            "type",
            "channel",
            "respondent_name_sealed",
            "respondent_org",
            "address_sealed",
            "address_sha256",
            "sample_item_ref",
            "tb_account_refs",
            "created_by",
        ),
        ("status", "row_version"),
    )
    _lock(
        "confirmation_lines",
        (
            "tenant_id",
            "confirmation_id",
            "position",
            "description",
            "account_last4",
            "book_amount",
        ),
    )
    _lock(
        "address_verifications",
        (
            "tenant_id",
            "confirmation_id",
            "method",
            "sources",
            "independent",
            "citation_ids",
            "address_sha256",
            "verified_by",
            "actor_kind",
        ),
    )
    _lock(
        "confirmation_events", ("tenant_id", "confirmation_id", "kind", "actor_kind", "actor_id")
    )
    _lock(
        "confirmation_responses",
        (
            "tenant_id",
            "confirmation_id",
            "via",
            "agrees",
            "respondent_name_sealed",
            "confirmed_total",
            "explanation_sealed",
            "attested",
            "attachment_version_ids",
        ),
    )
    _lock(
        "reconciliation_items",
        ("tenant_id", "confirmation_id", "kind", "amount", "citation_ids", "created_by"),
    )
    _lock(
        "alternative_procedures",
        ("tenant_id", "confirmation_id", "procedure_sealed", "citation_ids", "performed_by"),
    )
    _lock(
        "confirmation_decisions",
        ("tenant_id", "confirmation_id", "decision", "decided_by", "actor_kind", "content_hash"),
    )
    _lock("confirmation_links", ("confirmation_id", "tenant_id", "principal_id"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
