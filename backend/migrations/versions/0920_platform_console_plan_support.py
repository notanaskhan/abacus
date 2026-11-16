"""G-04 migration A: platform console, plan & usage and support (G-04-T04; G-04 §4.2; SPEC-680;
ADR-148, ADR-300, ADR-142; DEC-5204). Expand only: tightened rules use NOT VALID CHECKs so no
existing row changes meaning.

Tenant tables (forced RLS):
- `plan_entitlements`: insert-only versions of the plan term, seats, included agent-minutes, the
  usage-month anchor day and the library channel; the current row is the latest `valid_from`
  not after now. `tenant_entitlements` stays the per-module switch (F-03-T28); its `module` CHECK
  gains the four service lines (`tax`, `audit_assurance`, `client_accounting`, `advisory`),
  recorded and shown, not enforced (OQ-6).
- `usage_alert_policies` (one row, `version`), `usage_alert_rules` (firm thresholds and
  recipients), `usage_alert_events` (insert-only; once per threshold per scope per usage month).
- `plan_change_requests` ("Request more"): the decider is never the requester (a CHECK).
- `support_conversations` (one open thread per user), `support_messages` (insert-only, bodies
  `confidential`), `support_conversation_reads` (read state kept out of the messages).

Global tables (no app grant; definer functions only):
- `help_articles` (two-person publish, immutable once published), `status_components`,
  `status_incidents`, `status_incident_updates` (insert-only), `platform_regions`,
  `platform_settings`, `platform_tenant_directory` (metadata only) and `platform_audit_events`
  (insert-only, identifiers only).

Readers the app may execute: `platform_directory_list`, `platform_directory_get`,
`help_article_list`, `help_article_get`, `help_article_search`, `status_snapshot`,
`platform_regions_list`, `platform_setting_get`, and the append-only `platform_audit_record`.
Owner-only writers (the worker's `PlatformOpsWorkflow` and the operator CLI):
`platform_directory_upsert`, `help_article_draft`, `help_article_publish`,
`help_article_withdraw`, `status_incident_post`, `status_incident_update`,
`status_incident_resolve`. No content is written here (AGENTS 16): regions, components, support
hours and articles are content rows loaded by G-04-T20 and the seed slices (G-04-T13).

Revision ID: 0920
Revises: 0902
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0920"
down_revision = "0902"
branch_labels = None
depends_on = None

_HANDLE = "text NOT NULL CHECK (char_length({c}) BETWEEN 1 AND 200)"
_MONTH = "CHECK ({} ~ '^[0-9]{{4}}-(0[1-9]|1[0-2])$')"
_MODULES_OLD = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion', 'tax_entity_returns', "
    "'cas_closes')"
)
_MODULES_NEW = (
    "('attest', 'internal_audit', 'group_audit', 'statements_studio', 'office_addins', "
    "'insights', 'tax_returns', 'ebp_audits', 'assurance_completion', 'tax_entity_returns', "
    "'cas_closes', 'tax', 'audit_assurance', 'client_accounting', 'advisory')"
)
_SERVICE_LINES = "('tax', 'audit_assurance', 'client_accounting', 'advisory')"

TENANT_INSERTS: dict[str, tuple[str, ...]] = {
    "plan_entitlements": (
        "tenant_id", "plan_code", "term_start", "term_end", "renewal_on",
        "usage_month_anchor_day", "included_agent_minutes", "seats_total", "library_channel",
        "policy_principal_available", "valid_from", "changed_by_staff", "change_reason",
        "plan_request_id",
    ),
    "usage_alert_policies": (
        "tenant_id", "at_100_behaviour", "engagement_default_minutes", "engagement_alert_pct",
        "billing_contact_user_id", "partner_approver_user_id", "updated_by",
    ),
    "usage_alert_rules": (
        "tenant_id", "level", "threshold_pct", "enabled", "recipient_user_ids",
        "recipient_groups",
    ),
    "usage_alert_events": (
        "tenant_id", "scope", "rule_id", "engagement_id", "usage_month", "threshold_pct",
        "crossed_at", "minutes_at_crossing", "sent_to",
    ),
    "plan_change_requests": (
        "id", "tenant_id", "kind", "from_value", "to_value", "modules_add", "effective_from",
        "reason", "requested_by", "approver_user_id",
    ),
    "support_conversations": ("id", "tenant_id", "user_id"),
    "support_messages": (
        "tenant_id", "conversation_id", "author_kind", "author_user_id", "staff_subject", "body",
        "related_article_slug",
    ),
    "support_conversation_reads": ("tenant_id", "conversation_id", "reader_kind", "last_read_at"),
}  # fmt: skip
TENANT_UPDATES: dict[str, tuple[str, ...]] = {
    "usage_alert_policies": (
        "version", "at_100_behaviour", "engagement_default_minutes", "engagement_alert_pct",
        "billing_contact_user_id", "partner_approver_user_id", "updated_by", "updated_at",
    ),
    "usage_alert_rules": ("enabled", "recipient_user_ids", "recipient_groups", "updated_at"),
    "plan_change_requests": (
        "status", "decided_by", "decided_at", "decline_reason", "applied_by_staff", "applied_at",
        "plan_entitlement_version_id", "version",
    ),
    "support_conversations": (
        "status", "last_firm_message_at", "last_staff_message_at", "assigned_staff_subject",
    ),
    "support_conversation_reads": ("last_read_at",),
}  # fmt: skip
INSERT_ONLY_TENANT = ("plan_entitlements", "usage_alert_events", "support_messages")
GLOBAL = (
    "help_articles", "status_components", "status_incidents", "status_incident_updates",
    "platform_regions", "platform_settings", "platform_tenant_directory", "platform_audit_events",
)  # fmt: skip
READERS = (
    "platform_directory_list(text, text, text)",
    "platform_directory_get(uuid)",
    "help_article_list(text)",
    "help_article_get(text)",
    "help_article_search(text)",
    "status_snapshot()",
    "platform_regions_list()",
    "platform_setting_get(text)",
    "platform_audit_record(text, text, text, text, text, uuid, text, jsonb)",
)
OWNER_ONLY = (
    "platform_directory_upsert(uuid, text, text, text, integer, integer, text[], text, text,"
    " text, text, timestamptz, integer, boolean, uuid, date)",
    "help_article_draft(text, text, text, text, text[], integer, jsonb, text, text)",
    "help_article_publish(uuid, text, text)",
    "help_article_withdraw(uuid, text, text)",
    "status_incident_post(text, text, text, text, text)",
    "status_incident_update(uuid, text, text)",
    "status_incident_resolve(uuid, text, text)",
)
TRIGGERS = (
    "plan_entitlements_immutable()",
    "usage_alert_events_immutable()",
    "support_messages_immutable()",
    "help_articles_freeze()",
    "status_incident_updates_immutable()",
    "platform_audit_events_immutable()",
)


def _insert_only_trigger(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def _tenant_tables() -> None:
    op.execute(
        """
        CREATE TABLE plan_entitlements (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            plan_code text NOT NULL REFERENCES plans (code),
            term_start date NOT NULL,
            term_end date NOT NULL CHECK (term_end >= term_start),
            renewal_on date NOT NULL,
            usage_month_anchor_day smallint NOT NULL DEFAULT 1
                CHECK (usage_month_anchor_day BETWEEN 1 AND 28),
            included_agent_minutes integer NOT NULL CHECK (included_agent_minutes >= 0),
            seats_total integer NOT NULL CHECK (seats_total >= 1),
            library_channel text NOT NULL DEFAULT 'stable'
                CHECK (library_channel IN ('stable', 'early_access')),
            policy_principal_available boolean NOT NULL DEFAULT false,
            valid_from timestamptz NOT NULL DEFAULT abacus_now(),
            changed_by_staff text NULL CHECK (char_length(changed_by_staff) BETWEEN 1 AND 200),
            change_reason text NOT NULL
                CHECK (char_length(btrim(change_reason)) BETWEEN 20 AND 500),
            plan_request_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX plan_entitlements_current ON plan_entitlements (tenant_id, valid_from DESC)"
    )
    op.execute(
        """
        CREATE TABLE usage_alert_policies (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            at_100_behaviour text NOT NULL DEFAULT 'keep_running'
                CHECK (at_100_behaviour IN ('keep_running', 'pause_scheduled')),
            engagement_default_minutes integer NOT NULL DEFAULT 1500
                CHECK (engagement_default_minutes >= 0),
            engagement_alert_pct smallint NOT NULL DEFAULT 80
                CHECK (engagement_alert_pct BETWEEN 1 AND 100),
            billing_contact_user_id uuid NULL,
            partner_approver_user_id uuid NULL,
            updated_by uuid NULL,
            updated_at timestamptz NOT NULL DEFAULT abacus_now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE usage_alert_rules (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            level text NOT NULL DEFAULT 'firm' CHECK (level IN ('firm')),
            threshold_pct smallint NOT NULL CHECK (threshold_pct BETWEEN 1 AND 100),
            enabled boolean NOT NULL DEFAULT true,
            recipient_user_ids uuid[] NOT NULL DEFAULT '{}'
                CHECK (cardinality(recipient_user_ids) <= 50),
            recipient_groups text[] NOT NULL DEFAULT '{}'
                CHECK (recipient_groups <@ ARRAY['partners', 'firm_admins']::text[]),
            updated_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, level, threshold_pct),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE usage_alert_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            scope text NOT NULL CHECK (scope IN ('firm', 'engagement')),
            rule_id uuid NULL,
            engagement_id uuid NULL,
            usage_month text NOT NULL {_MONTH.format("usage_month")},
            threshold_pct smallint NOT NULL CHECK (threshold_pct BETWEEN 1 AND 100),
            crossed_at timestamptz NOT NULL,
            minutes_at_crossing integer NOT NULL CHECK (minutes_at_crossing >= 0),
            sent_to uuid[] NOT NULL DEFAULT '{{}}',
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CHECK ((scope = 'firm') = (rule_id IS NOT NULL)),
            CHECK ((scope = 'engagement') = (engagement_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, rule_id) REFERENCES usage_alert_rules (tenant_id, id),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX usage_alert_events_once ON usage_alert_events (tenant_id, scope, "
        "coalesce(rule_id, engagement_id), usage_month, threshold_pct)"
    )
    op.execute(
        """
        CREATE TABLE plan_change_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            kind text NOT NULL CHECK (kind IN ('seats', 'agent_minutes', 'modules')),
            from_value integer NULL CHECK (from_value >= 0),
            to_value integer NULL CHECK (to_value >= 0),
            modules_add text[] NOT NULL DEFAULT '{}' CHECK (cardinality(modules_add) <= 10),
            effective_from date NULL,
            reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 10 AND 500),
            requested_by uuid NOT NULL,
            approver_user_id uuid NULL,
            status text NOT NULL DEFAULT 'awaiting_partner' CHECK (status IN
                ('awaiting_partner', 'sent_to_accrued', 'applied', 'declined', 'withdrawn')),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            decline_reason text NULL
                CHECK (char_length(btrim(decline_reason)) BETWEEN 10 AND 500),
            applied_by_staff text NULL CHECK (char_length(applied_by_staff) BETWEEN 1 AND 200),
            applied_at timestamptz NULL,
            plan_entitlement_version_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            -- AC-41: never the requester.
            CHECK (decided_by IS NULL OR decided_by <> requested_by),
            CHECK (kind <> 'modules' OR cardinality(modules_add) >= 1),
            CHECK (kind = 'modules' OR to_value IS NOT NULL),
            CHECK (status <> 'declined' OR decline_reason IS NOT NULL),
            CHECK (status <> 'applied'
                   OR (applied_at IS NOT NULL AND plan_entitlement_version_id IS NOT NULL)),
            FOREIGN KEY (tenant_id, plan_entitlement_version_id)
                REFERENCES plan_entitlements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX plan_change_requests_open ON plan_change_requests (tenant_id, status) "
        "WHERE status IN ('awaiting_partner', 'sent_to_accrued')"
    )
    op.execute(
        """
        CREATE TABLE support_conversations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            user_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
            last_firm_message_at timestamptz NULL,
            last_staff_message_at timestamptz NULL,
            assigned_staff_subject text NULL
                CHECK (char_length(assigned_staff_subject) BETWEEN 1 AND 200),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX support_conversations_one_open ON support_conversations "
        "(tenant_id, user_id) WHERE status = 'open'"
    )
    op.execute(
        """
        CREATE TABLE support_messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            conversation_id uuid NOT NULL,
            author_kind text NOT NULL CHECK (author_kind IN ('firm_user', 'staff')),
            author_user_id uuid NULL,
            staff_subject text NULL CHECK (char_length(staff_subject) BETWEEN 1 AND 200),
            body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 4000),
            related_article_slug text NULL CHECK (related_article_slug ~ '^[a-z0-9-]{3,120}$'),
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            CHECK ((author_kind = 'firm_user') = (author_user_id IS NOT NULL)),
            CHECK ((author_kind = 'staff') = (staff_subject IS NOT NULL)),
            FOREIGN KEY (tenant_id, conversation_id)
                REFERENCES support_conversations (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX support_messages_thread ON support_messages "
        "(tenant_id, conversation_id, created_at)"
    )
    op.execute(
        """
        CREATE TABLE support_conversation_reads (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            conversation_id uuid NOT NULL,
            reader_kind text NOT NULL CHECK (reader_kind IN ('firm_user', 'staff')),
            last_read_at timestamptz NOT NULL,
            PRIMARY KEY (tenant_id, conversation_id, reader_kind),
            FOREIGN KEY (tenant_id, conversation_id)
                REFERENCES support_conversations (tenant_id, id)
        )
        """
    )
    for table, columns in TENANT_INSERTS.items():
        tenant_table(op, table)
        insert_columns(op, table, columns)
    for table in INSERT_ONLY_TENANT:
        insert_only(op, table)
        _insert_only_trigger(table)
    for table, columns in TENANT_UPDATES.items():
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    for table in TENANT_INSERTS:
        if table not in TENANT_UPDATES:
            op.execute(f"REVOKE DELETE ON {table} FROM abacus_app")


