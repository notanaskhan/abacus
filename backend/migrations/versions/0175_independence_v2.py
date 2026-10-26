"""P-07-T41 (M7): independence in-app, CLI-08 (P-07 §4.2 M7; SPEC-332 AC-17 to AC-22, AC-27,
AC-28; DEC-428).

- `independence_confirmations` (SPEC-025's, 0036) gains `statements` (the statement version and
  the three codes a person ticked), `interests_note` and `decline_note` (sealed per tenant),
  `reminder_count` and `last_reminded_at`. SPEC-025's plain `note` stays for its adapter route
  until P-07-T59.
- `independence_conclusions` (insert-only): the engagement partner's conclusion, one of three
  options, safeguards sealed (required for "with safeguards"), `mfa_verified_at`, `actor_kind =
  'human'` CHECK; a later conclusion names the one it supersedes (one successor each, one first
  per engagement). `independence_conclusions_guard` (BEFORE INSERT): `concluded_by` is the acting
  person, an engagement partner on the engagement and a partner-level staff member.
- `nas_evaluations` (insert-only, one per engagement and service code) and
  `nas_evaluation_events` (insert-only; the newest is the row's state: provided, status,
  evaluation and safeguards sealed, the SKE designee contact).
- `independence_breaches` (insert-only; the description sealed) and `independence_breach_events`
  (insert-only; evaluated, TCWG communicated, remediated, each once per breach).
- The person columns of the NAS, breach and breach-event rows are the acting person (0165's
  `acting_person_is`).
- `abacus_human_only_actions()`: 0168's 40 entries plus `independence.concluded` and
  `nas.evaluated` (42); the downgrade restores 0168's list.

SPEC-025's free-text `independence_concluded_by/at` are not converted here (a conclusion row needs
a concluder id the legacy text cannot give): G2 reads the newest conclusion row where one exists
and SPEC-025's row otherwise, until P-07-T59 converts and drops the table (DEC-428, as DEC-372).

Security review (DEC-429):
- `engagement_acceptance.legacy_g2` (new, default true, so every row written before 0175 has
  it): `engagement_acceptance_written_by_app` sets it false on any row the application writes
  from now on (the owner's paths and superuser seeding are not the app, as 0154's guard), so
  SPEC-025's route can never meet G2 again; G2 falls back only to rows with `legacy_g2`.
- `independence_confirmations_own_answer` (BEFORE UPDATE OF the answer columns only: status,
  statement_version, statements, interests_note, decline_note, note, answered_at): written by
  the app, the row is the acting person's own (`app.actor_id`) and `app.actor_kind` is `human`.
  Reminder counts (another person's row) and inserts (the member-added request) stay unbound.
- A conclusion supersedes one of the same engagement (`(tenant_id, engagement_id,
  supersedes_id)` foreign key on a new unique key).

Revision ID: 0175
Revises: 0180
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0175"
down_revision = "0180"
branch_labels = None
depends_on = None

# The register as 0168 left it (40 entries).
_HUMAN_ONLY_0168 = sorted(
    [
        "acceptance.decided",
        "acceptance.review_completed",
        "assurance.phase_recorded",
        "conflict.cleared",
        "contact.unlocked",
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
        "eqr.eligibility_approved",
        "evidence.accepted",
        "firm.ai_client_data_opted_in",
        "firm_export.approved",
        "firm_export.declined",
        "follow_up.sent",
        "fulfilment.voided",
        "going_concern.decided",
        "guidance_draft.approved",
        "independence.annual_confirmed",
        "independence.annual_declined",
        "independence.confirmed",
        "independence.declined",
        "independence.statement_published",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
        "portal_mfa.reset",
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "review_decision.created",
        "review_decision.undone",
        "risk.approved",
        "sample.approved",
        "service_line_policy.updated",
        "sign_off.recorded",
        "statement.approved",
        "team.approved",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0168, "independence.concluded", "nas.evaluated"])

_HUMAN = (
    "text NOT NULL DEFAULT current_setting('app.actor_kind', true) CHECK (actor_kind = 'human')"
)
_ENGAGEMENT_FK = "FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)"
_TABLES = (
    "independence_conclusions",
    "nas_evaluations",
    "nas_evaluation_events",
    "independence_breaches",
    "independence_breach_events",
)
_BOUND = (
    ("nas_evaluations", "created_by"),
    ("nas_evaluation_events", "recorded_by"),
    ("independence_breaches", "logged_by"),
    ("independence_breach_events", "recorded_by"),
)
_CONCLUSION_GUARD = """
    CREATE FUNCTION independence_conclusions_guard() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF current_setting('app.actor_id', true) IS DISTINCT FROM NEW.concluded_by::text THEN
            RAISE EXCEPTION 'a conclusion is the acting person''s own'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.engagement_members m
             WHERE m.tenant_id = NEW.tenant_id AND m.engagement_id = NEW.engagement_id
               AND m.user_id = NEW.concluded_by AND m.role = 'engagement_partner'
        ) OR NOT EXISTS (
            SELECT 1 FROM public.memberships s
             WHERE s.tenant_id = NEW.tenant_id AND s.user_id = NEW.concluded_by
               AND s.status = 'active' AND s.kind = 'staff' AND s.level = 'partner'
        ) THEN
            RAISE EXCEPTION 'only a partner-level engagement partner concludes independence'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""


