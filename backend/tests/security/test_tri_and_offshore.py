# ac-test-author: notanaskhan (G-01-T09; T-01 adds the I-7216 cases with its consent provider)
"""I-OFFSHORE (G-01 AC9.2 to AC9.4 as amended by TASK-1207; DEC-52, DEC-319 narrowed, ADR P-12,
§7216, F-03 section 4.4) against Postgres: an offshore member is refused exactly the matrix
actions that carry `not_offshore` (the reveals), at the condition layer (403), and allowed
everything else their roles allow; an agent acting for one works like them and is walled with
them; no reveal of a TIN or other identifier is ever among their allowed actions, consent or not;
and every response field tagged `pii_kind=tin` reaches them masked or null. TIN fields are few
until T-01 adds them: the served routes that carry one are pinned here, and the hook is proved on
a tagged test model.

The control is an onshore manager on the same engagements: their answers differ, so a refusal
can't pass by accident."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast, get_args

import pytest
from fastapi.routing import iter_route_contexts
from pydantic import BaseModel
from sqlalchemy import ColumnElement, literal

from abacus.api import create_app
from abacus.kernel.classification import classified, pii_paths, tri_paths
from abacus.kernel.db import TenantContext
from abacus.modules.identity import slots
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    agent_context_for_run,
    allowed_actions,
    authorise,
    mask_tins_for,
)
from abacus.modules.identity.authz.matrix import RULES

from .support import Env, Person

REVEALS = ("tin.reveal", "pii.reveal")
# The served responses that carry a `pii_kind=tin` field today (route, model), and how each
# reaches an offshore principal: the record through `mask_tins_for`, the reveal never (its action
# is `not_offshore`). A new one fails here until it is wired.
TIN_ROUTES = {
    ("GET", "/v1/clients/{client_id}"): "masked",
    ("PATCH", "/v1/clients/{client_id}"): "masked",
    ("POST", "/v1/client-entities/{entity_id}/tin/reveal"): "refused",
    # P-07-T37 (DEC-374): the client-import stub's rows carry only the masked TIN shape.
    ("GET", "/v1/client-imports/{import_id}/rows"): "masked",
    ("PUT", "/v1/client-imports/{import_id}/rows/{row_id}/decision"): "masked",
    # N-01-T02 (S13 stubs): the file drawer and an intake message's triage cards carry only the
    # masked TIN shape, masked again for an offshore reader (review 6).
    ("GET", "/v1/evidence-items/{item_id}/drawer"): "masked",
    ("GET", "/v1/inbox/messages/{message_id}/triage"): "masked",
    # T-01-T01 (C19 stub): the tax profile carries the masked TIN, through the offshore mask.
    ("GET", "/v1/client-entities/{client_entity_id}/tax-profile"): "masked",
    # T-02-T25 (DEC-1575): a K-1 package's detail carries the recipient's masked TIN.
    ("GET", "/v1/k1-packages/{package_id}"): "masked",
    ("GET", "/v1/portal/k1s/{package_id}"): "masked",
}


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _offshore(env: Env) -> Person:
    who = await env.net.seed.person(env.tenant_id)
    for site in (env.a, env.b):
        await env.net.seed.member(site, who, "manager")
    await env.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        env.tenant_id,
        who.user_id,
    )
    return who


@pytest.fixture
def b_consented(env: Env) -> Iterator[None]:
    """T-01's provider stand-in: a valid consent covers client B only."""
    b = env.b.client_id

    async def check(_tenant: TenantContext, client: uuid.UUID, _p: str, _at: datetime) -> bool:
        return client == b

    def column(client_id: object, _purpose: str) -> ColumnElement[bool]:
        return literal(b) == client_id

    # The real C19 gate registers this purpose when organisations is imported: set it aside for
    # the stand-in and put it back after, so neither registration leaks into another test.
    tables = (
        slots._CONSENTS,  # pyright: ignore[reportPrivateUsage] -- the stand-in swaps the registration
        slots._CONSENT_COLUMNS,  # pyright: ignore[reportPrivateUsage] -- likewise
        slots._CONSENT_COUNTS,  # pyright: ignore[reportPrivateUsage] -- likewise
    )
    saved = [table.pop(slots.OFFSHORE_DISCLOSURE, None) for table in tables]
    slots.register_consent_check(slots.OFFSHORE_DISCLOSURE, check, column)
    yield
    for table, original in zip(tables, saved, strict=True):
        table.pop(slots.OFFSHORE_DISCLOSURE, None)
        if original is not None:
            table[slots.OFFSHORE_DISCLOSURE] = original  # pyright: ignore[reportArgumentType] -- the entry popped above


