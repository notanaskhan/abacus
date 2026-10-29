"""Signatures v1: the C7 envelope tables (N-02-T07; N-02 §4.2 "T07"; P-38; DEC-816).

Twelve tables in `signatures`, every one tenant-scoped with forced RLS:

- `envelopes`: one signing request, numbered per firm ("E18") from `envelope_numbers`. `status`
  holds the registry's `envelope` codes; `purpose` C7's purposes. `sent_by`, `voided_by` and
  `imported_by` are human principals: a trigger refuses setting any of them unless the
  transaction's actor is a person (`app.actor_kind = 'human'`) and is that person
  (`app.actor_id`), the P-04 binding, checked only when the column changes so a later system
  update (a webhook's `viewed`) still passes. `voided` needs a reason.
- `envelope_documents`, `envelope_signers` (the registry's stored `envelope_signer` codes; at most
  three KBA failures), `envelope_fields` (PDF points).
- Insert-only (`REVOKE UPDATE, DELETE` plus a trigger that refuses UPDATE, DELETE and TRUNCATE for
  every role): `envelope_events` (identifiers and hashes only), `envelope_provider_calls` (W7
  request and response evidence), `signature_evidence` (one row per signer signature),
  `esign_disclosures` (versioned ERSD text, imported) and `esign_acceptances`.
- `envelope_policies`: the firm's floor per policy family and purpose; an e-file authorization
  policy keeps KBA, at most three attempts and the handwritten fallback (CHECK).
- `envelope_numbers`: the per-firm counter, row-locked at draft creation.
- `signing_sessions`: one embedded or redirect session, five minutes at most.

Classification (ADR-031): `message`, `decline_note`, `email_at_send`, `title`, `void_reason`
Confidential; `ip_sealed` Restricted (sealed bytes); `tri` marks a document carrying tax return
information (IRC §7216); everything else Internal. No data is inserted: the policy floor is
written at tenant provisioning and the ERSD text through an import, never by a migration.

Revision ID: 0292
Revises: 0340 (S12r R-01-T27; re-chained from 0291 for the S12-S14 batch)
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0292"
down_revision = "0340"
branch_labels = None
depends_on = None

_PURPOSES = (
    "engagement_letter",
    "consent_7216",
    "form_8879",
    "form_8879_pe",
    "form_8879_f",
    "form_2848",
    "form_8821",
    "rep_letter",
    "governance_letter",
    "notice_response",
    "confirmation_authorization",
    "system_description_approval",
    "other",
)
_ENVELOPE_STATUSES = (
    "draft",
    "sent",
    "viewed",
    "partially_signed",
    "completed",
    "declined",
    "expired",
    "voided",
)
_SIGNER_STATUSES = ("pending", "viewed", "signed", "declined", "verification_failed")
_INSERT_ONLY = (
    "envelope_events",
    "envelope_provider_calls",
    "signature_evidence",
    "esign_disclosures",
    "esign_acceptances",
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _immutable(table: str) -> None:
    insert_only(op, table)
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION signatures_rows_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        "FOR EACH STATEMENT EXECUTE FUNCTION signatures_rows_immutable()"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION signatures_rows_immutable() RETURNS trigger
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
        CREATE FUNCTION envelopes_human_actor() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            person text := current_setting('app.actor_id', true);
            human boolean := current_setting('app.actor_kind', true) = 'human';
        BEGIN
            IF NEW.sent_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.sent_by IS DISTINCT FROM OLD.sent_by)
               AND (NOT human OR NEW.sent_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is sent by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.voided_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.voided_by IS DISTINCT FROM OLD.voided_by)
               AND (NOT human OR NEW.voided_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is voided by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.imported_by IS NOT NULL
               AND (TG_OP = 'INSERT' OR NEW.imported_by IS DISTINCT FROM OLD.imported_by)
               AND (NOT human OR NEW.imported_by::text IS DISTINCT FROM person) THEN
                RAISE EXCEPTION 'an envelope is imported by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'UPDATE' AND (
                   NEW.number IS DISTINCT FROM OLD.number
                OR NEW.client_id IS DISTINCT FROM OLD.client_id
                OR NEW.provider IS DISTINCT FROM OLD.provider
                OR (OLD.imported_by IS NOT NULL
                    AND NEW.imported_by IS DISTINCT FROM OLD.imported_by)
                OR (OLD.sent_by IS NOT NULL AND NEW.sent_by IS DISTINCT FROM OLD.sent_by)
                OR (OLD.voided_by IS NOT NULL AND NEW.voided_by IS DISTINCT FROM OLD.voided_by)
                OR OLD.status IN ('completed', 'declined', 'expired', 'voided')
                   AND NEW.status IS DISTINCT FROM OLD.status) THEN
                RAISE EXCEPTION 'an envelope''s number, client, provider, actors and final status '
                    'do not change' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )

    op.execute(
        """
        CREATE TABLE envelope_numbers (
            tenant_id uuid PRIMARY KEY,
            next_value integer NOT NULL DEFAULT 1 CHECK (next_value >= 1)
        )
        """
    )
    tenant_table(op, "envelope_numbers")
    op.execute("REVOKE DELETE ON envelope_numbers FROM abacus_app")
    insert_columns(op, "envelope_numbers", ("tenant_id", "next_value"))
    op.execute("REVOKE UPDATE ON envelope_numbers FROM abacus_app")
    op.execute("GRANT UPDATE (next_value) ON envelope_numbers TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE envelopes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            number integer NOT NULL CHECK (number >= 1),
            purpose text NOT NULL CHECK (purpose IN ({_in(_PURPOSES)})),
            form_code text NULL CHECK (char_length(form_code) BETWEEN 1 AND 20),
            policy_family text NOT NULL CHECK (policy_family IN
                ('efile_authorization', 'engagement_letter', 'consent', 'general')),
            source_kind text NULL CHECK (char_length(source_kind) BETWEEN 1 AND 64),
            source_id uuid NULL,
            client_id uuid NOT NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            provider text NOT NULL CHECK (provider IN ('docusign', 'record', 'fake')),
            provider_envelope_id text NULL CHECK (char_length(provider_envelope_id) <= 200),
            provider_name text NULL CHECK (char_length(provider_name) BETWEEN 1 AND 100),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ({_in(_ENVELOPE_STATUSES)})),
            signer_order text NOT NULL DEFAULT 'sequential'
                CHECK (signer_order IN ('sequential', 'parallel')),
            date_as_of_mode text NOT NULL DEFAULT 'none'
                CHECK (date_as_of_mode IN ('none', 'fixed_date', 'report_date')),
            date_as_of date NULL,
            due_on date NULL,
            expires_at timestamptz NULL,
            channel text NOT NULL DEFAULT 'portal_email' CHECK (channel IN ('portal_email')),
            message text NULL CHECK (char_length(message) <= 4000),
            reminder_cadence text NULL CHECK (char_length(reminder_cadence) <= 32),
            retention_record_type text NULL CHECK (char_length(retention_record_type) <= 64),
            retention_folder_ref text NULL CHECK (char_length(retention_folder_ref) <= 200),
            gate_kind text NULL CHECK (char_length(gate_kind) <= 64),
            gate_target_ref uuid NULL,
            drafted_by_kind text NOT NULL CHECK (drafted_by_kind IN ('human', 'agent', 'system')),
            drafted_by uuid NULL,
            drafted_via_run_id uuid NULL,
            sent_by uuid NULL,
            sent_at timestamptz NULL,
            voided_by uuid NULL,
            voided_at timestamptz NULL,
            void_reason text NULL CHECK (void_reason IN
                ('wrong_document', 'wrong_signer', 'replaced', 'client_request', 'other')),
            imported_by uuid NULL,
            completed_at timestamptz NULL,
            superseded_at timestamptz NULL,
            superseded_reason text NULL CHECK (char_length(superseded_reason) <= 200),
            superseded_binding_ref text NULL CHECK (char_length(superseded_binding_ref) <= 200),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, number),
            CHECK (status <> 'voided' OR (void_reason IS NOT NULL AND voided_by IS NOT NULL
                                          AND voided_at IS NOT NULL)),
            CHECK (status <> 'completed' OR completed_at IS NOT NULL),
            CHECK ((sent_by IS NULL) = (sent_at IS NULL)),
            CHECK (provider <> 'record'
                   OR (imported_by IS NOT NULL AND provider_name IS NOT NULL)),
            CHECK (purpose NOT LIKE 'form_8879%' OR policy_family = 'efile_authorization'),
            CHECK (date_as_of_mode <> 'fixed_date' OR date_as_of IS NOT NULL),
            CHECK (drafted_by_kind <> 'agent' OR drafted_via_run_id IS NOT NULL),
            CHECK ((source_kind IS NULL) = (source_id IS NULL)),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id),
            FOREIGN KEY (tenant_id, sent_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, voided_by) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX envelopes_by_status ON envelopes (tenant_id, status, due_on)")
    op.execute("CREATE INDEX envelopes_by_client ON envelopes (tenant_id, client_id)")
    op.execute(
        "CREATE INDEX envelopes_by_source ON envelopes (tenant_id, source_kind, source_id) "
        "WHERE source_kind IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX envelopes_provider_id ON envelopes "
        "(tenant_id, provider, provider_envelope_id) WHERE provider_envelope_id IS NOT NULL"
    )
    tenant_table(op, "envelopes")
    op.execute("REVOKE DELETE ON envelopes FROM abacus_app")
    op.execute(
        "CREATE TRIGGER envelopes_human_actor BEFORE INSERT OR UPDATE ON envelopes "
        "FOR EACH ROW EXECUTE FUNCTION envelopes_human_actor()"
    )

    op.execute(
        """
        CREATE TABLE envelope_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            "order" smallint NOT NULL CHECK ("order" BETWEEN 1 AND 50),
            evidence_version_id uuid NULL,
            generated_document_version_id uuid NULL,
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            page_count smallint NULL CHECK (page_count BETWEEN 1 AND 2000),
            signer_visible boolean NOT NULL DEFAULT true,
            read_only boolean NOT NULL DEFAULT false,
            watermark text NULL CHECK (char_length(watermark) <= 64),
            source_ref text NULL CHECK (char_length(source_ref) <= 200),
            placement text NOT NULL DEFAULT 'anchors'
                CHECK (placement IN ('anchors', 'coordinates')),
            tri boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (envelope_id, "order"),
            CHECK ((evidence_version_id IS NULL) <> (generated_document_version_id IS NULL)),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    tenant_table(op, "envelope_documents")
    op.execute("REVOKE DELETE ON envelope_documents FROM abacus_app")

    op.execute(
        f"""
        CREATE TABLE envelope_signers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            "order" smallint NOT NULL CHECK ("order" BETWEEN 1 AND 20),
            routing_group smallint NOT NULL DEFAULT 1 CHECK (routing_group BETWEEN 1 AND 20),
            party_kind text NOT NULL CHECK (party_kind IN ('contact', 'user')),
            contact_id uuid NULL,
            user_id uuid NULL,
            role text NOT NULL DEFAULT 'signer' CHECK (role IN ('signer', 'countersigner', 'ero')),
            identity_method text NOT NULL
                CHECK (identity_method IN ('kba', 'email_code', 'in_person_id', 'firm_sso')),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ({_in(_SIGNER_STATUSES)})),
            kba_failures smallint NOT NULL DEFAULT 0 CHECK (kba_failures BETWEEN 0 AND 3),
            viewed_at timestamptz NULL,
            last_page_seen smallint NULL CHECK (last_page_seen >= 1),
            signed_at timestamptz NULL,
            signature_method text NULL
                CHECK (signature_method IN ('typed', 'drawn', 'provider_adopted', 'handwritten')),
            decline_reason text NULL CHECK (decline_reason IN
                ('have_questions', 'something_wrong', 'someone_else_should_sign', 'other')),
            decline_note text NULL CHECK (char_length(decline_note) <= 2000),
            provider_recipient_id text NULL CHECK (char_length(provider_recipient_id) <= 200),
            email_at_send text NULL CHECK (char_length(email_at_send) <= 320),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (envelope_id, "order"),
            CHECK ((party_kind = 'contact' AND contact_id IS NOT NULL AND user_id IS NULL)
                OR (party_kind = 'user' AND user_id IS NOT NULL AND contact_id IS NULL)),
            CHECK (status <> 'signed' OR (signed_at IS NOT NULL AND signature_method IS NOT NULL)),
            CHECK (status <> 'declined' OR decline_reason IS NOT NULL),
            CHECK (status <> 'verification_failed' OR kba_failures = 3),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "envelope_signers")
    op.execute("REVOKE DELETE ON envelope_signers FROM abacus_app")

    op.execute(
        """
        CREATE TABLE envelope_fields (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_document_id uuid NOT NULL,
            signer_id uuid NOT NULL,
            kind text NOT NULL
                CHECK (kind IN ('signature', 'date', 'pin', 'initial', 'title_prefill')),
            page smallint NULL CHECK (page >= 1),
            x numeric(8, 2) NULL CHECK (x >= 0),
            y numeric(8, 2) NULL CHECK (y >= 0),
            w numeric(8, 2) NULL CHECK (w > 0),
            h numeric(8, 2) NULL CHECK (h > 0),
            anchor text NULL CHECK (char_length(anchor) <= 100),
            UNIQUE (tenant_id, id),
            CHECK (anchor IS NOT NULL
                OR (page IS NOT NULL AND x IS NOT NULL AND y IS NOT NULL
                    AND w IS NOT NULL AND h IS NOT NULL)),
            FOREIGN KEY (tenant_id, envelope_document_id)
                REFERENCES envelope_documents (tenant_id, id),
            FOREIGN KEY (tenant_id, signer_id) REFERENCES envelope_signers (tenant_id, id)
        )
        """
    )
    tenant_table(op, "envelope_fields")

    op.execute(
        """
        CREATE TABLE envelope_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            signer_id uuid NULL,
            kind text NOT NULL CHECK (kind ~ '^[a-z][a-z_.]{1,63}$'),
            source text NOT NULL
                CHECK (source IN
                    ('firm', 'portal', 'provider_webhook', 'provider_poll', 'system')),
            provider_event_id text NULL CHECK (char_length(provider_event_id) <= 200),
            occurred_at timestamptz NOT NULL,
            payload_sha256 text NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, signer_id) REFERENCES envelope_signers (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX envelope_events_provider_event ON envelope_events "
        "(tenant_id, provider_event_id) WHERE provider_event_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX envelope_events_by_envelope ON envelope_events "
        "(tenant_id, envelope_id, occurred_at)"
    )
    tenant_table(op, "envelope_events")

    op.execute(
        """
        CREATE TABLE envelope_provider_calls (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            operation text NOT NULL CHECK (operation ~ '^[a-z][a-z_]{1,39}$'),
            idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 255),
            request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
            response_sha256 text NULL CHECK (response_sha256 ~ '^[0-9a-f]{64}$'),
            object_key text NULL CHECK (char_length(object_key) <= 512),
            status_code smallint NULL CHECK (status_code BETWEEN 100 AND 599),
            approval_grant_id uuid NULL,
            called_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, operation, idempotency_key),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, approval_grant_id) REFERENCES approval_grants (tenant_id, id)
        )
        """
    )
    tenant_table(op, "envelope_provider_calls")

    op.execute(
        """
        CREATE TABLE signature_evidence (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            signer_id uuid NOT NULL,
            signed_at timestamptz NOT NULL,
            ip_sealed bytea NULL,
            ip_masked text NULL CHECK (char_length(ip_masked) <= 64),
            login_ref text NULL CHECK (char_length(login_ref) <= 400),
            user_agent_family text NULL CHECK (char_length(user_agent_family) <= 64),
            device_label text NULL CHECK (char_length(device_label) <= 64),
            identity_result text NOT NULL CHECK (char_length(identity_result) BETWEEN 1 AND 200),
            signature_method text NOT NULL
                CHECK (signature_method IN ('typed', 'drawn', 'provider_adopted', 'handwritten')),
            signed_image_key text NULL CHECK (char_length(signed_image_key) <= 512),
            document_sha256s text[] NOT NULL
                CHECK (cardinality(document_sha256s) BETWEEN 1 AND 50),
            package_key text NULL CHECK (char_length(package_key) <= 512),
            package_sha256 text NULL CHECK (package_sha256 ~ '^[0-9a-f]{64}$'),
            retain_until date NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, signer_id),
            CHECK ((package_key IS NULL) = (package_sha256 IS NULL)),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, signer_id) REFERENCES envelope_signers (tenant_id, id)
        )
        """
    )
    tenant_table(op, "signature_evidence")

    op.execute(
        """
        CREATE TABLE envelope_policies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            policy_family text NOT NULL CHECK (policy_family IN
                ('efile_authorization', 'engagement_letter', 'consent', 'general')),
            purpose text NULL,
            allowed_identity_methods text[] NOT NULL
                CHECK (cardinality(allowed_identity_methods) BETWEEN 1 AND 4
                       AND allowed_identity_methods
                           <@ ARRAY['kba', 'email_code', 'in_person_id', 'firm_sso']),
            default_identity_method text NOT NULL,
            kba_max_attempts smallint NOT NULL DEFAULT 3 CHECK (kba_max_attempts BETWEEN 1 AND 3),
            failure_path text NOT NULL DEFAULT 'wet_signature'
                CHECK (failure_path IN ('wet_signature')),
            reminder_cadences text[] NOT NULL DEFAULT ARRAY[]::text[]
                CHECK (cardinality(reminder_cadences) <= 8),
            max_reminders smallint NOT NULL DEFAULT 3 CHECK (max_reminders BETWEEN 0 AND 10),
            default_expiry_days smallint NOT NULL DEFAULT 30
                CHECK (default_expiry_days BETWEEN 1 AND 120),
            countersign_required boolean NOT NULL DEFAULT false,
            date_as_of_rule text NOT NULL DEFAULT 'none'
                CHECK (date_as_of_rule IN ('none', 'fixed_date', 'report_date')),
            retention_record_type text NULL CHECK (char_length(retention_record_type) <= 64),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_by uuid NULL,
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (default_identity_method = ANY (allowed_identity_methods)),
            CHECK (policy_family <> 'efile_authorization'
                OR ('kba' = ANY (allowed_identity_methods) AND kba_max_attempts <= 3
                    AND failure_path = 'wet_signature')),
            FOREIGN KEY (tenant_id, updated_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX envelope_policies_scope ON envelope_policies "
        "(tenant_id, policy_family, coalesce(purpose, ''))"
    )
    tenant_table(op, "envelope_policies")
    op.execute("REVOKE DELETE ON envelope_policies FROM abacus_app")

    op.execute(
        """
        CREATE TABLE signing_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            signer_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            presentation text NOT NULL CHECK (presentation IN ('iframe', 'redirect')),
            issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            return_token_hash text NOT NULL CHECK (return_token_hash ~ '^[0-9a-f]{64}$'),
            state text NOT NULL DEFAULT 'issued'
                CHECK (state IN ('issued', 'returned', 'confirmed', 'abandoned')),
            UNIQUE (tenant_id, id),
            CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '5 minutes'),
            FOREIGN KEY (tenant_id, envelope_id) REFERENCES envelopes (tenant_id, id),
            FOREIGN KEY (tenant_id, signer_id) REFERENCES envelope_signers (tenant_id, id)
        )
        """
    )
    tenant_table(op, "signing_sessions")
    op.execute("REVOKE DELETE ON signing_sessions FROM abacus_app")
    insert_columns(
        op,
        "signing_sessions",
        (
            "tenant_id",
            "envelope_id",
            "signer_id",
            "principal_id",
            "presentation",
            "expires_at",
            "return_token_hash",
        ),
    )
    op.execute("REVOKE UPDATE ON signing_sessions FROM abacus_app")
    op.execute("GRANT UPDATE (state) ON signing_sessions TO abacus_app")

    op.execute(
        """
        CREATE TABLE esign_disclosures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 50000),
            body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
            imported_by uuid NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_no),
            FOREIGN KEY (tenant_id, imported_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "esign_disclosures")

    op.execute(
        """
        CREATE TABLE esign_acceptances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            signer_id uuid NOT NULL,
            disclosure_version_id uuid NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            ip_sealed bytea NULL,
            user_agent_family text NULL CHECK (char_length(user_agent_family) <= 64),
            UNIQUE (tenant_id, signer_id, disclosure_version_id),
            FOREIGN KEY (tenant_id, signer_id) REFERENCES envelope_signers (tenant_id, id),
            FOREIGN KEY (tenant_id, disclosure_version_id)
                REFERENCES esign_disclosures (tenant_id, id)
        )
        """
    )
    tenant_table(op, "esign_acceptances")

    for table in _INSERT_ONLY:
        _immutable(table)


def downgrade() -> None:
    for table in (
        "esign_acceptances",
        "esign_disclosures",
        "signing_sessions",
        "envelope_policies",
        "signature_evidence",
        "envelope_provider_calls",
        "envelope_events",
        "envelope_fields",
        "envelope_signers",
        "envelope_documents",
        "envelopes",
        "envelope_numbers",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION envelopes_human_actor()")
    op.execute("DROP FUNCTION signatures_rows_immutable()")
