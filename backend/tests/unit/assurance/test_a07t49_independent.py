"""Independent AC and property tests for the release and the archive (A-07-T49; ADR-078; A-07 F6,
F7; SPEC-644; DEC-3411).

Written apart from A-07-T30, T31, T36, T37 and T42, from the epic and the contract only:

- G8: a release is refused at every step (the request, the workflow's re-check and the one unit
  of work) unless G5, G6 and G7 hold; a replay with the same key answers the stored release; a
  failure inside the unit of work escapes it (so the kernel rolls back) and records nothing.
- F7: the archive's nine computed items; the lock refused at 8 of 9 and on a checklist the
  locker did not see; the 60-day clock; the five-year retention floor.
- The seal: byte-identical whatever the read order, moved by any leaf; the manifest in
  COMPLIANCE until the floor and the evidence in GOVERNANCE until retention.
- An addition after lock is approved only by the engagement partner, never by the person who
  added it; the agent and the system never release, lock or approve an addition.

Row acceptance: "Tests written in ayushkbhatia's session fail if a release can be recorded with
any gate unmet or if a locked row changes." The locked-row half runs against Postgres in
`tests/integration/test_a07t49_locked_rows.py`.
"""

from __future__ import annotations

import hashlib
import inspect
import random
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.assurance import archive_additions as aa
from abacus.modules.assurance import archive_gate as ag
from abacus.modules.assurance import archive_lock as al
from abacus.modules.assurance import clocks
from abacus.modules.assurance import release as rel
from abacus.modules.assurance.archive_records import FLOOR_YEARS, five_year_floor
from abacus.modules.assurance.archive_seal import EmptyBinder, Leaf, build, canonical, merkle_root
from abacus.modules.assurance.record_auth import RecordNeedsMfa
from abacus.modules.identity.api import AuthContext, Forbidden

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MATRIX = cast(
    dict[str, dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text())[
        "actions"
    ],
)
FRESH_MFA = {
    entry["action"]
    for entry in cast(
        list[dict[str, str]],
        yaml.safe_load((ROOT / "docs/architecture/fresh-mfa-actions.yaml").read_text())["actions"],
    )
}
M0669 = (BACKEND / "migrations/versions/0669_evidence_archive.py").read_text()

WORK_ITEM, ENGAGEMENT, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
MARGARET = uuid.uuid4()  # the engagement partner
RELEASED_ON = date(2026, 10, 9)  # the Northwind EBP release (AUD-24 d)
HUMAN_ONLY = ("report.release", "archive.lock", "archive_addition.approve")


def _ctx(
    kind: ActorKind = "human", *, user: uuid.UUID = MARGARET, mfa_minutes_ago: int | None = 1
) -> AuthContext:
    tenant = TenantContext(uuid.uuid4(), kind, str(user))
    mfa = (
        None if mfa_minutes_ago is None else datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago)
    )
    return AuthContext(tenant, user, uuid.uuid4(), None, mfa)


def _gates(g5: bool = True, g6: bool = True, g7: bool = True) -> tuple[rel.GateCard, ...]:
    return (
        rel.GateCard("G5", g5, True, () if g5 else ("unsigned:B-1",)),
        rel.GateCard("G6", g6, True, () if g6 else ("eqr_not_concurred",)),
        rel.GateCard("G7", g7, True, () if g7 else ("rep_letter_not_signed",)),
    )


def _snap(**over: object) -> rel.ReleaseSnapshot:
    base: dict[str, Any] = {  # Any: the dataclass's mixed field types
        "work_item_id": WORK_ITEM,
        "engagement_id": ENGAGEMENT,
        "gates": _gates(),
        "also_required": tuple(rel.AlsoRequired(k, True) for k in rel.ALSO_REQUIRED_KEYS),
        "report_id": uuid.uuid4(),
        "report_version_id": VERSION,
        "report_version_hash": "b" * 64,
        "report_status": "approved",
        "report_approved": True,
        "report_date": RELEASED_ON,
        "city": "Chicago",
    }
    base.update(over)
    return rel.ReleaseSnapshot(**base)


