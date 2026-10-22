"""P-01-T07: the `shell` slice (the training sandbox and Grace's membership in it, job titles,
Hannah's default office and notification preferences). Deterministic, ordered, every kind has a
loader handler, the default scenario hash is untouched, and the values match the TS seed."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import cast

import asyncpg
import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import JOB_TITLES
from abacus_tools.synthetic.scenarios.brightwater_hale.shell import (
    SANDBOX_FIRM_NAME,
    shell_events,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

WEB_SEED = Path(__file__).parents[4] / "apps/web/src/fixtures/seed"
SLICES = ("audit_core", "shell")


def _shell() -> list[Event]:
    return [e for e in build(slices=SLICES).events if e.slice == "shell"]


def test_the_slice_is_registered_and_opt_in() -> None:
    assert "shell" in registered()
    assert all(e.slice == "audit_core" for e in build().events)
    # Registering a slice never changes the default build, so SCENARIO_HASH holds.
    assert build().fingerprint() == SCENARIO_HASH


def test_the_slice_is_deterministic() -> None:
    assert build(slices=SLICES).fingerprint() == build(slices=SLICES).fingerprint()
    assert [e.id for e in shell_events()] == [e.id for e in shell_events()]


def test_its_events_are_dated_before_e0_and_ordered() -> None:
    events = _shell()
    assert len(events) == 14
    assert all(e.at <= DEMO_INSTANT for e in events)
    assert len(build("E0", slices=SLICES).events) == len(build("E0").events) + 14
    kinds = [e.kind for e in loader.replay_order(build(slices=SLICES).events)]
    last_staff = max(i for i, k in enumerate(kinds) if k == "identity.staff_member_added")
    first_shell = min(i for i, k in enumerate(kinds) if k in loader.SCHEMA_NEEDS)
    assert last_staff < first_shell
    order = [
        "identity.sandbox_firm_created",
        "organisations.sandbox_office_created",
        "identity.sandbox_membership_added",
        "identity.job_title_set",
        "identity.default_office_set",
        "notifications.preference_set",
    ]
    assert [k for k in dict.fromkeys(kinds) if k in order] == order


def test_every_shell_kind_has_a_handler() -> None:
    assert {e.kind for e in _shell()} <= set(loader.HANDLERS)


def test_the_sandbox_membership_is_graces_and_lives_in_the_sandbox_tenant() -> None:
    sandbox = [e for e in _shell() if e.kind in loader.SANDBOX_KINDS]
    assert [e.label for e in sandbox] == [
        "sandbox",
        "sandbox:membership:grace-holloway",
        "sandbox:office:Chicago",
        "sandbox:office:Denver",
        "sandbox:office:New York",
    ]
    assert sandbox[0].data == {"name": SANDBOX_FIRM_NAME, "sandbox_of": build().firm_id}
    assert SANDBOX_FIRM_NAME == "Brightwater Hale LLP — Training sandbox"
    assert all(loader.tenant_of(e) == loader.SANDBOX for e in sandbox)
    assert all(loader.tenant_of(e) == loader.TENANT for e in _shell() if e not in sandbox)
    assert {loader.sandbox_office_id_of(n) for n in ("Chicago", "Denver", "New York")}.isdisjoint(
        {loader.office_id_of(n) for n in ("Chicago", "Denver", "New York")}
    )


def test_job_titles_default_office_and_preferences_are_the_artboards() -> None:
    by_kind: dict[str, list[dict[str, object]]] = {}
    for e in _shell():
        by_kind.setdefault(e.kind, []).append(dict(e.data))
    assert {(d["initials"], d["job_title"]) for d in by_kind["identity.job_title_set"]} == {
        ("GH", "Client Service Coordinator"),
        ("HL", "Audit Senior Manager"),
        ("DR", "Tax Partner"),
        ("FA", "Qualified Individual"),
    }
    assert by_kind["identity.default_office_set"] == [{"initials": "HL", "office": "Chicago"}]
    prefs = {d["kind"]: (d["in_app"], d["email"]) for d in by_kind["notifications.preference_set"]}
    assert prefs == {
        "mention": (True, True),
        "todo_assigned": (True, True),
        "template_update_available": (True, False),
        "trigger_run_finished": (True, False),
    }


def test_people_acting_for_themselves_are_named() -> None:
    """`user_preference.updated` and `notification_preference.changed` name Hannah."""
    for e in _shell():
        expected = "HL" if e.kind.endswith(("default_office_set", "preference_set")) else "system"
        assert e.actor == expected, e.label


def test_the_ts_seed_carries_the_same_titles_and_sandbox_id_label() -> None:
    people = (WEB_SEED / "people.ts").read_text()
    block = people[people.index("export const JOB_TITLES") :]
    block = block[: block.index("};")]
    assert dict(re.findall(r'(\w+): "([^"]+)"', block)) == JOB_TITLES
    assert (
        'stableId("firm:brightwater-hale-training-sandbox")' in (WEB_SEED / "shell.ts").read_text()
    )


class _Schema:
    def __init__(self, present: bool) -> None:
        self.present = present
        self.asked: list[tuple[object, ...]] = []

    async def fetchval(self, _sql: str, *args: object) -> bool:
        self.asked.append(args)
        return self.present


def _conn(schema: _Schema) -> asyncpg.Connection:
    return cast("asyncpg.Connection", schema)  # only fetchval is called


def test_preflight_refuses_until_the_columns_exist() -> None:
    events = build(slices=SLICES).events
    with pytest.raises(loader.SchemaPending, match="P-01-T0"):
        asyncio.run(loader.preflight(_conn(_Schema(False)), events))
    present = _Schema(True)
    asyncio.run(loader.preflight(_conn(present), events))
    assert ("notification_preferences", None) in present.asked
    assert ("memberships", "job_title") in present.asked
    quiet = _Schema(False)
    asyncio.run(loader.preflight(_conn(quiet), build().events))
    assert quiet.asked == []
