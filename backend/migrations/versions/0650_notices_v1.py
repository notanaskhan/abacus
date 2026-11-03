"""Notices v1 (N-04-T03; N-04 §4.2; DEC-2052). Expand only.

- `notices` (F-03-T22, 0089) gains the v1 columns, every one nullable or defaulted: client and
  entity, agency and jurisdiction, the catalogue type key, tax year and form, the notice and
  respond-by dates with the respond-by source, the four amounts, the taxpayer TIN's last four
  digits, the related return, the authorization facts, `status` (C2's `notice` codes, default
  `received`), the partner's position with its decision, follow-up, close and escalation facts,
  client visibility, the source intake and a row version. The app may now update the v1 columns,
  never the identity columns, and never deletes a notice.
- `notice_intakes`: a notice on its way in (mutable until created or discarded).
- Insert-only and immutable (a BEFORE UPDATE OR DELETE and a BEFORE TRUNCATE trigger):
  `notice_status_events`, `notice_field_values`, `notice_proposed_items`,
  `notice_return_snapshots`, `notice_analyses`, `notice_notes`, `notice_response_versions`,
  `notice_sent_records`, `notice_agency_replies`. A correction is a new row superseding the old.
- `notice_responses`: the response's current state (one per notice).

Every new table has forced RLS. Field confirmations, sent records and agency replies are a
person's: the row's actor kind is `human` and equals the session's `app.actor_kind`. TINs and
confirmation numbers are sealed (`bytea`); only the last four digits are plain.

Revision ID: 0650
Revises: 0644
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0650"
down_revision = "0644"
branch_labels = None
depends_on = None

STATUSES = (
    "received",
    "classified",
    "analyzing",
    "response_drafted",
    "approved",
    "sent",
    "awaiting_irs",
    "closed",
    "escalated",
)
TYPE_KEYS = ("cp2000", "cp14", "cp501", "cp503", "cp504", "cp3219a", "state_generic", "unknown")
INTAKE_STATUSES = ("extracting", "ready", "manual_entry", "created", "discarded", "failed")
FIELD_KEYS = (
    "notice.code",
    "notice.tax_year",
    "notice.form",
    "notice.date",
    "notice.respond_by",
    "notice.amount_tax",
    "notice.amount_interest",
    "notice.amount_penalty",
    "notice.amount_total",
    "notice.interest_to",
    "notice.response_page",
    "taxpayer.name",
    "taxpayer.tin",
    "agency.name",
)
# The person's act: the row says human and the session says so too (0643's rule).
_HUMAN = "CHECK ({c} = 'human' AND {c} = current_setting('app.actor_kind', true))"


def _in(codes: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{c}'" for c in codes) + ")"


NOTICE_COLUMNS = (
    "client_id uuid NULL",
    "client_entity_id uuid NULL",
    "agency text NULL CHECK (agency IN ('irs', 'state'))",
    "agency_name text NULL CHECK (char_length(agency_name) BETWEEN 1 AND 120)",
    "jurisdiction text NULL CHECK (jurisdiction ~ '^(US|[A-Z]{2})$')",
    f"notice_type_key text NULL CHECK (notice_type_key IN {_in(TYPE_KEYS)})",
    "title text NULL CHECK (char_length(title) BETWEEN 1 AND 200)",
    "tax_year smallint NULL CHECK (tax_year BETWEEN 1990 AND 2100)",
    "form text NULL CHECK (char_length(form) BETWEEN 1 AND 20)",
    "notice_date date NULL",
    "respond_by date NULL",
    "respond_by_source text NULL "
    "CHECK (respond_by_source IN ('extracted', 'entered', 'corrected'))",
    "amount_tax numeric(18, 2) NULL",
    "amount_interest numeric(18, 2) NULL",
    "amount_penalty numeric(18, 2) NULL",
    "amount_total numeric(18, 2) NULL",
    "interest_to date NULL",
    "taxpayer_tin_last4 char(4) NULL CHECK (taxpayer_tin_last4 ~ '^[0-9]{4}$')",
    "related_return_id uuid NULL REFERENCES tax_returns (work_item_id)",
    "authorization_id uuid NULL",
    "authorization_kind text NOT NULL DEFAULT 'none' "
    "CHECK (authorization_kind IN ('form_8821', 'form_2848', 'state_poa', 'none'))",
    f"status text NOT NULL DEFAULT 'received' CHECK (status IN {_in(STATUSES)})",
    "status_changed_at timestamptz NOT NULL DEFAULT abacus_now()",
    "position text NULL CHECK (position IN ('agree', 'partially_agree', 'disagree'))",
    "decision_id uuid NULL",
    "decided_at timestamptz NULL",
    "partner_owned boolean NOT NULL DEFAULT false",
    "follow_up_on date NULL",
    "closed_on date NULL",
    "escalated_reason text NULL CHECK (char_length(escalated_reason) BETWEEN 1 AND 500)",
    "client_visible boolean NOT NULL DEFAULT false",
    "source_intake_id uuid NULL",
    "source_evidence_version_id uuid NULL",
    "assignee_user_id uuid NULL",
    "row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1)",
)
NOTICE_CHECKS = (
    ("notices_position_decided", "CHECK ((position IS NULL) = (decision_id IS NULL))"),
    ("notices_closed_on", "CHECK ((status = 'closed') = (closed_on IS NOT NULL))"),
    ("notices_escalated_reason", "CHECK (status <> 'escalated' OR escalated_reason IS NOT NULL)"),
)
NOTICE_UPDATE = tuple(c.split(" ", 1)[0] for c in NOTICE_COLUMNS)
NOTICE_INSERT = (
    "tenant_id",
    "work_item_id",
    "engagement_id",
    "notice_code",
    "received_on",
    *(c for c in NOTICE_UPDATE if c not in ("status_changed_at", "row_version")),
)
_WI = "work_item_id uuid NOT NULL REFERENCES notices (work_item_id)"
_ID = "id uuid NOT NULL DEFAULT gen_random_uuid()"
_TENANT = "tenant_id uuid NOT NULL REFERENCES firms (tenant_id)"
_AT = "created_at timestamptz NOT NULL DEFAULT abacus_now()"

IMMUTABLE = (
    "notice_status_events",
    "notice_field_values",
    "notice_proposed_items",
    "notice_return_snapshots",
    "notice_analyses",
    "notice_notes",
    "notice_response_versions",
    "notice_sent_records",
    "notice_agency_replies",
)
MUTABLE = ("notice_intakes", "notice_responses")
INSERTS: dict[str, tuple[str, ...]] = {
    "notice_status_events": (
        "tenant_id",
        "work_item_id",
        "from_status",
        "to_status",
        "actor_kind",
        "actor_user_id",
        "reason_code",
    ),
    "notice_intakes": (
        "tenant_id",
        "source",
        "inbox_item_id",
        "evidence_version_id",
        "client_id",
        "status",
        "extraction_mode",
        "match",
        "authorization_facts",
        "assignee_user_id",
        "notify_user_ids",
        "created_by",
    ),
    "notice_field_values": (
        "tenant_id",
        "owner_type",
        "owner_id",
        "field_key",
        "value_type",
        "value_text",
        "value_sealed",
        "last4",
        "confidence",
        "low_confidence",
        "origin",
        "extracted_field_id",
        "citation_id",
        "agent_run_id",
        "recorded_actor_kind",
        "recorded_by",
        "confirmed_by",
        "supersedes_id",
    ),
    "notice_proposed_items": (
        "tenant_id",
        "work_item_id",
        "kind",
        "line_key",
        "label",
        "payer_name",
        "info_form",
        "amount_shown",
        "amount_irs",
        "origin",
        "citation_id",
        "recorded_actor_kind",
        "recorded_by",
        "supersedes_id",
    ),
    "notice_return_snapshots": (
        "tenant_id",
        "work_item_id",
        "source",
        "tax_return_id",
        "engine_summary_id",
        "filing_status",
        "filed_on",
        "lines",
        "recorded_actor_kind",
        "recorded_by",
        "inputs_hash",
    ),
    "notice_analyses": (
        "tenant_id",
        "work_item_id",
        "version",
        "status",
        "analysis_kind",
        "rows",
        "information_returns",
        "checks",
        "sources",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "agent_run_id",
        "agent_stage",
        "recommended_position",
    ),
    "notice_notes": ("tenant_id", "work_item_id", "body_sealed", "author_id", "decision_card_id"),
    "notice_responses": (
        "tenant_id",
        "work_item_id",
        "template_key",
        "template_version_id",
        "position_source",
        "enclosures",
        "payment",
        "signer_contact_ids",
        "channel",
        "follow_up_days",
        "owner_user_id",
    ),
    "notice_response_versions": (
        "tenant_id",
        "response_id",
        "version_no",
        "blocks",
        "content_hash",
        "edit_diff",
        "based_on_version_id",
        "created_by",
        "created_actor_kind",
    ),
    "notice_sent_records": (
        "tenant_id",
        "work_item_id",
        "response_id",
        "channel",
        "confirmation_sealed",
        "confirmation_last4",
        "sent_on",
        "follow_up_on",
        "recorded_by",
        "recorded_actor_kind",
        "supersedes_id",
    ),
    "notice_agency_replies": (
        "tenant_id",
        "work_item_id",
        "outcome",
        "closed_on",
        "note_sealed",
        "evidence_version_id",
        "recorded_by",
        "recorded_actor_kind",
    ),
}
UPDATES: dict[str, tuple[str, ...]] = {
    "notice_intakes": (
        "client_id",
        "status",
        "extraction_mode",
        "match",
        "authorization_facts",
        "duplicate_of_work_item_id",
        "created_work_item_id",
        "discarded_reason_code",
        "assignee_user_id",
        "notify_user_ids",
        "row_version",
    ),
    "notice_responses": (
        "template_key",
        "template_version_id",
        "position_source",
        "current_version_id",
        "enclosures",
        "payment",
        "signer_contact_ids",
        "channel",
        "follow_up_days",
        "owner_user_id",
        "envelope_id",
        "generated_document_id",
        "binder_id",
        "row_version",
    ),
}


def upgrade() -> None:
    for column in NOTICE_COLUMNS:
        op.execute(f"ALTER TABLE notices ADD COLUMN {column}")
    for name, check in NOTICE_CHECKS:
        op.execute(f"ALTER TABLE notices ADD CONSTRAINT {name} {check}")
    op.execute("CREATE INDEX notices_open ON notices (tenant_id, status, respond_by)")
    op.execute("CREATE INDEX notices_client ON notices (tenant_id, client_entity_id)")
    # 0089 made the subtype insert-only; v1 updates its own columns (never the identity ones).
    op.execute(f"GRANT UPDATE ({', '.join(NOTICE_UPDATE)}) ON notices TO abacus_app")
    insert_columns(op, "notices", NOTICE_INSERT)

    op.execute(
        f"""
        CREATE TABLE notice_status_events (
            id bigint GENERATED ALWAYS AS IDENTITY,
            {_TENANT},
            {_WI},
            from_status text NULL CHECK (from_status IN {_in(STATUSES)}),
            to_status text NOT NULL CHECK (to_status IN {_in(STATUSES)}),
            actor_kind text NOT NULL CHECK (actor_kind IN ('human', 'system')),
            actor_user_id uuid NULL,
            reason_code text NULL CHECK (reason_code ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            at timestamptz NOT NULL DEFAULT abacus_now(),
            PRIMARY KEY (tenant_id, id),
            CHECK (actor_kind = 'system' OR actor_user_id IS NOT NULL)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_intakes (
            {_ID},
            {_TENANT},
            source text NOT NULL CHECK (source IN ('upload', 'inbox', 'portal', 'organizer')),
            inbox_item_id uuid NULL,
            evidence_version_id uuid NULL,
            client_id uuid NULL,
            status text NOT NULL DEFAULT 'extracting' CHECK (status IN {_in(INTAKE_STATUSES)}),
            extraction_mode text NULL CHECK (extraction_mode IN ('code_map', 'agent', 'manual')),
            match jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(match) = 'object'),
            authorization_facts jsonb NOT NULL DEFAULT '{{}}'::jsonb
                CHECK (jsonb_typeof(authorization_facts) = 'object'),
            duplicate_of_work_item_id uuid NULL REFERENCES notices (work_item_id),
            created_work_item_id uuid NULL REFERENCES notices (work_item_id),
            discarded_reason_code text NULL
                CHECK (discarded_reason_code ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            assignee_user_id uuid NULL,
            notify_user_ids uuid[] NOT NULL DEFAULT '{{}}',
            created_by uuid NOT NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK (inbox_item_id IS NOT NULL OR evidence_version_id IS NOT NULL),
            CHECK ((status = 'created') = (created_work_item_id IS NOT NULL)),
            CHECK ((status = 'discarded') = (discarded_reason_code IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_field_values (
            {_ID},
            {_TENANT},
            owner_type text NOT NULL CHECK (owner_type IN ('intake', 'notice')),
            owner_id uuid NOT NULL,
            field_key text NOT NULL CHECK (field_key IN {_in(FIELD_KEYS)}),
            value_type text NOT NULL
                CHECK (value_type IN ('money', 'date', 'text', 'tin', 'code', 'int')),
            value_text text NULL CHECK (char_length(value_text) <= 500),
            value_sealed bytea NULL CHECK (octet_length(value_sealed) <= 4096),
            last4 char(4) NULL CHECK (last4 ~ '^[0-9]{{4}}$'),
            confidence numeric(4, 3) NULL CHECK (confidence BETWEEN 0 AND 1),
            low_confidence boolean NOT NULL DEFAULT false,
            origin text NOT NULL CHECK (origin IN ('code_map', 'agent', 'human')),
            extracted_field_id uuid NULL,
            citation_id uuid NULL,
            agent_run_id uuid NULL,
            recorded_actor_kind text NOT NULL
                CHECK (recorded_actor_kind IN ('system', 'agent', 'human')),
            recorded_by uuid NULL,
            confirmed_by uuid NULL,
            supersedes_id uuid NULL,
            {_AT},
            PRIMARY KEY (tenant_id, id),
            -- A TIN is sealed and never plain; every other value is plain and never sealed.
            CHECK ((value_type = 'tin') = (value_sealed IS NOT NULL AND value_text IS NULL)),
            CHECK (origin <> 'human' OR recorded_actor_kind = 'human'),
            CHECK (origin <> 'agent' OR agent_run_id IS NOT NULL),
            CHECK (recorded_actor_kind <> 'human' OR recorded_by IS NOT NULL),
            -- A confirmation or a person's value is a person's act in a person's session.
            CHECK (confirmed_by IS NULL OR current_setting('app.actor_kind', true) = 'human'),
            CHECK (recorded_actor_kind <> 'human'
                OR current_setting('app.actor_kind', true) = 'human'),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES notice_field_values (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_proposed_items (
            {_ID},
            {_TENANT},
            {_WI},
            kind text NOT NULL CHECK (kind IN ('line_change', 'payer_item')),
            line_key text NOT NULL CHECK (char_length(line_key) BETWEEN 1 AND 60),
            label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
            payer_name text NULL CHECK (char_length(payer_name) <= 200),
            info_form text NULL CHECK (char_length(info_form) <= 20),
            amount_shown numeric(18, 2) NULL,
            amount_irs numeric(18, 2) NULL,
            origin text NOT NULL CHECK (origin IN ('code_map', 'agent', 'human')),
            citation_id uuid NULL,
            recorded_actor_kind text NOT NULL
                CHECK (recorded_actor_kind IN ('system', 'agent', 'human')),
            recorded_by uuid NULL,
            supersedes_id uuid NULL,
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK (origin <> 'human'
                OR (recorded_actor_kind = 'human' AND recorded_by IS NOT NULL)),
            CHECK (origin <> 'human' OR citation_id IS NOT NULL),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES notice_proposed_items (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_return_snapshots (
            {_ID},
            {_TENANT},
            {_WI},
            source text NOT NULL CHECK (source IN ('engine_import', 'entry')),
            tax_return_id uuid NULL REFERENCES tax_returns (work_item_id),
            engine_summary_id uuid NULL,
            filing_status text NULL
                CHECK (filing_status IN ('single', 'mfj', 'mfs', 'hoh', 'qss')),
            filed_on date NULL,
            lines jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(lines) = 'array'),
            recorded_actor_kind text NOT NULL CHECK (recorded_actor_kind IN ('system', 'human')),
            recorded_by uuid NULL,
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK ((source = 'engine_import') = (engine_summary_id IS NOT NULL)),
            CHECK (source <> 'entry'
                OR (recorded_actor_kind = 'human' AND recorded_by IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_analyses (
            {_ID},
            {_TENANT},
            {_WI},
            version integer NOT NULL CHECK (version >= 1),
            status text NOT NULL CHECK (status IN ('running', 'ready', 'failed', 'superseded')),
            analysis_kind text NOT NULL
                CHECK (analysis_kind IN ('underreporter_comparison', 'balance_due', 'none')),
            rows jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(rows) = 'array'),
            information_returns jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(information_returns) = 'array'),
            checks jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(checks) = 'object'),
            sources jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(sources) = 'array'),
            engine_name text NOT NULL CHECK (char_length(engine_name) BETWEEN 1 AND 60),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            agent_run_id uuid NULL,
            agent_stage text NOT NULL DEFAULT 'off'
                CHECK (agent_stage IN ('off', 'shadow', 'live', 'refused')),
            recommended_position text NULL
                CHECK (recommended_position IN ('agree', 'partially_agree', 'disagree')),
            {_AT},
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, version),
            -- A recommendation shows only from a live agent stage (§6).
            CHECK (recommended_position IS NULL OR agent_stage = 'live')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_notes (
            {_ID},
            {_TENANT},
            {_WI},
            body_sealed bytea NOT NULL CHECK (octet_length(body_sealed) <= 65536),
            author_id uuid NOT NULL,
            decision_card_id uuid NULL,
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK (current_setting('app.actor_kind', true) = 'human')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_responses (
            {_ID},
            {_TENANT},
            {_WI},
            template_key text NOT NULL CHECK (template_key ~ '^[a-z][a-z0-9_]{{0,59}}$'),
            template_version_id uuid NOT NULL,
            position_source text NOT NULL CHECK (position_source IN ('decided', 'provisional')),
            current_version_id uuid NULL,
            enclosures jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(enclosures) = 'array'),
            payment jsonb NULL CHECK (payment IS NULL OR jsonb_typeof(payment) = 'object'),
            signer_contact_ids uuid[] NOT NULL DEFAULT '{{}}',
            channel text NULL CHECK (channel IN ('dut', 'fax', 'mail')),
            follow_up_days integer NOT NULL DEFAULT 60 CHECK (follow_up_days BETWEEN 1 AND 365),
            owner_user_id uuid NULL,
            envelope_id uuid NULL,
            generated_document_id uuid NULL,
            binder_id uuid NULL,
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            {_AT},
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, work_item_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_response_versions (
            {_ID},
            {_TENANT},
            response_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            blocks jsonb NOT NULL CHECK (jsonb_typeof(blocks) = 'array'),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            edit_diff jsonb NULL,
            based_on_version_id uuid NULL,
            created_by uuid NULL,
            created_actor_kind text NOT NULL CHECK (created_actor_kind IN ('human', 'system')),
            {_AT},
            PRIMARY KEY (tenant_id, id),
            UNIQUE (tenant_id, response_id, version_no),
            CHECK (created_actor_kind <> 'human' OR created_by IS NOT NULL),
            FOREIGN KEY (tenant_id, response_id) REFERENCES notice_responses (tenant_id, id),
            FOREIGN KEY (tenant_id, based_on_version_id)
                REFERENCES notice_response_versions (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_sent_records (
            {_ID},
            {_TENANT},
            {_WI},
            response_id uuid NOT NULL,
            channel text NOT NULL CHECK (channel IN ('dut', 'fax', 'mail')),
            confirmation_sealed bytea NULL CHECK (octet_length(confirmation_sealed) <= 4096),
            confirmation_last4 char(4) NULL CHECK (confirmation_last4 ~ '^[0-9A-Za-z]{{4}}$'),
            sent_on date NOT NULL,
            follow_up_on date NOT NULL CHECK (follow_up_on > sent_on),
            recorded_by uuid NOT NULL,
            recorded_actor_kind text NOT NULL {_HUMAN.format(c="recorded_actor_kind")},
            supersedes_id uuid NULL,
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK ((confirmation_sealed IS NULL) = (confirmation_last4 IS NULL)),
            FOREIGN KEY (tenant_id, response_id) REFERENCES notice_responses (tenant_id, id),
            FOREIGN KEY (tenant_id, supersedes_id) REFERENCES notice_sent_records (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE notice_agency_replies (
            {_ID},
            {_TENANT},
            {_WI},
            outcome text NOT NULL CHECK (outcome IN ('resolved', 'escalated')),
            closed_on date NULL,
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            evidence_version_id uuid NULL,
            recorded_by uuid NOT NULL,
            recorded_actor_kind text NOT NULL {_HUMAN.format(c="recorded_actor_kind")},
            {_AT},
            PRIMARY KEY (tenant_id, id),
            CHECK (outcome <> 'resolved' OR closed_on IS NOT NULL)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION notice_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: notice records never change; add a superseding row'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION notice_rows_immutable() FROM PUBLIC")
    for table in (*IMMUTABLE, *MUTABLE):
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in IMMUTABLE:
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION notice_rows_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION notice_rows_immutable()"
        )
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    for table in (
        "notice_status_events",
        "notice_proposed_items",
        "notice_return_snapshots",
        "notice_analyses",
        "notice_notes",
        "notice_sent_records",
        "notice_agency_replies",
    ):
        op.execute(f"CREATE INDEX {table}_work_item ON {table} (tenant_id, work_item_id)")
    op.execute(
        "CREATE INDEX notice_field_values_owner ON notice_field_values "
        "(tenant_id, owner_type, owner_id, field_key)"
    )
    op.execute("CREATE INDEX notice_intakes_status ON notice_intakes (tenant_id, status)")


def downgrade() -> None:
    # Dependents first: sent records and versions name responses; intakes name notices.
    for table in (
        "notice_agency_replies",
        "notice_sent_records",
        "notice_response_versions",
        "notice_responses",
        "notice_notes",
        "notice_analyses",
        "notice_return_snapshots",
        "notice_proposed_items",
        "notice_field_values",
        "notice_intakes",
        "notice_status_events",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION notice_rows_immutable()")
    op.execute(f"REVOKE UPDATE ({', '.join(NOTICE_UPDATE)}) ON notices FROM abacus_app")
    insert_columns(
        op, "notices", ("tenant_id", "work_item_id", "engagement_id", "notice_code", "received_on")
    )
    op.execute("DROP INDEX notices_client")
    op.execute("DROP INDEX notices_open")
    for name, _check in reversed(NOTICE_CHECKS):
        op.execute(f"ALTER TABLE notices DROP CONSTRAINT {name}")
    for column in reversed(NOTICE_COLUMNS):
        op.execute(f"ALTER TABLE notices DROP COLUMN {column.split(' ', 1)[0]}")
