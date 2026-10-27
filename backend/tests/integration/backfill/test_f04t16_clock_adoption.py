# ac-test-author: ayushkbhatia
"""F-04-T16 (TASK-392; SPEC-307 AC-7), the Q-03-T011 catch-up suite: the amber modules and the
tooling use `kernel.clock.now` for business time and `system_now` for system time.

SPEC-307 AC-7: `now(tenant)` reads a `frozen(at)` block first, and `system_now()` is always real
time. So under a frozen business instant far from today:
- the engagements module records the partner's independence conclusion at that instant (business
  time: the demo walks it);
- the communications mail sink stamps each message with the real time it was written, and the
  founder's tools (signup codes, the quarterly access review) date their expiries and reports in
  real time (system time: security and audit windows).

The static half (only `kernel.clock` reads the wall clock) is CLOCK-001 in `banned_patterns`
(F-04-T17). Boundaries: the acceptance route over HTTP through `create_app()` on the migrated
Postgres; `communications.api.LocalMailbox`; the tools' public functions. Expectations come from
the task row and the spec, not the implementation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

from abacus.kernel import clock
from abacus.modules.communications.api import LocalMailbox
from abacus_tools import access_review, signup_codes

from .support import Migrated, Net, Seeder

# SPEC-307: the demo instant, Mon 14 Sep 2026, 9:24 AM CT.
DEMO: Final = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
NEAR: Final = timedelta(minutes=5)


def _real_now() -> datetime:
    return datetime.now(UTC)


async def test_ac7_engagements_record_the_independence_conclusion_in_business_time(
    net: Net, seed: Seeder
) -> None:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "accept", opened=False)
    partner = await seed.person(tenant_id)
    await seed.member(site, partner, "engagement_partner")
    with clock.frozen(DEMO):
        response = await net.call(
            "PUT",
            f"/v1/engagements/{site.engagement_id}/acceptance",
            partner,
            body={
                "decision": "accepted",
                "documented_at": "PPC 1-200",
                "independence_concluded": True,
                "independence_documented_at": "Memo 2",
            },
        )
    assert response.status_code == 200, response.text
    concluded = await seed.value(
        "SELECT independence_concluded_at FROM engagement_acceptance "
        "WHERE tenant_id = $1 AND engagement_id = $2",
        tenant_id,
        site.engagement_id,
    )
    assert concluded == DEMO


def test_ac7_the_mail_sink_stamps_each_message_in_system_time(tmp_path: Path) -> None:
    with clock.frozen(DEMO):
        LocalMailbox(tmp_path).send(
            to="claire.feld@sink.brightwaterhale.test",
            subject="Your sign-in code",
            body="Your code is in the portal.",
        )
    [written] = list(tmp_path.glob("*.json"))
    record = cast(dict[str, str], json.loads(written.read_text(encoding="utf-8")))
    sent = datetime.fromisoformat(record["sent_at"])
    assert abs(sent - _real_now()) < NEAR
    assert abs(sent - DEMO) > NEAR


async def test_ac7_a_signup_code_expires_in_system_time(migrated_db: Migrated) -> None:
    with clock.frozen(DEMO):
        await signup_codes.issue(migrated_db.superuser_dsn, "Clock adoption (F-04-T16)", 7)
    rows = await signup_codes.listing(migrated_db.superuser_dsn)
    [row] = [r for r in rows if r["note"] == "Clock adoption (F-04-T16)"]
    expires = cast(datetime, row["expires_at"])
    assert abs(expires - (_real_now() + timedelta(days=7))) < NEAR


async def test_ac7_the_access_review_is_generated_in_system_time(migrated_db: Migrated) -> None:
    with clock.frozen(DEMO):
        report = await access_review.review(migrated_db.superuser_dsn, "2026Q3")
    generated = datetime.fromisoformat(str(report["generated_at"]))
    assert abs(generated - _real_now()) < NEAR
    assert abs(generated - DEMO) > NEAR