def _global_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE help_articles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            slug text NOT NULL CHECK (slug ~ '^[a-z0-9-]{{3,120}}$'),
            version integer NOT NULL CHECK (version > 0),
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'withdrawn')),
            title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 160),
            summary text NOT NULL CHECK (char_length(btrim(summary)) BETWEEN 1 AND 300),
            group_key text NOT NULL CHECK (group_key ~ '^[a-z_]{{3,40}}$'),
            context_screen_ids text[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(context_screen_ids) <= 30),
            read_minutes smallint NOT NULL CHECK (read_minutes BETWEEN 1 AND 60),
            body jsonb NOT NULL CHECK (jsonb_typeof(body) = 'array'),
            body_schema_version integer NOT NULL DEFAULT 1 CHECK (body_schema_version > 0),
            search tsvector GENERATED ALWAYS AS (
                to_tsvector('english'::regconfig, title || ' ' || summary)
            ) STORED,
            drafted_by {_HANDLE.format(c="drafted_by")},
            drafted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            change_reason text NOT NULL
                CHECK (char_length(btrim(change_reason)) BETWEEN 1 AND 500),
            approved_by text NULL CHECK (char_length(approved_by) BETWEEN 1 AND 200),
            published_at timestamptz NULL,
            withdrawn_by text NULL CHECK (char_length(withdrawn_by) BETWEEN 1 AND 200),
            withdrawn_at timestamptz NULL,
            UNIQUE (slug, version),
            -- AC-52: two people; the approver is never the drafter.
            CHECK (approved_by IS NULL OR approved_by <> drafted_by),
            CHECK (status = 'draft' OR (approved_by IS NOT NULL AND published_at IS NOT NULL)),
            CHECK (status <> 'draft' OR (approved_by IS NULL AND published_at IS NULL)),
            CHECK ((status = 'withdrawn') = (withdrawn_at IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX help_articles_one_draft ON help_articles (slug) "
        "WHERE status = 'draft'"
    )
    op.execute(
        "CREATE UNIQUE INDEX help_articles_one_published ON help_articles (slug) "
        "WHERE status = 'published'"
    )
    op.execute(
        "CREATE INDEX help_articles_search ON help_articles USING gin (search) "
        "WHERE status = 'published'"
    )
    op.execute(
        """
        CREATE TABLE status_components (
            key text PRIMARY KEY CHECK (key ~ '^[a-z0-9_]{3,80}$'),
            label text NOT NULL CHECK (char_length(btrim(label)) BETWEEN 1 AND 120),
            kind text NOT NULL CHECK (kind IN ('core', 'integration')),
            integration_key text NULL CHECK (char_length(integration_key) BETWEEN 1 AND 80),
            display_order smallint NOT NULL DEFAULT 100,
            active boolean NOT NULL DEFAULT true,
            CHECK ((kind = 'integration') = (integration_key IS NOT NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE status_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            component_key text NOT NULL REFERENCES status_components (key),
            severity text NOT NULL CHECK (severity IN ('degraded', 'outage', 'maintenance')),
            title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 3 AND 120),
            public_note text NOT NULL CHECK (char_length(btrim(public_note)) BETWEEN 3 AND 280),
            started_at timestamptz NOT NULL DEFAULT abacus_now(),
            resolved_at timestamptz NULL CHECK (resolved_at IS NULL OR resolved_at >= started_at),
            posted_by {_HANDLE.format(c="posted_by")}
        )
        """
    )
    op.execute(
        "CREATE INDEX status_incidents_open ON status_incidents (component_key) "
        "WHERE resolved_at IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE status_incident_updates (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incident_id uuid NOT NULL REFERENCES status_incidents (id),
            kind text NOT NULL CHECK (kind IN ('posted', 'updated', 'resolved')),
            note text NOT NULL CHECK (char_length(btrim(note)) BETWEEN 3 AND 280),
            posted_by {_HANDLE.format(c="posted_by")},
            at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE platform_regions (
            code text PRIMARY KEY CHECK (code IN ('us', 'eu', 'uk')),
            label text NOT NULL CHECK (char_length(btrim(label)) BETWEEN 1 AND 80),
            status text NOT NULL CHECK (status IN ('live', 'planned')),
            planned_label text NULL CHECK (char_length(planned_label) BETWEEN 1 AND 80),
            storage_label text NULL CHECK (char_length(storage_label) BETWEEN 1 AND 120),
            backup_label text NULL CHECK (char_length(backup_label) BETWEEN 1 AND 120),
            inference_label text NULL CHECK (char_length(inference_label) BETWEEN 1 AND 120)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE platform_settings (
            key text PRIMARY KEY CHECK (key ~ '^[a-z_]{3,60}$'),
            value jsonb NOT NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE platform_tenant_directory (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            tenant_code text NOT NULL UNIQUE CHECK (tenant_code ~ '^tnt_[a-z0-9-]{2,40}$'),
            display_name text NOT NULL CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 200),
            region text NOT NULL REFERENCES platform_regions (code),
            seats_total integer NOT NULL DEFAULT 0 CHECK (seats_total >= 0),
            seats_used integer NOT NULL DEFAULT 0 CHECK (seats_used >= 0),
            modules text[] NOT NULL DEFAULT '{}',
            health text NOT NULL DEFAULT 'healthy'
                CHECK (health IN ('healthy', 'degraded', 'onboarding')),
            health_reason_code text NULL CHECK (health_reason_code ~ '^[a-z_]{3,60}$'),
            onboarding_state text NOT NULL DEFAULT 'ready'
                CHECK (onboarding_state IN ('invited', 'first_admin_signed_in', 'ready')),
            support_state text NULL CHECK (support_state IN
                ('requested', 'active', 'declined', 'revoked', 'ended', 'expired')),
            support_state_at timestamptz NULL,
            plan_requests_open integer NOT NULL DEFAULT 0 CHECK (plan_requests_open >= 0),
            synthetic boolean NOT NULL DEFAULT false,
            sandbox_of uuid NULL REFERENCES firms (tenant_id),
            since date NOT NULL,
            refreshed_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE platform_audit_events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            staff_subject text NOT NULL CHECK (char_length(staff_subject) BETWEEN 1 AND 200),
            staff_role text NOT NULL
                CHECK (staff_role IN ('platform_admin', 'platform_support_desk', 'system')),
            action text NOT NULL CHECK (action ~ '^[a-z_]+\\.[a-z_]+$'),
            target_kind text NOT NULL CHECK (target_kind ~ '^[a-z_]{3,40}$'),
            target_ref text NOT NULL CHECK (char_length(target_ref) BETWEEN 1 AND 200),
            tenant_id uuid NULL,
            reason text NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 500),
            -- Identifiers only (DEC-60): an object of scalars, never message bodies or names.
            facts jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(facts) = 'object')
        )
        """
    )
    op.execute(
        "CREATE INDEX platform_audit_events_tenant ON platform_audit_events (tenant_id, at DESC)"
    )
    for table in GLOBAL:
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC, abacus_app")
    for table in ("status_incident_updates", "platform_audit_events"):
        _insert_only_trigger(table)
    # A help article leaves `draft` once; afterwards only `published` -> `withdrawn` moves and
    # nothing else changes; a published or withdrawn version is never deleted (AC-52).
    op.execute(
        """
        CREATE FUNCTION help_articles_freeze() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' THEN
                RAISE EXCEPTION 'help_articles cannot be truncated'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.status <> 'draft' THEN
                    RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN OLD;
            END IF;
            IF NEW.id <> OLD.id OR NEW.slug <> OLD.slug OR NEW.version <> OLD.version
               OR NEW.drafted_by <> OLD.drafted_by OR NEW.drafted_at <> OLD.drafted_at THEN
                RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.status = 'draft' THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'published' AND NEW.status = 'withdrawn'
               AND NEW.title = OLD.title AND NEW.summary = OLD.summary
               AND NEW.group_key = OLD.group_key
               AND NEW.context_screen_ids = OLD.context_screen_ids
               AND NEW.read_minutes = OLD.read_minutes AND NEW.body = OLD.body
               AND NEW.body_schema_version = OLD.body_schema_version
               AND NEW.change_reason = OLD.change_reason
               AND NEW.approved_by = OLD.approved_by
               AND NEW.published_at = OLD.published_at THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'version_frozen' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER help_articles_freeze BEFORE UPDATE OR DELETE ON help_articles "
        "FOR EACH ROW EXECUTE FUNCTION help_articles_freeze()"
    )
    op.execute(
        "CREATE TRIGGER help_articles_no_truncate BEFORE TRUNCATE ON help_articles "
        "FOR EACH STATEMENT EXECUTE FUNCTION help_articles_freeze()"
    )


