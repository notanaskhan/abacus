"""The individual return engines' CPA review record (T-04-T49; ADR P-28; chapter 10 §10.9.4;
DEC-4524).

`parameters/review.yaml` says whether the tax CPA has signed
`docs/quality/golden-reviews/tax-individual@v1.md`. Until it is signed, with a date and a vault
reference, the T-04 workspace (`tax.review_workspace`) answers 404 to every firm that isn't
synthetic; synthetic firms are the review's own test bed. Every engine in this package is
`requires_review` (ENGINES).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Final, cast

import yaml

REVIEW: Final = Path(__file__).parent / "parameters" / "review.yaml"
# The engines the memo covers (each requires review before a real firm relies on it).
ENGINES: Final = (
    "residency.allocation",
    "residency.it112r",
    "residency.it225",
    "residency.rules",
    "k1.qbi_199a",
    "k1.outside_basis",
    "k1.state_sourcing",
    "k1.ptet_share",
    "k1.sch_e_matrix",
    "leadsheets.form_1040",
    "worksheets.it201",
)


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
