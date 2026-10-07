"""Provider capacity: admission control for model calls (SPEC-003 AC-9 to AC-12; TASK-018
design §6, D4, and the 018c detailed design; ADR-072).

One token bucket per provider and model holds requests and tokens per minute. Every process
shares it, so it lives here, not in memory. Like the work slot ledger (0013) it is platform-owned
with no app privileges: the app reaches it only through two SECURITY DEFINER functions, which need
a tenant session (so only request-serving code calls them) but hold no tenant data, only provider,
model and counts.

`capacity_admit` refills the buckets by elapsed database time, then takes one request and the
estimated tokens only if both stay above the caller's reserve (a share of the bucket kept for
higher work classes, D4), and never while the model is blocked. `capacity_block` empties the
buckets and blocks the model for the time a provider's rate-limit response asked for (AC-12).
Limits come from the app, bounded here.

`usage_records.outcome` gains `rate_limited`: a provider's rate-limit response, spending nothing.

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "capacity_admit(text, text, integer, integer, integer, integer)",
    "capacity_block(text, text, integer)",
)
_OUTCOMES = "('ok', 'invalid', 'repaired', 'budget_refused', 'provider_error'"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE provider_capacity (
            provider text NOT NULL CHECK (provider ~ '^[a-z][a-z0-9_-]{0,49}$'),
            model text NOT NULL CHECK (length(model) BETWEEN 1 AND 100),
            requests_left numeric NOT NULL CHECK (requests_left >= 0),
            tokens_left numeric NOT NULL CHECK (tokens_left >= 0),
            refilled_at timestamptz NOT NULL,
            blocked_until timestamptz NULL,
            PRIMARY KEY (provider, model)
        )
        """
    )
    op.execute("REVOKE ALL ON provider_capacity FROM PUBLIC, abacus_app")
    op.execute("ALTER TABLE provider_capacity ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE FUNCTION capacity_admit(
            p_provider text, p_model text, p_rpm integer, p_tpm integer, p_reserve_pct integer,
            p_tokens integer
        ) RETURNS TABLE (admitted boolean, retry_after_seconds integer)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET lock_timeout = '5s'
        SET statement_timeout = '10s'
        AS $$
        DECLARE
            v_now timestamptz := clock_timestamp();
            v_row public.provider_capacity;
            v_requests numeric;
            v_tokens numeric;
            v_wait numeric;
        BEGIN
            IF NULLIF(current_setting('app.tenant_id', true), '') IS NULL THEN
                RAISE EXCEPTION 'provider capacity needs a tenant session'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_rpm NOT BETWEEN 1 AND 1000000 OR p_tpm NOT BETWEEN 1 AND 100000000
               OR p_reserve_pct NOT BETWEEN 0 AND 99 OR p_tokens NOT BETWEEN 1 AND p_tpm THEN
                RAISE EXCEPTION 'invalid capacity request'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            INSERT INTO public.provider_capacity
                (provider, model, requests_left, tokens_left, refilled_at)
            VALUES (p_provider, p_model, p_rpm, p_tpm, v_now)
            ON CONFLICT (provider, model) DO NOTHING;
            SELECT * INTO v_row FROM public.provider_capacity
             WHERE provider = p_provider AND model = p_model FOR UPDATE;

            IF v_row.blocked_until IS NOT NULL AND v_row.blocked_until > v_now THEN
                RETURN QUERY SELECT false,
                    greatest(1, ceil(extract(epoch FROM v_row.blocked_until - v_now)))::integer;
                RETURN;
            END IF;
            -- Refill by elapsed time, up to one minute's worth.
            v_requests := least(p_rpm, v_row.requests_left
                + p_rpm * extract(epoch FROM v_now - v_row.refilled_at) / 60.0);
            v_tokens := least(p_tpm, v_row.tokens_left
                + p_tpm * extract(epoch FROM v_now - v_row.refilled_at) / 60.0);

            IF v_requests - 1 >= p_rpm * p_reserve_pct / 100.0
               AND v_tokens - p_tokens >= p_tpm * p_reserve_pct / 100.0 THEN
                UPDATE public.provider_capacity
                   SET requests_left = v_requests - 1, tokens_left = v_tokens - p_tokens,
                       refilled_at = v_now, blocked_until = NULL
                 WHERE provider = p_provider AND model = p_model;
                RETURN QUERY SELECT true, 0;
                RETURN;
            END IF;
            UPDATE public.provider_capacity
               SET requests_left = v_requests, tokens_left = v_tokens, refilled_at = v_now
             WHERE provider = p_provider AND model = p_model;
            -- When enough will have refilled for this call above the reserve.
            v_wait := greatest(
                (p_rpm * p_reserve_pct / 100.0 + 1 - v_requests) * 60.0 / p_rpm,
                (p_tpm * p_reserve_pct / 100.0 + p_tokens - v_tokens) * 60.0 / p_tpm,
                1
            );
            RETURN QUERY SELECT false, least(ceil(v_wait), 60)::integer;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION capacity_block(p_provider text, p_model text, p_seconds integer)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        SET lock_timeout = '5s'
        SET statement_timeout = '10s'
        AS $$
        DECLARE
            v_now timestamptz := clock_timestamp();
        BEGIN
            IF NULLIF(current_setting('app.tenant_id', true), '') IS NULL THEN
                RAISE EXCEPTION 'provider capacity needs a tenant session'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_seconds NOT BETWEEN 1 AND 3600 THEN
                RAISE EXCEPTION 'invalid capacity block'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            INSERT INTO public.provider_capacity AS c
                (provider, model, requests_left, tokens_left, refilled_at, blocked_until)
            VALUES (p_provider, p_model, 0, 0, v_now, v_now + make_interval(secs => p_seconds))
            ON CONFLICT (provider, model) DO UPDATE
               SET requests_left = 0, tokens_left = 0, refilled_at = v_now,
                   blocked_until = greatest(coalesce(c.blocked_until, v_now),
                                            v_now + make_interval(secs => p_seconds));
        END
        $$
        """
    )
    for signature in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_app")
    op.execute("ALTER TABLE usage_records DROP CONSTRAINT usage_records_outcome_check")
    op.execute(
        "ALTER TABLE usage_records ADD CONSTRAINT usage_records_outcome_check "
        "CHECK (outcome IN " + _OUTCOMES + ", 'rate_limited'))"
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM usage_records WHERE outcome = 'rate_limited') THEN "
        "RAISE EXCEPTION 'refusing to downgrade: rate_limited usage records exist'; END IF; END $$"
    )
    op.execute("ALTER TABLE usage_records DROP CONSTRAINT usage_records_outcome_check")
    op.execute(
        "ALTER TABLE usage_records ADD CONSTRAINT usage_records_outcome_check "
        "CHECK (outcome IN " + _OUTCOMES + "))"
    )
    for signature in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE provider_capacity")