def _readers() -> None:
    op.execute(
        """
        CREATE FUNCTION platform_directory_list(p_region text, p_health text, p_q text)
        RETURNS SETOF platform_tenant_directory
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT d.* FROM public.platform_tenant_directory d
             WHERE (p_region IS NULL OR d.region = p_region)
               AND (p_health IS NULL OR d.health = p_health)
               AND (p_q IS NULL OR d.display_name ILIKE '%' || p_q || '%'
                    OR d.tenant_code ILIKE '%' || p_q || '%')
             ORDER BY d.since, d.tenant_code
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_directory_get(p_tenant_id uuid)
        RETURNS SETOF platform_tenant_directory
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT d.* FROM public.platform_tenant_directory d WHERE d.tenant_id = p_tenant_id
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_list(p_context text)
        RETURNS TABLE (id uuid, slug text, version integer, title text, summary text,
                       group_key text,
                       context_screen_ids text[], read_minutes smallint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT a.id, a.slug, a.version, a.title, a.summary, a.group_key,
                   a.context_screen_ids, a.read_minutes
              FROM public.help_articles a
             WHERE a.status = 'published'
             ORDER BY (p_context IS NOT NULL AND p_context = ANY (a.context_screen_ids)) DESC,
                      a.group_key, a.title
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_get(p_slug text)
        RETURNS TABLE (id uuid, slug text, version integer, title text, read_minutes smallint,
                       body jsonb, body_schema_version integer, published_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT a.id, a.slug, a.version, a.title, a.read_minutes, a.body,
                   a.body_schema_version, a.published_at
              FROM public.help_articles a
             WHERE a.slug = p_slug AND a.status = 'published'
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_search(p_q text)
        RETURNS TABLE (id uuid, slug text, version integer, title text, summary text,
                       group_key text,
                       context_screen_ids text[], read_minutes smallint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT a.id, a.slug, a.version, a.title, a.summary, a.group_key,
                   a.context_screen_ids, a.read_minutes
              FROM public.help_articles a
             WHERE a.status = 'published' AND a.search @@ plainto_tsquery('english', p_q)
             ORDER BY ts_rank(a.search, plainto_tsquery('english', p_q)) DESC, a.title
             LIMIT 50
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION status_snapshot()
        RETURNS TABLE (key text, label text, kind text, integration_key text,
                       display_order smallint, severity text, public_note text,
                       started_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT c.key, c.label, c.kind, c.integration_key, c.display_order, i.severity,
                   i.public_note, i.started_at
              FROM public.status_components c
              LEFT JOIN LATERAL (
                  SELECT s.severity, s.public_note, s.started_at
                    FROM public.status_incidents s
                   WHERE s.component_key = c.key AND s.resolved_at IS NULL
                   ORDER BY CASE s.severity WHEN 'outage' THEN 0 WHEN 'degraded' THEN 1
                            ELSE 2 END, s.started_at
                   LIMIT 1
              ) i ON true
             WHERE c.active
             ORDER BY c.display_order, c.key
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_regions_list() RETURNS SETOF platform_regions
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT r.* FROM public.platform_regions r
             ORDER BY (r.status = 'live') DESC, r.code
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_setting_get(p_key text)
        RETURNS TABLE (value jsonb, version integer)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            SELECT s.value, s.version FROM public.platform_settings s WHERE s.key = p_key
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION platform_audit_record(p_staff_subject text, p_staff_role text,
                                              p_action text, p_target_kind text,
                                              p_target_ref text, p_tenant_id uuid,
                                              p_reason text, p_facts jsonb)
        RETURNS bigint
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, tenant_id, reason, facts)
            VALUES (p_staff_subject, p_staff_role, p_action, p_target_kind, p_target_ref,
                    p_tenant_id, p_reason, coalesce(p_facts, '{}'::jsonb))
            RETURNING id
        $$
        """
    )