def _request(gate_hash: str) -> rel.ReleaseRequest:
    return rel.ReleaseRequest(
        tenant_id=str(uuid.uuid4()),
        work_item_id=str(WORK_ITEM),
        engagement_id=str(ENGAGEMENT),
        grant_id=str(uuid.uuid4()),
        released_by=str(MARGARET),
        report_version_id=str(VERSION),
        draft_document_id=str(uuid.uuid4()),
        draft_hash="c" * 64,
        gate_hash=gate_hash,
        idempotency_key="release-1",
    )


@dataclass
class _Unit:
    """A unit of work double: what was recorded and how the block ended."""

    entered: int = 0
    recorded: list[str] = field(default_factory=list[str])
    escaped: list[BaseException] = field(default_factory=list[BaseException])
    session: object = None

    def record(self, action: str, **_k: object) -> None:
        self.recorded.append(action)

    def emit(self, _event: object) -> None:
        self.recorded.append("emit")


def _unit_of_work(unit: _Unit) -> object:
    @asynccontextmanager
    async def factory(_t: TenantContext) -> AsyncGenerator[_Unit]:
        unit.entered += 1
        try:
            yield unit
        except BaseException as exc:
            unit.escaped.append(exc)
            raise

    return factory


async def _none(*_a: object, **_k: object) -> None:
    return None


# =================================================================================================
# G8: no release with any gate unmet
# =================================================================================================

GATE_FLAGS = st.tuples(st.booleans(), st.booleans(), st.booleans()).filter(lambda f: not all(f))


@given(GATE_FLAGS)
def test_any_unmet_gate_is_a_blocker_and_names_itself(flags: tuple[bool, bool, bool]) -> None:
    snap = _snap(gates=_gates(*flags))
    unmet = {g for g, met in zip(("G5", "G6", "G7"), flags, strict=True) if not met}
    assert set(snap.blockers) == unmet
    assert snap.sha256 != _snap().sha256  # the dialog's hash moves with any gate


def test_all_gates_met_and_everything_required_is_the_only_unblocked_snapshot() -> None:
    assert _snap().blockers == ()
    assert _snap(report_approved=False).blockers == ("report_not_approved",)
    for key in rel.ALSO_REQUIRED_KEYS:
        items = tuple(rel.AlsoRequired(k, k != key) for k in rel.ALSO_REQUIRED_KEYS)
        assert _snap(also_required=items).blockers == (f"also_required:{key}",)


def _request_world(
    monkeypatch: pytest.MonkeyPatch, unit: _Unit, snap: rel.ReleaseSnapshot, done: object = None
) -> None:
    async def item(_t: TenantContext, _w: uuid.UUID) -> object:
        return SimpleNamespace(engagement_id=ENGAGEMENT)

    async def ref(_tx: object, _e: uuid.UUID) -> object:
        from abacus.modules.identity.api import Resource

        return SimpleNamespace(
            resource=lambda: Resource(uuid.uuid4(), archived=False, engagement_id=ENGAGEMENT)
        )

    async def in_app(_t: TenantContext) -> str:
        return "in_app"

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return snap

    async def released(_t: TenantContext, _w: uuid.UUID) -> object:
        return done

    monkeypatch.setattr(rel, "assurance_item", item)
    monkeypatch.setattr(rel, "lock_ref", ref)
    monkeypatch.setattr(rel, "uow", _unit_of_work(unit))
    monkeypatch.setattr(rel, "authorise_record", _none)
    monkeypatch.setattr(rel, "release_mode", in_app)
    monkeypatch.setattr(rel, "snapshot", current)
    monkeypatch.setattr(rel, "released", released)
    monkeypatch.setattr(rel, "lock_assurance_item", _none)


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [(False, True, True), (True, False, True), (True, True, False)])
async def test_the_request_is_refused_when_a_gate_is_unmet(
    monkeypatch: pytest.MonkeyPatch, flags: tuple[bool, bool, bool]
) -> None:
    unit = _Unit()
    snap = _snap(gates=_gates(*flags))
    _request_world(monkeypatch, unit, snap)
    with pytest.raises(rel.GatesNotMet):
        await rel.request_release(_ctx(), WORK_ITEM, snap.sha256, "release-1")
    assert unit.recorded == []


