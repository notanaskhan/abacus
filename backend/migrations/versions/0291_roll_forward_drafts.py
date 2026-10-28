"""ENG-13's roll-forward drafts (P-07-T55; P-07 §4.2 "(T55, S13)", Story 7.1; DEC-805).

New `roll_forward_drafts`: the wizard's saved state for rolling one released engagement (the
`source`, `delivered` or `archived`) into next year's. Its owner's only (the service filters by
`created_by`; RLS by tenant). `selections` holds one boolean per v1 carry category (`team`,
`template`, `request_list`, `prior_year_notes`); `team` the people and roles carried, as ids and
role codes; `template_decision` `current` (pin the template's current version at Create) or
`skip`. `name` is the new engagement's name (the source's, its year moved on), the only free
text. `version` is the autosave's `seen_version`. A draft is discarded or created
(`created_engagement_id`, set once by Create); the app never deletes one.

Revision ID: 0291
Revises: 0290
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0291"
down_revision = "0290"
branch_labels = None
depends_on = None

_UPDATES = (
    "target_period_start",
    "target_period_end",
    "name",
    "selections",
    "team",
    "template_decision",
    "created_engagement_id",
    "version",
    "saved_at",
    "discarded_at",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE roll_forward_drafts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            source_engagement_id uuid NOT NULL,
            created_by uuid NOT NULL,
            target_period_start date NOT NULL,
            target_period_end date NOT NULL,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
            selections jsonb NOT NULL DEFAULT '{}'::jsonb
                CHECK (jsonb_typeof(selections) = 'object'
                       AND octet_length(selections::text) <= 1024),
            team jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(team) = 'array' AND octet_length(team::text) <= 16384),
            template_decision text NOT NULL DEFAULT 'current'
                CHECK (template_decision IN ('current', 'skip')),
            created_engagement_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            discarded_at timestamptz NULL,
            UNIQUE (tenant_id, id),
            CHECK (target_period_end > target_period_start),
            CHECK (discarded_at IS NULL OR created_engagement_id IS NULL),
            FOREIGN KEY (tenant_id, source_engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, created_engagement_id) REFERENCES engagements (tenant_id, id),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX roll_forward_drafts_by_source ON roll_forward_drafts "
        "(tenant_id, source_engagement_id, created_by)"
    )
    tenant_table(op, "roll_forward_drafts")
    op.execute("REVOKE UPDATE, DELETE ON roll_forward_drafts FROM abacus_app")
    insert_columns(
        op,
        "roll_forward_drafts",
        (
            "tenant_id",
            "source_engagement_id",
            "created_by",
            "target_period_start",
            "target_period_end",
            "name",
            "selections",
            "team",
            "template_decision",
        ),
    )
    op.execute(f"GRANT UPDATE ({', '.join(_UPDATES)}) ON roll_forward_drafts TO abacus_app")


def downgrade() -> None:
    op.execute("DROP TABLE roll_forward_drafts")
