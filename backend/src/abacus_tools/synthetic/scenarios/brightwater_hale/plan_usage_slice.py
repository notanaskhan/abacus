"""The `plan_usage` slice (G-04-T13; G-04 §5 `plan-oct-01`; DEC-5421): Brightwater Hale's plan
row, budget-alert rules and the alerts its usage crossed, through `platform.api`
`seed_synthetic_plan` and `seed_synthetic_alert`.

- Plan: 46 seats, 20,000 included agent-minutes, usage months from the 15th, term Jan 1 to
  Dec 31, 2026, renewal Jan 1, 2027 ("renewal in 92 days" at Thu Oct 1). Billing contact Grace
  Holloway; partner approver Margaret Okonkwo; engagement default 1,500 minutes, alert at 80%.
- Rules: 75% → Grace Holloway, Margaret Okonkwo; 90% → the same and Felix Andersen; 100% → the
  partners and firm admins (groups).
- Alerts crossed in the usage month `2026-09` (Sep 15 to Oct 14): 75% at 15,000 on Thu Oct 1,
  11:06 AM (ADM-14 a's helper) and 90% at 18,000 on Fri Oct 9, 1:47 PM (ADM-14 b's banner).

The `plans` row is platform content; the loader (the owner) writes it once before the plan.
Opt-in: `--slice plan_usage` (brings `agent_minutes`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "plan_usage"
NEEDS: Final = ("agent_minutes",)
PLAN_CODE: Final = "brightwater_synthetic"
PLAN_NAME: Final = "Synthetic test plan (Brightwater Hale)"
GRACE: Final = "Grace Holloway"
MARGARET: Final = "Margaret Okonkwo"
FELIX: Final = "Felix Andersen"
USAGE_MONTH: Final = "2026-09"
RULES: Final = ((75, (GRACE, MARGARET), ()), (90, (GRACE, MARGARET, FELIX), ()),
                (100, (), ("partners", "firm_admins")))  # fmt: skip
ALERTS: Final = (
    (75, datetime(2026, 10, 1, 11, 6, tzinfo=CT), 15_000, (GRACE, MARGARET)),
    (90, datetime(2026, 10, 9, 13, 47, tzinfo=CT), 18_000, (GRACE, MARGARET, FELIX)),
)


@register_slice(SLICE)
def plan_usage_events() -> list[Event]:
    events = [
        Event(
            label="plan_usage:plan",
            at=datetime(2026, 1, 1, 9, 0, tzinfo=CT),
            kind="platform.plan_seeded",
            actor="system",
            slice=SLICE,
            data={
                "plan_code": PLAN_CODE,
                "plan_name": PLAN_NAME,
                "term_start": date(2026, 1, 1).isoformat(),
                "term_end": date(2026, 12, 31).isoformat(),
                "renewal_on": date(2027, 1, 1).isoformat(),
                "included_agent_minutes": 20_000,
                "seats_total": 46,
                "anchor_day": 15,
                "billing_contact": GRACE,
                "partner_approver": MARGARET,
                "engagement_default_minutes": 1_500,
                "engagement_alert_pct": 80,
                "rules": [
                    {"pct": pct, "people": list(people), "groups": list(groups)}
                    for pct, people, groups in RULES
                ],
            },
        )
    ]
    events += [
        Event(
            label=f"plan_usage:alert:{pct}",
            at=at,
            kind="platform.usage_alert_seeded",
            actor="system",
            slice=SLICE,
            data={
                "usage_month": USAGE_MONTH,
                "pct": pct,
                "minutes": minutes,
                "sent_to": list(people),
            },
        )
        for pct, at, minutes, people in ALERTS
    ]
    return events