@pytest.mark.asyncio
async def test_the_workflow_rechecks_the_gates_after_consuming_the_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _snap()
    later = _snap(gates=_gates(g6=False))  # G6 fell between the dialog and the workflow

    async def consumed(*_a: object) -> bool:
        return True

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return later

    monkeypatch.setattr("abacus.modules.identity.api.consume_grant", consumed)
    monkeypatch.setattr(rel, "snapshot", current)
    with pytest.raises(rel.GatesNotMet):
        await rel.consume_and_render(_request(seen.sha256))


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [(False, True, True), (True, False, True), (True, True, False)])
async def test_the_one_unit_of_work_never_opens_with_a_gate_unmet(
    monkeypatch: pytest.MonkeyPatch, flags: tuple[bool, bool, bool]
) -> None:
    unit = _Unit()
    seen = _snap()
    later = _snap(gates=_gates(*flags))

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return later

    monkeypatch.setattr(rel, "snapshot", current)
    monkeypatch.setattr(rel, "uow", _unit_of_work(unit))
    with pytest.raises(rel.GatesNotMet):
        await rel.record_in_app_release(
            _request(seen.sha256), uuid.uuid4(), uuid.uuid4(), "d" * 64, 4
        )
    assert unit.entered == 0
    assert unit.recorded == []


@pytest.mark.asyncio
async def test_a_changed_snapshot_with_gates_met_is_still_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _Unit()
    later = _snap(report_version_hash="e" * 64)  # all met, but not what the EP saw

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return later

    monkeypatch.setattr(rel, "snapshot", current)
    monkeypatch.setattr(rel, "uow", _unit_of_work(unit))
    with pytest.raises(rel.ContentChanged):
        await rel.record_in_app_release(
            _request(_snap().sha256), uuid.uuid4(), uuid.uuid4(), "d" * 64, 4
        )
    assert unit.entered == 0


@pytest.mark.asyncio
async def test_a_failure_inside_the_unit_escapes_it_and_nothing_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _Unit()
    snap = _snap()

    async def current(_t: TenantContext, _w: uuid.UUID) -> rel.ReleaseSnapshot:
        return snap

    async def hold(_t: TenantContext, _e: uuid.UUID) -> object:
        return SimpleNamespace(client_id=uuid.uuid4())

    async def audiences(_t: TenantContext, _e: uuid.UUID) -> tuple[object, ...]:
        return ()

    async def publish(*_a: object, **_k: object) -> object:
        raise RuntimeError("deliverable store down")

    monkeypatch.setattr(rel, "snapshot", current)
    monkeypatch.setattr(rel, "engagement_hold_facts", hold)
    monkeypatch.setattr(rel, "_audiences", audiences)
    monkeypatch.setattr(rel, "lock_assurance_item", _none)
    monkeypatch.setattr(rel, "released", _none)
    monkeypatch.setattr(rel, "uow", _unit_of_work(unit))
    monkeypatch.setattr("abacus.modules.reporting.api.publish_deliverable", publish)
    with pytest.raises(RuntimeError):
        await rel.record_in_app_release(
            _request(snap.sha256), uuid.uuid4(), uuid.uuid4(), "d" * 64, 4
        )
    assert unit.entered == 1
    assert len(unit.escaped) == 1  # the kernel's unit rolls back on an escaping exception
    assert unit.recorded == []


@pytest.mark.asyncio
async def test_a_replay_with_the_same_key_answers_the_stored_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _Unit()
    done = SimpleNamespace(release_id=uuid.uuid4(), idempotency_key="release-1")
    _request_world(monkeypatch, unit, _snap(), done)
    answered = await rel.request_release(_ctx(), WORK_ITEM, _snap().sha256, "release-1")
    assert answered is done
    assert unit.recorded == ["report.release_replayed"]  # no grant, no second release


@pytest.mark.asyncio
async def test_a_second_release_under_another_key_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _Unit()
    done = SimpleNamespace(release_id=uuid.uuid4(), idempotency_key="release-1")
    _request_world(monkeypatch, unit, _snap(), done)
    with pytest.raises(rel.AlreadyReleased):
        await rel.request_release(_ctx(), WORK_ITEM, _snap().sha256, "release-2")
    assert unit.recorded == []


# =================================================================================================
# F7: the nine items, the 60-day clock and the five-year floor
# =================================================================================================

