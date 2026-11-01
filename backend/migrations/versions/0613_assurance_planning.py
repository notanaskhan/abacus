"""A-04 M2 `assurance_planning` (A-04-T06; A-04 §4.2; SPEC-620; DEC-1866): expand-only.

The planning record of an audit work item. Each table has `tenant_id`, `engagement_id` and
`work_item_id`, and forced row-level security; walls are `visible()` in the service, as on every
engagement table:

- `materiality_versions` (insert-only): AUD-07's versions. A decided, reassessed or revised row
  names the person's `decisions` row on its card. `decisions` is human-only (0094), and a guard
  checks that the decision is this firm's and on this version's card. "Current" and "Superseded"
  are derived, never stored.
- `risk_register_rows`: AUD-08's register. The plan calls the table `risks`, but SPEC-300's live
  `risks` and `risk_versions` (0066) keep that name (DEC-1757's rule, DEC-1866). Management
  override is never rebuttable.
- `risk_linkages`: a risk's links to program steps, workpapers and procedures.
- `service_organizations`: the inventory AUD-04 and AUD-10 share.
- `fraud_brainstorm_sessions`: one per work item, with the minutes as text (Confidential).
- `fraud_minutes_approvals` (insert-only): the engagement partner's approval of a minutes hash.
  `actor_kind` is `human`, and a guard binds the approver to the session's own person.
- `fraud_inquiries`: management and governance inquiries. "Requested" or "Answered" is derived
  from `answered_at`.

Status CHECKs are the status vocabulary's codes, frozen here; a test holds them equal to
`docs/product/status-vocabulary.yaml`.

Revision ID: 0613
Revises: 0612
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0613"
down_revision = "0612"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""

# The status vocabulary's codes (status-vocabulary.yaml), frozen as of this migration.
MATERIALITY_VERSION = ("proposed", "decided", "reassessed", "revised")
RISK_REGISTER_ROW = ("draft", "ep_approved", "revised")
RISK_SIGNIFICANCE = ("none", "mandatory", "proposed", "approved", "not_significant")
RISK_FRAUD = ("none", "presumed", "rebuttal_proposed", "rebuttal_approved")
RISK_LINKAGE = ("linked", "suggested")
FRAUD_MINUTES = ("draft", "awaiting_approval", "approved")
SERVICE_ORGANIZATION = (
    "pending",
    "gap_found",
    "bridge_letter_received",
    "reliance_concluded",
    "certification_accepted",
    "no_reliance",
    "not_relevant",
)


def _in(codes: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{c}'" for c in codes) + ")"


_TABLES = (
    "fraud_inquiries",
    "fraud_minutes_approvals",
    "fraud_brainstorm_sessions",
    "service_organizations",
    "risk_linkages",
    "risk_register_rows",
    "materiality_versions",
)
_INSERT_ONLY = ("materiality_versions", "fraud_minutes_approvals")
_JSON_OBJECT = "jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof({name}) = 'object')"
_JSON_ARRAY = "jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof({name}) = 'array')"

INSERTS: dict[str, tuple[str, ...]] = {
    "materiality_versions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "version_no",
        "status",
        "basis",
        "tb_snapshot_id",
        "tb_layer",
        "benchmarks",
        "benchmark_key",
        "rate_pct",
        "overall",
        "pm_pct",
        "pm",
        "ct_pct",
        "ct",
        "specific",
        "qualitative_factors",
        "prior_year_overall",
        "policy_version_id",
        "decision_card_id",
        "decision_id",
        "reassessment",
        "impact",
        "engine_name",
        "engine_version",
        "inputs_hash",
        "computed_at",
        "created_by_kind",
        "created_by_user_id",
        "on_behalf_of_user_id",
    ),
    "risk_register_rows": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "code",
        "level",
        "area_key",
        "area_label",
        "assertions",
        "inherent_risk",
        "control_risk",
        "rmm",
        "rmm_policy_version_id",
        "significance",
        "fraud",
        "presumption_kind",
        "inherent_factors",
        "rationale",
        "status",
        "approved_card_id",
        "content_hash",
        "version_no",
    ),
    "risk_linkages": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "risk_id",
        "target_kind",
        "target_ref",
        "state",
        "suggestion_id",
    ),
    "service_organizations": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "name",
        "services",
        "relevant",
        "evidence_type",
        "status",
        "subservice_orgs",
        "third_party_contact_id",
    ),
    "fraud_brainstorm_sessions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "held_at",
        "medium",
        "led_by_user_id",
        "attendees",
        "excluded",
        "discussion",
        "presumed_risk_conclusions",
        "minutes_text",
        "minutes_hash",
        "minutes_status",
        "minutes_source",
    ),
    "fraud_minutes_approvals": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "session_id",
        "minutes_hash",
        "approved_by_user_id",
        "actor_kind",
    ),
    "fraud_inquiries": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "respondent_contact_id",
        "governance_body_ref",
        "questionnaire_id",
    ),
}
# A risk's fields move through `review.api.record_value` (field history) with a new content hash
# and version; a linkage is suggested, linked or removed; an organization's evidence and status
# move as the SOC work proceeds; the session's minutes are a person's draft until approved.
UPDATES: dict[str, tuple[str, ...]] = {
    "risk_register_rows": (
        "area_label",
        "assertions",
        "inherent_risk",
        "control_risk",
        "rmm",
        "rmm_policy_version_id",
        "significance",
        "fraud",
        "inherent_factors",
        "rationale",
        "status",
        "approved_card_id",
        "content_hash",
        "version_no",
        "updated_at",
    ),
    "risk_linkages": ("state", "suggestion_id", "removed_at"),
    "service_organizations": (
        "services",
        "relevant",
        "evidence_type",
        "status",
        "subservice_orgs",
        "third_party_contact_id",
        "updated_at",
    ),
    "fraud_brainstorm_sessions": (
        "held_at",
        "medium",
        "led_by_user_id",
        "attendees",
        "excluded",
        "discussion",
        "presumed_risk_conclusions",
        "minutes_text",
        "minutes_hash",
        "minutes_status",
        "minutes_source",
        "updated_at",
    ),
    "fraud_inquiries": ("answered_at",),
}

_MATERIALITY_GUARD = """
CREATE FUNCTION materiality_versions_decision_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NEW.decision_id IS NULL THEN
        RETURN NEW;
    END IF;
    -- A person's decision on this version's own card, in this firm (decisions is human-only).
    IF NOT EXISTS (
        SELECT 1 FROM public.decisions d
         WHERE d.id = NEW.decision_id
           AND d.tenant_id = NEW.tenant_id
           AND d.card_id = NEW.decision_card_id
           AND d.actor_kind = 'human'
    ) THEN
        RAISE EXCEPTION 'a materiality version names the person''s decision on its own card'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