# --- refused only the `not_offshore` actions, at the condition layer -----------------------------

NOT_OFFSHORE = frozenset(a for a, rule in RULES.items() if rule.not_offshore)


async def _outcome(ctx: AuthContext, action: str, resource: Resource) -> str:
    try:
        await authorise(ctx, action, resource, reason="probe")
    except Forbidden as denied:
        return denied.layer
    return "allowed"


async def test_i_offshore_only_the_not_offshore_actions_are_refused_at_the_condition_layer(
    env: Env,
) -> None:
    """Remy (offshore) and an onshore manager hold the same roles on both engagements: over every
    matrix action, their answers differ only on `not_offshore` actions, which Remy is refused at
    the condition layer, and the onshore manager is allowed at least one of them."""
    remy = _ctx(await _offshore(env))
    manager = await env.net.seed.person(env.tenant_id)
    for site in (env.a, env.b):
        await env.net.seed.member(site, manager, "manager")
    control = _ctx(manager)
    resources = (
        Resource.client(env.tenant_id, env.a.client_id),
        Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False),
    )
    found: list[str] = []
    refused: set[str] = set()
    for action in sorted(RULES):
        for resource in resources:
            mine = await _outcome(remy, action, resource)
            theirs = await _outcome(control, action, resource)
            if mine == theirs:
                continue
            if action in NOT_OFFSHORE and mine == "condition" and theirs == "allowed":
                refused.add(action)
                continue
            found.append(f"{action}: offshore {mine}, onshore {theirs}")
    assert found == []
    # Not vacuous: every `not_offshore` action is reached and refused at the condition, where the
    # onshore manager is allowed it (security review: both reveals, independence confirmed; the
    # re-check's exports). `firm_export.download` is firm-level and a manager's role never holds
    # it: the security admins below show it.
    assert {
        "tin.reveal",
        "pii.reveal",
        "export.create",
        "export.download",  # A-01-T17 (DEC-376): the engagement export bundle
        "email_template.test_send",  # R-01-T16 (DEC-379): firm-level, below
        "run_trace.export",
        "trial_balance.export",
        "signer.reveal_ip",  # N-02-T02 (SPEC-381): a signer's IP, revealed as a second step
        "envelope.evidence_download",  # N-02-T02: the signed envelope's evidence package
        "inbox.read_content",  # N-01-T02 (SPEC-380): an intake item's content
        "inbox.download",  # N-01-T02: an intake attachment
        # A-03-T01 (DEC-1550): the sample workbook keeps census fields onshore.
        "sample_set.export",
        "firm_export.download",
    } == NOT_OFFSHORE
    assert refused == NOT_OFFSHORE - {"firm_export.download", "email_template.test_send"}
    admin = await env.net.seed.person(env.tenant_id, "security_admin")
    offshore_admin = await env.net.seed.person(env.tenant_id, "security_admin")
    await env.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        env.tenant_id,
        offshore_admin.user_id,
    )
    firm = Resource.firm(env.tenant_id)
    as_admin = replace(_ctx(admin), firm_role="security_admin")
    as_offshore = replace(_ctx(offshore_admin), firm_role="security_admin")
    assert await _outcome(as_admin, "firm_export.download", firm) == "allowed"
    assert await _outcome(as_offshore, "firm_export.download", firm) == "condition"
    # R-01-T16 (DEC-379): a test send is a firm admin's, firm-level: refused offshore at the
    # condition where the onshore firm admin is allowed it.
    firm_admin = await env.net.seed.person(env.tenant_id, "firm_admin")
    offshore_firm_admin = await env.net.seed.person(env.tenant_id, "firm_admin")
    await env.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        env.tenant_id,
        offshore_firm_admin.user_id,
    )
    as_firm_admin = replace(_ctx(firm_admin), firm_role="firm_admin")
    as_offshore_firm_admin = replace(_ctx(offshore_firm_admin), firm_role="firm_admin")
    assert await _outcome(as_firm_admin, "email_template.test_send", firm) == "allowed"
    assert await _outcome(as_offshore_firm_admin, "email_template.test_send", firm) == "condition"
    engagement = resources[1]
    mine_allowed = await allowed_actions(remy, engagement)
    assert "engagement.read" in mine_allowed
    assert mine_allowed == await allowed_actions(control, engagement) - NOT_OFFSHORE