NINE = (
    "workpapers_signed",
    "review_notes_resolved",
    "versions_handled",
    "binder_index_complete",
    "final_report_filed",
    "governance_filed",
    "independence_filed",
    "run_logs_packaged",
    "type_filing",
)


def _state(done: tuple[bool, ...], status: str = "assembling") -> ag.ArchiveState:
    archive = SimpleNamespace(id=uuid.uuid4(), engagement_id=ENGAGEMENT, status=status)
    items = tuple(ag.ArchiveItem(k, k, d) for k, d in zip(NINE, done, strict=True))
    return ag.ArchiveState(cast(Any, archive), items, (), 47)  # Any: a row double


def test_the_checklist_is_the_nine_items_in_order() -> None:
    assert tuple(k for k, _ in ag.ARCHIVE_ITEMS) == NINE


@given(st.tuples(*[st.booleans()] * 9), st.integers(min_value=0, max_value=8))
def test_any_one_item_flipping_moves_the_checklist_hash(done: tuple[bool, ...], flip: int) -> None:
    other = tuple(not d if i == flip else d for i, d in enumerate(done))
    assert _state(done).checklist_sha256 != _state(other).checklist_sha256
    assert _state(done).done == sum(done)


def _lock_world(monkeypatch: pytest.MonkeyPatch, state: ag.ArchiveState, unit: _Unit) -> None:
    async def current(_t: TenantContext, _w: uuid.UUID) -> ag.ArchiveState:
        return state

    monkeypatch.setattr(ag, "archive_state", current)
    monkeypatch.setattr(al, "uow", _unit_of_work(unit))


@pytest.mark.asyncio
@pytest.mark.parametrize("open_item", range(9))
async def test_the_lock_is_refused_at_8_of_9(
    monkeypatch: pytest.MonkeyPatch, open_item: int
) -> None:
    unit = _Unit()
    state = _state(tuple(i != open_item for i in range(9)))
    _lock_world(monkeypatch, state, unit)
    with pytest.raises(al.ArchiveNotReady):
        await al.decide_lock(
            _ctx(), WORK_ITEM, then_roll_forward=False, seen_checklist_hash=state.checklist_sha256
        )
    assert unit.entered == 0


@pytest.mark.asyncio
async def test_the_lock_is_refused_on_a_checklist_the_locker_did_not_see(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _Unit()
    _lock_world(monkeypatch, _state((True,) * 9), unit)
    seen = _state((True,) * 8 + (False,)).checklist_sha256
    with pytest.raises(al.ChecklistChanged):
        await al.decide_lock(_ctx(), WORK_ITEM, then_roll_forward=False, seen_checklist_hash=seen)
    assert unit.entered == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["locking", "locked"])
async def test_a_locked_or_locking_archive_is_never_locked_again(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    unit = _Unit()
    state = _state((True,) * 9, status)
    _lock_world(monkeypatch, state, unit)
    with pytest.raises(al.AlreadyLocking):
        await al.decide_lock(
            _ctx(), WORK_ITEM, then_roll_forward=False, seen_checklist_hash=state.checklist_sha256
        )
    assert unit.entered == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [None, 40])
async def test_the_lock_needs_a_fresh_second_factor(
    monkeypatch: pytest.MonkeyPatch, mfa: int | None
) -> None:
    """DEC-3411: the contract's "human only, fresh MFA" (audit-completion.md) on the lock itself;
    before this row the decision stored the server's time when no factor was presented."""
    unit = _Unit()
    state = _state((True,) * 9)
    _lock_world(monkeypatch, state, unit)
    with pytest.raises(RecordNeedsMfa):
        await al.decide_lock(
            _ctx(mfa_minutes_ago=mfa),
            WORK_ITEM,
            then_roll_forward=False,
            seen_checklist_hash=state.checklist_sha256,
        )
    assert unit.entered == 0


@dataclass(frozen=True)
class _Row:
    key: str
    band: str
    state_provider: Any  # Any: an async provider double


