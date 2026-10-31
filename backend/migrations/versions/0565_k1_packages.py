"""K-1 package core (T-02-T20; T-02 §3.6, §5; DEC-78, DEC-88, DEC-52; DEC-1471). Expand-only.

Seven `tax` tables, every one tenant-scoped with forced RLS:

- `k1_recipients`: one partner, shareholder or beneficiary of an issuing return (`work_item_id`),
  by the engine's own reference; the TIN is its last four only (DEC-52), the address
  confidential.
- `k1_packages`: one recipient's K-1 set at a version. Status words are the registry's
  (`not_prepared`, `draft`, `released`, `viewed`, `downloaded`, `bounced`, `superseded`); a
  released-or-later package carries `released_at` (CHECK), and a corrected set after release is a
  new package naming the one it supersedes.
- `k1_package_events` (insert-only): what happened to a package.
- `k1_documents` (insert-only): the K-1, K-3, state K-1 and letter documents, each an evidence
  version; `is_draft` documents never reach the portal (DEC-78).
- `k1_box_lines` (insert-only, TRI): the import's box values when it carries them.
- `k1_handoffs`: a draft or final K-1 shared to another return's intake (DEC-88), with the copy
  filed there and the request it fulfilled.
- `recipient_details_changes`: a recipient's W-9, W-8 or address for a person to accept or reject
  (DV-10); decided once.

`engine_sync_events.kind` (0465) gains `k1_set`: the engine's K-1 set, uploaded through the bridge.

Revision ID: 0565
Revises: 0564
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_only, tenant_table

revision = "0565"
down_revision = "0564"
branch_labels = None
depends_on = None

_TABLES = (
    "recipient_details_changes",
    "k1_handoffs",
    "k1_box_lines",
    "k1_documents",
    "k1_package_events",
    "k1_packages",
    "k1_recipients",
)


_SYNC_KINDS = (
    "'export_generated', 'marked_exported', 'import_uploaded', 'import_approved', "
    "'import_rejected', 'diagnostics', 'pdfs', 'acks'"
)


def _sync_kinds(kinds: str) -> None:
    op.execute(
        """
        DO $$
        DECLARE c record;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'engine_sync_events'::regclass AND contype = 'c'
                       AND pg_get_constraintdef(oid) LIKE '%((kind = ANY%'
            LOOP
                EXECUTE format('ALTER TABLE engine_sync_events DROP CONSTRAINT %I', c.conname);
            END LOOP;
        END $$
        """
    )
    op.execute(
        "ALTER TABLE engine_sync_events ADD CONSTRAINT engine_sync_events_kind "
        f"CHECK (kind IN ({kinds}))"
    )


def upgrade() -> None:
    _sync_kinds(_SYNC_KINDS + ", 'k1_set'")
    op.execute(
        """
        CREATE TABLE k1_recipients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            engine_ref text NOT NULL CHECK (char_length(engine_ref) BETWEEN 1 AND 100),
            display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 200),
            recipient_kind text NOT NULL
                CHECK (recipient_kind IN ('gp', 'lp', 'shareholder', 'beneficiary')),
            is_entity boolean NOT NULL DEFAULT false,
            tin_last4 text NULL CHECK (tin_last4 ~ '^[0-9]{4}$'),
            tin_kind text NULL CHECK (tin_kind IN ('ssn', 'ein', 'itin')),
            address jsonb NULL CHECK (address IS NULL OR (jsonb_typeof(address) = 'object'
                AND octet_length(address::text) <= 1024)),
            contact_id uuid NULL,
            client_entity_id uuid NULL,
            ownership_note text NULL CHECK (char_length(ownership_note) <= 200),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, engine_ref),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE k1_packages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            recipient_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            form text NOT NULL CHECK (form IN ('1065', '1120s', '1041')),
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2000 AND 2100),
            period_start date NULL,
            period_end date NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('not_prepared', 'draft',
                'released', 'viewed', 'downloaded', 'bounced', 'superseded')),
            k3_status text NOT NULL DEFAULT 'not_included'
                CHECK (k3_status IN ('included', 'not_required', 'not_included')),
            state_codes text[] NOT NULL DEFAULT ARRAY[]::text[]
                CHECK (cardinality(state_codes) <= 60),
            is_final_set boolean NOT NULL DEFAULT false,
            source_import_id uuid NULL,
            released_at timestamptz NULL,
            released_by uuid NULL,
            release_grant_id uuid NULL,
            supersedes_package_id uuid NULL,
            delivery_channel text NOT NULL DEFAULT 'portal' CHECK (delivery_channel = 'portal'),
            delivery_contact_id uuid NULL,
            e_furnishing_consent text NOT NULL DEFAULT 'unknown'
                CHECK (e_furnishing_consent IN ('unknown', 'given', 'declined')),
            version_no integer NOT NULL CHECK (version_no >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, recipient_id, version_no),
            CHECK (status NOT IN ('released', 'viewed', 'downloaded', 'bounced')
                   OR released_at IS NOT NULL),
            FOREIGN KEY (tenant_id, recipient_id) REFERENCES k1_recipients (tenant_id, id),
            FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_package_id) REFERENCES k1_packages (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX k1_packages_by_return ON k1_packages (tenant_id, work_item_id, status)"
    )
    op.execute(
        """
        CREATE TABLE k1_package_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            package_id uuid NOT NULL,
            kind text NOT NULL CHECK (char_length(kind) BETWEEN 1 AND 60),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            facts jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(facts) = 'object' AND octet_length(facts::text) <= 1024),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, package_id) REFERENCES k1_packages (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE k1_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            package_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('k1', 'k3', 'state_k1', 'letter')),
            jurisdiction text NULL CHECK (jurisdiction ~ '^[A-Z]{2}$'),
            evidence_version_id uuid NOT NULL,
            is_draft boolean NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'state_k1') = (jurisdiction IS NOT NULL)),
            FOREIGN KEY (tenant_id, package_id) REFERENCES k1_packages (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE k1_box_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            package_id uuid NOT NULL,
            document_kind text NOT NULL CHECK (document_kind IN ('k1', 'k3', 'state_k1')),
            box_code text NOT NULL CHECK (char_length(box_code) BETWEEN 1 AND 20),
            description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 200),
            amount numeric(18, 2) NOT NULL,
            is_total boolean NOT NULL DEFAULT false,
            position integer NOT NULL CHECK (position >= 0),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, package_id, document_kind, position),
            FOREIGN KEY (tenant_id, package_id) REFERENCES k1_packages (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE k1_handoffs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            package_id uuid NOT NULL,
            target_work_item_id uuid NOT NULL,
            target_evidence_version_id uuid NULL,
            target_request_item_id uuid NULL,
            status text NOT NULL DEFAULT 'draft_shared'
                CHECK (status IN ('draft_shared', 'final_replaced', 'withdrawn')),
            shared_by uuid NOT NULL,
            shared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            replaced_at timestamptz NULL,
            final_values jsonb NULL CHECK (final_values IS NULL
                OR (jsonb_typeof(final_values) = 'object'
                    AND octet_length(final_values::text) <= 4096)),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, package_id, target_work_item_id),
            CHECK ((status = 'final_replaced') = (replaced_at IS NOT NULL)),
            FOREIGN KEY (tenant_id, package_id) REFERENCES k1_packages (tenant_id, id),
            FOREIGN KEY (tenant_id, target_work_item_id) REFERENCES work_items (tenant_id, id),
            FOREIGN KEY (tenant_id, shared_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE recipient_details_changes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            recipient_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('w9', 'w8', 'address')),
            evidence_version_id uuid NULL,
            address jsonb NULL CHECK (address IS NULL OR (jsonb_typeof(address) = 'object'
                AND octet_length(address::text) <= 1024)),
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'rejected')),
            submitted_by uuid NOT NULL,
            submitted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            reason text NULL CHECK (char_length(reason) <= 500),
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'address') = (address IS NOT NULL)),
            CHECK ((kind = 'address') OR evidence_version_id IS NOT NULL),
            CHECK ((status = 'pending') = (decided_by IS NULL AND decided_at IS NULL)),
            FOREIGN KEY (tenant_id, recipient_id) REFERENCES k1_recipients (tenant_id, id)
        )
        """
    )
    # A decision is a person's, once (DV-10).
    op.execute(
        """
        CREATE FUNCTION recipient_details_changes_decided() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF OLD.status <> 'pending' THEN
                RAISE EXCEPTION 'a details change is decided once'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.decided_by::text THEN
                RAISE EXCEPTION 'a details change is decided by a person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER recipient_details_changes_decided BEFORE UPDATE ON "
        "recipient_details_changes FOR EACH ROW EXECUTE FUNCTION "
        "recipient_details_changes_decided()"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in ("k1_package_events", "k1_documents", "k1_box_lines"):
        insert_only(op, table)
    op.execute("REVOKE UPDATE ON k1_recipients, k1_packages, k1_handoffs FROM abacus_app")
    op.execute(
        "GRANT UPDATE (display_name, recipient_kind, is_entity, tin_last4, tin_kind, address, "
        "ownership_note) ON k1_recipients TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (status, delivery_contact_id, e_furnishing_consent) "
        "ON k1_packages TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (status, replaced_at, final_values, target_evidence_version_id, "
        "target_request_item_id) ON k1_handoffs TO abacus_app"
    )
    op.execute(
        "REVOKE UPDATE ON recipient_details_changes FROM abacus_app; "
        "GRANT UPDATE (status, decided_by, decided_at, reason) "
        "ON recipient_details_changes TO abacus_app"
    )


def downgrade() -> None:
    _sync_kinds(_SYNC_KINDS)
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION recipient_details_changes_decided()")
