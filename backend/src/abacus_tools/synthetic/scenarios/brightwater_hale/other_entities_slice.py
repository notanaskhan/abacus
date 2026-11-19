"""The Brightwater Hale other-entity slice (T-06-T28; TASK-8723; T-06 §5.3; DEC-5717): Bluestem
Analytics, LLC's 2025 Form 1120-S (Accepted Mar 13, read-only), Ashford Manufacturing Co.'s 2025
Form 1120 provision (on the NetSuite seed) and Lakeshore Literacy Alliance's 990 (FYE June) for
TXP-13 a to c.

Every name and figure is the TXP-13 handoff's. The AAA end, the shareholder shares, the provision
and the ETR are computed here by the engines (E10, E11; ADR-050), never typed, so a changed row
fails `tests/unit/synthetic/test_t06t28_other_entities.py`. No database code: the service-API
load follows T-06-T42's other-entity service.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.tax.api import provision_engine as e11
from abacus.modules.tax.api import s_corp_engine as e10

D = Decimal
BLUESTEM: Final = "Bluestem Analytics, LLC"
ASHFORD: Final = "Ashford Manufacturing Co."
LAKESHORE: Final = "Lakeshore Literacy Alliance"
BLUESTEM_ACCEPTED_ON: Final = date(2026, 3, 13)

# TXP-13 a: Schedule M-2 and the shareholder allocation (per share, per day; full year).
AAA_BEGIN: Final = D("1240000")
ORDINARY_INCOME: Final = D("860000")
INTEREST: Final = D("12400")
NONDEDUCTIBLE: Final = D("4200")
DISTRIBUTIONS: Final = D("620000")
SHAREHOLDERS: Final = {"Arjun Mehta": (70, 365), "Sunita Rao": (30, 365)}
# The handoff's rows per shareholder: ordinary income, interest, nondeductible, distributions.
ALLOCATION_ROWS: Final = {
    "Arjun Mehta": (D("602000"), D("8680"), D("2940"), D("434000")),
    "Sunita Rao": (D("258000"), D("3720"), D("1260"), D("186000")),
}

# TXP-13 b and b2: Ashford's provision and the variant 1,200 off.
ASHFORD_CURRENT: Final = D("2134650")
ASHFORD_DEFERRED: Final = D("122550")
ASHFORD_ETR_PCT: Final = D("28.9")
ASHFORD_B2_OFF: Final = D("1200")

# TXP-13 c: Lakeshore's Part IX, program ratio and public support.
LAKESHORE_PART_IX: Final = D("4014000")
LAKESHORE_PROGRAM_PCT: Final = D("80.0")
LAKESHORE_PUBLIC_SUPPORT_PCT: Final = D("87.4")


def bluestem_aaa() -> e10.AaaRoll:
    return e10.aaa_roll(
        AAA_BEGIN,
        income=ORDINARY_INCOME + INTEREST,
        losses=D("0"),
        nondeductible=NONDEDUCTIBLE,
        distributions=DISTRIBUTIONS,
    )


def bluestem_split(item: Decimal) -> dict[str, Decimal]:
    return e10.per_share_per_day(item, SHAREHOLDERS)


def ashford_provision() -> Decimal:
    return e11.provision(ASHFORD_CURRENT, ASHFORD_DEFERRED)


__all__ = [
    "ALLOCATION_ROWS",
    "ASHFORD",
    "BLUESTEM",
    "LAKESHORE",
    "ashford_provision",
    "bluestem_aaa",
    "bluestem_split",
]
