# ac-test-author: ayushkbhatia
"""P-04-T20 (ADR-078, TASK-1347): independent AC and property tests for I-SEGREGATION and the
sign-off invariants R-SO-1 to R-SO-6 (SHL-12).

"Property tests over random sign-off sequences, written in ayushkbhatia's session, find no
accepted sequence that breaks R-SO-1 to R-SO-6." Preparer never L2/L3, EQR never L1-L4, EP never
EQR, open notes block L2 and above, staleness by hash, five-layer human-only.

Written from P-04 §3 F2, the R-SO table and §4.7 of `docs/plan/03-backend-architecture.md`,
ADR-160 clauses 2 to 4, `docs/contracts/review-grammar.md` (§2 and the live paragraph),
`docs/architecture/permission-matrix/review.yaml`, DEC-216 and DEC-400 to DEC-402. The code was
read only for routes and fixtures. Requests go through `create_app()` as each person
(`current_context` overridden) with `review.grammar_api` on. The target is a reviewable type this
suite owns (`segregation_probe`), registered through review's facts slot as an owner would
(DEC-216), so a test states the owner's facts: preparers, empty required fields, uncited values
and the hash.

The model below is this suite's reading of the matrix and the spec, not the service's code:
who may sign which level (R-SO-2), segregation both ways (R-SO-3, DEC-400), open notes (R-SO-4),
the signer's own independence (R-SO-5), incomplete or uncited values (R-SO-6), and the hash the
signer saw (409 `content_changed`). Every accepted row must satisfy it; every attempt it forbids
must be refused with one of the contract's fixed codes; rows are insert-only.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import RULES, AuthContext, current_context
from abacus.modules.review import stale as review_stale
from abacus.modules.review.api import STATEMENTS, ReviewableFacts, register_reviewable_facts
from abacus_tools.quality import banned_patterns

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

PROBE: Final = "segregation_probe"
LEVELS: Final = ("L1_preparer", "L2_reviewer", "L3_manager", "L4_partner", "L5_eqr")
LEVEL_NO: Final = {name: n for n, name in enumerate(LEVELS, start=1)}
# review.yaml, the level rows (R-SO-2; DEC-401 adds `eqr_reviewer` beside `reviewer` on L5).
LEVEL_ROLES: Final[dict[str, frozenset[str]]] = {
    "L1_preparer": frozenset({"manager", "senior", "staff"}),
    "L2_reviewer": frozenset({"engagement_partner", "manager", "senior"}),
    "L3_manager": frozenset({"engagement_partner", "manager"}),
    "L4_partner": frozenset({"engagement_partner"}),
    "L5_eqr": frozenset({"reviewer", "eqr_reviewer"}),
}
LEVEL_ACTIONS: Final = (
    "sign_off.prepare",
    "sign_off.review",
    "sign_off.manager",
    "sign_off.partner",
    "sign_off.eqr",
)
# The contract's fixed codes (review-grammar §6 and the live paragraph), plus the generic refusals.
FIXED: Final = frozenset(
    {
        "forbidden",
        "not found",
        "not_found",
        "level_not_permitted",
        "segregation",
        "open_review_notes",
        "independence_pending",
        "content_changed",
        "sign_off_invalid",
        "incomplete",
        "uncited_change",
        "already_signed",
        "not_prepared",
    }
)
# The cast: role on the engagement (None: not on the team); Lena has not confirmed independence.
CAST: Final[dict[str, str | None]] = {
    "ana": "staff",
    "marcus": "senior",
    "kevin": "senior",
    "hannah": "manager",
    "margaret": "engagement_partner",
    "thomas": "eqr_reviewer",
    "rhea": "reviewer",
    "lena": "staff",
    "omar": None,
}
UNCONFIRMED: Final = frozenset({"lena"})
SIGNERS: Final = tuple(CAST)

FACTS: dict[uuid.UUID, ReviewableFacts] = {}


async def _probe_facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    return FACTS.get(target_id)


register_reviewable_facts(PROBE, _probe_facts)


def _statement(level: str) -> str:
    return STATEMENTS[5].version if level == "L5_eqr" else STATEMENTS[2].version


def _seen(digest: str) -> str:
    return f"sha256:{digest}"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


def _ctx(who: Person, kind: str = "human") -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, kind, str(who.user_id)),  # type: ignore[arg-type]  # the actor kind under test is a plain str
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


@dataclass
class Ladder:
    """One firm, one engagement (Northwind Robotics 401(k) Plan) and the cast above."""

    seed: Seeder
    tenant: uuid.UUID
    engagement: uuid.UUID
    people: dict[str, Person]
    app_url: str
    app: FastAPI = field(default_factory=create_app)

    async def call(
        self, ctx: AuthContext, method: str, path: str, **kwargs: object
    ) -> httpx.Response:
        self.app.dependency_overrides[current_context] = lambda: ctx
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx keywords passed through

    async def sign(
        self,
        who: str,
        target: uuid.UUID,
        level: str,
        seen: str,
        *,
        kind: str = "human",
        statement: str | None = None,
    ) -> httpx.Response:
        body = {
            "target_type": PROBE,
            "target_id": str(target),
            "level": level,
            "seen_hash": seen,
            "statement_version": statement or _statement(level),
        }
        return await self.call(_ctx(self.people[who], kind), "POST", "/v1/sign-offs", json=body)

    async def ladder(self, who: str, target: uuid.UUID) -> httpx.Response:
        params = {"target_type": PROBE, "target_id": str(target)}
        return await self.call(_ctx(self.people[who]), "GET", "/v1/sign-offs", params=params)

    def target(
        self,
        *,
        preparers: frozenset[str] = frozenset(),
        incomplete: int = 0,
        uncited: int = 0,
        digest: str | None = None,
    ) -> uuid.UUID:
        target = uuid.uuid4()
        FACTS[target] = ReviewableFacts(
            PROBE,
            target,
            self.engagement,
            digest or uuid.uuid4().hex * 2,
            1,
            frozenset(self.people[p].user_id for p in preparers),
            label="Probe workpaper",
            incomplete_count=incomplete,
            uncited_count=uncited,
            cell_count=4,
            cited_count=4 - uncited,
        )
        return target

    def edit(self, target: uuid.UUID) -> str:
        """The owner changes the target: a new hash, the version moves on."""
        old = FACTS[target]
        digest = uuid.uuid4().hex * 2
        FACTS[target] = replace(old, content_hash=digest, version_no=old.version_no + 1)
        return digest

    async def notes(self, target: uuid.UUID, count: int) -> None:
        for n in range(count):
            await self.seed.as_actor(
                self.tenant,
                ("human", str(self.people["hannah"].user_id)),
                "INSERT INTO reviewable_notes (tenant_id, engagement_id, target_type, target_id, "
                "anchor, body, raised_by) VALUES ($1, $2, $3, $4, $5, 'Tie this to the TB.', $6)",
                self.tenant,
                self.engagement,
                PROBE,
                target,
                f"RA!C{14 + n}",
                self.people["hannah"].user_id,
            )

    async def rows(self, target: uuid.UUID) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT id, level, signed_by, content_hash, actor_kind, actor_id, created_at "
            "FROM sign_offs WHERE target_id = $1 ORDER BY created_at, id",
            target,
        )

    def name_of(self, user_id: uuid.UUID) -> str:
        return next(n for n, p in self.people.items() if p.user_id == user_id)


async def _ladder(migrated_db: MigratedDatabase) -> Ladder:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    people = {name: await seed.person(tenant) for name in CAST}
    entity = await seed.entity(tenant, "Northwind Robotics 401(k) Plan")
    engagement = await seed.engagement(tenant, entity, people["margaret"].user_id)
    for name, role in CAST.items():
        if role is None:
            continue
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            tenant,
            engagement,
            people[name].user_id,
            role,
        )
        if name not in UNCONFIRMED:
            await seed.confirm(engagement, people[name])
        else:
            await seed.run(
                "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                tenant,
                engagement,
                people[name].user_id,
            )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'p04t20', 'TASK-1347')",
        tenant,
    )
    return Ladder(seed, tenant, engagement, people, migrated_db.app_url)


@pytest.fixture
async def ladder(migrated_db: MigratedDatabase) -> Ladder:
    return await _ladder(migrated_db)


# ================================================================================================
# The model: what R-SO-1 to R-SO-6 forbid, from the matrix and the spec
# ================================================================================================


@dataclass(frozen=True)
class Signed:
    who: str
    level: int
    digest: str


@dataclass
class Model:
    preparers: frozenset[str]
    notes: int
    incomplete: int
    uncited: int
    digest: str
    signed: list[Signed] = field(default_factory=list[Signed])

    def forbidden(self, who: str, level: str, kind: str, seen: str) -> str | None:
        """The rule that forbids this attempt, or None when the model has no objection."""
        n = LEVEL_NO[level]
        role = CAST[who]
        if kind != "human":
            return "R-SO-1"
        if role is None or role not in LEVEL_ROLES[level]:
            return "R-SO-2"
        if who in UNCONFIRMED:
            return "R-SO-5"
        if seen != _seen(self.digest):
            return "content_changed"
        if self.incomplete or self.uncited:
            return "R-SO-6"
        if n >= 2 and self.notes:
            return "R-SO-4"
        mine = {s.level for s in self.signed if s.who == who}
        if n in (2, 3) and (who in self.preparers or 1 in mine):
            return "R-SO-3 preparer"
        if n == 1 and mine & {2, 3}:
            return "R-SO-3 reviewer"
        if n == 5 and mine & {1, 2, 3, 4}:
            return "R-SO-3 eqr"
        if n <= 4 and 5 in mine:
            return "R-SO-3 eqr"
        if n >= 2 and not any(s.level == 1 and s.digest == self.digest for s in self.signed):
            return "not_prepared"
        return None


def _broken(model: Model, rows: list[asyncpg.Record], ladder: Ladder) -> list[str]:
    """Every way the accepted rows break R-SO-1 to R-SO-6."""
    problems: list[str] = []
    by_level: dict[int, set[str]] = {n: set() for n in range(1, 6)}
    for row in rows:
        who = ladder.name_of(cast(uuid.UUID, row["signed_by"]))
        level = cast(int, row["level"])
        by_level[level].add(who)
        if row["actor_kind"] != "human" or row["actor_id"] != str(ladder.people[who].user_id):
            problems.append(f"R-SO-1: {who} L{level} written as {row['actor_kind']}")
        if CAST[who] not in LEVEL_ROLES[LEVELS[level - 1]]:
            problems.append(f"R-SO-2: {who} ({CAST[who]}) holds L{level}")
        if who in UNCONFIRMED:
            problems.append(f"R-SO-5: {who} signed L{level} unconfirmed")
        if level >= 2 and model.notes:
            problems.append(f"R-SO-4: L{level} signed over {model.notes} open notes")
        if model.incomplete or model.uncited:
            problems.append(f"R-SO-6: L{level} signed incomplete or uncited")
    reviewers = by_level[2] | by_level[3]
    if clash := reviewers & (model.preparers | by_level[1]):
        problems.append(f"R-SO-3: preparer(s) {sorted(clash)} signed L2/L3")
    if clash := by_level[5] & (by_level[1] | by_level[2] | by_level[3] | by_level[4]):
        problems.append(f"R-SO-3: {sorted(clash)} signed L5 and L1-L4")
    if "thomas" in by_level[1] | by_level[2] | by_level[3] | by_level[4]:
        problems.append("R-SO-3: the EQR signed L1-L4")
    if "margaret" in by_level[5]:
        problems.append("R-SO-3: the engagement partner signed as EQR")
    return problems


# One step: an attempt (person, level, actor kind) or an edit by the owner.
ATTEMPT = st.tuples(
    st.just("sign"),
    st.sampled_from(SIGNERS),
    st.sampled_from(LEVELS),
    st.sampled_from(("human",) * 6 + ("agent", "system")),
)
STEP = st.one_of(ATTEMPT, ATTEMPT, ATTEMPT, st.just(("edit", "", "", "")))


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    preparers=st.frozensets(st.sampled_from(SIGNERS), max_size=3),
    notes=st.sampled_from((0, 0, 0, 1, 2)),
    incomplete=st.sampled_from((0, 0, 0, 0, 1)),
    uncited=st.sampled_from((0, 0, 0, 0, 1)),
    steps=st.lists(STEP, min_size=1, max_size=10),
    fresh=st.lists(st.sampled_from((True, True, True, False)), min_size=10, max_size=10),
)
async def test_property_no_accepted_sequence_breaks_r_so_1_to_6(
    ladder: Ladder,
    preparers: frozenset[str],
    notes: int,
    incomplete: int,
    uncited: int,
    steps: list[tuple[str, str, str, str]],
    fresh: list[bool],
) -> None:
    target = ladder.target(preparers=preparers, incomplete=incomplete, uncited=uncited)
    await ladder.notes(target, notes)
    model = Model(preparers, notes, incomplete, uncited, FACTS[target].content_hash)
    accepted: dict[str, Signed] = {}
    for n, (step, who, level, kind) in enumerate(steps):
        if step == "edit":
            model.digest = ladder.edit(target)
            continue
        # Mostly the hash the signer just read; sometimes one from before an edit or made up.
        seen = _seen(model.digest) if fresh[n] else _seen(uuid.uuid4().hex * 2)
        rule = model.forbidden(who, level, kind, seen)
        found = await ladder.sign(who, target, level, seen, kind=kind)
        if found.status_code == 201:
            assert rule is None, (rule, who, level, kind, found.text)
            body = found.json()
            assert body["content_hash"] == seen, body
            assert body["level"] == level, body
            signed = Signed(who, LEVEL_NO[level], model.digest)
            model.signed.append(signed)
            accepted[cast(str, body["id"])] = signed
        else:
            assert found.status_code in (403, 404, 409, 422), found.text
            assert found.json().get("detail") in FIXED, found.text
    rows = await ladder.rows(target)
    assert _broken(model, rows, ladder) == []
    # Exactly the accepted attempts were written, each with the hash its signer saw, and no row
    # was updated afterwards (insert-only; staleness is computed, never written).
    assert {str(r["id"]): (r["level"], r["content_hash"]) for r in rows} == {
        k: (s.level, s.digest) for k, s in accepted.items()
    }


# ================================================================================================
# The named invariants as examples (SHL-12 c, g; R-SO-3 and R-SO-4)
# ================================================================================================


async def test_ac_the_preparer_is_never_l2_or_l3(ladder: Ladder) -> None:
    target = ladder.target(preparers=frozenset({"marcus", "hannah"}))
    seen = _seen(FACTS[target].content_hash)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    for who, level in (
        ("marcus", "L2_reviewer"),
        ("hannah", "L2_reviewer"),
        ("hannah", "L3_manager"),
    ):
        refused = await ladder.sign(who, target, level, seen)
        assert (refused.status_code, refused.json()["detail"]) == (409, "segregation"), level
    # Ana signed L1, so she is a preparer too, whatever the owner's facts say (DEC-216).
    refused = await ladder.sign("ana", target, "L2_reviewer", seen)
    assert refused.status_code in (403, 409), refused.text
    assert len(await ladder.rows(target)) == 1


async def test_ac_a_reviewer_never_signs_l1_on_what_they_reviewed(ladder: Ladder) -> None:
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    assert (await ladder.sign("kevin", target, "L2_reviewer", seen)).status_code == 201
    # A later change makes Ana's L1 stale; Kevin may not prepare the new content (any content).
    digest = ladder.edit(target)
    refused = await ladder.sign("kevin", target, "L1_preparer", _seen(digest))
    assert (refused.status_code, refused.json()["detail"]) == (409, "segregation")


async def test_ac_the_eqr_never_signs_l1_to_l4_and_the_ep_never_l5(ladder: Ladder) -> None:
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    for level in ("L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"):
        refused = await ladder.sign("thomas", target, level, seen)
        assert (refused.status_code, refused.json()["detail"]) == (403, "level_not_permitted")
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    ep = await ladder.sign("margaret", target, "L5_eqr", seen)
    assert (ep.status_code, ep.json()["detail"]) == (403, "level_not_permitted")
    eqr = await ladder.sign("thomas", target, "L5_eqr", seen)
    assert eqr.status_code == 201, eqr.text
    assert eqr.json()["statement_version"] == STATEMENTS[5].version
    assert [r["level"] for r in await ladder.rows(target)] == [1, 5]


async def test_ac_one_person_never_holds_l5_and_a_lower_level(ladder: Ladder) -> None:
    """R-SO-3 (DEC-400 review L2): the `reviewer` role holds L5; once Rhea signs L5 nobody
    can make her a lower signer, and the matrix never lets her sign L1 to L4 in the first place."""
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    assert (await ladder.sign("rhea", target, "L5_eqr", seen)).status_code == 201
    for level in ("L1_preparer", "L2_reviewer", "L3_manager", "L4_partner"):
        assert (await ladder.sign("rhea", target, level, seen)).status_code in (403, 409)
    rows = await ladder.rows(target)
    assert {(ladder.name_of(r["signed_by"]), r["level"]) for r in rows} == {
        ("ana", 1),
        ("rhea", 5),
    }


async def test_ac_open_notes_block_every_level_from_l2_but_not_l1(ladder: Ladder) -> None:
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    await ladder.notes(target, 2)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    for who, level in (
        ("hannah", "L2_reviewer"),
        ("hannah", "L3_manager"),
        ("margaret", "L4_partner"),
        ("thomas", "L5_eqr"),
    ):
        refused = await ladder.sign(who, target, level, seen)
        assert refused.status_code == 409, (level, refused.text)
        assert refused.json() == {"detail": "open_review_notes", "facts": {"count": 2}}, level
    # Clearing both lets the same reviewer sign (P-04-T21's acceptance, through the notes' state).
    await ladder.seed.run(
        "UPDATE reviewable_notes SET status = 'cleared' WHERE target_id = $1", target
    )
    assert (await ladder.sign("hannah", target, "L2_reviewer", seen)).status_code == 201


async def test_ac_an_unconfirmed_member_is_independence_pending_at_every_level(
    ladder: Ladder,
) -> None:
    target = ladder.target()
    refused = await ladder.sign("lena", target, "L1_preparer", _seen(FACTS[target].content_hash))
    assert (refused.status_code, refused.json()["detail"]) == (409, "independence_pending")
    assert await ladder.rows(target) == []


# ================================================================================================
# Staleness by hash (DEC-84, SHL-12 e)
# ================================================================================================


async def test_ac_a_change_makes_signed_levels_stale_without_touching_a_row(
    ladder: Ladder,
) -> None:
    target = ladder.target()
    first = FACTS[target].content_hash
    assert (await ladder.sign("ana", target, "L1_preparer", _seen(first))).status_code == 201
    assert (await ladder.sign("hannah", target, "L2_reviewer", _seen(first))).status_code == 201
    before = [dict(r) for r in await ladder.rows(target)]

    second = ladder.edit(target)
    view = (await ladder.ladder("hannah", target)).json()
    assert view["target"]["content_hash"] == _seen(second)
    latest = {lv["level"]: lv["latest"] for lv in view["levels"]}
    assert latest["L1_preparer"]["stale"] is True
    assert latest["L2_reviewer"]["stale"] is True
    assert latest["L1_preparer"]["content_hash"] == _seen(first)
    # Nothing about a row changed: staleness is computed from the hashes.
    assert [dict(r) for r in await ladder.rows(target)] == before

    # The old hash is now refused; the re-sign is a new row on the new hash.
    old = await ladder.sign("ana", target, "L1_preparer", _seen(first))
    assert (old.status_code, old.json()["detail"]) == (409, "content_changed")
    assert (await ladder.sign("ana", target, "L1_preparer", _seen(second))).status_code == 201
    view = (await ladder.ladder("hannah", target)).json()
    assert "sign_off.resign.L2_reviewer" in view["allowed_actions"]
    again = await ladder.sign("hannah", target, "L2_reviewer", _seen(second))
    assert again.status_code == 201, again.text
    rows = await ladder.rows(target)
    assert [dict(r) for r in rows[:2]] == before
    assert [(r["level"], r["content_hash"]) for r in rows[2:]] == [(1, second), (2, second)]
    latest = {
        lv["level"]: lv["latest"] for lv in (await ladder.ladder("ana", target)).json()["levels"]
    }
    assert latest["L1_preparer"]["stale"] is False and latest["L2_reviewer"]["stale"] is False


async def test_ac_the_signer_is_told_once_per_sign_off(
    ladder: Ladder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The detector announces `sign_off.went_stale` once per stale sign-off: a replayed or a
    further change event writes nothing more (DEC-402). The probe's owner announces its changes
    as `segregation_probe.version_created`, registered for this test only."""
    monkeypatch.setitem(
        review_stale.STALE_SOURCES, "segregation_probe.version_created", (PROBE, "target_id")
    )
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    assert (await ladder.sign("hannah", target, "L2_reviewer", seen)).status_code == 201

    def changed() -> OutboxEvent:
        return OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=ladder.tenant,
            event_type="segregation_probe.version_created",
            payload={"target_id": str(target)},
        )

    assert await review_stale.detect_stale(changed()) == 0  # nothing stale yet
    ladder.edit(target)
    assert await review_stale.detect_stale(changed()) == 2
    assert await review_stale.detect_stale(changed()) == 0  # the replay
    ladder.edit(target)
    assert await review_stale.detect_stale(changed()) == 0  # a further change: told already
    told = await ladder.seed.rows(
        "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'sign_off.went_stale'",
        ladder.tenant,
    )
    assert [r["actor_kind"] for r in told] == ["system", "system"]