@pytest.mark.asyncio
async def test_the_binder_is_always_a_to_h_and_a_failing_row_is_not_in_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def present(_t: TenantContext, _w: uuid.UUID) -> object:
        return object()

    async def down(_t: TenantContext, _w: uuid.UUID) -> object:
        raise RuntimeError("provider down")

    rows = [_Row("ebp_05", "fieldwork", present), _Row("going_concern", "completion", down)]

    async def runs(_t: TenantContext, _e: uuid.UUID) -> tuple[int, int]:
        return 4, 3

    async def zero(*_a: object) -> int:
        return 0

    async def nobody(*_a: object) -> list[tuple[uuid.UUID, str]]:
        return []

    monkeypatch.setattr("abacus.modules.assurance.sections.registered_sections", lambda: rows)
    monkeypatch.setattr("abacus.modules.agents.api.run_log_count", runs)
    monkeypatch.setattr("abacus.modules.evidence.api.source_document_count", zero)
    monkeypatch.setattr("abacus.modules.identity.api.team_of", nobody)
    tenant = TenantContext(uuid.uuid4(), "system", "t")
    binder = await ag.binder_sections(tenant, ENGAGEMENT, WORK_ITEM)
    assert [b.section for b in binder] == list("ABCDEFGH")
    assert [b.title for b in binder] == [ag.BINDER_TITLES[k] for k in "ABCDEFGH"]
    by = {b.section: b for b in binder}
    assert by["C"].workpapers == 1  # an EBP test paper files under Testing
    assert by["D"].workpapers == 0  # a provider that cannot answer is not counted
    assert by["G"].run_logs == 4


@given(st.lists(st.integers(min_value=0, max_value=40), min_size=8, max_size=8), st.data())
def test_the_binder_index_hash_moves_with_any_count(
    counts: list[int], data: st.DataObject
) -> None:
    from abacus.modules.assurance.archive_records import BinderSection, index_sha256

    def sections(values: list[int]) -> list[BinderSection]:
        return [
            BinderSection(k, ag.BINDER_TITLES[k], v, 0, 0)
            for k, v in zip("ABCDEFGH", values, strict=True)
        ]

    i = data.draw(st.integers(min_value=0, max_value=7))
    moved = [v + 1 if j == i else v for j, v in enumerate(counts)]
    assert index_sha256(sections(counts)) == index_sha256(sections(list(counts)))
    assert index_sha256(sections(counts)) != index_sha256(sections(moved))


# The clocks: AU-C 230's 60 days from the release date (the firm's business date).
CLOCK_GOLDENS = [
    (date(2026, 10, 9), date(2026, 10, 22), 47, "running"),  # AUD-25 "Archive in 47 days"
    (date(2026, 10, 9), date(2026, 11, 30), 8, "running"),
    (date(2026, 10, 9), date(2026, 12, 1), 7, "at_risk"),
    (date(2026, 10, 9), date(2026, 12, 7), 1, "at_risk"),
    (date(2026, 10, 9), date(2026, 12, 8), 0, "due_today"),
    (date(2026, 10, 9), date(2026, 12, 9), -1, "overdue"),
    (date(2024, 12, 31), date(2025, 3, 1), 0, "due_today"),  # across a non-leap February
    (date(2023, 12, 31), date(2024, 2, 29), 0, "due_today"),  # onto a leap day
]


@pytest.mark.parametrize(("released", "today", "left", "state"), CLOCK_GOLDENS)
def test_the_archive_clock_goldens(released: date, today: date, left: int, state: str) -> None:
    found = clocks.read("archive", released, today)
    assert (found.days_left, found.state) == (left, state)
    assert found.deadline == released + timedelta(days=60)


def test_a_locked_archive_stops_its_clock_even_overdue() -> None:
    assert clocks.read("archive", RELEASED_ON, date(2027, 1, 1), stopped=True).state == "stopped"


def test_the_release_timers_golden() -> None:
    assert [(t.kind, t.at, t.event) for t in clocks.timers(RELEASED_ON)] == [
        ("archive", date(2026, 12, 1), "deadline_risk"),
        ("archive", date(2026, 12, 8), "deadline"),
        ("au_c_265", date(2026, 12, 8), "deadline"),
        ("archive", date(2026, 12, 9), "overdue"),
        ("au_c_265", date(2026, 12, 9), "overdue"),
    ]


DAYS = st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31))


