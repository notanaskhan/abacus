"""P-11-T25 (DEC-2332): `upload_extractions` takes `ocr-v1` rows (P-11 §4). Expand only.

`0666_ocr_v1` said the table already keyed on `extractor_version`, but its CHECK allowed only
`v<n>`, so no OCR-derived row could be stored.
"""

from __future__ import annotations

from alembic import op

revision = "0672"
down_revision = "0671"
branch_labels = None
depends_on = None

_NAME = "upload_extractions_extractor_version_check"


def upgrade() -> None:
    op.execute(f"ALTER TABLE upload_extractions DROP CONSTRAINT {_NAME}")
    op.execute(
        f"ALTER TABLE upload_extractions ADD CONSTRAINT {_NAME} "
        "CHECK (extractor_version ~ '^(ocr-)?v[0-9]{1,4}$')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM upload_extractions WHERE extractor_version LIKE 'ocr-%'")
    op.execute(f"ALTER TABLE upload_extractions DROP CONSTRAINT {_NAME}")
    op.execute(
        f"ALTER TABLE upload_extractions ADD CONSTRAINT {_NAME} "
        "CHECK (extractor_version ~ '^v[0-9]{1,4}$')"
    )
