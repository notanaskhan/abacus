"""A-07 M1: EQR and completion (A-07-T07; A-07 §4.2 M1; AUD-18, AUD-19, AUD-24; DEC-2232;
expand-only).

On the assurance work item, tenant-scoped with forced RLS:
- `eqr_reviews` (one per work item), `eqr_checklist_items` and `eqr_digest_cards`: the EQR's
  review, its checklist from the firm template, and code-built cards whose content never
  changes (only the reviewed and superseded columns move; a person marks a card reviewed).
- `eqr_concurrences` (0077) gains the work-item columns: a v2 concurrence names its review, the
  checklist snapshot, the cleared-notes count and the fresh second factor, one per review, and
  its actor is the transaction's own (`app.actor_kind`, `app.actor_id`) and human. 0077's
  engagement rows stay valid (DEC-2261).
- `completion_items` (the AUD-19 projection; not applicable needs a basis),
  `subsequent_event_procedures`, insert-only `subsequent_events`, `legal_letters` (not
  applicable exactly when a basis is held), `going_concern_evaluations` (code's inputs; the
  conclusion is the decided card's) and `filings` (`filed` needs the date and the evidence).
- The assurance phases `archiving` and `archived` are already in 0134's CHECK.
- `eqr.concurred` and `eqr.card_reviewed` join the human-only audit actions.

Text that carries client facts is sealed (`*_sealed`, ADR-031). The downgrade drops the new
tables and columns and restores 0662's human-only list.

Revision ID: 0664
Revises: 0663
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0664"
down_revision = "0663"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_SHA = "~ '^[0-9a-f]{64}$'"
_STAMPS = """
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),"""
# The row is the transaction's own actor's, and a person's (0642's rule; ADR-005).
_HUMAN_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_HUMAN_TRANSACTION = (
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_TABLES = (
    "eqr_reviews",
    "eqr_checklist_items",
    "eqr_digest_cards",
    "completion_items",
    "subsequent_event_procedures",
    "subsequent_events",
    "legal_letters",
    "going_concern_evaluations",
    "filings",
)
INSERTS: dict[str, tuple[str, ...]] = {
    "eqr_reviews": (
        "tenant_id", "engagement_id", "work_item_id", "eqr_user_id", "assignment_ref",
        "eligibility_snapshot", "status",
    ),
    "eqr_checklist_items": (
        "tenant_id", "engagement_id", "work_item_id", "eqr_review_id", "item_key",
        "template_version_id", "position", "status", "sub_line", "updated_by",
    ),
    "eqr_digest_cards": (
        "tenant_id", "engagement_id", "work_item_id", "eqr_review_id", "source_kind",
        "source_ref", "title", "snapshot", "snapshot_sha256", "citation_ids", "built_by_run_id",
    ),
    "completion_items": (
        "tenant_id", "engagement_id", "work_item_id", "item_key", "template_version_id",
        "position", "status", "derived", "evidence_text", "link_target", "gate_tag",
        "depends_on_client", "due_on", "na_basis_sealed", "na_by", "last_event_id",
    ),
    "subsequent_event_procedures": (
        "tenant_id", "engagement_id", "work_item_id", "procedure_key", "performed_through",
        "performed_by", "status", "run_id",
    ),
    "subsequent_events": (
        "tenant_id", "engagement_id", "work_item_id", "description_sealed", "recognition",
        "fs_effect_sealed", "note_ref", "citation_ids", "recorded_by", "actor_kind", "actor_id",
    ),
    "legal_letters": (
        "tenant_id", "engagement_id", "work_item_id", "not_applicable", "basis_sealed",
        "request_item_id", "status",
    ),
    "going_concern_evaluations": (
        "tenant_id", "engagement_id", "work_item_id", "decision_card_id", "inputs",
        "engine_version", "inputs_hash",
    ),
    "filings": (
        "tenant_id", "engagement_id", "work_item_id", "form", "filer_name", "preparer_name",
        "channel", "due_on", "extended_due_on", "status", "filed_on", "ack_evidence_version_id",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "eqr_reviews": ("eligibility_snapshot", "status", "version", "updated_at"),
    "eqr_checklist_items": ("status", "sub_line", "updated_by", "version", "updated_at"),
    "eqr_digest_cards": ("reviewed_at", "reviewed_by", "reviewed_actor_kind", "superseded_by"),
    "completion_items": (
        "status", "derived", "evidence_text", "link_target", "gate_tag", "depends_on_client",
        "due_on", "na_basis_sealed", "na_by", "last_event_id", "version", "updated_at",
    ),
    "subsequent_event_procedures": (
        "performed_through", "performed_by", "status", "run_id", "version", "updated_at",
    ),
    "legal_letters": (
        "not_applicable", "basis_sealed", "request_item_id", "status", "version", "updated_at",
    ),
    "going_concern_evaluations": (
        "decision_card_id", "inputs", "engine_version", "inputs_hash", "version", "updated_at",
    ),
    "filings": (
        "due_on", "extended_due_on", "status", "filed_on", "ack_evidence_version_id", "version",
        "updated_at",
    ),
}  # fmt: skip
_CONCURRENCE_0077 = (
    "tenant_id", "engagement_id", "digest_hash", "not_involved", "concurred_by", "actor_kind",
)  # fmt: skip
_CONCURRENCE_V2 = (
    "work_item_id", "eqr_review_id", "concurrence_date", "checklist_snapshot_sha256",
    "notes_cleared_count", "mfa_verified_at", "actor_id",
)  # fmt: skip

_IMMUTABLE = """
    CREATE FUNCTION a07_rows_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
    BEGIN
        RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
    END $$