@given(DAYS, st.integers(min_value=-200, max_value=200))
def test_the_clock_state_follows_the_days_left(released: date, offset: int) -> None:
    today = released + timedelta(days=60 - offset)
    found = clocks.read("archive", released, today)
    assert found.days_left == offset
    expected = (
        "overdue"
        if offset < 0
        else "due_today"
        if offset == 0
        else "at_risk"
        if offset <= clocks.RISK_DAYS
        else "running"
    )
    assert found.state == expected


@given(DAYS)
def test_the_retention_floor_is_never_short_of_five_years(released: date) -> None:
    floor = five_year_floor(released)
    assert floor.year == released.year + FLOOR_YEARS
    assert (floor.month, floor.day) == (
        (released.month, released.day) if (released.month, released.day) != (2, 29) else (2, 28)
    )
    assert (floor - released).days >= 365 * FLOOR_YEARS  # five years, never fewer days


def test_the_floor_is_also_a_database_check() -> None:
    assert "retention_until >= (release_date + interval '5 years')::date" in M0669
    assert "GENERATED ALWAYS AS (release_date + 60) STORED" in M0669


# =================================================================================================
# The seal
# =================================================================================================

LEAVES = st.lists(
    st.builds(
        Leaf,
        st.sampled_from(["evidence_version", "row", "run_record"]),
        st.uuids().map(str),
        st.binary(min_size=1, max_size=8).map(lambda b: hashlib.sha256(b).hexdigest()),
    ),
    min_size=1,
    max_size=24,
    unique_by=lambda leaf: (leaf.kind, leaf.id),
)


def _manifest(leaves: list[Leaf]) -> bytes:
    return build(
        tenant_id="t",
        engagement_id="e",
        work_item_id="w",
        archive_id="a",
        release_id="r",
        release_date=RELEASED_ON,
        retention_until=date(2033, 10, 9),
        compliance_retain_until=five_year_floor(RELEASED_ON),
        leaves=leaves,
        audit_checkpoint_seq_to=1042,
        audit_checkpoint_root="f" * 64,
        checklist_sha256="0" * 64,
    ).body


@settings(max_examples=60)
@given(LEAVES, st.randoms(use_true_random=False))
def test_the_seal_is_byte_identical_whatever_the_read_order(
    leaves: list[Leaf],
    rnd: random.Random,
) -> None:
    shuffled = list(leaves)
    rnd.shuffle(shuffled)
    assert merkle_root(shuffled) == merkle_root(leaves)
    assert _manifest(shuffled) == _manifest(leaves)


@settings(max_examples=60)
@given(LEAVES, st.data())
def test_any_changed_leaf_moves_the_seal(leaves: list[Leaf], data: st.DataObject) -> None:
    i = data.draw(st.integers(min_value=0, max_value=len(leaves) - 1))
    changed = list(leaves)
    leaf = changed[i]
    changed[i] = Leaf(leaf.kind, leaf.id, hashlib.sha256(leaf.sha256.encode()).hexdigest())
    assert merkle_root(changed) != merkle_root(leaves)
    assert (
        hashlib.sha256(_manifest(changed)).digest() != hashlib.sha256(_manifest(leaves)).digest()
    )


def test_an_empty_binder_has_no_seal() -> None:
    with pytest.raises(EmptyBinder):
        merkle_root([])


@given(st.dictionaries(st.text(min_size=1, max_size=6), st.integers(), max_size=8))
def test_canonical_bytes_ignore_key_order(doc: dict[str, int]) -> None:
    reversed_doc = dict(reversed(list(doc.items())))
    assert canonical(doc) == canonical(reversed_doc)
    assert b" " not in canonical({k: v for k, v in doc.items() if " " not in k})


def test_the_manifest_holds_no_floats() -> None:
    with pytest.raises(TypeError):
        canonical({"amount": 1.5})


