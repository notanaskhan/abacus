"""T-04-T19 (TASK-6618; SPEC-649; §7216; C17 §4 to §6): the twelve tax tools through C17's runtime.

Row acceptance: "A tri read without both section 7216 consents for the taxpayer and tax year fails
with consent_required before data is fetched, no tool output holds a full TIN, and every propose
tool creates a proposal, never a value." The runtime's database seams (pinned scope, engagement
lookups, `authorise`, C19's gate, access events) are fakes that record what was asked; each tool's
handler is replaced by a probe that records whether it ran, so a refusal is proven to come before
any data is read. The handlers' own SQL runs in the integration suite (T-04-T42's).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field, replace

import pytest

import abacus.modules.organisations.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers C19's consent checks
from abacus.kernel.db import TenantContext
from abacus.modules.agents.tools import registry, runtime
from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool
from abacus.modules.identity import context
from abacus.modules.identity.api import RULES, AgentContext, AuthContext, Resource
from abacus.modules.organisations.api import TriConsentRequired
from abacus.modules.tax import tools as tax_tools

NORTHWIND, GRANITE = uuid.uuid4(), uuid.uuid4()
NORTHWIND_RETURNS, GRANITE_RETURNS = uuid.uuid4(), uuid.uuid4()
FELD, GRANITE_ENTITY = uuid.uuid4(), uuid.uuid4()
CLIENT_OF = {NORTHWIND_RETURNS: NORTHWIND, GRANITE_RETURNS: GRANITE}
ENTITY_CLIENT = {FELD: NORTHWIND, GRANITE_ENTITY: GRANITE}


def _args(entity: uuid.UUID) -> dict[str, dict[str, object]]:
    year: dict[str, object] = {"client_entity_id": entity, "tax_year": 2025}
    return {
        "tax.read_return": year,
        "tax.list_documents": year,
        "tax.read_worksheet": {**year, "worksheet_key": "f1040"},
        "tax.read_pass_through_activity": year,
        "tax.read_prior_year": year,
        "tax.compare_years": year,
        "tax.compute_pass_through_facts": {
            **year, "qbi": "1000", "w2_wages": "500", "ubia": "0", "tax_capital": "10",
            "liability_share_752": "5",
        },
        "tax.compute_residency_facts": {
            **year, "nyc_days": 120, "has_nyc_abode": True, "main_home_outside_nyc": True,
        },
        "tax.compute_state_allocation": {**year, "amount": "100", "by_state": [["NY", "1"]]},
        "tax.propose_field_changes": {
            **year,
            "changes": [{"worksheet_id": uuid.uuid4(), "field_key": "line_1", "after": "1"}],
        },
        "tax.propose_pass_through_treatments": {
            **year, "changes": [{"treatment_id": uuid.uuid4(), "treatment": "Passive"}],
        },
        "tax.propose_residency": {
            **year, "determination_id": uuid.uuid4(), "option": "part_year",
        },
    }  # fmt: skip


TAX_TOOLS = sorted(_args(FELD))


@dataclass
class World:
    consent: bool = True
    consent_asked: list[object] = field(default_factory=list[object])
    handled: list[str] = field(default_factory=list[str])


def _agent() -> AgentContext:
    user = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), "human", str(user))
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(tenant.tenant_id, "agent", f"agent:t04.tools:{run}"),
        agent_id="t04.tools",
        agent_run_id=run,
        engagement_id=NORTHWIND_RETURNS,
        task_scope=frozenset(RULES),
        initiator=AuthContext(tenant, user, uuid.uuid4(), None, None),
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- the run's context
    )


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    w = World()

    async def pinned(_: AgentContext) -> frozenset[uuid.UUID]:
        return frozenset({NORTHWIND})

    async def resource(tenant: TenantContext, engagement_id: uuid.UUID) -> Resource:
        return Resource.engagement(
            tenant.tenant_id, engagement_id, archived=False, client_id=CLIENT_OF.get(engagement_id)
        )

    async def client_of(_: TenantContext, engagement_id: uuid.UUID) -> uuid.UUID | None:
        return CLIENT_OF.get(engagement_id)

    async def client_of_entity(_: TenantContext, entity: uuid.UUID) -> uuid.UUID | None:
        return ENTITY_CLIENT.get(entity)

    async def authorise(_: AgentContext, action: str, res: Resource) -> None:
        return None

    async def consent(_: TenantContext, subjects: list[object], **__: object) -> tuple[()]:
        w.consent_asked.append(subjects)
        if not w.consent:
            raise TriConsentRequired(facts={"purpose": "use"})
        return ()

    async def record_reads(
        _: TenantContext, kind: str, subjects: list[object], **__: object
    ) -> int:
        return len(subjects)

    async def claim(*_: object) -> object:
        return runtime._Claim(id=uuid.uuid4())  # pyright: ignore[reportPrivateUsage] -- the step-6 claim, faked

    async def settle(*_: object) -> None:
        return None

    for name, fake in {
        "pinned_scope": pinned, "engagement_resource": resource, "client_of": client_of,
        "client_of_entity": client_of_entity, "authorise": authorise,
        "require_tri_consent": consent, "record_reads": record_reads,
        "_claim": claim, "_settle": settle,
    }.items():  # fmt: skip
        monkeypatch.setattr(runtime, name, fake)

    # Each tax tool's handler becomes a probe: it records that it ran and reads nothing.
    probed = dict(registry.registered_tools())
    for name in TAX_TOOLS:
        real = probed[name]

        async def probe(_: object, __: object, *, _name: str = name) -> object:
            w.handled.append(_name)
            raise RuntimeError("probe: the handler ran")

        probed[name] = replace(real, handler=probe)
    monkeypatch.setattr(registry, "_TOOLS", probed)
    yield w


def _call(agent: AgentContext, name: str, arguments: dict[str, object]) -> ToolCallIn:
    raw = json.loads(json.dumps(arguments, default=str))
    return ToolCallIn(run_id=agent.agent_run_id, step_seq=1, attempt=1, name=name, arguments=raw)


def test_the_twelve_tools_are_all_registered_and_tri() -> None:
    assert tax_tools.read_return is not None  # the module registers at import
    found = registry.registered_tools()
    assert {n for n in found if n.startswith("tax.")} >= set(TAX_TOOLS)
    assert {found[n].data_class for n in TAX_TOOLS} == {"tri"}


@pytest.mark.parametrize("name", TAX_TOOLS)
async def test_ac1_without_both_consents_each_tool_refuses_before_its_handler(
    world: World, name: str
) -> None:
    world.consent = False
    agent = _agent()
    outcome = await call_tool(agent, _call(agent, name, _args(FELD)[name]))
    assert (outcome.ok, outcome.code) == (False, "consent_required")
    assert world.handled == []  # no data was fetched
    assert world.consent_asked, "C19's gate was asked for the taxpayer and year"


@pytest.mark.parametrize("name", TAX_TOOLS)
async def test_the_consent_gate_names_the_taxpayer_and_the_year(world: World, name: str) -> None:
    agent = _agent()
    await call_tool(agent, _call(agent, name, _args(FELD)[name]))
    subjects = [s for asked in world.consent_asked for s in asked]  # type: ignore[attr-defined] -- recorded lists
    assert [(s.entity_id, s.tax_year) for s in subjects] == [(FELD, 2025)]  # type: ignore[attr-defined] -- TriSubject


@pytest.mark.parametrize("name", TAX_TOOLS)
async def test_a_taxpayer_outside_the_runs_client_scope_is_refused_first(
    world: World, name: str
) -> None:
    agent = _agent()
    outcome = await call_tool(agent, _call(agent, name, _args(GRANITE_ENTITY)[name]))
    assert outcome.ok is False
    assert outcome.code in ("out_of_scope", "not_visible")
    assert world.handled == []
    assert world.consent_asked == []  # scope is decided before consent is even asked


@pytest.mark.parametrize("name", TAX_TOOLS)
async def test_with_consent_and_scope_the_handler_runs(world: World, name: str) -> None:
    agent = _agent()
    outcome = await call_tool(agent, _call(agent, name, _args(FELD)[name]))
    assert world.handled == [name]
    assert (outcome.ok, outcome.code) == (False, "tool_failed")  # the probe raises
