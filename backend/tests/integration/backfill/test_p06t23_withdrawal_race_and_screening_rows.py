# ac-test-author: ayushkbhatia
"""SPEC-319 AC-15 (§12 "withdraw racing an accept"), AC-21 and AC-28 at the database (P-06-T23,
TASK-1280): the two rules the database itself holds for P-06-T19 and P-06-T20.

- **Accept racing a withdrawal** (TASK-1172 left it here; ADR-162 §1, §2): the first commit wins
  and the other is refused, whichever order they arrive in; a version is never both accepted and
  withdrawn, and an accepted version's key is retained, never destroyed.
- **Screening rows** (AC-21, AC-28; DEC-48, DEC-324): every 0010 rule still holds for `version`
  rows (an agent's proposal on its own run's version: insert-only, once per run, `action`,
  `confidence` and `rationale` in range, `created_by_kind` the database's and always `agent`, no
  person or system may write one); a `request_batch` row is code's (`system`), each supersedes
  the item's previous row with `batch_no + 1`, no row is updated or deleted, and an agent or a
  person may write none. A review decision may name only a `version` row.

Boundary: the app role through the kernel's unit of work (`uow`), so the session carries the
tenant and the actor GUCs as every app write does; seeding as the superuser (`Seeder`). Expected
refusals are the database's: `insufficient_privilege` (42501) or a constraint (23xxx).
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass
from typing import Final, cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow

from .support import Person, Seeder, Site

pytestmark = pytest.mark.asyncio

PRIVILEGE: Final = "42501"
# 23502 not null, 23503 foreign key, 23505 unique, 23514 check
CONSTRAINT: Final = ("23502", "23503", "23505", "23514")


def _sqlstate(exc: BaseException) -> str:
    orig = getattr(exc, "orig", None)
    for candidate in (orig, getattr(orig, "__cause__", None), exc.__cause__):
        code = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if code:
            return str(code)
    return ""


async def _write(
    ctx: TenantContext,
    sql: str,
    params: Mapping[str, object],
    *,
    between: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """One app write in a unit of work as `ctx`; `between` runs after the statement and before
    the commit (to hold the transaction open while another arrives)."""
    async with uow(ctx) as tx:
        await tx.session.execute(text(sql), dict(params))
        if between is not None:
            await between()
        tx.record("evidence_version.probed", target=Target("tenant", ctx.tenant_id))


async def _refused(ctx: TenantContext, sql: str, params: Mapping[str, object]) -> str:
    """The SQLSTATE the database refuses the write with (the test fails if it is written)."""
    with pytest.raises(DBAPIError) as caught:
        await _write(ctx, sql, params)
    return _sqlstate(caught.value)


def _human(who: Person) -> TenantContext:
    return TenantContext(who.tenant_id, "human", str(who.user_id))


def _agent(w: World) -> TenantContext:
    """The screener, acting for the manager who started its run (Q-02-T16)."""
    return TenantContext(w.tenant, "agent", "evidence.screener", w.manager.user_id)


def _system(firm: uuid.UUID) -> TenantContext:
    return TenantContext(firm, "system", "evidence.screening_aggregate")


# --- the world ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class World:
    seed: Seeder
    site: Site
    manager: Person
    client: Person

    @property
    def tenant(self) -> uuid.UUID:
        return self.site.tenant_id

    async def client_upload(self) -> uuid.UUID:
        """A client's detached-key upload on the site's item (ADR-162 §5), with its key row,
        fulfilling the item; never accepted."""
        version = uuid.uuid4()
        evidence = await self.seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Bank statement', 'human', $3) RETURNING id",
            self.tenant,
            self.site.engagement_id,
            str(self.client.user_id),
        )
        await self.seed.run(
            "INSERT INTO evidence_versions (id, tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method, storage_mode) VALUES ($1, $2, $3, $4, 1, $5, $6, 'v1', 10, "
            "'application/pdf', 'client_upload', 'uploaded', 'detached_key')",
            version,
            self.tenant,
            self.site.engagement_id,
            evidence,
            hashlib.sha256(version.bytes).hexdigest(),
            f"tenants/{self.tenant}/v/{version}",
        )
        await self.seed.run(
            "INSERT INTO evidence_object_keys (tenant_id, evidence_version_id, key_id, "
            "wrapped_key) VALUES ($1, $2, 'test-kek', $3)",
            self.tenant,
            version,
            uuid.uuid4().bytes * 2,
        )
        await self.seed.run(
            "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
            "evidence_version_id, created_by_kind, created_by_id) "
            "VALUES ($1, $2, $3, $4, 'human', $5)",
            self.tenant,
            self.site.engagement_id,
            self.site.item_id,
            version,
            str(self.client.user_id),
        )
        return version

    async def run(self, version: uuid.UUID) -> uuid.UUID:
        """A completed screener run on `version`."""
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
                "evidence_version_id, initiator_user_id, task_scope, status, finished_at) "
                "VALUES ($1, 'evidence.screener', 1, $2, $3, $4, ARRAY['evidence.read'], "
                "'completed', now()) RETURNING id",
                self.tenant,
                self.site.engagement_id,
                version,
                self.manager.user_id,
            ),
        )


@pytest.fixture
async def w(seed: Seeder) -> World:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Granite")
    manager = await seed.person(tenant)
    await seed.member(site, manager, "manager")
    client = await seed.client_contact(site, "client_contributor")
    return World(seed, site, manager, client)


# --- accept racing a withdrawal (SPEC-319 §12, AC-15) -----------------------------------------

_WITHDRAW: Final = (
    "INSERT INTO evidence_withdrawals (tenant_id, evidence_version_id, engagement_id, "
    "request_item_id, withdrawn_by_user_id, withdrawn_at, erase_after) VALUES (:tenant, "
    ":version, :engagement, :item, :who, now(), now() + interval '30 days')"
)
_ACCEPT: Final = (
    "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
    "request_item_id, decision, corrects_proposal, actor_kind, actor_id) VALUES (:tenant, "
    ":engagement, :version, :item, 'accept', false, 'human', :who)"
)


def _withdraw_params(w: World, version: uuid.UUID) -> dict[str, object]:
    return {
        "tenant": w.tenant,
        "version": version,
        "engagement": w.site.engagement_id,
        "item": w.site.item_id,
        "who": w.client.user_id,
    }


def _accept_params(w: World, version: uuid.UUID) -> dict[str, object]:
    return {
        "tenant": w.tenant,
        "version": version,
        "engagement": w.site.engagement_id,
        "item": w.site.item_id,
        "who": str(w.manager.user_id),
    }


async def _outcome(w: World, version: uuid.UUID) -> tuple[int, int, bool]:
    """(withdrawal rows, accept rows, key retained) for the version."""
    withdrawn = await w.seed.value(
        "SELECT count(*) FROM evidence_withdrawals WHERE tenant_id = $1 "
        "AND evidence_version_id = $2",
        w.tenant,
        version,
    )
    accepted = await w.seed.value(
        "SELECT count(*) FROM review_decisions WHERE tenant_id = $1 "
        "AND evidence_version_id = $2 AND decision = 'accept'",
        w.tenant,
        version,
    )
    retained = await w.seed.value(
        "SELECT retained_at IS NOT NULL FROM evidence_object_keys WHERE tenant_id = $1 "
        "AND evidence_version_id = $2",
        w.tenant,
        version,
    )
    return cast(int, withdrawn), cast(int, accepted), bool(retained)


async def _second_waits(
    first: Callable[[Callable[[], Awaitable[None]]], Coroutine[object, object, None]],
    second: Callable[[], Coroutine[object, object, None]],
) -> BaseException | None:
    """`first` writes and holds its transaction open; `second` starts and must wait on it; then
    `first` commits. Returns what `second` raised (None if it committed)."""
    written = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        written.set()
        await release.wait()

    holder = asyncio.create_task(first(hold))
    await written.wait()
    waiter = asyncio.create_task(second())
    await asyncio.sleep(0.5)
    assert not waiter.done(), "the second write waits for the first one's lock"
    release.set()
    await holder
    try:
        await waiter
    except DBAPIError as exc:
        return exc
    return None


async def test_ac15_a_withdrawal_committed_first_refuses_the_racing_accept(w: World) -> None:
    version = await w.client_upload()
    refused = await _second_waits(
        lambda hold: _write(
            _human(w.client), _WITHDRAW, _withdraw_params(w, version), between=hold
        ),
        lambda: _write(_human(w.manager), _ACCEPT, _accept_params(w, version)),
    )
    assert refused is not None, "an accept of a withdrawn version is refused"
    assert _sqlstate(refused) in CONSTRAINT
    assert "evidence_withdrawn" in str(refused)
    assert await _outcome(w, version) == (1, 0, False)


async def test_ac15_an_accept_committed_first_refuses_the_racing_withdrawal(w: World) -> None:
    version = await w.client_upload()
    refused = await _second_waits(
        lambda hold: _write(_human(w.manager), _ACCEPT, _accept_params(w, version), between=hold),
        lambda: _write(_human(w.client), _WITHDRAW, _withdraw_params(w, version)),
    )
    assert refused is not None, "accepted evidence is never withdrawn"
    assert _sqlstate(refused) in CONSTRAINT
    assert "evidence_accepted" in str(refused)
    assert await _outcome(w, version) == (0, 1, True)


async def test_ac15_unordered_races_never_leave_a_version_accepted_and_withdrawn(
    w: World,
) -> None:
    for _ in range(6):
        version = await w.client_upload()
        results = await asyncio.gather(
            _write(_human(w.client), _WITHDRAW, _withdraw_params(w, version)),
            _write(_human(w.manager), _ACCEPT, _accept_params(w, version)),
            return_exceptions=True,
        )
        failures = [r for r in results if isinstance(r, BaseException)]
        assert len(failures) == 1, results
        assert isinstance(failures[0], DBAPIError) and _sqlstate(failures[0]) in CONSTRAINT
        withdrawn, accepted, retained = await _outcome(w, version)
        assert (withdrawn, accepted) in ((1, 0), (0, 1))
        assert retained == bool(accepted)


async def test_ac15_a_retained_key_is_never_cleared_by_the_app(w: World) -> None:
    version = await w.client_upload()
    await _write(_human(w.manager), _ACCEPT, _accept_params(w, version))
    sql = (
        "UPDATE evidence_object_keys SET retained_at = NULL WHERE tenant_id = :tenant "
        "AND evidence_version_id = :version"
    )
    state = await _refused(_human(w.manager), sql, {"tenant": w.tenant, "version": version})
    assert state == PRIVILEGE
    assert (await _outcome(w, version))[2] is True


async def test_ac15_a_withdrawal_is_the_sessions_own_persons(w: World) -> None:
    version = await w.client_upload()
    params = _withdraw_params(w, version)
    # Someone else's name on it, an agent, the system: all refused (INV-1, ADR-162).
    assert await _refused(_human(w.manager), _WITHDRAW, params) == PRIVILEGE
    assert await _refused(_agent(w), _WITHDRAW, params) == PRIVILEGE
    assert await _refused(_system(w.tenant), _WITHDRAW, params) == PRIVILEGE
    assert await _outcome(w, version) == (0, 0, False)


async def test_ac15_an_agent_or_the_system_never_accepts(w: World) -> None:
    version = await w.client_upload()
    for ctx, kind in ((_agent(w), "agent"), (_system(w.tenant), "system")):
        params = {**_accept_params(w, version), "who": ctx.actor_id}
        sql = _ACCEPT.replace("'human'", f"'{kind}'")
        with pytest.raises(DBAPIError):
            await _write(ctx, sql, params)
    assert await _outcome(w, version) == (0, 0, False)


# --- screening_results: `version` rows keep every 0010 rule (AC-21) ---------------------------

_VERSION_ROW: Final = (
    "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
    "agent_run_id, action, confidence, rationale, citations, unverified) VALUES (:tenant, "
    ":engagement, :version, :run, :action, :confidence, :rationale, '[]'::jsonb, '[]'::jsonb)"
)


def _version_row(w: World, run: uuid.UUID, **overrides: object) -> dict[str, object]:
    return {
        "tenant": w.tenant,
        "engagement": w.site.engagement_id,
        "version": w.site.version_id,
        "run": run,
        "action": "needs_revision",
        "confidence": 0.5,
        "rationale": "Totals differ from the request",
        **overrides,
    }


async def _version_rows(w: World) -> list[dict[str, object]]:
    rows = await w.seed.rows(
        "SELECT id, subject_kind, created_by_kind, batch_no FROM screening_results "
        "WHERE tenant_id = $1 AND subject_kind = 'version'",
        w.tenant,
    )
    return [dict(r) for r in rows]


async def test_ac21_an_agents_proposal_on_its_runs_version_is_written_as_the_agents(
    w: World,
) -> None:
    run = await w.run(w.site.version_id)
    await _write(_agent(w), _VERSION_ROW, _version_row(w, run))
    rows = await _version_rows(w)
    assert len(rows) == 1
    assert rows[0]["created_by_kind"] == "agent" and rows[0]["batch_no"] is None


async def test_ac21_a_version_row_is_written_once_per_run(w: World) -> None:
    run = await w.run(w.site.version_id)
    await _write(_agent(w), _VERSION_ROW, _version_row(w, run))
    assert await _refused(_agent(w), _VERSION_ROW, _version_row(w, run)) in CONSTRAINT


async def test_ac21_a_version_row_is_about_its_own_runs_version(w: World) -> None:
    other = await w.client_upload()
    run = await w.run(other)
    state = await _refused(_agent(w), _VERSION_ROW, _version_row(w, run))
    assert state in CONSTRAINT


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "accept"},
        {"action": None},
        {"confidence": 1.5},
        {"confidence": -0.1},
        {"confidence": None},
        {"rationale": ""},
        {"rationale": "x" * 2001},
        {"rationale": None},
    ],
    ids=lambda o: "-".join(f"{k}={str(v)[:8]}" for k, v in o.items()),
)
async def test_ac21_a_version_rows_action_confidence_and_rationale_stay_in_range(
    w: World, overrides: dict[str, object]
) -> None:
    run = await w.run(w.site.version_id)
    state = await _refused(_agent(w), _VERSION_ROW, _version_row(w, run, **overrides))
    assert state in CONSTRAINT
    assert await _version_rows(w) == []


async def test_ac21_the_app_never_says_who_created_a_screening_result(w: World) -> None:
    run = await w.run(w.site.version_id)
    sql = _VERSION_ROW.replace("unverified)", "unverified, created_by_kind)").replace(
        "'[]'::jsonb)", "'[]'::jsonb, 'agent')"
    )
    assert sql != _VERSION_ROW
    assert await _refused(_agent(w), sql, _version_row(w, run)) == PRIVILEGE


@pytest.mark.parametrize("actor", ["human", "system"])
async def test_ac21_no_person_or_system_writes_an_agents_proposal(w: World, actor: str) -> None:
    run = await w.run(w.site.version_id)
    ctx = _human(w.manager) if actor == "human" else _system(w.tenant)
    assert await _refused(ctx, _VERSION_ROW, _version_row(w, run)) == PRIVILEGE
    assert await _version_rows(w) == []


async def test_ac21_a_version_row_carries_no_aggregate_columns(w: World) -> None:
    run = await w.run(w.site.version_id)
    sql = _VERSION_ROW.replace("unverified)", "unverified, batch_no)").replace(
        "'[]'::jsonb)", "'[]'::jsonb, 1)"
    )
    assert await _refused(_agent(w), sql, _version_row(w, run)) in CONSTRAINT


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE screening_results SET rationale = 'changed' WHERE tenant_id = :tenant",
        "UPDATE screening_results SET action = 'ready_for_review' WHERE tenant_id = :tenant",
        "DELETE FROM screening_results WHERE tenant_id = :tenant",
    ],
)
@pytest.mark.parametrize("actor", ["agent", "system", "human"])
async def test_ac21_a_version_row_is_never_updated_or_deleted(
    w: World, sql: str, actor: str
) -> None:
    run = await w.run(w.site.version_id)
    await _write(_agent(w), _VERSION_ROW, _version_row(w, run))
    ctx = {"agent": _agent(w), "system": _system(w.tenant), "human": _human(w.manager)}
    assert await _refused(ctx[actor], sql, {"tenant": w.tenant}) == PRIVILEGE
    row = await w.seed.rows(
        "SELECT action, rationale FROM screening_results WHERE tenant_id = $1", w.tenant
    )
    assert [tuple(r.values()) for r in row] == [
        ("needs_revision", "Totals differ from the request")
    ]


# --- screening_results: `request_batch` rows are code's, superseded, never updated (AC-21) ----

_BATCH_ROW: Final = (
    "INSERT INTO screening_results (id, tenant_id, engagement_id, subject_kind, "
    "request_item_id, batch_no, supersedes_id, source_result_ids, source_review_ids, "
    "evidence_version_ids, checks, file_flags, verdict, citations, unverified) VALUES (:id, "
    ":tenant, :engagement, 'request_batch', :item, :batch_no, :supersedes, "
    "CAST(:results AS uuid[]), CAST(:reviews AS uuid[]), CAST(:versions AS uuid[]), "
    "'[]'::jsonb, '[]'::jsonb, :verdict, '[]'::jsonb, '[]'::jsonb)"
)


def _batch(
    w: World, batch_no: int, supersedes: uuid.UUID | None, **overrides: object
) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "tenant": w.tenant,
        "engagement": w.site.engagement_id,
        "item": w.site.item_id,
        "batch_no": batch_no,
        "supersedes": supersedes,
        "results": [],
        "reviews": [],
        "versions": [str(w.site.version_id)],
        "verdict": "not_screened",
        **overrides,
    }


async def _batches(w: World) -> list[tuple[object, ...]]:
    rows = await w.seed.rows(
        "SELECT id, batch_no, supersedes_id, created_by_kind, verdict FROM screening_results "
        "WHERE tenant_id = $1 AND subject_kind = 'request_batch' ORDER BY batch_no",
        w.tenant,
    )
    return [tuple(r.values()) for r in rows]


async def _chain(w: World, n: int) -> list[uuid.UUID]:
    made: list[uuid.UUID] = []
    for batch_no in range(1, n + 1):
        params = _batch(w, batch_no, made[-1] if made else None)
        await _write(_system(w.tenant), _BATCH_ROW, params)
        made.append(cast(uuid.UUID, params["id"]))
    return made


async def test_ac21_code_composes_a_chain_each_superseding_the_last(w: World) -> None:
    first, second, third = await _chain(w, 3)
    assert await _batches(w) == [
        (first, 1, None, "system", "not_screened"),
        (second, 2, first, "system", "not_screened"),
        (third, 3, second, "system", "not_screened"),
    ]


@pytest.mark.parametrize("actor", ["agent", "human"])
async def test_ac21_an_agent_or_a_person_never_writes_an_aggregate(w: World, actor: str) -> None:
    ctx = _agent(w) if actor == "agent" else _human(w.manager)
    assert await _refused(ctx, _BATCH_ROW, _batch(w, 1, None)) == PRIVILEGE
    assert await _batches(w) == []


async def test_ac21_an_aggregate_out_of_its_chain_is_refused(w: World) -> None:
    first, second = await _chain(w, 2)
    system = _system(w.tenant)
    # Superseding an older row, repeating a number, skipping one, or a second first row.
    for params in (
        _batch(w, 3, first),
        _batch(w, 2, first),
        _batch(w, 4, second),
        _batch(w, 1, None),
        _batch(w, 3, None),
    ):
        assert await _refused(system, _BATCH_ROW, params) in CONSTRAINT, params
    assert [b[0] for b in await _batches(w)] == [first, second]


async def test_ac21_an_aggregate_carries_no_run_action_confidence_or_rationale(
    w: World,
) -> None:
    run = await w.run(w.site.version_id)
    sql = _BATCH_ROW.replace("unverified)", "unverified, agent_run_id)").replace(
        "'[]'::jsonb, '[]'::jsonb)", "'[]'::jsonb, '[]'::jsonb, :run)"
    )
    params = {**_batch(w, 1, None), "run": run}
    assert await _refused(_system(w.tenant), sql, params) in CONSTRAINT


async def test_ac21_an_aggregate_needs_its_composition(w: World) -> None:
    assert (
        await _refused(_system(w.tenant), _BATCH_ROW, _batch(w, 1, None, verdict=None))
        in CONSTRAINT
    )
    assert (
        await _refused(_system(w.tenant), _BATCH_ROW, _batch(w, 1, None, verdict="maybe"))
        in CONSTRAINT
    )


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE screening_results SET verdict = 'passed' WHERE tenant_id = :tenant",
        "UPDATE screening_results SET supersedes_id = NULL WHERE tenant_id = :tenant",
        "DELETE FROM screening_results WHERE tenant_id = :tenant",
    ],
)
async def test_ac21_no_aggregate_is_ever_updated_or_deleted(w: World, sql: str) -> None:
    made = await _chain(w, 2)
    assert await _refused(_system(w.tenant), sql, {"tenant": w.tenant}) == PRIVILEGE
    assert [b[0] for b in await _batches(w)] == made
    assert {b[4] for b in await _batches(w)} == {"not_screened"}


async def test_ac21_the_app_cannot_name_an_aggregate_the_agents(w: World) -> None:
    sql = _BATCH_ROW.replace("unverified)", "unverified, created_by_kind)").replace(
        "'[]'::jsonb, '[]'::jsonb)", "'[]'::jsonb, '[]'::jsonb, 'agent')"
    )
    assert await _refused(_system(w.tenant), sql, _batch(w, 1, None)) == PRIVILEGE


# --- AC-28: a review decision names only a `version` row --------------------------------------


async def test_ac28_a_review_decision_may_not_name_an_aggregate(w: World) -> None:
    (aggregate,) = await _chain(w, 1)
    await w.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        w.tenant,
        w.site.engagement_id,
        w.site.item_id,
        w.site.version_id,
    )
    sql = _ACCEPT.replace("corrects_proposal,", "corrects_proposal, screening_result_id,").replace(
        "false, 'human'", "false, :screening, 'human'"
    )
    params = {**_accept_params(w, w.site.version_id), "screening": aggregate}
    assert await _refused(_human(w.manager), sql, params) in CONSTRAINT


async def test_ac28_a_review_decision_may_name_the_agents_version_row(w: World) -> None:
    run = await w.run(w.site.version_id)
    await _write(_agent(w), _VERSION_ROW, _version_row(w, run))
    proposal = (await _version_rows(w))[0]["id"]
    await w.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        w.tenant,
        w.site.engagement_id,
        w.site.item_id,
        w.site.version_id,
    )
    sql = _ACCEPT.replace("corrects_proposal,", "corrects_proposal, screening_result_id,").replace(
        "false, 'human'", "false, :screening, 'human'"
    )
    params = {**_accept_params(w, w.site.version_id), "screening": proposal}
    await _write(_human(w.manager), sql, params)