"""
_BEFORE = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "attribute_result.marked",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "deficiency.concluded",
    "delivery_packet.approved",
    "efile_ack.recorded",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fraud_minutes.approved",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "letter.approved",
    "materiality.decided",
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "return.delivered",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "schedule_k_release.requested",
    "schedule_k_release.undone",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "sum.concluded",
    "team.approved",
    "transmission.recorded",
]
_HUMAN_ONLY = sorted([*_BEFORE, "eqr.card_reviewed", "eqr.concurred"])


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE eqr_reviews (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            eqr_user_id uuid NOT NULL,
            assignment_ref uuid NULL,
            eligibility_snapshot jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(eligibility_snapshot) = 'object'),
            status text NOT NULL DEFAULT 'in_progress'
                CHECK (status IN ('in_progress', 'concurred')),{_STAMPS}
            UNIQUE (tenant_id, id),
            CONSTRAINT eqr_reviews_one_per_work_item UNIQUE (tenant_id, work_item_id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE eqr_checklist_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            eqr_review_id uuid NOT NULL,
            item_key text NOT NULL CHECK (item_key ~ '^[a-z0-9_]{{1,60}}$'),
            template_version_id uuid NULL,
            position integer NOT NULL CHECK (position >= 1),
            status text NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'partial', 'done')),
            sub_line text NULL CHECK (char_length(sub_line) <= 280),
            updated_by uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, eqr_review_id, item_key),
            FOREIGN KEY (tenant_id, eqr_review_id)
                REFERENCES eqr_reviews (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE eqr_digest_cards (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            eqr_review_id uuid NOT NULL,
            source_kind text NOT NULL CHECK (source_kind IN ('decision', 'conclusion')),
            source_ref text NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 120),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'array'),
            snapshot_sha256 text NOT NULL CHECK (snapshot_sha256 {_SHA}),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(citation_ids) <= 50),
            built_by_run_id uuid NULL,
            reviewed_at timestamptz NULL,
            reviewed_by uuid NULL,
            reviewed_actor_kind text NULL,
            superseded_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT eqr_digest_cards_reviewed_by_a_person CHECK (reviewed_at IS NULL
                OR (reviewed_by IS NOT NULL AND reviewed_actor_kind = 'human')),
            FOREIGN KEY (tenant_id, eqr_review_id) REFERENCES eqr_reviews (tenant_id, id),
            FOREIGN KEY (tenant_id, superseded_by)
                REFERENCES eqr_digest_cards (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE completion_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            item_key text NOT NULL CHECK (item_key ~ '^[a-z0-9_]{{1,60}}$'),
            template_version_id uuid NULL,
            position integer NOT NULL CHECK (position >= 1),
            status text NOT NULL DEFAULT 'open'
                CHECK (status IN ('done', 'open', 'not_applicable', 'partial')),
            derived boolean NOT NULL DEFAULT true,
            evidence_text text NULL CHECK (char_length(evidence_text) <= 500),
            link_target text NULL CHECK (char_length(link_target) <= 300),
            gate_tag text NULL CHECK (gate_tag ~ '^G[1-9]$'),
            depends_on_client boolean NOT NULL DEFAULT false,
            due_on date NULL,
            na_basis_sealed bytea NULL,
            na_by uuid NULL,
            last_event_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, item_key),
            CONSTRAINT completion_items_na_has_basis
                CHECK (status <> 'not_applicable'
                    OR (na_basis_sealed IS NOT NULL AND na_by IS NOT NULL)),
            CONSTRAINT completion_items_na_is_manual
                CHECK (status <> 'not_applicable' OR NOT derived),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE subsequent_event_procedures (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            procedure_key text NOT NULL CHECK (procedure_key ~ '^[a-z0-9_]{{1,80}}$'),
            performed_through date NULL,
            performed_by uuid NULL,
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'performed')),
            run_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, procedure_key),
            CHECK (status <> 'performed'
                OR (performed_through IS NOT NULL AND performed_by IS NOT NULL)),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE subsequent_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            description_sealed bytea NOT NULL,
            recognition text NOT NULL CHECK (recognition IN ('recognized', 'nonrecognized')),
            fs_effect_sealed bytea NULL,
            note_ref text NULL CHECK (char_length(note_ref) <= 40),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(citation_ids) <= 20),
            recorded_by uuid NOT NULL,
            {_HUMAN_ACTOR},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CONSTRAINT subsequent_events_recorded_by_a_person {_HUMAN_TRANSACTION},{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE legal_letters (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            not_applicable boolean NOT NULL DEFAULT false,
            basis_sealed bytea NULL,
            request_item_id uuid NULL,
            status text NULL
                CHECK (status IN ('not_applicable', 'requested', 'received')),{_STAMPS}
            UNIQUE (tenant_id, id),
            CONSTRAINT legal_letters_one_per_work_item UNIQUE (tenant_id, work_item_id),
            CONSTRAINT legal_letters_na_has_basis
                CHECK (not_applicable = (basis_sealed IS NOT NULL)),
            CHECK ((status = 'not_applicable') = not_applicable OR status IS NULL),
            CHECK (status NOT IN ('requested', 'received')
                OR request_item_id IS NOT NULL),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE going_concern_evaluations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            decision_card_id uuid NULL,
            inputs jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(inputs) = 'object'),
            engine_version text NULL CHECK (char_length(engine_version) <= 40),
            inputs_hash text NULL CHECK (inputs_hash {_SHA}),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id),
            CHECK (inputs = '{{}}'::jsonb OR inputs_hash IS NOT NULL),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE filings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            form text NOT NULL CHECK (form IN ('form_5500')),
            filer_name text NOT NULL CHECK (char_length(filer_name) BETWEEN 1 AND 200),
            preparer_name text NULL CHECK (char_length(preparer_name) <= 200),
            channel text NOT NULL DEFAULT 'efast2' CHECK (channel IN ('efast2')),
            due_on date NULL,
            extended_due_on date NULL,
            status text NOT NULL DEFAULT 'awaiting_client_filing'
                CHECK (status IN ('awaiting_client_filing', 'filed')),
            filed_on date NULL,
            ack_evidence_version_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, form),
            CONSTRAINT filings_filed_has_evidence CHECK (status <> 'filed'
                OR (filed_on IS NOT NULL AND ack_evidence_version_id IS NOT NULL)),
            CHECK (extended_due_on IS NULL OR due_on IS NULL OR extended_due_on >= due_on),
            FOREIGN KEY (tenant_id, ack_evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )


def _extend_concurrences() -> None:
    op.execute(
        f"""
        ALTER TABLE eqr_concurrences
            ADD COLUMN work_item_id uuid NULL,
            ADD COLUMN eqr_review_id uuid NULL,
            ADD COLUMN concurrence_date date NULL,
            ADD COLUMN checklist_snapshot_sha256 text NULL
                CHECK (checklist_snapshot_sha256 {_SHA}),
            ADD COLUMN notes_cleared_count integer NULL CHECK (notes_cleared_count >= 0),
            ADD COLUMN mfa_verified_at timestamptz NULL,
            ADD COLUMN actor_id text NULL DEFAULT current_setting('app.actor_id', true),
            ADD CONSTRAINT eqr_concurrences_one_per_review UNIQUE (tenant_id, eqr_review_id),
            ADD CONSTRAINT eqr_concurrences_v2_complete CHECK (eqr_review_id IS NULL OR (
                work_item_id IS NOT NULL AND concurrence_date IS NOT NULL
                AND checklist_snapshot_sha256 IS NOT NULL AND notes_cleared_count IS NOT NULL
                AND mfa_verified_at IS NOT NULL)),
            ADD CONSTRAINT eqr_concurrences_v2_transaction_actor CHECK (eqr_review_id IS NULL OR (
                actor_kind = current_setting('app.actor_kind', true)
                AND actor_id = current_setting('app.actor_id', true))),
            ADD CONSTRAINT eqr_concurrences_work_item
                FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            ADD CONSTRAINT eqr_concurrences_review FOREIGN KEY (tenant_id, eqr_review_id)
                REFERENCES eqr_reviews (tenant_id, id)
        """
    )
    # insert_columns revokes the table's INSERT first, which drops 0077's column grants too, so
    # the full list is granted again: 0077's record-mode columns and the v2 ones.
    insert_columns(op, "eqr_concurrences", (*_CONCURRENCE_0077, *_CONCURRENCE_V2))


def upgrade() -> None:
    _create_tables()
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        if table in UPDATES:
            op.execute(f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON {table} TO abacus_app")
    insert_only(op, "subsequent_events")
    op.execute(_IMMUTABLE)
    op.execute("REVOKE ALL ON FUNCTION a07_rows_immutable() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER subsequent_events_immutable BEFORE UPDATE OR DELETE ON subsequent_events "
        "FOR EACH ROW EXECUTE FUNCTION a07_rows_immutable()"
    )
    op.execute(
        "CREATE TRIGGER subsequent_events_no_truncate BEFORE TRUNCATE ON subsequent_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION a07_rows_immutable()"
    )
    op.execute(
        "CREATE INDEX eqr_digest_cards_review ON eqr_digest_cards (tenant_id, eqr_review_id) "
        "WHERE superseded_by IS NULL"
    )
    op.execute(
        "CREATE INDEX completion_items_open ON completion_items (tenant_id, work_item_id) "
        "WHERE status IN ('open', 'partial')"
    )
    _extend_concurrences()
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute(
        "ALTER TABLE eqr_concurrences "
        "DROP CONSTRAINT eqr_concurrences_review, DROP CONSTRAINT eqr_concurrences_work_item, "
        "DROP CONSTRAINT eqr_concurrences_v2_transaction_actor, "
        "DROP CONSTRAINT eqr_concurrences_v2_complete, "
        "DROP CONSTRAINT eqr_concurrences_one_per_review, "
        + ", ".join(f"DROP COLUMN {c}" for c in _CONCURRENCE_V2)
    )
    insert_columns(op, "eqr_concurrences", _CONCURRENCE_0077)
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION a07_rows_immutable()")