# ================================================================================================
# Five-layer human-only (R-SO-1; §4.7; INV-1)
# ================================================================================================


def test_layer1_the_matrix_denies_the_agent_every_sign_off_action() -> None:
    for action in (*LEVEL_ACTIONS, "sign_off.create", "sign_off.bulk"):
        assert RULES[action].decisions.get("agent") == "deny", action
    for action in ("sign_off.create", "sign_off.bulk"):
        assert RULES[action].decisions.get("system") == "deny", action
    # Who holds each level row is exactly the spec's (R-SO-2).
    for level, action in zip(LEVELS, LEVEL_ACTIONS, strict=True):
        allowed = {r for r, d in RULES[action].decisions.items() if d == "allow"}
        assert allowed == set(LEVEL_ROLES[level]), action


async def test_layer2_an_agent_or_system_context_never_signs_any_level(ladder: Ladder) -> None:
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    for kind in ("agent", "system"):
        for who, level in (
            ("ana", "L1_preparer"),
            ("hannah", "L2_reviewer"),
            ("hannah", "L3_manager"),
            ("margaret", "L4_partner"),
            ("thomas", "L5_eqr"),
        ):
            refused = await ladder.sign(who, target, level, seen, kind=kind)
            assert refused.status_code == 403, (kind, level, refused.text)
    assert await ladder.rows(target) == []


