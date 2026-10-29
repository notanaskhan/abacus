"""Firm intake: the inbox's threads, messages, attachments and triage (N-01-T07; N-01 §4.2 "T07").

Six tables in `communications`, every one tenant-scoped with forced RLS:

- `inbox_threads`: one conversation from a mailbox, the portal or a staff log, matched to a
  client by a method the row names (`none` until matched).
- `inbound_messages` (insert-only): one received message. The body is sealed (`body_sealed`,
  Restricted); the sender's address is kept only as an HMAC.
- `inbox_attachments`: one received file, stored by fingerprint and storage key. `status` moves
  only through `communications/transitions.py` (chapter 03 §1.3 rule 2); the app may update
  only status and filing columns.
- `triage_decisions` (insert-only): a person's file, ignore or hold. `actor_kind` must be
  `human` and equal the transaction's `app.actor_kind` and `app.actor_id` (the P-04 binding), so
  an agent or system insert is refused by the database.
- `inbox_sender_rules`: "mail from this address is this client's", the address HMAC'd and sealed;
  revoked, never deleted.
- `inbox_attachment_flags` (insert-only): the checker's findings per run; `facts` holds
  identifiers, years and masked last-4 only.

Classification (ADR-031): `body_sealed`, `reason_note_sealed`, `address_sealed` Restricted;
`subject_display`, `sender_display`, `file_name` Confidential; `facts` Internal; the TRI tag is
derived at read time from the client's `tax_return` work item. `pg_trgm` (0103) indexes the
subject and sender for INB-01's search.

Revision ID: 0293
Revises: 0292
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0293"
down_revision = "0292"
branch_labels = None
depends_on = None

_INSERT_ONLY = ("inbound_messages", "triage_decisions", "inbox_attachment_flags")
_THREAD_UPDATES = (
    "client_id",
    "client_entity_id",
    "match_method",
    "matched_by",
    "matched_at",
    "ignored_reason",
    "last_received_at",
)
_ATTACHMENT_UPDATES = (
    "client_id",
    "status",
    "classification_id",
    "filed_evidence_version_id",
    "filed_destination_kind",
    "filed_destination_id",
    "data_classes",
)
_HEX64 = "~ '^[0-9a-f]{64}$'"


def _immutable(table: str) -> None:
    insert_only(op, table)
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION intake_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION intake_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION intake_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )

    op.execute(
        """
        CREATE TABLE inbox_threads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            source_kind text NOT NULL CHECK (source_kind IN ('mailbox', 'portal', 'staff')),
            source_display text NULL CHECK (char_length(source_display) <= 200),
            client_id uuid NULL,
            client_entity_id uuid NULL,
            subject_display text NOT NULL CHECK (char_length(subject_display) <= 500),
            sender_display text NOT NULL CHECK (char_length(sender_display) BETWEEN 1 AND 320),
            match_method text NOT NULL DEFAULT 'none' CHECK (match_method IN
                ('contact_email', 'sender_rule', 'portal_principal', 'staff_selected', 'manual',
                 'none')),
            matched_by uuid NULL,
            matched_at timestamptz NULL,
            ignored_reason text NULL CHECK (char_length(ignored_reason) <= 200),
            first_received_at timestamptz NOT NULL,
            last_received_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (last_received_at >= first_received_at),
            CHECK ((match_method = 'none') = (client_id IS NULL)),
            CHECK (match_method NOT IN ('staff_selected', 'manual')
                OR (matched_by IS NOT NULL AND matched_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities (tenant_id, id),
            FOREIGN KEY (tenant_id, matched_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX inbox_threads_by_client ON inbox_threads "
        "(tenant_id, client_id, last_received_at DESC)"
    )
    op.execute(
        "CREATE INDEX inbox_threads_unmatched ON inbox_threads (tenant_id, last_received_at DESC) "
        "WHERE client_id IS NULL"
    )
    op.execute(
        "CREATE INDEX inbox_threads_subject_trgm ON inbox_threads "
        "USING gin (subject_display gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX inbox_threads_sender_trgm ON inbox_threads "
        "USING gin (sender_display gin_trgm_ops)"
    )
    tenant_table(op, "inbox_threads")
    op.execute("REVOKE UPDATE, DELETE ON inbox_threads FROM abacus_app")
    op.execute(f"GRANT UPDATE ({', '.join(_THREAD_UPDATES)}) ON inbox_threads TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE inbound_messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            thread_id uuid NOT NULL,
            channel text NOT NULL CHECK (channel IN ('email', 'portal_upload', 'staff_logged')),
            received_via text NULL CHECK (received_via IN
                ('email', 'mail', 'fax', 'in_person', 'portal', 'other')),
            sender_display text NOT NULL CHECK (char_length(sender_display) BETWEEN 1 AND 320),
            sender_address_hmac text NULL CHECK (sender_address_hmac {_HEX64}),
            sender_contact_id uuid NULL,
            sender_principal_id uuid NULL,
            logged_by_user_id uuid NULL,
            internet_message_id text NULL CHECK (char_length(internet_message_id) <= 998),
            in_reply_to text NULL CHECK (char_length(in_reply_to) <= 998),
            reference_ids text[] NULL CHECK (cardinality(reference_ids) <= 100),
            subject_display text NOT NULL CHECK (char_length(subject_display) <= 500),
            body_sealed bytea NULL,
            body_kind text NULL CHECK (body_kind IN ('email_text', 'portal_note', 'staff_note')),
            received_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((body_sealed IS NULL) = (body_kind IS NULL)),
            CHECK (channel <> 'staff_logged'
                OR (logged_by_user_id IS NOT NULL AND received_via IS NOT NULL)),
            CHECK (channel <> 'portal_upload' OR sender_principal_id IS NOT NULL),
            FOREIGN KEY (tenant_id, thread_id) REFERENCES inbox_threads (tenant_id, id),
            FOREIGN KEY (tenant_id, sender_contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, logged_by_user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX inbound_messages_internet_id ON inbound_messages "
        "(tenant_id, internet_message_id) WHERE internet_message_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX inbound_messages_by_thread ON inbound_messages "
        "(tenant_id, thread_id, received_at)"
    )
    tenant_table(op, "inbound_messages")

    op.execute(
        f"""
        CREATE TABLE inbox_attachments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            message_id uuid NOT NULL,
            thread_id uuid NOT NULL,
            client_id uuid NULL,
            file_name text NOT NULL CHECK (char_length(file_name) BETWEEN 1 AND 255),
            media_type text NOT NULL CHECK (char_length(media_type) BETWEEN 3 AND 127),
            size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
            fingerprint text NOT NULL CHECK (fingerprint {_HEX64}),
            storage_key text NOT NULL CHECK (char_length(storage_key) BETWEEN 1 AND 512),
            storage_version_id text NULL CHECK (char_length(storage_version_id) <= 200),
            key_mode text NOT NULL CHECK (key_mode IN ('content', 'detached')),
            status text NOT NULL DEFAULT 'new' CHECK (status IN
                ('new', 'waiting', 'filed', 'ignored', 'held', 'withdrawn')),
            classification_id uuid NULL,
            filed_evidence_version_id uuid NULL,
            filed_destination_kind text NULL CHECK (char_length(filed_destination_kind) <= 40),
            filed_destination_id uuid NULL,
            data_classes text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(data_classes) <= 20),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (status <> 'filed' OR filed_evidence_version_id IS NOT NULL),
            CHECK ((filed_destination_kind IS NULL) = (filed_destination_id IS NULL)),
            FOREIGN KEY (tenant_id, message_id) REFERENCES inbound_messages (tenant_id, id),
            FOREIGN KEY (tenant_id, thread_id) REFERENCES inbox_threads (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, filed_evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX inbox_attachments_by_status ON inbox_attachments "
        "(tenant_id, status, client_id)"
    )
    op.execute(
        "CREATE INDEX inbox_attachments_by_fingerprint ON inbox_attachments "
        "(tenant_id, fingerprint)"
    )
    tenant_table(op, "inbox_attachments")
    op.execute("REVOKE UPDATE, DELETE ON inbox_attachments FROM abacus_app")
    op.execute(
        f"GRANT UPDATE ({', '.join(_ATTACHMENT_UPDATES)}) ON inbox_attachments TO abacus_app"
    )

    op.execute(
        """
        CREATE TABLE triage_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            attachment_id uuid NOT NULL,
            thread_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('file', 'ignore', 'hold')),
            destination_kind text NULL CHECK (char_length(destination_kind) <= 40),
            destination_id uuid NULL,
            version_mode text NULL CHECK (version_mode IN
                ('new_document', 'new_version', 'new_version_supersede')),
            supersede_version_id uuid NULL,
            keep_both boolean NOT NULL DEFAULT false,
            rename_to text NULL CHECK (char_length(rename_to) BETWEEN 1 AND 255),
            reason_codes text[] NULL CHECK (cardinality(reason_codes) <= 10),
            reason_note_sealed bytea NULL,
            tell_client boolean NOT NULL DEFAULT false,
            client_message_id uuid NULL,
            also_accepted boolean NOT NULL DEFAULT false,
            followed_suggestion boolean NOT NULL DEFAULT false,
            suggestion_source text NOT NULL DEFAULT 'none'
                CHECK (suggestion_source IN ('rule', 'content', 'matcher', 'none')),
            suggestion_rank smallint NULL CHECK (suggestion_rank BETWEEN 1 AND 10),
            seen_proposal_id uuid NULL,
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true)),
            CHECK (decision <> 'file'
                OR (destination_kind IS NOT NULL AND destination_id IS NOT NULL
                    AND version_mode IS NOT NULL)),
            CHECK (version_mode IS DISTINCT FROM 'new_version_supersede'
                OR supersede_version_id IS NOT NULL),
            CHECK (decision <> 'ignore' OR reason_codes IS NOT NULL),
            CHECK (followed_suggestion = false OR suggestion_source <> 'none'),
            FOREIGN KEY (tenant_id, attachment_id) REFERENCES inbox_attachments (tenant_id, id),
            FOREIGN KEY (tenant_id, thread_id) REFERENCES inbox_threads (tenant_id, id),
            FOREIGN KEY (tenant_id, supersede_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX triage_decisions_by_attachment ON triage_decisions "
        "(tenant_id, attachment_id, created_at)"
    )
    tenant_table(op, "triage_decisions")

    op.execute(
        f"""
        CREATE TABLE inbox_sender_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            address_hmac text NOT NULL CHECK (address_hmac {_HEX64}),
            address_sealed bytea NOT NULL,
            client_id uuid NOT NULL,
            contact_id uuid NULL,
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            revoked_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX inbox_sender_rules_live ON inbox_sender_rules "
        "(tenant_id, address_hmac) WHERE revoked_at IS NULL"
    )
    tenant_table(op, "inbox_sender_rules")
    op.execute("REVOKE UPDATE, DELETE ON inbox_sender_rules FROM abacus_app")
    op.execute("GRANT UPDATE (revoked_at) ON inbox_sender_rules TO abacus_app")
    insert_columns(
        op,
        "inbox_sender_rules",
        ("tenant_id", "address_hmac", "address_sealed", "client_id", "contact_id", "created_by"),
    )

    op.execute(
        """
        CREATE TABLE inbox_attachment_flags (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            attachment_id uuid NOT NULL,
            run_no integer NOT NULL CHECK (run_no >= 1),
            kind text NOT NULL CHECK (kind IN
                ('duplicate_hash', 'wrong_year', 'tin_mismatch', 'possible_replacement',
                 'corrected_form', 'unreadable', 'low_confidence', 'ambiguous_candidates',
                 'duplicate_of_notice')),
            severity text NOT NULL CHECK (severity IN ('info', 'block_bulk', 'force_hold')),
            ref_evidence_version_id uuid NULL,
            facts jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(facts) = 'object' AND octet_length(facts::text) <= 2048),
            checker_version text NOT NULL CHECK (char_length(checker_version) BETWEEN 1 AND 40),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, attachment_id, run_no, kind),
            FOREIGN KEY (tenant_id, attachment_id) REFERENCES inbox_attachments (tenant_id, id),
            FOREIGN KEY (tenant_id, ref_evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "inbox_attachment_flags")

    for table in _INSERT_ONLY:
        _immutable(table)


def downgrade() -> None:
    for table in (
        "inbox_attachment_flags",
        "inbox_sender_rules",
        "triage_decisions",
        "inbox_attachments",
        "inbound_messages",
        "inbox_threads",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION intake_rows_immutable()")