async def test_i_offshore_the_control_onshore_manager_is_allowed(env: Env) -> None:
    manager = await env.net.seed.person(env.tenant_id)
    await env.net.seed.member(env.a, manager, "manager")
    resource = Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False)
    assert "engagement.read" in await allowed_actions(_ctx(manager), resource)


async def test_i_offshore_an_agent_for_remy_works_like_him_and_is_walled_with_him(
    env: Env,
) -> None:
    remy = await _offshore(env)
    run = await env.net.seed.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status) VALUES ($1, 'evidence.screener', 1, $2, $3, "
        "'{}', 'running') RETURNING id",
        env.tenant_id,
        env.a.engagement_id,
        remy.user_id,
    )
    agent = await agent_context_for_run(
        tenant_id=env.tenant_id,
        run_id=uuid.UUID(str(run)),
        agent_id="evidence.screener",
        engagement_id=env.a.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=remy.user_id,
    )
    resource = Resource.engagement(env.tenant_id, env.a.engagement_id, archived=False)
    await authorise(agent, "evidence.read", resource)  # offshore is no wall (TASK-1207)
    await env.net.wall(env.admin, remy, env.a)
    with pytest.raises(Forbidden) as denied:
        await authorise(agent, "evidence.read", resource)
    assert denied.value.layer == "wall"


# --- no reveal, ever -----------------------------------------------------------------------------


def test_recheck_every_export_and_download_of_client_content_is_not_offshore() -> None:
    """TASK-1207 re-check, item 10: an export or download hands over client content wholesale,
    so offshore is refused it at the condition layer like a reveal."""
    exports = {"export.create", "firm_export.download", "run_trace.export", "trial_balance.export"}
    assert [a for a in sorted(exports) if not RULES[a].not_offshore] == []


def test_i_offshore_every_reveal_action_is_not_offshore_in_the_matrix() -> None:
    reveals = sorted(a for a in RULES if a.endswith(".reveal"))
    assert set(REVEALS) <= set(reveals)
    assert [a for a in reveals if not RULES[a].not_offshore] == []


async def test_i_offshore_a_consented_client_still_allows_no_reveal(
    env: Env, b_consented: None
) -> None:
    remy = _ctx(await _offshore(env))
    for site in (env.b, env.a):  # B consented, A not: the same answers (TASK-1207)
        resource = Resource.engagement(env.tenant_id, site.engagement_id, archived=False)
        allowed = await allowed_actions(remy, resource)
        assert "engagement.read" in allowed  # his manager role applies, consent or not
        assert not set(REVEALS) & allowed


# --- TIN fields reach an offshore principal masked -----------------------------------------------


class _TinOut(BaseModel):
    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    last4: Annotated[str | None, classified("restricted", pii_kind="tin")] = None
    name: Annotated[str, classified("confidential")]


class _NestedOut(BaseModel):
    one: _TinOut
    many: Annotated[list[_TinOut], classified("internal")]


def _sample() -> _NestedOut:
    tin = _TinOut(tin="900-12-3456", last4="3456", name="Remy")
    return _NestedOut(one=tin, many=[tin, tin])


