"""A-07 M2: letters, report and release (A-07-T08; A-07 §4.2 M2; AUD-21 to AUD-24; DEC-2302;
expand-only).

On the assurance work item, tenant-scoped with forced RLS:
- `representation_letters` (one per work item), insert-only `representation_letter_versions` and
  human-only `representation_letter_approvals`.
- `governance_communications` (the AU-C 260, 265 and 703 letters), insert-only
  `governance_communication_versions`, human-only `governance_communication_sends`,
  `governance_recipients` and insert-only `governance_acknowledgements`.
- `audit_reports` (one per work item), insert-only `audit_report_versions`, and insert-only
  human-only `report_releases`: **one original release per work item**, enforced by the database;
  a reissue names the release it reissues. Status columns on the parents are projections, moved
  by the service; the versions, approvals, sends and releases never change.

A row's actor is the transaction's own (`app.actor_kind`, `app.actor_id`) and a person
(0642's rule; ADR-005). Text that carries client facts is sealed (`*_sealed`, ADR-031). G8 is
`report_releases`; 0077's `releases` stays for its engagement rows (DEC-2302).

Revision ID: 0668
Revises: 0667
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0668"
down_revision = "0667"
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
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
# The row is the transaction's own actor's, and a person's (0642's rule; ADR-005).
_ACTOR = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true)"
)
_HUMAN = (
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true))"
)
_TABLES = (
    "representation_letters",
    "representation_letter_versions",
    "representation_letter_approvals",
    "governance_communications",
    "governance_communication_versions",
    "governance_communication_sends",
    "governance_recipients",
    "governance_acknowledgements",
    "audit_reports",
    "audit_report_versions",
    "report_releases",
)
_SCOPED = ("tenant_id", "engagement_id", "work_item_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "representation_letters": (
        *_SCOPED, "template_id", "status", "current_version_id", "envelope_id", "dated_as_of",
    ),
    "representation_letter_versions": (
        *_SCOPED, "letter_id", "version_no", "template_version_id", "representations",
        "edited_paragraphs_sealed", "sum_snapshot_id", "content_hash", "drafted_by_run_id",
        "created_by", "generated_document_id",
    ),
    "representation_letter_approvals": (
        *_SCOPED, "version_id", "approved_by", "seen_hash", "mfa_verified_at",
        "actor_kind", "actor_id",
    ),
    "governance_communications": (
        *_SCOPED, "kind", "standard", "combined_with_id", "due_rule", "due_on", "status",
        "current_version_id", "channel", "envelope_id",
    ),
    "governance_communication_versions": (
        *_SCOPED, "communication_id", "version_no", "template_version_id", "sections_sealed",
        "section_refs", "content_hash", "drafted_by_run_id", "created_by",
        "generated_document_id",
    ),
    "governance_communication_sends": (
        *_SCOPED, "version_id", "sent_by", "governance_body_id", "recipient_contact_ids",
        "channel", "approval_grant_id", "mfa_verified_at", "actor_kind", "actor_id",
    ),
    "governance_recipients": (*_SCOPED, "governance_body_id", "ack_required"),
    "governance_acknowledgements": (
        *_SCOPED, "communication_id", "version_id", "acknowledged_by_contact_id",
        "acknowledged_at", "channel",
    ),
    "audit_reports": (
        *_SCOPED, "report_kind", "framework", "standards_set_id", "template_id", "status",
        "current_version_id", "report_date", "city",
    ),
    "audit_report_versions": (
        *_SCOPED, "report_id", "version_no", "choices", "paragraphs", "report_date", "city",
        "dual_date", "reissue_of_release_id", "content_hash", "created_by",
    ),
    "report_releases": (
        *_SCOPED, "kind", "reissue_of_id", "report_version_id", "report_version_hash",
        "released_by", "released_at", "report_date", "city", "gate_snapshot",
        "gate_snapshot_sha256", "final_document_version_id", "deliverable_ids",
        "approval_grant_id", "idempotency_key", "actor_kind", "actor_id",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "representation_letters": (
        "status", "current_version_id", "envelope_id", "dated_as_of", "signed_on", "g7_met_at",
        "version", "updated_at",
    ),
    "governance_communications": (
        "combined_with_id", "due_rule", "due_on", "status", "current_version_id", "channel",
        "envelope_id", "version", "updated_at",
    ),
    "governance_recipients": ("ack_required", "version", "updated_at"),
    "audit_reports": (
        "status", "current_version_id", "report_date", "city", "version", "updated_at",
    ),
}  # fmt: skip
_INSERT_ONLY = tuple(t for t in _TABLES if t not in UPDATES)
# 0664's list, plus this migration's human-only audit actions.
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
    "eqr.card_reviewed",
    "eqr.concurred",
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
_HUMAN_ONLY = sorted(
    {*_BEFORE, "governance_communication.sent", "report.reissued", "report.released"}
    | {"rep_letter.approved"}
)


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def _create_letters() -> None:
    op.execute(
        f"""
        CREATE TABLE representation_letters (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            template_id uuid NULL,
            status text NOT NULL DEFAULT 'drafting' CHECK (status IN ('drafting', 'draft',
                'awaiting_partner_approval', 'approved', 'sent', 'signed', 'date_mismatch')),
            current_version_id uuid NULL,
            envelope_id uuid NULL,
            dated_as_of date NULL,
            signed_on date NULL,
            g7_met_at timestamptz NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE representation_letter_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            letter_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            template_version_id uuid NULL,
            representations jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(representations) = 'array'),
            edited_paragraphs_sealed bytea NULL CHECK (octet_length(edited_paragraphs_sealed)
                <= 1048576),
            sum_snapshot_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            drafted_by_run_id uuid NULL,
            created_by uuid NOT NULL,
            generated_document_id uuid NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, letter_id, version_no),
            FOREIGN KEY (tenant_id, letter_id)
                REFERENCES representation_letters (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE representation_letter_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            version_id uuid NOT NULL,
            approved_by uuid NOT NULL,
            seen_hash text NOT NULL CHECK (seen_hash {_SHA}),
            mfa_verified_at timestamptz NOT NULL,
            {_ACTOR},
            {_CREATED},
            UNIQUE (tenant_id, id),
            CONSTRAINT representation_letter_approvals_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES representation_letter_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_communications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL CHECK (kind IN ('planning_260', 'completion_260', 'sd_mw_265',
                'reportable_703', 'management_letter')),
            standard text NULL CHECK (char_length(standard) <= 40),
            combined_with_id uuid NULL,
            due_rule text NULL CHECK (char_length(due_rule) <= 80),
            due_on date NULL,
            status text NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'draft',
                'awaiting_ep_approval', 'sent', 'acknowledged')),
            current_version_id uuid NULL,
            channel text NULL CHECK (channel IN ('governance_room', 'ack_envelope')),
            envelope_id uuid NULL,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, kind),
            FOREIGN KEY (tenant_id, combined_with_id)
                REFERENCES governance_communications (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_communication_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            communication_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            template_version_id uuid NULL,
            sections_sealed bytea NULL CHECK (octet_length(sections_sealed) <= 1048576),
            section_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(section_refs) = 'array'),
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            drafted_by_run_id uuid NULL,
            created_by uuid NOT NULL,
            generated_document_id uuid NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, communication_id, version_no),
            FOREIGN KEY (tenant_id, communication_id)
                REFERENCES governance_communications (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_communication_sends (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            version_id uuid NOT NULL,
            sent_by uuid NOT NULL,
            governance_body_id uuid NOT NULL,
            recipient_contact_ids uuid[] NOT NULL DEFAULT '{{}}',
            channel text NOT NULL CHECK (channel IN ('governance_room', 'ack_envelope')),
            approval_grant_id uuid NULL,
            mfa_verified_at timestamptz NOT NULL,
            sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_ACTOR},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id),
            CONSTRAINT governance_communication_sends_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES governance_communication_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_recipients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            governance_body_id uuid NOT NULL,
            ack_required boolean NOT NULL DEFAULT false,{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, governance_body_id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_acknowledgements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            communication_id uuid NOT NULL,
            version_id uuid NOT NULL,
            acknowledged_by_contact_id uuid NOT NULL,
            acknowledged_at timestamptz NOT NULL,
            channel text NOT NULL CHECK (channel IN ('governance_room', 'ack_envelope')),
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, version_id, acknowledged_by_contact_id),
            FOREIGN KEY (tenant_id, communication_id)
                REFERENCES governance_communications (tenant_id, id),
            FOREIGN KEY (tenant_id, version_id)
                REFERENCES governance_communication_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )


def _create_report() -> None:
    op.execute(
        f"""
        CREATE TABLE audit_reports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            report_kind text NOT NULL CHECK (report_kind IN ('audit', 'review', 'compilation')),
            framework text NULL CHECK (char_length(framework) <= 80),
            standards_set_id uuid NULL,
            template_id uuid NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'approved', 'released', 'reissued')),
            current_version_id uuid NULL,
            report_date date NULL,
            city text NULL CHECK (char_length(city) <= 120),{_STAMPS}
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE audit_report_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            report_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            choices jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(choices) = 'object'),
            paragraphs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(paragraphs) = 'array'),
            report_date date NULL,
            city text NULL CHECK (char_length(city) <= 120),
            dual_date date NULL,
            reissue_of_release_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            created_by uuid NOT NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, report_id, version_no),
            FOREIGN KEY (tenant_id, report_id) REFERENCES audit_reports (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE report_releases (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL CHECK (kind IN ('original', 'reissue')),
            reissue_of_id uuid NULL,
            report_version_id uuid NOT NULL,
            report_version_hash text NOT NULL CHECK (report_version_hash {_SHA}),
            released_by uuid NOT NULL,
            released_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            report_date date NOT NULL,
            city text NULL CHECK (char_length(city) <= 120),
            gate_snapshot jsonb NOT NULL CHECK (jsonb_typeof(gate_snapshot) = 'object'),
            gate_snapshot_sha256 text NOT NULL CHECK (gate_snapshot_sha256 {_SHA}),
            final_document_version_id uuid NOT NULL,
            deliverable_ids uuid[] NOT NULL DEFAULT '{{}}',
            approval_grant_id uuid NULL,
            idempotency_key text NULL CHECK (char_length(idempotency_key) <= 200),
            {_ACTOR},
            UNIQUE (tenant_id, id),
            CHECK ((kind = 'reissue') = (reissue_of_id IS NOT NULL)),
            CONSTRAINT report_releases_by_a_person {_HUMAN},
            FOREIGN KEY (tenant_id, reissue_of_id) REFERENCES report_releases (tenant_id, id),
            FOREIGN KEY (tenant_id, report_version_id)
                REFERENCES audit_report_versions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX report_releases_one_original ON report_releases "
        "(tenant_id, work_item_id) WHERE kind = 'original'"
    )
    op.execute(
        "ALTER TABLE audit_report_versions ADD CONSTRAINT audit_report_versions_reissue "
        "FOREIGN KEY (tenant_id, reissue_of_release_id) REFERENCES report_releases (tenant_id, id)"
    )


def upgrade() -> None:
    _create_letters()
    _create_report()
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        if table in UPDATES:
            op.execute(f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON {table} TO abacus_app")
    for table in _INSERT_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION a07_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION a07_rows_immutable()"
        )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute("ALTER TABLE audit_report_versions DROP CONSTRAINT audit_report_versions_reissue")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