async def test_layer3_the_database_refuses_a_row_not_written_by_the_acting_person(
    ladder: Ladder,
) -> None:
    ana = ladder.people["ana"]
    insert = (
        "INSERT INTO sign_offs (tenant_id, engagement_id, target_type, target_id, level, "
        "content_hash, signed_by, actor_kind, actor_id) "
        "VALUES ($1, $2, $3, $4, 1, $5, $6, $7, $8)"
    )
    digest = "b" * 64
    for kind in ("agent", "system", "policy"):
        with pytest.raises(asyncpg.CheckViolationError):
            await ladder.seed.as_actor(
                ladder.tenant,
                (kind, str(ana.user_id)),
                insert,
                ladder.tenant,
                ladder.engagement,
                PROBE,
                uuid.uuid4(),
                digest,
                ana.user_id,
                kind,
                str(ana.user_id),
            )
    # A human row claiming someone other than the transaction's actor is refused too.
    with pytest.raises(asyncpg.CheckViolationError):
        await ladder.seed.as_actor(
            ladder.tenant,
            ("human", str(ladder.people["kevin"].user_id)),
            insert,
            ladder.tenant,
            ladder.engagement,
            PROBE,
            uuid.uuid4(),
            digest,
            ana.user_id,
            "human",
            str(ana.user_id),
        )


