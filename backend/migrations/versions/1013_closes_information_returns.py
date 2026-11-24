"""C-02-T38 (S53; TASK-8904; C-02 §4.2; SPEC CLS-13; amber): information returns (closes).
Expand-only.

- `vendors_1099`: one per client entity and external vendor. A TIN is never stored in plaintext:
  `tin_sealed` (an envelope under the firm's key, ADR-167 / P-12), `tin_last4` (the only digits
  any payload shows), `tin_kind` and `tin_fingerprint` (HMAC under the firm's key; one TIN once per
  entity), all present together or not at all (P-07-T07's shape on `client_entities`).
- `vendor_payment_rollups`: derived per vendor, tax year and method; recomputed, never edited.
- Insert-only `w9_requests` (`vendor_link` refused until R-03's link principal exists),
  `tin_match_results` (recorded by a person, source `manual`; no IRS-login automation) and
  `backup_withholding_events` (the 30-business-day rule is a code check, C-02-T33).
- `information_return_batches`: one per entity and tax year, status forward through approval,
  export, IRIS filing and acknowledgement, each step with its person and time.
- Insert-only `information_returns` per batch.

No column is named `tin`, `ssn` or `ein`; schema_check refuses one.

Revision ID: 1013
Revises: 1012
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "1013"
down_revision = "1012"
branch_labels = None
depends_on = None

ENTITY_TYPES = (
    "individual", "single_member_llc", "partnership", "c_corporation", "s_corporation",
    "trust_estate", "llc_c", "llc_s", "llc_p", "other", "unknown",
)  # fmt: skip
_PERSON = "FOREIGN KEY (tenant_id, {col}) REFERENCES memberships (tenant_id, user_id)"
_ENTITY = "FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id)"
_VENDOR = "FOREIGN KEY (tenant_id, vendor_id) REFERENCES vendors_1099 (tenant_id, id)"
_YEAR = "tax_year integer NOT NULL CHECK (tax_year BETWEEN 2020 AND 2100)"


def _person(col: str) -> str:
    return _PERSON.format(col=col)


def upgrade() -> None:
    types = ", ".join(f"'{t}'" for t in ENTITY_TYPES)
    op.execute(
        f"""
        CREATE TABLE vendors_1099 (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            external_vendor_id text NOT NULL CHECK (length(external_vendor_id) BETWEEN 1 AND 120),
            display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 300),
            entity_type text NOT NULL DEFAULT 'unknown' CHECK (entity_type IN ({types})),
            entity_type_source text NOT NULL DEFAULT 'ledger' CHECK (entity_type_source IN (
                'w9', 'ledger', 'person', 'agent_suggestion_adopted')),
            is_attorney boolean NOT NULL DEFAULT false,
            exempt_reason text NULL CHECK (length(btrim(exempt_reason)) BETWEEN 1 AND 300),
            tin_sealed bytea NULL CHECK (octet_length(tin_sealed) <= 1024),
            tin_last4 text NULL CHECK (tin_last4 ~ '^[0-9]{{4}}$'),
            tin_kind text NULL CHECK (tin_kind IN ('ssn', 'ein')),
            tin_fingerprint bytea NULL CHECK (octet_length(tin_fingerprint) = 32),
            w9_status text NOT NULL DEFAULT 'missing'
                CHECK (w9_status IN ('on_file', 'requested', 'tin_mismatch', 'missing')),
            w9_evidence_version_id uuid NULL,
            w9_signed_on date NULL,
            backup_withholding text NOT NULL DEFAULT 'none'
                CHECK (backup_withholding IN ('none', 'watch', 'started')),
            updated_by uuid NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, external_vendor_id),
            {_ENTITY},
            FOREIGN KEY (w9_evidence_version_id) REFERENCES evidence_versions (id),
            {_person("updated_by")},
            CONSTRAINT vendors_1099_tin_whole CHECK (
                (tin_sealed IS NULL) = (tin_last4 IS NULL)
                AND (tin_sealed IS NULL) = (tin_kind IS NULL)
                AND (tin_sealed IS NULL) = (tin_fingerprint IS NULL)),
            CONSTRAINT vendors_1099_w9_on_file CHECK (
                w9_status <> 'on_file' OR (w9_evidence_version_id IS NOT NULL
                                           AND w9_signed_on IS NOT NULL)),
            CONSTRAINT vendors_1099_person_source CHECK (
                entity_type_source NOT IN ('person', 'agent_suggestion_adopted')
                OR updated_by IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX vendors_1099_one_tin ON vendors_1099 "
        "(tenant_id, client_entity_id, tin_fingerprint) WHERE tin_fingerprint IS NOT NULL"
    )
    op.execute(
        f"""
        CREATE TABLE vendor_payment_rollups (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            vendor_id uuid NOT NULL,
            {_YEAR},
            method text NOT NULL
                CHECK (method IN ('check', 'ach', 'card', 'payment_app', 'other')),
            amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
            txn_count integer NOT NULL CHECK (txn_count >= 0),
            source_snapshot_id uuid NOT NULL,
            computed_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, vendor_id, tax_year, method),
            {_ENTITY},
            {_VENDOR}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE w9_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            vendor_ids uuid[] NOT NULL CHECK (cardinality(vendor_ids) BETWEEN 1 AND 500),
            channel text NOT NULL CHECK (channel IN ('portal', 'vendor_link')),
            request_item_ids uuid[] NOT NULL DEFAULT '{{}}',
            wording_template_version_id uuid NULL,
            sent_by uuid NOT NULL CHECK (sent_by::text = current_setting('app.actor_id', true)),
            sent_at timestamptz NOT NULL DEFAULT abacus_now(),
            {_ENTITY},
            {_person("sent_by")},
            -- Dropped when R-03's vendor link principal exists (C-02 §4.2).
            CONSTRAINT w9_requests_no_vendor_link_yet CHECK (channel <> 'vendor_link')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tin_match_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            vendor_id uuid NOT NULL,
            checked_on date NOT NULL,
            result text NOT NULL CHECK (result IN ('match', 'mismatch', 'not_issued', 'invalid')),
            source text NOT NULL DEFAULT 'manual' CHECK (source = 'manual'),
            recorded_by uuid NOT NULL
                CHECK (recorded_by::text = current_setting('app.actor_id', true)),
            recorded_at timestamptz NOT NULL DEFAULT abacus_now(),
            evidence_version_id uuid NULL,
            {_VENDOR},
            FOREIGN KEY (evidence_version_id) REFERENCES evidence_versions (id),
            {_person("recorded_by")}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE backup_withholding_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            vendor_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('watch_started', 'b_notice_received', 'started',
                                                  'stopped')),
            reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
            rate_percent numeric(5, 2) NULL CHECK (rate_percent = 24.00),
            notice_received_on date NULL,
            recorded_by uuid NOT NULL
                CHECK (recorded_by::text = current_setting('app.actor_id', true)),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            evidence_version_id uuid NULL,
            {_VENDOR},
            FOREIGN KEY (evidence_version_id) REFERENCES evidence_versions (id),
            {_person("recorded_by")},
            CHECK ((event = 'started') = (rate_percent IS NOT NULL)),
            CHECK (event <> 'b_notice_received' OR (notice_received_on IS NOT NULL
                                                    AND evidence_version_id IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE information_return_batches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_entity_id uuid NOT NULL,
            {_YEAR},
            status text NOT NULL DEFAULT 'not_started' CHECK (status IN (
                'not_started', 'approved', 'exported', 'filed_iris', 'accepted', 'rejected')),
            due_on date NOT NULL,
            approved_by uuid NULL,
            approved_at timestamptz NULL,
            iris_file_document_id uuid NULL,
            iris_file_sha256 char(64) NULL CHECK (iris_file_sha256 ~ '^[0-9a-f]{{64}}$'),
            exported_by uuid NULL,
            exported_at timestamptz NULL,
            iris_receipt_id text NULL CHECK (iris_receipt_id ~ '^[A-Za-z0-9-]{{1,60}}$'),
            filed_recorded_by uuid NULL,
            filed_on date NULL,
            filed_at timestamptz NULL,
            filed_evidence_version_id uuid NULL,
            ack_recorded_by uuid NULL,
            ack_at timestamptz NULL,
            ack_evidence_version_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, client_entity_id, tax_year),
            {_ENTITY},
            FOREIGN KEY (iris_file_document_id) REFERENCES generated_documents (id),
            FOREIGN KEY (filed_evidence_version_id) REFERENCES evidence_versions (id),
            FOREIGN KEY (ack_evidence_version_id) REFERENCES evidence_versions (id),
            {_person("approved_by")},
            {_person("exported_by")},
            {_person("filed_recorded_by")},
            {_person("ack_recorded_by")},
            CONSTRAINT information_return_batches_approved CHECK (
                status = 'not_started' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
            CONSTRAINT information_return_batches_exported CHECK (
                status IN ('not_started', 'approved')
                OR (exported_by IS NOT NULL AND exported_at IS NOT NULL
                    AND iris_file_sha256 IS NOT NULL)),
            CONSTRAINT information_return_batches_filed CHECK (
                status NOT IN ('filed_iris', 'accepted', 'rejected')
                OR (filed_recorded_by IS NOT NULL AND filed_at IS NOT NULL
                    AND iris_receipt_id IS NOT NULL AND filed_on IS NOT NULL)),
            CONSTRAINT information_return_batches_acknowledged CHECK (
                status NOT IN ('accepted', 'rejected')
                OR (ack_recorded_by IS NOT NULL AND ack_at IS NOT NULL
                    AND ack_evidence_version_id IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE information_returns (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            batch_id uuid NOT NULL,
            vendor_id uuid NOT NULL,
            form text NOT NULL CHECK (form IN ('nec', 'misc')),
            box text NOT NULL CHECK (box ~ '^[0-9]{{1,2}}[a-z]?$'),
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            threshold_ref text NOT NULL CHECK (length(threshold_ref) BETWEEN 1 AND 120),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, batch_id, vendor_id, form, box),
            FOREIGN KEY (tenant_id, batch_id)
                REFERENCES information_return_batches (tenant_id, id),
            {_VENDOR}
        )
        """
    )
    for index in (
        "vendor_payment_rollups_by_entity ON vendor_payment_rollups "
        "(tenant_id, client_entity_id, tax_year)",
        "tin_match_results_by_vendor ON tin_match_results (tenant_id, vendor_id, checked_on)",
        "backup_withholding_events_by_vendor ON backup_withholding_events "
        "(tenant_id, vendor_id, at)",
        "w9_requests_by_entity ON w9_requests (tenant_id, client_entity_id, sent_at)",
    ):
        op.execute(f"CREATE INDEX {index}")
    for table, inserts, updates in GRANTS:
        tenant_table(op, table)
        insert_columns(op, table, inserts)
        if updates is None:
            insert_only(op, table)
            continue
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(updates)}) ON {table} TO abacus_app")
    # Only a rollup is ever replaced (recomputed); nothing else is deleted.
    for table in ("vendors_1099", "information_return_batches"):
        op.execute(f"REVOKE DELETE ON {table} FROM abacus_app")


GRANTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...] | None], ...] = (
    ("vendors_1099",
     ("id", "tenant_id", "client_entity_id", "external_vendor_id", "display_name",
      "entity_type", "entity_type_source", "is_attorney"),
     ("display_name", "entity_type", "entity_type_source", "is_attorney", "exempt_reason",
      "tin_sealed", "tin_last4", "tin_kind", "tin_fingerprint", "w9_status",
      "w9_evidence_version_id", "w9_signed_on", "backup_withholding", "updated_by",
      "updated_at", "version")),
    ("vendor_payment_rollups",
     ("tenant_id", "client_entity_id", "vendor_id", "tax_year", "method", "amount",
      "txn_count", "source_snapshot_id"),
     ("amount", "txn_count", "source_snapshot_id", "computed_at")),
    ("w9_requests",
     ("id", "tenant_id", "client_entity_id", "vendor_ids", "channel", "request_item_ids",
      "wording_template_version_id", "sent_by"),
     None),
    ("tin_match_results",
     ("tenant_id", "vendor_id", "checked_on", "result", "recorded_by", "evidence_version_id"),
     None),
    ("backup_withholding_events",
     ("tenant_id", "vendor_id", "event", "reason", "rate_percent", "notice_received_on",
      "recorded_by", "evidence_version_id"),
     None),
    ("information_return_batches",
     ("id", "tenant_id", "client_entity_id", "tax_year", "due_on"),
     ("status", "due_on", "approved_by", "approved_at", "iris_file_document_id",
      "iris_file_sha256", "exported_by", "exported_at", "iris_receipt_id",
      "filed_recorded_by", "filed_on", "filed_at", "filed_evidence_version_id",
      "ack_recorded_by", "ack_at", "ack_evidence_version_id", "version")),
    ("information_returns",
     ("tenant_id", "batch_id", "vendor_id", "form", "box", "amount", "threshold_ref"),
     None),
)  # fmt: skip


def downgrade() -> None:
    for table in ("information_returns", "information_return_batches",
                  "backup_withholding_events", "tin_match_results", "w9_requests",
                  "vendor_payment_rollups", "vendors_1099"):  # fmt: skip
        op.execute(f"DROP TABLE {table}")
