"""The EBP engines' CPA review record (A-05-T49; ADR P-28; chapter 10 §10.9.4).

`reference/review.yaml` says whether the audit CPA (EBP) has signed `docs/quality/golden-reviews/
ebp@1.md`. The `ebp_audits` entitlement holds for a firm that isn't synthetic only once it is
signed, with a date and a vault reference (`platform.entitlements.register_module_review`).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Final, cast

import yaml

REVIEW: Final = Path(__file__).parent / "reference" / "review.yaml"


@cache
def review_signed() -> bool:
    """True only for a signed record naming its date and vault reference (fail closed)."""
    record = cast(dict[str, object], yaml.safe_load(REVIEW.read_text(encoding="utf-8")) or {})
    return (
        record.get("signed") is True
        and bool(record.get("signed_on"))
        and isinstance(record.get("vault_ref"), str)
        and str(record["vault_ref"]).startswith("V-")
    )