async def test_layer3_sign_offs_are_insert_only_for_the_app(ladder: Ladder) -> None:
    """The app role (the kernel's tenant session) may neither update nor delete a sign-off."""
    target = ladder.target()
    seen = _seen(FACTS[target].content_hash)
    assert (await ladder.sign("ana", target, "L1_preparer", seen)).status_code == 201
    ana = ladder.people["ana"]
    for statement in (
        "UPDATE sign_offs SET content_hash = repeat('c', 64) WHERE target_id = :t",
        "DELETE FROM sign_offs WHERE target_id = :t",
    ):
        with pytest.raises(DBAPIError) as refused:
            async with tenant_session(
                TenantContext(ladder.tenant, "human", str(ana.user_id))
            ) as session:
                await session.execute(text(statement), {"t": target})
        assert "permission denied" in str(refused.value), statement
    assert len(await ladder.rows(target)) == 1


def test_layer4_only_the_review_service_reaches_a_sign_off(tmp_path: Path) -> None:
    rel = "src/abacus/modules/fieldwork/shortcut.py"

    def found(text: str) -> list[str]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return [v.rule_id for v in banned_patterns.scan(tmp_path) if v.path == rel]

    assert "SIGNOFF-001" not in found("VALUE = 1\n")
    assert "SIGNOFF-001" in found(
        "from abacus.modules.review.service import record_sign_off\n"
        "async def go(ctx):\n    await record_sign_off(ctx)\n"
    )
    assert "SIGNOFF-001" in found(
        "from abacus.modules.review.sign_offs import sign_target\n"
        "async def go(ctx):\n    await sign_target(ctx)\n"
    )