def test_the_seal_is_the_sha256_of_the_manifest_body() -> None:
    leaves = [Leaf("evidence_version", "v1", "1" * 64), Leaf("row", "r1", "2" * 64)]
    manifest = build(
        tenant_id="t",
        engagement_id="e",
        work_item_id="w",
        archive_id="a",
        release_id="r",
        release_date=RELEASED_ON,
        retention_until=date(2033, 10, 9),
        compliance_retain_until=date(2031, 10, 9),
        leaves=leaves,
        audit_checkpoint_seq_to=None,
        audit_checkpoint_root=None,
        checklist_sha256="0" * 64,
    )
    assert manifest.sha256 == hashlib.sha256(manifest.body).hexdigest()
    assert (manifest.evidence_leaf_count, manifest.row_leaf_count) == (1, 1)


def test_the_manifest_is_compliance_until_the_floor_and_evidence_governance_until_retention() -> (
    None
):
    from abacus.modules.evidence import records, retention_anchor

    seal = inspect.getsource(al.seal_activity)
    assert "compliance_until = five_year_floor(release_date)" in seal
    assert "_end_of(compliance_until)" in seal
    extend = inspect.getsource(al.extend_evidence_activity)
    assert "_end_of(row.retention_until)" in extend
    assert 'ObjectLockMode="COMPLIANCE"' in inspect.getsource(records.put_record)
    assert "GOVERNANCE" in inspect.getsource(retention_anchor.extend_versions_until)
    # The day's end in the firm's zone: never a day short.
    end = al._end_of(date(2031, 10, 9))  # pyright: ignore[reportPrivateUsage]  # the helper under test
    assert (end.date(), end.hour, end.minute) == (date(2031, 10, 9), 23, 59)


# =================================================================================================
# Additions and who may act
# =================================================================================================


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_the_agent_and_the_system_never_release_lock_or_approve(action: str) -> None:
    assert MATRIX[action]["agent"] == "deny"
    assert MATRIX[action]["system"] == "deny"
    assert MATRIX[action]["mfa_recent"] == "required"
    assert action in FRESH_MFA


def test_only_the_engagement_partner_approves_an_addition() -> None:
    allowed = {
        role for role, cell in MATRIX["archive_addition.approve"].items() if cell == "allow"
    }
    assert allowed == {"engagement_partner"}
    assert {r for r, c in MATRIX["archive.lock"].items() if c == "allow"} == {
        "engagement_partner",
        "manager",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_a_non_person_is_refused_before_the_archive_is_read(
    monkeypatch: pytest.MonkeyPatch, kind: ActorKind
) -> None:
    read: list[str] = []

    async def locked(*_a: object) -> object:
        read.append("archive")
        raise AssertionError("never read")

    monkeypatch.setattr(aa, "locked_archive", locked)
    with pytest.raises(Forbidden):
        await aa.decide_addition(_ctx(kind), WORK_ITEM, uuid.uuid4(), approve=True)
    assert read == []


@pytest.mark.asyncio
async def test_the_person_who_added_it_never_approves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    async def locked(*_a: object) -> object:
        return SimpleNamespace(release_date=RELEASED_ON)

    async def one(*_a: object) -> object:
        return SimpleNamespace(decision=None, added_by=MARGARET, content_sha256="0" * 64)

    written: list[object] = []

    async def put(*a: object) -> None:
        written.append(a)

    monkeypatch.setattr(aa, "locked_archive", locked)
    monkeypatch.setattr(aa, "_one", one)
    monkeypatch.setattr("abacus.modules.evidence.api.put_record", put)
    with pytest.raises(Forbidden):
        await aa.decide_addition(_ctx(), WORK_ITEM, uuid.uuid4(), approve=True)
    assert written == []


@pytest.mark.asyncio
async def test_a_decided_addition_is_never_decided_again(monkeypatch: pytest.MonkeyPatch) -> None:
    async def locked(*_a: object) -> object:
        return SimpleNamespace(release_date=RELEASED_ON)

    async def one(*_a: object) -> object:
        return SimpleNamespace(decision="approved", added_by=uuid.uuid4(), content_sha256="0" * 64)

    monkeypatch.setattr(aa, "locked_archive", locked)
    monkeypatch.setattr(aa, "_one", one)
    with pytest.raises(aa.AdditionDecided):
        await aa.decide_addition(_ctx(), WORK_ITEM, uuid.uuid4(), approve=False, reason="dup")


def test_an_addition_needs_a_locked_archive() -> None:
    source = inspect.getsource(aa.locked_archive)
    assert "raise ArchiveNotLocked" in source