# 0154's precedent: the owner's definer paths and superuser seeding are not the application.
_BY_APP = (
    "current_user <> 'abacus_owner' "
    "AND NOT (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)"
)
_OWN_ANSWER = f"""
    CREATE FUNCTION independence_confirmations_own_answer() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF {_BY_APP} AND (
            current_setting('app.actor_id', true) IS DISTINCT FROM NEW.user_id::text
            OR current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
        ) THEN
            RAISE EXCEPTION 'an independence answer is the acting person''s own'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$
"""
_LEGACY_CUTOFF = f"""
    CREATE FUNCTION engagement_acceptance_written_by_app() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    BEGIN
        IF {_BY_APP} THEN
            NEW.legacy_g2 := false;
        END IF;
        RETURN NEW;
    END $$
"""
_ANSWER_COLUMNS = (
    "status, statement_version, statements, interests_note, decline_note, note, answered_at"
)


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")


def upgrade() -> None:
    # --- confirmations: the statements, sealed notes, reminders --------------------------------
    op.execute(
        """
        ALTER TABLE independence_confirmations
            ADD COLUMN statements jsonb NULL
                CHECK (statements IS NULL OR jsonb_typeof(statements) = 'object'),
            ADD COLUMN interests_note bytea NULL CHECK (octet_length(interests_note) <= 65536),
            ADD COLUMN decline_note bytea NULL CHECK (octet_length(decline_note) <= 65536),
            ADD COLUMN reminder_count integer NOT NULL DEFAULT 0 CHECK (reminder_count >= 0),
            ADD COLUMN last_reminded_at timestamptz NULL
        """
    )
    op.execute(
        "GRANT UPDATE (statements, interests_note, decline_note, reminder_count, "
        "last_reminded_at) ON independence_confirmations TO abacus_app"
    )
    op.execute(_OWN_ANSWER)
    op.execute(
        "CREATE TRIGGER independence_confirmations_own_answer BEFORE UPDATE OF "
        f"{_ANSWER_COLUMNS} ON independence_confirmations "
        "FOR EACH ROW EXECUTE FUNCTION independence_confirmations_own_answer()"
    )
    # SPEC-025's conclusion counts for G2 only on rows the app wrote before this migration.
    op.execute(
        "ALTER TABLE engagement_acceptance ADD COLUMN legacy_g2 boolean NOT NULL DEFAULT true"
    )
    op.execute(_LEGACY_CUTOFF)
    op.execute(
        "CREATE TRIGGER engagement_acceptance_written_by_app BEFORE INSERT ON "
        "engagement_acceptance FOR EACH ROW EXECUTE FUNCTION "
        "engagement_acceptance_written_by_app()"
    )

    # --- the conclusion -------------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE independence_conclusions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            option text NOT NULL CHECK (
                option IN ('independent', 'independent_with_safeguards', 'not_independent')
            ),
            safeguards_sealed bytea NULL CHECK (octet_length(safeguards_sealed) <= 65536),
            concluded_by uuid NOT NULL,
            concluded_at timestamptz NOT NULL DEFAULT abacus_now(),
            mfa_verified_at timestamptz NOT NULL,
            supersedes_id uuid NULL,
            actor_kind {_HUMAN},
            CONSTRAINT independence_conclusions_safeguards
                CHECK (option <> 'independent_with_safeguards' OR safeguards_sealed IS NOT NULL),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, id),
            UNIQUE (tenant_id, supersedes_id),
            {_ENGAGEMENT_FK},
            FOREIGN KEY (tenant_id, engagement_id, supersedes_id)
                REFERENCES independence_conclusions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, concluded_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX independence_conclusions_first ON independence_conclusions "
        "(tenant_id, engagement_id) WHERE supersedes_id IS NULL"
    )
    op.execute(
        "CREATE INDEX independence_conclusions_by_engagement ON independence_conclusions "
        "(tenant_id, engagement_id, concluded_at)"
    )

    # --- NAS ------------------------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE nas_evaluations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            service_code text NOT NULL CHECK (service_code ~ '^[a-z0-9_]{{1,64}}$'),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind {_HUMAN},
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, engagement_id, service_code),
            {_ENGAGEMENT_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE nas_evaluation_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            seq bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            nas_id uuid NOT NULL,
            provided boolean NOT NULL,
            status text NOT NULL CHECK (status IN ('pending', 'concluded', 'not_applicable')),
            evaluation_sealed bytea NULL CHECK (octet_length(evaluation_sealed) <= 65536),
            safeguards_sealed bytea NULL CHECK (octet_length(safeguards_sealed) <= 65536),
            ske_contact_id uuid NULL,
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind {_HUMAN},
            FOREIGN KEY (tenant_id, nas_id) REFERENCES nas_evaluations (tenant_id, id),
            FOREIGN KEY (tenant_id, ske_contact_id) REFERENCES contacts (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX nas_evaluation_events_by_row ON nas_evaluation_events "
        "(tenant_id, nas_id, seq DESC)"
    )

    # --- breaches -------------------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TABLE independence_breaches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            description_sealed bytea NOT NULL CHECK (octet_length(description_sealed) <= 65536),
            user_id uuid NULL,
            logged_by uuid NOT NULL,
            logged_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind {_HUMAN},
            UNIQUE (tenant_id, id),
            {_ENGAGEMENT_FK},
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX independence_breaches_by_engagement ON independence_breaches "
        "(tenant_id, engagement_id, logged_at)"
    )
    op.execute(
        f"""
        CREATE TABLE independence_breach_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            breach_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('evaluated', 'tcwg_communicated', 'remediated')),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind {_HUMAN},
            UNIQUE (tenant_id, breach_id, kind),
            FOREIGN KEY (tenant_id, breach_id) REFERENCES independence_breaches (tenant_id, id)
        )
        """
    )

    # --- row-level security, grants, guards -----------------------------------------------------
    for table in _TABLES:
        tenant_table(op, table)
        _immutable(table)
    insert_columns(
        op,
        "independence_conclusions",
        (
            "id",
            "tenant_id",
            "engagement_id",
            "option",
            "safeguards_sealed",
            "concluded_by",
            "mfa_verified_at",
            "supersedes_id",
        ),
    )
    insert_columns(
        op, "nas_evaluations", ("id", "tenant_id", "engagement_id", "service_code", "created_by")
    )
    insert_columns(
        op,
        "nas_evaluation_events",
        (
            "id",
            "tenant_id",
            "nas_id",
            "provided",
            "status",
            "evaluation_sealed",
            "safeguards_sealed",
            "ske_contact_id",
            "recorded_by",
        ),
    )
    insert_columns(
        op,
        "independence_breaches",
        ("id", "tenant_id", "engagement_id", "description_sealed", "user_id", "logged_by"),
    )
    insert_columns(
        op,
        "independence_breach_events",
        ("id", "tenant_id", "breach_id", "kind", "note_sealed", "recorded_by"),
    )
    op.execute(_CONCLUSION_GUARD)
    op.execute(
        "CREATE TRIGGER independence_conclusions_guard BEFORE INSERT ON independence_conclusions "
        "FOR EACH ROW EXECUTE FUNCTION independence_conclusions_guard()"
    )
    for table, column in _BOUND:
        op.execute(
            f"CREATE TRIGGER {table}_acting_person BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION acting_person_is('{column}')"
        )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0168)
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
        op.execute(f"DROP FUNCTION {table}_immutable()")
    op.execute("DROP FUNCTION independence_conclusions_guard()")
    op.execute("DROP TRIGGER engagement_acceptance_written_by_app ON engagement_acceptance")
    op.execute("DROP FUNCTION engagement_acceptance_written_by_app()")
    op.execute("ALTER TABLE engagement_acceptance DROP COLUMN legacy_g2")
    op.execute("DROP TRIGGER independence_confirmations_own_answer ON independence_confirmations")
    op.execute("DROP FUNCTION independence_confirmations_own_answer()")
    op.execute(
        "REVOKE UPDATE (statements, interests_note, decline_note, reminder_count, "
        "last_reminded_at) ON independence_confirmations FROM abacus_app"
    )
    op.execute(
        """
        ALTER TABLE independence_confirmations
            DROP COLUMN last_reminded_at,
            DROP COLUMN reminder_count,
            DROP COLUMN decline_note,
            DROP COLUMN interests_note,
            DROP COLUMN statements
        """
    )