def test_layer5_no_sign_off_executes_a_write_after_approval() -> None:
    """§4.7 layer 5 (the single-use approval grant) covers writes that execute after an
    approval (posting, export, send). A sign-off executes nothing afterwards: it is itself the
    row. The register keeps it human-only (`docs/architecture/human-only-actions.yaml`)."""
    register = (
        Path(__file__).resolve().parents[3] / "docs/architecture/human-only-actions.yaml"
    ).read_text(encoding="utf-8")
    assert "sign_off.recorded" in register


# --- the model judges correctly: a planted breach is caught -----------------------------------


def test_the_judgement_catches_a_planted_breach() -> None:
    @dataclass(frozen=True)
    class FakeLadder:
        people: dict[str, Person]

        def name_of(self, user_id: uuid.UUID) -> str:
            return next(n for n, p in self.people.items() if p.user_id == user_id)

    tenant = uuid.uuid4()
    people = {name: Person(uuid.uuid4(), tenant) for name in CAST}

    def row(who: str, level: int, kind: str = "human") -> dict[str, object]:
        return {
            "signed_by": people[who].user_id,
            "level": level,
            "actor_kind": kind,
            "actor_id": str(people[who].user_id),
        }

    model = Model(frozenset({"marcus"}), 0, 0, 0, "a" * 64)
    fake = cast(Ladder, FakeLadder(people))
    clean = [row("ana", 1), row("hannah", 2), row("thomas", 5)]
    assert _broken(model, cast(list[asyncpg.Record], clean), fake) == []
    planted = [row("ana", 1), row("marcus", 2), row("thomas", 3), row("hannah", 5, "agent")]
    found = _broken(model, cast(list[asyncpg.Record], planted), fake)
    assert any(p.startswith("R-SO-3: preparer") for p in found)
    assert any(p.startswith("R-SO-1") for p in found)
    assert any("EQR signed L1-L4" in p for p in found)
    noted = Model(frozenset(), 1, 0, 0, "a" * 64)
    assert any(
        p.startswith("R-SO-4") for p in _broken(noted, cast(list[asyncpg.Record], clean), fake)
    )