_MINUTES_GUARD = """
CREATE FUNCTION fraud_minutes_approvals_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
       OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.approved_by_user_id::text
    THEN
        RAISE EXCEPTION 'the minutes are approved by the session''s own person'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    money = "numeric(18, 2) NOT NULL CHECK ({name} >= 0)"
    pct = "numeric(7, 4) NOT NULL CHECK ({name} > 0 AND {name} <= 100)"
    op.execute(
        f"""
        CREATE TABLE materiality_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            version_no integer NOT NULL CHECK (version_no >= 1),
            status text NOT NULL CHECK (status IN {_in(MATERIALITY_VERSION)}),
            basis text NOT NULL CHECK (basis IN ('unadjusted', 'final')),
            tb_snapshot_id uuid NULL,
            tb_layer text NULL CHECK (char_length(tb_layer) <= 40),
            benchmarks {_JSON_ARRAY.format(name="benchmarks")},
            benchmark_key text NOT NULL CHECK (benchmark_key ~ '^[a-z][a-z0-9_]{{0,63}}$'),
            rate_pct {pct.format(name="rate_pct")},
            overall {money.format(name="overall")},
            pm_pct {pct.format(name="pm_pct")},
            pm {money.format(name="pm")},
            ct_pct {pct.format(name="ct_pct")},
            ct {money.format(name="ct")},
            specific jsonb NULL CHECK (specific IS NULL OR jsonb_typeof(specific) = 'array'),
            qualitative_factors {_JSON_ARRAY.format(name="qualitative_factors")},
            prior_year_overall jsonb NULL
                CHECK (prior_year_overall IS NULL OR jsonb_typeof(prior_year_overall) = 'object'),
            policy_version_id uuid NULL,
            decision_card_id uuid NULL,
            decision_id uuid NULL,
            reassessment jsonb NULL
                CHECK (reassessment IS NULL OR jsonb_typeof(reassessment) = 'object'),
            impact jsonb NULL CHECK (impact IS NULL OR jsonb_typeof(impact) = 'object'),
            engine_name text NOT NULL CHECK (char_length(engine_name) BETWEEN 1 AND 40),
            engine_version text NOT NULL CHECK (char_length(engine_version) BETWEEN 1 AND 20),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{{64}}$'),
            computed_at timestamptz NOT NULL,
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('agent', 'human')),
            created_by_user_id uuid NOT NULL,
            on_behalf_of_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, version_no),
            -- AC3.4: a version past `proposed` is a person's decision (A-04 §4.2 M2).
            CONSTRAINT materiality_versions_decided_by_a_person
                CHECK (status = 'proposed' OR decision_id IS NOT NULL),
            CHECK (decision_id IS NULL OR decision_card_id IS NOT NULL),
            CHECK (pm <= overall AND ct <= overall),
            FOREIGN KEY (tenant_id, decision_card_id)
                REFERENCES decision_cards (tenant_id, id),
            FOREIGN KEY (decision_id) REFERENCES decisions (id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE risk_register_rows (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            code text NOT NULL CHECK (code ~ '^R[1-9][0-9]{{0,2}}$'),
            level text NOT NULL CHECK (level IN ('financial_statement', 'assertion')),
            area_key text NOT NULL CHECK (area_key ~ '^[a-z][a-z0-9_]{{0,63}}$'),
            area_label text NOT NULL CHECK (char_length(btrim(area_label)) BETWEEN 1 AND 120),
            assertions text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(assertions) <= 12),
            inherent_risk text NOT NULL CHECK (inherent_risk IN ('low', 'moderate', 'high')),
            control_risk text NOT NULL
                CHECK (control_risk IN ('low', 'moderate', 'high', 'max')),
            rmm text NOT NULL CHECK (rmm IN ('low', 'moderate', 'high')),
            rmm_policy_version_id uuid NULL,
            significance text NOT NULL DEFAULT 'none'
                CHECK (significance IN {_in(RISK_SIGNIFICANCE)}),
            fraud text NOT NULL DEFAULT 'none' CHECK (fraud IN {_in(RISK_FRAUD)}),
            presumption_kind text NOT NULL DEFAULT 'none'
                CHECK (presumption_kind IN ('none', 'management_override',
                    'revenue_recognition')),
            inherent_factors {_JSON_ARRAY.format(name="inherent_factors")},
            rationale text NULL CHECK (char_length(rationale) <= 4000),
            status text NOT NULL DEFAULT 'draft' CHECK (status IN {_in(RISK_REGISTER_ROW)}),
            approved_card_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
            version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, code),
            -- AC4.5: management override is presumed and never rebuttable (AU-C 240).
            CONSTRAINT risk_register_rows_override_not_rebuttable CHECK (NOT (
                presumption_kind = 'management_override'
                AND fraud IN ('rebuttal_proposed', 'rebuttal_approved'))),
            FOREIGN KEY (tenant_id, approved_card_id)
                REFERENCES decision_cards (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE risk_linkages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            risk_id uuid NOT NULL,
            target_kind text NOT NULL
                CHECK (target_kind IN ('program_step', 'workpaper', 'procedure')),
            target_ref text NOT NULL CHECK (char_length(target_ref) BETWEEN 1 AND 120),
            state text NOT NULL CHECK (state IN {_in(RISK_LINKAGE)}),
            suggestion_id uuid NULL,
            removed_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (state <> 'suggested' OR suggestion_id IS NOT NULL),
            FOREIGN KEY (tenant_id, risk_id) REFERENCES risk_register_rows (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX risk_linkages_one_live ON risk_linkages "
        "(tenant_id, risk_id, target_kind, target_ref) WHERE removed_at IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE service_organizations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            name text NOT NULL CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),
            services text NOT NULL DEFAULT '' CHECK (char_length(services) <= 500),
            relevant boolean NOT NULL DEFAULT true,
            evidence_type text NOT NULL DEFAULT 'none' CHECK (evidence_type IN
                ('soc1_type2', 'soc1_type1', 'certification', 'tested_directly', 'none')),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN {_in(SERVICE_ORGANIZATION)}),
            subservice_orgs {_JSON_ARRAY.format(name="subservice_orgs")},
            third_party_contact_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, name),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fraud_brainstorm_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            held_at timestamptz NULL,
            medium text NULL CHECK (medium IN ('in_person', 'video', 'hybrid')),
            led_by_user_id uuid NULL,
            attendees {_JSON_ARRAY.format(name="attendees")},
            excluded {_JSON_ARRAY.format(name="excluded")},
            discussion {_JSON_ARRAY.format(name="discussion")},
            presumed_risk_conclusions {_JSON_OBJECT.format(name="presumed_risk_conclusions")},
            minutes_text text NULL CHECK (char_length(minutes_text) <= 20000),
            minutes_hash text NULL CHECK (minutes_hash ~ '^[0-9a-f]{{64}}$'),
            minutes_status text NOT NULL DEFAULT 'draft'
                CHECK (minutes_status IN {_in(FRAUD_MINUTES)}),
            minutes_source text NULL CHECK (minutes_source IN ('human', 'adopted_suggestion')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id),
            CHECK ((minutes_text IS NULL) = (minutes_hash IS NULL)),
            CHECK (minutes_status = 'draft' OR minutes_hash IS NOT NULL),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fraud_minutes_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            session_id uuid NOT NULL,
            minutes_hash text NOT NULL CHECK (minutes_hash ~ '^[0-9a-f]{{64}}$'),
            approved_by_user_id uuid NOT NULL,
            -- AC2.4 (INV-1): a person only; the guard binds them to the session's actor.
            actor_kind text NOT NULL CONSTRAINT fraud_minutes_approvals_human_only
                CHECK (actor_kind = 'human'),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, session_id, minutes_hash),
            FOREIGN KEY (tenant_id, session_id)
                REFERENCES fraud_brainstorm_sessions (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE fraud_inquiries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            respondent_contact_id uuid NULL,
            governance_body_ref text NULL CHECK (char_length(governance_body_ref) <= 120),
            questionnaire_id uuid NULL,
            answered_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK ((respondent_contact_id IS NULL) <> (governance_body_ref IS NULL)),{_SCOPE_FK}
        )
        """
    )
    for table in _TABLES:
        op.execute(f"CREATE INDEX {table}_work_item ON {table} (tenant_id, work_item_id)")
    op.execute(_MATERIALITY_GUARD)
    op.execute(
        "CREATE TRIGGER materiality_versions_decision BEFORE INSERT ON materiality_versions "
        "FOR EACH ROW EXECUTE FUNCTION materiality_versions_decision_guard()"
    )
    op.execute(_MINUTES_GUARD)
    op.execute(
        "CREATE TRIGGER fraud_minutes_approvals_actor BEFORE INSERT ON fraud_minutes_approvals "
        "FOR EACH ROW EXECUTE FUNCTION fraud_minutes_approvals_guard()"
    )
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        insert_only(op, table)
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION fraud_minutes_approvals_guard()")
    op.execute("DROP FUNCTION materiality_versions_decision_guard()")