async def test_i_offshore_tagged_tin_fields_are_masked_or_null_for_an_offshore_principal(
    env: Env,
) -> None:
    remy = _ctx(await _offshore(env))
    masked = await mask_tins_for(remy, _sample())
    for item in (masked.one, *masked.many):
        assert item.tin == "•••-••-3456"
        assert item.last4 is None
        assert item.name == "Remy"
    manager = await env.net.seed.person(env.tenant_id)
    assert await mask_tins_for(_ctx(manager), _sample()) == _sample()


def test_i_offshore_every_served_tin_field_is_masked_or_refused() -> None:
    def models(annotation: object) -> Iterator[type[BaseModel]]:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield annotation
        for arg in get_args(annotation):
            yield from models(arg)

    found: dict[tuple[str, str], str] = {}
    for context in iter_route_contexts(create_app().routes):
        route = context.original_route
        path = str(context.path)
        methods = cast(set[str], getattr(route, "methods", None) or set())
        for model in models(getattr(route, "response_model", None)):
            if pii_paths(model, "tin"):
                for method in methods:
                    found[(method, path)] = TIN_ROUTES.get((method, path), "?")
    assert found == TIN_ROUTES
    reveal = RULES["tin.reveal"]
    assert reveal.not_offshore


# --- T-02-T30 (TASK-2533): K-1 and organizer fields ---------------------------------------------
# Written from T-02 §3.6 to §3.8 and `docs/contracts/k1-packages.md` §3 ("box amounts TRI; names
# and addresses confidential; TIN last four only"): the amounts and the organizer's answers are
# TRI, a list row carries neither amounts nor a TIN, and an offshore reader of a K-1's detail
# gets its TIN null through the central mask. The product contracts are imported inside each test:
# importing the tax module registers the firm's consent provider, which `b_consented` above
# installs its stand-in for, so a module-level import would collide at collection.


def test_t02t30_k1_amounts_and_organizer_answers_are_tri_and_rows_carry_neither() -> None:
    from abacus.modules.requests.questionnaires_contract import AnswerIn, QuestionnaireOut
    from abacus.modules.tax.k1_contract import (
        K1PackageDetailOut,
        K1PackageOut,
        PortalK1ExpectedOut,
    )

    assert any("amount" in path for path in tri_paths(K1PackageDetailOut))
    assert any("answer" in path for path in tri_paths(QuestionnaireOut))
    assert any("value" in path for path in tri_paths(AnswerIn))
    assert pii_paths(K1PackageDetailOut, "tin")
    for row in (K1PackageOut, PortalK1ExpectedOut):
        assert tri_paths(row) == (), row.__name__
        assert pii_paths(row, "tin") == (), row.__name__


def _k1_detail() -> BaseModel:
    from abacus.kernel._statuses import K1PackageStatus
    from abacus.modules.tax.k1_contract import K1MaskedTinOut, K1PackageDetailOut, K1PackageOut

    return K1PackageDetailOut(
        package=K1PackageOut(
            id=uuid.uuid4(),
            recipient_id=uuid.uuid4(),
            recipient_name="Pell Street Ventures LLC",
            recipient_kind="lp",
            form="1065",
            tax_year=2025,
            status=K1PackageStatus.RELEASED,
            k3_status="included",
            state_codes=["IL"],
            released_at=None,
            version_no=1,
            allowed_actions=[],
        ),
        lines=[],
        documents=[],
        tin=K1MaskedTinOut(kind="ein", last4="7741"),
    )


async def test_t02t30_an_offshore_reader_of_a_k1_gets_its_tin_null(env: Env) -> None:
    remy = _ctx(await _offshore(env))
    masked = cast(
        dict[str, dict[str, object] | None], (await mask_tins_for(remy, _k1_detail())).model_dump()
    )
    tin = masked["tin"]
    assert tin is None or tin["last4"] is None
    manager = await env.net.seed.person(env.tenant_id)
    detail = _k1_detail()
    assert await mask_tins_for(_ctx(manager), detail) == detail
