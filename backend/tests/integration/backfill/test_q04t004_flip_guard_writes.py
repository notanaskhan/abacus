# ac-test-author: ayushkbhatia
"""Q-04-T004 (SPEC-403 AC-8, AC-9; Q-04 AC-4.1, AC-4.3, AC-4.7): the flip guard's writes. An
allowed flip's `feature_flag.set` carries the approver, rollback, request and slot references; a
refused flip writes nothing; `--all-off` sets every flag for one firm to its default in one unit
of work with one `feature_flag.bulk_off` event and touches no other firm. Boundary: the operator
CLI (`abacus_tools.flags.main`, `abacus_tools.tenants.main`) and its functions on the migrated
Postgres, with the calendar loaded from a test copy of `deploy/windows.yaml`."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml

from abacus.kernel._flags import FLAGS
from abacus_tools import flags as flags_tool
from abacus_tools import flip_guard, release_windows
from abacus_tools.flags import all_off, set_flag

from .support import Seeder

pytestmark = pytest.mark.asyncio
ROLLOUT = "evidence.viewer_v1"  # a registered boolean, default false
OTHER = "contacts.v2"  # another registered boolean, default false
ROLLBACK = "docs/ops/flips/2027-09-21-PF-A1.md#rollback"


def _calendar(firm: UUID) -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [
        {
            "tenant_id": str(firm),
            "code": "PF-A1",
            "real_data_since": "2027-06-01",
            "autumn_window": True,
        }
    ]
    return release_windows.parse(doc)


async def _after(seed: Seeder, tenant: UUID, action: str) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT after_ref::text AS after, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = $2 ORDER BY seq",
        tenant,
        action,
    )
    return [{"after": json.loads(str(r["after"])), "actor": r["actor_id"]} for r in rows]


async def test_ac9_an_allowed_flip_records_approver_rollback_request_and_slot(
    seed: Seeder, tmp_path: Path
) -> None:
    firm = await seed.firm()
    request = tmp_path / "flip.yaml"
    request.write_text("kind: flag_flip\n", encoding="utf-8")
    verdict = flip_guard.check(
        _calendar(firm),
        flip_guard.Flip(
            firm=firm,
            operator="ayushkbhatia",
            at=datetime.fromisoformat("2027-09-21T19:10:00-05:00"),
            flags=(ROLLOUT,),
            approved_by="notanaskhan",
            rollback=ROLLBACK,
            request=request,
        ),
    )
    assert verdict.allowed
    await set_flag(firm, ROLLOUT, "true", "ayushkbhatia", "PW1 flip", verdict.refs)
    [event] = await _after(seed, firm, "feature_flag.set")
    after = event["after"]
    assert isinstance(after, dict)
    assert after["approved_by"] == flip_guard.fingerprint("notanaskhan")
    assert after["rollback"] == flip_guard.fingerprint(ROLLBACK)
    assert after["request"] == flip_guard.fingerprint("kind: flag_flip\n")
    assert after["slot"] == int(datetime.fromisoformat("2027-09-21T19:00:00-05:00").timestamp())
    assert event["actor"] == "operator:ayushkbhatia"


@pytest.fixture
def pilot(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, UUID]]:
    """`deploy/windows.yaml` lists the firm the test makes as PF-A1."""
    holder: dict[str, UUID] = {}

    def load(_path: Path = release_windows.WINDOWS_FILE) -> release_windows.Calendar:
        return _calendar(holder["firm"])

    monkeypatch.setattr(release_windows, "load", load)
    yield holder


async def test_ac8_a_refused_flip_writes_nothing(
    seed: Seeder, pilot: dict[str, UUID], capsys: pytest.CaptureFixture[str]
) -> None:
    firm = await seed.firm()
    pilot["firm"] = firm
    code = flags_tool.main(
        [
            "--firm", str(firm), "--flag", ROLLOUT, "--value", "true",
            "--operator", "ayushkbhatia", "--reason", "PW1",
            "--approved-by", "ayushkbhatia", "--rollback", ROLLBACK,
        ]
    )  # fmt: skip
    assert code == 2
    assert "approver_is_operator" in capsys.readouterr().err
    assert (
        await seed.value("SELECT count(*) FROM feature_flag_states WHERE tenant_id = $1", firm)
        == 0
    )
    assert await _after(seed, firm, "feature_flag.set") == []


async def test_ac8_the_entitlement_cli_takes_the_same_guard(
    seed: Seeder, pilot: dict[str, UUID], capsys: pytest.CaptureFixture[str]
) -> None:
    from abacus_tools import tenants

    firm = await seed.firm()
    pilot["firm"] = firm
    code = tenants.main(
        [
            "entitlement", "--firm", str(firm), "--module", "attest", "--enabled", "true",
            "--operator", "ayushkbhatia", "--reason", "PW1 plan",
        ]
    )  # fmt: skip
    assert code != 0
    assert "approver_missing" in capsys.readouterr().err
    assert (
        await seed.value("SELECT count(*) FROM tenant_entitlements WHERE tenant_id = $1", firm)
        == 0
    )


async def test_ac9_all_off_sets_every_flag_to_its_default_in_one_event(seed: Seeder) -> None:
    firm = await seed.firm()
    other = await seed.firm()
    for tenant in (firm, other):
        await set_flag(tenant, ROLLOUT, "true", "seed", "on")
        await set_flag(tenant, OTHER, "true", "seed", "on")
    refs = {"approved_by": flip_guard.fingerprint("notanaskhan")}
    assert await all_off(firm, "ayushkbhatia", "PF-A1 rollback", refs) == 2
    values = await seed.rows(
        "SELECT tenant_id, flag, value FROM feature_flag_states ORDER BY tenant_id, flag"
    )
    by = {(r["tenant_id"], r["flag"]): r["value"] for r in values}
    assert by[(firm, ROLLOUT)] == FLAGS[ROLLOUT].default
    assert by[(firm, OTHER)] == FLAGS[OTHER].default
    assert by[(other, ROLLOUT)] == "true" and by[(other, OTHER)] == "true"  # no other firm
    [event] = await _after(seed, firm, "feature_flag.bulk_off")
    assert event["after"] == {"flags": 2, **refs}
    assert await _after(seed, other, "feature_flag.bulk_off") == []
    # Run again: nothing left to change, still one event per run.
    assert await all_off(firm, "ayushkbhatia", "again", refs) == 0


async def test_guard_fails_closed_on_a_broken_calendar(tmp_path: Path) -> None:
    broken = tmp_path / "windows.yaml"
    broken.write_text("rules_version: 2\n", encoding="utf-8")
    verdict = flags_tool.guard(
        flip_guard.Flip(firm=UUID(int=1), operator="ayushkbhatia", at=datetime.now(UTC)),
        windows=broken,
    )
    assert verdict.why == ("windows_unreadable",)