def _writers() -> None:
    op.execute(
        """
        CREATE FUNCTION platform_directory_upsert(
            p_tenant_id uuid, p_tenant_code text, p_display_name text, p_region text,
            p_seats_total integer, p_seats_used integer, p_modules text[], p_health text,
            p_health_reason_code text, p_onboarding_state text, p_support_state text,
            p_support_state_at timestamptz, p_plan_requests_open integer, p_synthetic boolean,
            p_sandbox_of uuid, p_since date)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            INSERT INTO public.platform_tenant_directory AS d (tenant_id, tenant_code,
                display_name, region, seats_total, seats_used, modules, health,
                health_reason_code, onboarding_state, support_state, support_state_at,
                plan_requests_open, synthetic, sandbox_of, since, refreshed_at)
            VALUES (p_tenant_id, p_tenant_code, p_display_name, p_region, p_seats_total,
                    p_seats_used, p_modules, p_health, p_health_reason_code, p_onboarding_state,
                    p_support_state, p_support_state_at, p_plan_requests_open, p_synthetic,
                    p_sandbox_of, p_since, clock_timestamp())
            ON CONFLICT (tenant_id) DO UPDATE SET tenant_code = EXCLUDED.tenant_code,
                display_name = EXCLUDED.display_name, region = EXCLUDED.region,
                seats_total = EXCLUDED.seats_total, seats_used = EXCLUDED.seats_used,
                modules = EXCLUDED.modules, health = EXCLUDED.health,
                health_reason_code = EXCLUDED.health_reason_code,
                onboarding_state = EXCLUDED.onboarding_state,
                support_state = EXCLUDED.support_state,
                support_state_at = EXCLUDED.support_state_at,
                plan_requests_open = EXCLUDED.plan_requests_open,
                synthetic = EXCLUDED.synthetic, sandbox_of = EXCLUDED.sandbox_of,
                since = EXCLUDED.since, refreshed_at = clock_timestamp()
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_draft(p_slug text, p_title text, p_summary text,
                                           p_group_key text, p_context_screen_ids text[],
                                           p_read_minutes integer, p_body jsonb,
                                           p_drafted_by text, p_change_reason text)
        RETURNS uuid
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
            INSERT INTO public.help_articles (slug, version, title, summary, group_key,
                context_screen_ids, read_minutes, body, drafted_by, change_reason)
            SELECT p_slug, coalesce(max(a.version), 0) + 1, p_title, p_summary, p_group_key,
                   coalesce(p_context_screen_ids, '{}'), p_read_minutes, p_body, p_drafted_by,
                   p_change_reason
              FROM public.help_articles a WHERE a.slug = p_slug
            RETURNING id
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_publish(p_id uuid, p_approver text, p_reason text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v public.help_articles%ROWTYPE;
        BEGIN
            SELECT * INTO v FROM public.help_articles WHERE id = p_id FOR UPDATE;
            IF NOT FOUND OR v.status <> 'draft' THEN
                RAISE EXCEPTION 'not_a_draft' USING ERRCODE = 'check_violation';
            END IF;
            IF v.drafted_by = p_approver THEN
                RAISE EXCEPTION 'approver_is_drafter' USING ERRCODE = 'check_violation';
            END IF;
            -- The published predecessor is withdrawn by the same two people (one published).
            UPDATE public.help_articles SET status = 'withdrawn', withdrawn_by = p_approver,
                   withdrawn_at = clock_timestamp()
             WHERE slug = v.slug AND status = 'published';
            UPDATE public.help_articles SET status = 'published', approved_by = p_approver,
                   published_at = clock_timestamp()
             WHERE id = p_id;
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, reason, facts)
            VALUES (p_approver, 'platform_admin', 'help_article.published', 'help_article',
                    v.slug, p_reason, jsonb_build_object('version', v.version,
                                                         'drafted_by', v.drafted_by));
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION help_article_withdraw(p_id uuid, p_operator text, p_reason text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v public.help_articles%ROWTYPE;
        BEGIN
            SELECT * INTO v FROM public.help_articles WHERE id = p_id FOR UPDATE;
            IF NOT FOUND OR v.status <> 'published' THEN
                RAISE EXCEPTION 'not_published' USING ERRCODE = 'check_violation';
            END IF;
            UPDATE public.help_articles SET status = 'withdrawn', withdrawn_by = p_operator,
                   withdrawn_at = clock_timestamp()
             WHERE id = p_id;
            INSERT INTO public.platform_audit_events (staff_subject, staff_role, action,
                target_kind, target_ref, reason, facts)
            VALUES (p_operator, 'platform_admin', 'help_article.withdrawn', 'help_article',
                    v.slug, p_reason, jsonb_build_object('version', v.version));
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION status_incident_post(p_component_key text, p_severity text,
                                             p_title text, p_note text, p_posted_by text)
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            v_id uuid;
        BEGIN
            INSERT INTO public.status_incidents (component_key, severity, title, public_note,
                posted_by)
            VALUES (p_component_key, p_severity, p_title, p_note, p_posted_by)
            RETURNING id INTO v_id;
            INSERT INTO public.status_incident_updates (incident_id, kind, note, posted_by)
            VALUES (v_id, 'posted', p_note, p_posted_by);
            RETURN v_id;
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION status_incident_update(p_id uuid, p_note text, p_posted_by text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.status_incidents SET public_note = p_note
             WHERE id = p_id AND resolved_at IS NULL;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'incident_not_open' USING ERRCODE = 'check_violation';
            END IF;
            INSERT INTO public.status_incident_updates (incident_id, kind, note, posted_by)
            VALUES (p_id, 'updated', p_note, p_posted_by);
        END $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION status_incident_resolve(p_id uuid, p_note text, p_posted_by text)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            UPDATE public.status_incidents SET resolved_at = abacus_now(), public_note = p_note
             WHERE id = p_id AND resolved_at IS NULL;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'incident_not_open' USING ERRCODE = 'check_violation';
            END IF;
            INSERT INTO public.status_incident_updates (incident_id, kind, note, posted_by)
            VALUES (p_id, 'resolved', p_note, p_posted_by);
        END $$
        """
    )


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        "ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_MODULES_NEW})"
    )
    _tenant_tables()
    _global_tables()
    _readers()
    _writers()
    for signature in READERS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")
    for signature in (*OWNER_ONLY, *TRIGGERS):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM abacus_app")


def downgrade() -> None:
    for signature in (*READERS, *OWNER_ONLY):
        op.execute(f"DROP FUNCTION {signature}")
    for table in reversed(GLOBAL):
        op.execute(f"DROP TABLE {table}")
    for table in (
        "support_conversation_reads", "support_messages", "support_conversations",
        "plan_change_requests", "usage_alert_events", "usage_alert_rules",
        "usage_alert_policies", "plan_entitlements",
    ):  # fmt: skip
        op.execute(f"DROP TABLE {table}")
    for signature in TRIGGERS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(f"DELETE FROM tenant_entitlements WHERE module IN {_SERVICE_LINES}")  # noqa: S608 -- fixed SQL, no input
    op.execute("ALTER TABLE tenant_entitlements DROP CONSTRAINT tenant_entitlements_module_check")
    op.execute(
        "ALTER TABLE tenant_entitlements ADD CONSTRAINT tenant_entitlements_module_check "
        f"CHECK (module IN {_MODULES_OLD})"
    )
