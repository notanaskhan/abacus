"""R-02 C10 deliverables, governance bodies and the uncorrected-misstatements acknowledgement
(R-02-T05; R-02 §4.2; POR-08, POR-09, POR-15).

Expand-only, ahead of the Thu Dec 23, 2027 train.

- `reporting`: `deliverables` (one per source_module and source_ref), insert-only
  `deliverable_audiences`, `deliverable_versions` and `deliverable_events`, and the
  `deliverable_receipts` projection (rebuildable from audit events).
- `assurance`: `governance_bodies` and `governance_body_members` (DEC-93); A-07's
  `governance_recipients` and `governance_communication_sends` gain their FK to the body, added
  NOT VALID and validated here (the tables are near empty before the season).
- `assurance`: insert-only, human-only `uncorrected_misstatement_acknowledgements`. Only a client
  principal acting as itself inserts one: the row's actor must be the session's (`app.actor_kind`,
  `app.actor_id`), and `principal_kind` is always `client`, so neither an agent, the platform nor a
  firm user's session can write one (R-02 AC-12, I-AGENT-NEVER).
- Human-only audit actions gain the client's three decisions (R-02 §4.7):
  `uncorrected_misstatements.acknowledged`, `proposed_entry.client_decided` and
  `statement.approved_by_management`.

Revision ID: 0710
Revises: 0701
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0710"
down_revision = "0701"
branch_labels = None
depends_on = None

_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_UPDATED = "updated_at timestamptz NOT NULL DEFAULT clock_timestamp()"
_VERSION = "version integer NOT NULL DEFAULT 1 CHECK (version >= 1)"
_DELIVERABLE_KINDS = (
    "'fs_draft', 'fs_final', 'auditor_report', 'review_report', 'compilation_report', "
    "'preparation_statements', 'close_package', 'governance_letter', 'signed_copy', "
    "'return_copy', 'filing_letter', 'memo', 'soc_report', 'assertion', 'other'"
)
_SCOPE_KINDS = "'client', 'client_entity', 'engagement', 'work_item', 'governance_room'"
_HUMAN_SESSION = (
    "actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true) "
    "AND actor_id = current_setting('app.actor_id', true)"
)

INSERTS: dict[str, tuple[str, ...]] = {
    "deliverables": (
        "id", "tenant_id", "client_id", "client_entity_id", "engagement_id", "work_item_id",
        "kind", "title", "source_module", "source_ref", "restricted_use", "legend_kind",
        "created_by",
    ),
    "deliverable_audiences": ("tenant_id", "deliverable_id", "scope_kind", "scope_id"),
    "deliverable_versions": (
        "id", "tenant_id", "deliverable_id", "version_no", "evidence_version_id",
        "generated_document_id", "render_hash", "page_count", "is_draft", "page_comments",
        "approval_kind", "approval_item_id", "published_by_user_id", "actor_kind",
        "on_behalf_of_user_id", "supersedes_version_id",
    ),
    "deliverable_events": (
        "id", "tenant_id", "deliverable_version_id", "kind", "reason_code", "note_sealed",
        "actor_kind", "actor_user_id", "on_behalf_of_user_id",
    ),
    "deliverable_receipts": (
        "tenant_id", "deliverable_version_id", "contact_id", "first_viewed_at", "last_viewed_at",
        "first_downloaded_at", "download_count",
    ),
    "governance_bodies": ("id", "tenant_id", "client_id", "client_entity_id", "name", "kind"),
    "governance_body_members": (
        "id", "tenant_id", "body_id", "contact_id", "member_role", "started_on",
    ),
    "uncorrected_misstatement_acknowledgements": (
        "id", "tenant_id", "engagement_id", "work_item_id", "sum_snapshot_id",
        "approval_item_id", "net_effect", "engine_version", "inputs_hash", "entry_ids",
        "contact_id", "actor_user_id", "actor_kind", "actor_id", "principal_kind", "grant_id",
        "mfa_verified_at", "seen_hash",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "deliverables": ("title", "restricted_use", "legend_kind", "version", "updated_at"),
    "deliverable_receipts": (
        "first_viewed_at", "last_viewed_at", "first_downloaded_at", "download_count",
    ),
    "governance_bodies": ("name", "kind", "status", "version", "updated_at"),
    "governance_body_members": ("member_role", "ended_on"),
}  # fmt: skip
# reporting's insert-only tables reuse `reporting_rows_immutable` (0430); assurance's has its own.
INSERT_ONLY: dict[str, str] = {
    "deliverable_audiences": "reporting_rows_immutable",
    "deliverable_versions": "reporting_rows_immutable",
    "deliverable_events": "reporting_rows_immutable",
    "uncorrected_misstatement_acknowledgements": "acknowledgement_rows_immutable",
}
_TABLES = (
    "deliverables",
    "deliverable_audiences",
    "deliverable_versions",
    "deliverable_events",
    "deliverable_receipts",
    "governance_bodies",
    "governance_body_members",
    "uncorrected_misstatement_acknowledgements",
)
_BODY_FKS = (
    ("governance_recipients", "governance_recipients_body_fk"),
    ("governance_communication_sends", "governance_communication_sends_body_fk"),
)

_BEFORE = [  # 0668's list
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
    "governance_communication.sent",
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
    "rep_letter.approved",
    "report.approved",
    "report.reissued",
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
    {*_BEFORE, "proposed_entry.client_decided", "statement.approved_by_management"}
    | {"uncorrected_misstatements.acknowledged"}
)


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def _create_deliverables() -> None:
    op.execute(
        f"""
        CREATE TABLE deliverables (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            client_entity_id uuid NULL,
            engagement_id uuid NULL,
            work_item_id uuid NULL,
            kind text NOT NULL CHECK (kind IN ({_DELIVERABLE_KINDS})),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            source_module text NOT NULL CHECK (source_module ~ '^[a-z][a-z_]{{1,40}}$'),
            source_ref text NOT NULL CHECK (char_length(source_ref) BETWEEN 1 AND 200),
            restricted_use boolean NOT NULL DEFAULT false,
            legend_kind text NULL CHECK (legend_kind IN ('ar_c_70')),
            created_by uuid NOT NULL,
            {_VERSION},
            {_CREATED},
            {_UPDATED},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, source_module, source_ref),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id, client_entity_id)
                REFERENCES client_entities (tenant_id, client_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            CONSTRAINT deliverables_work_item_needs_engagement
                CHECK (work_item_id IS NULL OR engagement_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE deliverable_audiences (
            tenant_id uuid NOT NULL,
            deliverable_id uuid NOT NULL,
            scope_kind text NOT NULL CHECK (scope_kind IN ({_SCOPE_KINDS})),
            scope_id uuid NOT NULL,
            {_CREATED},
            PRIMARY KEY (tenant_id, deliverable_id, scope_kind, scope_id),
            FOREIGN KEY (tenant_id, deliverable_id) REFERENCES deliverables (tenant_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE deliverable_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            deliverable_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            evidence_version_id uuid NOT NULL,
            generated_document_id uuid NULL,
            render_hash text NOT NULL CHECK (render_hash ~ '^[0-9a-f]{64}$'),
            page_count integer NOT NULL CHECK (page_count > 0),
            is_draft boolean NOT NULL,
            page_comments boolean NOT NULL DEFAULT false,
            approval_kind text NULL CHECK (approval_kind ~ '^[a-z][a-z_]{1,60}$'),
            approval_item_id uuid NULL,
            published_by_user_id uuid NOT NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            on_behalf_of_user_id uuid NULL,
            published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            supersedes_version_id uuid NULL,
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, deliverable_id, version_no),
            UNIQUE (tenant_id, deliverable_id, evidence_version_id),
            FOREIGN KEY (tenant_id, deliverable_id) REFERENCES deliverables (tenant_id, id),
            FOREIGN KEY (tenant_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, generated_document_id)
                REFERENCES generated_documents (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_version_id)
                REFERENCES deliverable_versions (tenant_id, id),
            CONSTRAINT deliverable_versions_comments_on_drafts
                CHECK (NOT page_comments OR is_draft),
            CONSTRAINT deliverable_versions_draft_is_generated
                CHECK (NOT is_draft OR generated_document_id IS NOT NULL),
            CONSTRAINT deliverable_versions_system_acts_for_someone
                CHECK (actor_kind = 'human' OR on_behalf_of_user_id IS NOT NULL),
            CONSTRAINT deliverable_versions_approval_pair
                CHECK ((approval_kind IS NULL) = (approval_item_id IS NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE deliverable_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            deliverable_version_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('published', 'superseded', 'withdrawn')),
            reason_code text NULL CHECK (reason_code IN ('wrong_file', 'reissued', 'other')),
            note_sealed bytea NULL,
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            on_behalf_of_user_id uuid NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, deliverable_version_id)
                REFERENCES deliverable_versions (tenant_id, id),
            CONSTRAINT deliverable_events_withdrawn_has_reason
                CHECK ((kind = 'withdrawn') = (reason_code IS NOT NULL)),
            CONSTRAINT deliverable_events_actor CHECK (
                (actor_kind = 'human' AND actor_user_id IS NOT NULL)
                OR (actor_kind = 'system' AND on_behalf_of_user_id IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX deliverable_events_one_terminal ON deliverable_events "
        "(tenant_id, deliverable_version_id) WHERE kind IN ('superseded', 'withdrawn')"
    )
    op.execute(
        "CREATE UNIQUE INDEX deliverable_events_one_published ON deliverable_events "
        "(tenant_id, deliverable_version_id) WHERE kind = 'published'"
    )
    op.execute(
        """
        CREATE TABLE deliverable_receipts (
            tenant_id uuid NOT NULL,
            deliverable_version_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            first_viewed_at timestamptz NULL,
            last_viewed_at timestamptz NULL,
            first_downloaded_at timestamptz NULL,
            download_count integer NOT NULL DEFAULT 0 CHECK (download_count >= 0),
            PRIMARY KEY (tenant_id, deliverable_version_id, contact_id),
            FOREIGN KEY (tenant_id, deliverable_version_id)
                REFERENCES deliverable_versions (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            CONSTRAINT deliverable_receipts_downloads
                CHECK ((download_count = 0) = (first_downloaded_at IS NULL)),
            CONSTRAINT deliverable_receipts_views
                CHECK (last_viewed_at IS NULL OR first_viewed_at <= last_viewed_at)
        )
        """
    )


def _create_governance() -> None:
    op.execute(
        f"""
        CREATE TABLE governance_bodies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            client_id uuid NOT NULL,
            client_entity_id uuid NULL,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
            kind text NOT NULL CHECK (kind IN ('benefits_committee', 'audit_committee', 'board',
                'ia_committee', 'other')),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            {_VERSION},
            {_CREATED},
            {_UPDATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES clients (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id, client_entity_id)
                REFERENCES client_entities (tenant_id, client_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE governance_body_members (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            body_id uuid NOT NULL,
            contact_id uuid NOT NULL,
            member_role text NOT NULL CHECK (member_role IN ('chair', 'member')),
            started_on date NOT NULL,
            ended_on date NULL,
            {_CREATED},
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, body_id) REFERENCES governance_bodies (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            CONSTRAINT governance_body_members_dates
                CHECK (ended_on IS NULL OR ended_on >= started_on)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX governance_body_members_current ON governance_body_members "
        "(tenant_id, body_id, contact_id) WHERE ended_on IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX governance_body_members_one_chair ON governance_body_members "
        "(tenant_id, body_id) WHERE ended_on IS NULL AND member_role = 'chair'"
    )
    for table, name in _BODY_FKS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            "FOREIGN KEY (tenant_id, governance_body_id) "
            "REFERENCES governance_bodies (tenant_id, id) NOT VALID"
        )
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")
    op.execute(
        f"""
        CREATE TABLE uncorrected_misstatement_acknowledgements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,
            sum_snapshot_id uuid NOT NULL,
            approval_item_id uuid NULL,
            net_effect numeric(18, 2) NOT NULL,
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            entry_ids uuid[] NOT NULL CHECK (cardinality(entry_ids) >= 1),
            contact_id uuid NOT NULL,
            actor_user_id uuid NOT NULL,
            actor_kind text NOT NULL,
            actor_id text NOT NULL,
            principal_kind text NOT NULL CHECK (principal_kind = 'client'),
            grant_id uuid NOT NULL,
            mfa_verified_at timestamptz NOT NULL,
            seen_hash text NOT NULL CHECK (seen_hash ~ '^[0-9a-f]{{64}}$'),
            acknowledged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, sum_snapshot_id, contact_id),
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, sum_snapshot_id) REFERENCES sum_snapshots (tenant_id, id),
            FOREIGN KEY (tenant_id, contact_id) REFERENCES contacts (tenant_id, id),
            FOREIGN KEY (tenant_id, grant_id) REFERENCES client_access_grants (tenant_id, id),
            CONSTRAINT uncorrected_misstatement_acknowledgements_by_a_person
                CHECK ({_HUMAN_SESSION} AND actor_id = actor_user_id::text)
        )
        """
    )


def upgrade() -> None:
    _create_deliverables()
    _create_governance()
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
        insert_columns(op, table, INSERTS[table])
        if table in UPDATES:
            op.execute(f"GRANT UPDATE ({', '.join(UPDATES[table])}) ON {table} TO abacus_app")
    op.execute(
        """
        CREATE FUNCTION acknowledgement_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION acknowledgement_rows_immutable() FROM PUBLIC")
    for table, function in INSERT_ONLY.items():
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {function}()"
        )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    for table, name in _BODY_FKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION acknowledgement_rows_immutable()")
