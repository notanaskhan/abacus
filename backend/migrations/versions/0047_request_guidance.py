"""Request guidance for the client hub (SPEC-031; TASK-060).

- `request_items`: `why`, `good_looks_like`, `still_needed` (firm-written text clients read),
  `blocks_fieldwork`, `effort` (`small`, `medium`, `large`), and `guidance_source` (`template`,
  `kind_default`, `firm`).
- `methodology_request_items`: the template's `why`, `good_looks_like`, `blocks_fieldwork` and
  `effort`, carried to engagements when the methodology is applied and on roll-forward.

Revision ID: 0047
Revises: 0046
"""

from __future__ import annotations

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

_TEXT = "text NULL CHECK (length({0}) BETWEEN 1 AND 1000)"
_EFFORT = "text NULL CHECK (effort IN ('small', 'medium', 'large'))"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE request_items "
        f"ADD COLUMN why {_TEXT.format('why')}, "
        f"ADD COLUMN good_looks_like {_TEXT.format('good_looks_like')}, "
        f"ADD COLUMN still_needed {_TEXT.format('still_needed')}, "
        "ADD COLUMN blocks_fieldwork boolean NOT NULL DEFAULT false, "
        f"ADD COLUMN effort {_EFFORT}, "
        "ADD COLUMN guidance_source text NULL "
        "CHECK (guidance_source IN ('template', 'kind_default', 'firm'))"
    )
    op.execute(
        "GRANT INSERT (why, good_looks_like, blocks_fieldwork, effort, guidance_source), "
        "UPDATE (why, good_looks_like, still_needed, blocks_fieldwork, effort, guidance_source) "
        "ON request_items TO abacus_app"
    )
    op.execute(
        "ALTER TABLE methodology_request_items "
        f"ADD COLUMN why {_TEXT.format('why')}, "
        f"ADD COLUMN good_looks_like {_TEXT.format('good_looks_like')}, "
        "ADD COLUMN blocks_fieldwork boolean NOT NULL DEFAULT false, "
        f"ADD COLUMN effort {_EFFORT}"
    )
    op.execute(
        "GRANT INSERT (why, good_looks_like, blocks_fieldwork, effort) "
        "ON methodology_request_items TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE INSERT (why, good_looks_like, blocks_fieldwork, effort) "
        "ON methodology_request_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE methodology_request_items DROP COLUMN why, DROP COLUMN good_looks_like, "
        "DROP COLUMN blocks_fieldwork, DROP COLUMN effort"
    )
    op.execute(
        "REVOKE INSERT (why, good_looks_like, blocks_fieldwork, effort, guidance_source), "
        "UPDATE (why, good_looks_like, still_needed, blocks_fieldwork, effort, guidance_source) "
        "ON request_items FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE request_items DROP COLUMN why, DROP COLUMN good_looks_like, "
        "DROP COLUMN still_needed, DROP COLUMN blocks_fieldwork, DROP COLUMN effort, "
        "DROP COLUMN guidance_source"
    )
