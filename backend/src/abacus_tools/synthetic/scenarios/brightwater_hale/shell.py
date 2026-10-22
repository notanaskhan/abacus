"""The `shell` slice (P-01-T07): what the firm menu (SHL-03) and the notification settings (SHL-04)
need from the live seed, as events the loader replays. Epic P-01 §5.3: "The live seed also
includes Grace's sandbox membership, the job titles and Hannah's default office."

- The training sandbox: a second synthetic firm, "Brightwater Hale LLP — Training sandbox",
  marked as a sandbox of Brightwater Hale LLP; its offices (the parent's three, so a staff
  membership can carry one); and Grace Holloway's membership in it (SHL-03e). PLT-01 (G-04) owns
  provisioning; this only seeds the membership SHL-03e displays.
- Job titles for the four SHL-03 personas, verbatim from their person cards (`JOB_TITLES`).
- Hannah Leclerc's default office filter, Chicago (SHL-03b), set by her.
- Hannah's notification preferences for the four R2 kinds, as the SHL-04 settings menu shows
  them (In Accrued on for all; Email on for Mention and To-do assigned, as the built canvas has).

Everything is dated at `SETUP_AT`, before the demo week. The slice is opt-in (`--slice shell`):
`build()` keeps its default `("audit_core",)`, so `SCENARIO_HASH` is unchanged. Mirrors
apps/web/src/fixtures/seed/shell.ts and notifications.ts.
"""

from __future__ import annotations

from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    DEFAULT_OFFICE_FILTERS,
    JOB_TITLES,
    OFFICES,
    SEATS,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import FIRM_ID, SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "shell"
SANDBOX_FIRM_ID: Final = stable_id("firm:brightwater-hale-training-sandbox")
SANDBOX_FIRM_NAME: Final = "Brightwater Hale LLP — Training sandbox"
# SHL-03e: only Grace Holloway holds a sandbox membership.
SANDBOX_MEMBERS: Final = ("GH",)
# The SHL-04 settings menu (R2): kind, In Accrued, Email.
NOTIFICATION_PREFERENCES: Final[dict[str, tuple[tuple[str, bool, bool], ...]]] = {
    "HL": (
        ("mention", True, True),
        ("todo_assigned", True, True),
        ("template_update_available", True, False),
        ("trigger_run_finished", True, False),
    ),
}

_SEATS: Final = {s.initials: s for s in SEATS}


def _slug(initials: str) -> str:
    return slug_of(_SEATS[initials].name)


@register_slice(SLICE)
def shell_events() -> list[Event]:
    events = [
        Event(
            "sandbox",
            SETUP_AT,
            "identity.sandbox_firm_created",
            "system",
            SLICE,
            {"name": SANDBOX_FIRM_NAME, "sandbox_of": FIRM_ID},
        )
    ]
    events += [
        Event(
            f"sandbox:office:{o.name}",
            SETUP_AT,
            "organisations.sandbox_office_created",
            "system",
            SLICE,
            {"office": o.name},
        )
        for o in OFFICES
    ]
    events += [
        Event(
            f"sandbox:membership:{_slug(initials)}",
            SETUP_AT,
            "identity.sandbox_membership_added",
            "system",
            SLICE,
            {"initials": initials, "office": _SEATS[initials].office},
        )
        for initials in SANDBOX_MEMBERS
    ]
    events += [
        Event(
            f"job-title:{_slug(initials)}",
            SETUP_AT,
            "identity.job_title_set",
            "system",
            SLICE,
            {"initials": initials, "job_title": title},
        )
        for initials, title in JOB_TITLES.items()
    ]
    events += [
        Event(
            f"default-office:{_slug(initials)}",
            SETUP_AT,
            "identity.default_office_set",
            initials,
            SLICE,
            {"initials": initials, "office": office},
        )
        for initials, office in DEFAULT_OFFICE_FILTERS.items()
    ]
    events += [
        Event(
            f"notification-preference:{_slug(initials)}:{kind}",
            SETUP_AT,
            "notifications.preference_set",
            initials,
            SLICE,
            {"initials": initials, "kind": kind, "in_app": in_app, "email": email},
        )
        for initials, rows in NOTIFICATION_PREFERENCES.items()
        for kind, in_app, email in rows
    ]
    return events
