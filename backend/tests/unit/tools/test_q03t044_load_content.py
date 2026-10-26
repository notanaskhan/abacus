"""Q-03-T044 (TASK-1357; Q-03 E1): load scenario content from the journeys.

- The J02, J04-PBC and J12 step mixes load as profiles, with persona weights: each virtual user
  is one persona for the run and plays only its groups, signed in with its own token.
- The 300-item PBC import body is a workbook the request-list import reads as 300 distinct rows.
- x1, x25 and x100 are 1, 25 and 100 Brightwater-size firms (46 seats, 184 clients, 27 audits,
  counted from the F-04 scenario), nested and distinct, wired to `make seed-staging PROFILE=`.

No network and no database: the API is an `httpx.MockTransport`.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from abacus.modules.requests.workbook import read_rows
from abacus_tools.loadtest.bodies import PBC_IMPORT_ROWS, PBC_SHEET, XLSX, pbc_import_300
from abacus_tools.loadtest.journey_vars import journey_vars
from abacus_tools.loadtest.run import run
from abacus_tools.loadtest.scenario import Scenario, profile
from abacus_tools.synthetic import fleet
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

REPO = Path(__file__).resolve().parents[4]


def _scenario(**overrides: object) -> Scenario:
    raw: dict[str, object] = {
        "name": "unit",
        "duration_seconds": 0.3,
        "users": 12,
        "think_ms": 2,
        "groups": [
            {"name": "staff_reads", "steps": [{"path": "/v1/home"}]},
            {"name": "client_reads", "steps": [{"path": "/v1/me"}]},
            {
                "name": "import",
                "steps": [{"method": "POST", "path": "/v1/import", "body": "pbc_import_300"}],
            },
        ],
        "personas": [
            {"subject": "staff", "weight": 3, "groups": ["staff_reads", "import"]},
            {"subject": "client", "weight": 1, "groups": ["client_reads"]},
        ],
    }
    raw.update(overrides)
    return Scenario.model_validate(raw)


class Api:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str | None, str | None, int]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(
            (
                request.url.path,
                request.headers.get("authorization"),
                request.headers.get("content-type"),
                len(request.content),
            )
        )
        return httpx.Response(200, json={})


# --- the profiles ------------------------------------------------------------------------------


def test_ac_the_journey_mixes_load_with_persona_weights() -> None:
    journeys = profile("journeys")
    groups = {g.name for g in journeys.groups}
    assert {g for g in groups if g.startswith("j02_")} and {
        g for g in groups if g.startswith("j12_")
    }
    assert {"j04_pbc_requests", "j04_pbc_work"} <= groups
    assert journeys.persona is None and len(journeys.personas) >= 4
    client = [p for p in journeys.personas if all(g.startswith("j12_") for g in p.groups)]
    assert client, "a client persona plays only the J12 mix"
    for persona in journeys.personas:
        if persona not in client:
            assert not any(g.startswith("j12_") for g in persona.groups)
    # Every write is the sign-in start, which answers 202 for any address.
    writes = [s for g in journeys.groups for s in g.steps if s.method != "GET"]
    assert [(s.path, s.expect) for s in writes] == [("/v1/portal/auth/start", (202,))]


def test_ac_the_pbc_import_burst_names_the_300_item_body() -> None:
    burst = profile("pbc_import_burst")
    [importing] = [g for g in burst.groups if g.name == "j04_pbc_import"]
    [step] = importing.steps
    assert (step.method, step.body, step.expect) == ("POST", "pbc_import_300", (201,))
    assert step.path.startswith("/v1/engagements/{engagement_id}/request-items/import?")
    assert f"sheet={PBC_SHEET}" in step.path
    [importer] = [p for p in burst.personas if "j04_pbc_import" in p.groups]
    assert importer.groups == ("j04_pbc_import",)


def test_ac_the_journey_ids_are_northwinds_audit_and_its_team_signs_in() -> None:
    found = journey_vars()
    northwind = BY_LABEL["A1"]
    assert found["engagement_id"] == northwind.id
    subjects = {p.subject for p in profile("journeys").personas}
    assert {
        "scenario-margaret-okonkwo",
        "scenario-hannah-leclerc",
        "scenario-marcus-delaney",
        "scenario-ana-cruz",
    } <= subjects


REFUSED: list[dict[str, object]] = [
    {"persona": "dev-staff"},  # one persona or weighted ones, never both
    {"personas": [{"subject": "s", "groups": ["nope"]}]},  # an unknown group
    {"personas": [{"subject": "s", "groups": ["staff_reads"]}]},  # groups nobody plays
    {
        "groups": [
            {"name": "g", "steps": [{"path": "/x", "body": "pbc_import_300", "json_body": {}}]}
        ],
        "personas": [],
    },
    {
        "groups": [{"name": "g", "steps": [{"path": "/x", "body": "unknown_body"}]}],
        "personas": [],
    },
]


@pytest.mark.parametrize("change", REFUSED)
def test_ac_an_inconsistent_persona_or_body_is_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _scenario(**change)


# --- the runner with personas ------------------------------------------------------------------


async def test_ac_each_user_plays_only_its_personas_groups_with_its_own_token() -> None:
    api = Api()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(api), base_url="http://127.0.0.1:8001"
    ) as client:
        report = await run(
            _scenario(), client, tokens={"staff": "staff-token", "client": "client-token"}
        )
    tokens_by_path: dict[str, set[str | None]] = {}
    for path, auth, _, _ in api.seen:
        tokens_by_path.setdefault(path, set()).add(auth)
    assert tokens_by_path["/v1/home"] == {"Bearer staff-token"}
    assert tokens_by_path["/v1/import"] == {"Bearer staff-token"}
    assert tokens_by_path["/v1/me"] == {"Bearer client-token"}
    imports = [s for s in api.seen if s[0] == "/v1/import"]
    assert {(ctype, size) for _, _, ctype, size in imports} == {
        (XLSX, len(pbc_import_300().content))
    }
    assert report.verdict.passed


async def test_ac_a_persona_without_a_token_is_refused_before_anything_runs() -> None:
    api = Api()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(api), base_url="http://127.0.0.1:8001"
    ) as client:
        with pytest.raises(ValueError, match="client"):
            await run(_scenario(), client, tokens={"staff": "t"})
    assert api.seen == []


# --- the PBC import body -----------------------------------------------------------------------


def test_ac_the_import_body_is_300_distinct_requests_the_import_reads() -> None:
    body = pbc_import_300()
    assert body.content_type == XLSX
    rows, empty = read_rows(body.content, PBC_SHEET, 1, 0, 1, 2)
    assert (len(rows), empty) == (PBC_IMPORT_ROWS, 0) == (300, 0)
    assert len({r.description for r in rows}) == 300
    assert {r.tier for r in rows} <= set("ABCDE")
    assert pbc_import_300() is body  # built once


# --- x1, x25, x100 -----------------------------------------------------------------------------


def test_ac_a_firm_is_brightwater_size() -> None:
    shape = fleet.brightwater_shape()
    assert (shape.seats, shape.clients, shape.audits) == (len(SEATS), 184, 27) == (46, 184, 27)
    assert shape.requests_per_audit == 16


@pytest.mark.parametrize(("name", "count"), [("x1", 1), ("x25", 25), ("x100", 100)])
def test_ac_each_profile_is_that_many_distinct_synthetic_firms(name: str, count: int) -> None:
    firms = fleet.plan(name)
    assert len(firms) == count
    assert len({f.tenant for f in firms}) == count
    assert len({f.name for f in firms}) == count
    assert all(f.shape == fleet.brightwater_shape() for f in firms)


def test_ac_profiles_nest_so_x25_after_x1_adds_24_firms() -> None:
    x1, x25, x100 = (fleet.plan(p) for p in ("x1", "x25", "x100"))
    assert [f.tenant for f in x25[:1]] == [f.tenant for f in x1]
    assert [f.tenant for f in x100[:25]] == [f.tenant for f in x25]
    with pytest.raises(ValueError, match="x25"):
        fleet.plan("x7")


def test_ac_every_audit_team_is_four_distinct_seats_past_the_admins() -> None:
    firm = fleet.plan("x1")[0]
    for a in range(firm.shape.audits):
        team = firm.team(a)
        seats = [s for s, _ in team]
        assert len(set(seats)) == 4 and all(2 <= s < firm.shape.seats for s in seats)
        assert [r for _, r in team] == ["engagement_partner", "manager", "senior", "staff"]
    assert (firm.firm_role(0), firm.firm_role(1), firm.firm_role(2)) == (
        "firm_admin",
        "practice_leader",
        None,
    )


def test_ac_fleet_firms_turn_on_the_rollout_and_portal_flags() -> None:
    assert {"portal.sign_in_v2", "portal.home_v2"} <= set(fleet.FLEET_FLAGS)
    assert len(set(fleet.FLEET_FLAGS)) == len(fleet.FLEET_FLAGS)


def test_ac_make_wires_the_profiles() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "FLEET_PROFILE = $(filter x1 x25 x100,$(PROFILE))" in makefile
    assert "abacus_tools.synthetic.fleet --staging --profile $(FLEET_PROFILE)" in makefile
    assert "$$(uv run python -m abacus_tools.loadtest.journey_vars)" in makefile


def test_ac_the_fleet_loader_keeps_the_scenario_loaders_refusals() -> None:
    from abacus_tools.synthetic.scenarios.brightwater_hale import loader

    assert fleet.guard is loader.guard and fleet.LoadRefused is loader.LoadRefused
