"""The security incident register (Q-02-T33; Q-02 §4.2, AC-38, AC-39; OQ-5; ADR-097; DEC-290).

- `security_incidents` (tenant, forced RLS): one row per incident in a firm's register, `ref`
  `INC-<year>-NNN` per firm. A firm entry (`source = 'firm'`) is recorded by the session's own
  person (`created_by`, bound by the guard trigger). An Accrued entry (`source = 'accrued'`) is
  written by the system when platform staff propagate an Accrued-side incident (RB-27): it names
  Accrued's reference, when Accrued confirmed it and when the firm was given notice
  (`dpa_notice_at`, the DPA's 72-hour clock), and has no person.
- `notification_event` is generated: unencrypted data of 500 or more consumers. `ftc_notify_by`
  is written by the service (the discovery date in the firm's time zone plus 30 calendar days)
  and is not a generated column, because time-zone conversion is not immutable.
- Insert-only for the app in v1: G-02-T18 grants the status change with its decisions.

Revision ID: 0143
Revises: 0133
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0143"
down_revision = "0133"
branch_labels = None
depends_on = None

_KINDS = (
    "('unauthorized_access', 'credential_attack', 'data_exposure', 'lost_device', "
    "'vendor_incident', 'other')"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE security_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            ref text NOT NULL CHECK (ref ~ '^INC-[0-9]{{4}}-[0-9]{{3,}}$'),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            event_kind text NOT NULL CHECK (event_kind IN {_KINDS}),
            discovered_at timestamptz NOT NULL,
            consumers_affected integer NULL CHECK (consumers_affected >= 0),
            unencrypted boolean NULL,
            notification_event boolean GENERATED ALWAYS AS (
                coalesce(unencrypted, false) AND coalesce(consumers_affected, 0) >= 500
            ) STORED,
            ftc_notify_by date NOT NULL,
            status text NOT NULL DEFAULT 'investigating'
                CHECK (status IN ('investigating', 'closed')),
            source text NOT NULL CHECK (source IN ('firm', 'accrued')),
            accrued_ref text NULL CHECK (accrued_ref ~ '^[A-Z0-9][A-Z0-9-]{{2,39}}$'),
            accrued_confirmed_at timestamptz NULL,
            dpa_notice_at timestamptz NULL,
            created_by uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, ref),
            UNIQUE (tenant_id, accrued_ref),
            CONSTRAINT security_incidents_source_shape CHECK (
                CASE source
                    WHEN 'firm' THEN created_by IS NOT NULL AND accrued_ref IS NULL
                        AND accrued_confirmed_at IS NULL AND dpa_notice_at IS NULL
                    ELSE created_by IS NULL AND accrued_ref IS NOT NULL
                        AND accrued_confirmed_at IS NOT NULL AND dpa_notice_at IS NOT NULL
                END
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX security_incidents_open ON security_incidents (tenant_id, discovered_at) "
        "WHERE status = 'investigating'"
    )
    tenant_table(op, "security_incidents")
    insert_only(op, "security_incidents")
    op.execute("REVOKE TRUNCATE ON security_incidents FROM abacus_app")
    insert_columns(
        op,
        "security_incidents",
        (
            "id",
            "tenant_id",
            "ref",
            "title",
            "event_kind",
            "discovered_at",
            "consumers_affected",
            "unencrypted",
            "ftc_notify_by",
            "source",
            "accrued_ref",
            "accrued_confirmed_at",
            "dpa_notice_at",
            "created_by",
        ),
    )
    # A firm entry is the session's own person's; an Accrued entry is the platform's (system).
    op.execute(
        """
        CREATE FUNCTION security_incidents_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.source = 'firm' AND (
                current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR NEW.created_by::text IS DISTINCT FROM current_setting('app.actor_id', true)
            ) THEN
                RAISE EXCEPTION 'a firm''s incident is recorded by the session''s own person'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.source = 'accrued'
               AND current_setting('app.actor_kind', true) IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'an Accrued incident is propagated by the system'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER security_incidents_guard BEFORE INSERT ON security_incidents "
        "FOR EACH ROW EXECUTE FUNCTION security_incidents_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE security_incidents")
    op.execute("DROP FUNCTION security_incidents_guard()")
