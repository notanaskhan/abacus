"""The audit label index's own logic, without a database (G-02-T10; SPEC-349; Q-03-T072).

The integration suite (`test_g02t10_audit_labels.py`) proves the projection end to end; these
tests pin the pieces a mutation run decides on the unit suites alone: which people and targets a
batch names, how labels are clipped and joined into `keywords`, how a search becomes words, the
SQL each predicate builds, and how the back-fill and the catch-up treat a busy indexer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import column
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from abacus.kernel.db import TenantContext
from abacus.modules.audit_trail import labels

labels_uuid = labels._uuid  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_refs = labels._refs  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_clip = labels._clip  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_query = labels._query  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_indexer = labels._indexer  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_config = labels._config  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_lock_key = labels._lock_key  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_pending = labels._pending  # pyright: ignore[reportPrivateUsage] -- the helper under test
labels_label_rows = labels._label_rows  # pyright: ignore[reportPrivateUsage] -- the helper under test

TENANT = uuid.UUID("00000000-0000-4000-8000-0000000000aa")
ALICE = uuid.UUID("00000000-0000-4000-8000-000000000001")
BOB = uuid.UUID("00000000-0000-4000-8000-000000000002")
CARA = uuid.UUID("00000000-0000-4000-8000-000000000003")
WHEN = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _sql(expr: ClauseElement) -> str:
    return str(expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


# --- small helpers -------------------------------------------------------------------------------


def test_uuid_reads_a_uuid_a_string_or_nothing() -> None:
    assert labels_uuid(ALICE) is ALICE
    assert labels_uuid(str(BOB)) == BOB
    assert labels_uuid("system:agent") is None
    assert labels_uuid(None) is None


def test_refs_is_the_dict_or_empty() -> None:
    assert labels_refs({"a": 1}) == {"a": 1}
    assert labels_refs(["a"]) == {}
    assert labels_refs(None) == {}


def test_clip_strips_cuts_and_empties_to_none() -> None:
    assert labels_clip(None, 5) is None
    assert labels_clip("  abcdefgh  ", 5) == "abcde"
    assert labels_clip("abc", 3) == "abc"
    assert labels_clip("   ", 5) is None
    assert labels_clip("", 5) is None


def test_keywords_text_joins_labels_and_action_words_in_order() -> None:
    text = labels.keywords_text("request_item.returned_to_client", "Ana", "PBC 4", ["Bo", "Cy"])
    assert text == "Ana PBC 4 Bo Cy request item returned to client"


def test_keywords_text_skips_missing_labels() -> None:
    assert labels.keywords_text("evidence.uploaded", None, None, []) == "evidence uploaded"
    assert labels.keywords_text("a.b", "", "T", ["", "X"]) == "T X a b"


def test_query_is_lower_case_words_capped_at_max_q() -> None:
    assert labels_query("  Ana  O'Neil, PBC-4! ") == "ana o neil pbc 4"
    assert labels_query("!!!") == ""
    long = "a" * (labels.MAX_Q - 2) + " bcd"  # the cut falls after "b"
    assert labels_query(long) == "a" * (labels.MAX_Q - 2) + " b"


def test_indexer_context_is_the_system_indexer() -> None:
    ctx = labels_indexer(TENANT)
    assert ctx.tenant_id == TENANT
    assert ctx.actor_kind == "system"
    assert ctx.actor_id == "system:audit_label_index"


def test_index_busy_names_the_firm() -> None:
    err = labels.IndexBusy(TENANT)
    assert str(err) == f"the audit label index of {TENANT} is being written"
    assert isinstance(err, RuntimeError)


# --- SQL the predicates build --------------------------------------------------------------------


def test_config_is_the_simple_regconfig() -> None:
    assert _sql(labels_config()) == "CAST('simple' AS REGCONFIG)"


def test_lock_key_hashes_the_firm_label() -> None:
    assert _sql(labels_lock_key(TENANT)) == (f"hashtextextended('audit_label_index:{TENANT}', 0)")


def test_pending_with_an_explicit_after_is_the_range_only() -> None:
    sql = _sql(labels_pending(10, 10))
    assert sql == "audit_events.seq > 10"


def test_pending_catch_up_also_reads_unlabelled_events_of_the_settle_window() -> None:
    sql = _sql(labels_pending(None, 7))
    assert sql.startswith("audit_events.seq > 7 OR ")
    assert (
        "audit_events.occurred_at > clock_timestamp() - make_interval(0, 0, 0, 0, 0, 0, 120)"
        in sql
    )
    assert "NOT (EXISTS (SELECT 1" in sql
    assert "audit_event_labels.tenant_id = audit_events.tenant_id" in sql
    assert "audit_event_labels.seq = audit_events.seq" in sql
    assert " AND " in sql


def test_matching_nothing_to_search_is_false() -> None:
    assert _sql(labels.matching(column("seq"), " ,, ")) == "false"


def test_matching_is_a_seq_predicate_over_the_keywords() -> None:
    sql = _sql(labels.matching(column("seq"), "Ana PBC"))
    assert sql.startswith("seq IN (SELECT audit_event_labels.seq")
    assert (
        "audit_event_labels.keywords @@ plainto_tsquery(CAST('simple' AS REGCONFIG), 'ana pbc')"
        in sql
    )


# --- the rows a batch writes ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Label:
    text: str


class _Calls:
    def __init__(self) -> None:
        self.names: list[list[uuid.UUID]] = []
        self.labels: list[tuple[str, list[str], TenantContext]] = []


def _event(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "seq": 1,
        "effective_at": WHEN,
        "actor_kind": "human",
        "actor_id": str(ALICE),
        "on_behalf_of_user_id": None,
        "action": "request_item.sent",
        "target_type": "request_item",
        "target_id": "r-1",
        "before_ref": None,
        "after_ref": None,
        "client_id": uuid.UUID(int=11),
        "office_id": uuid.UUID(int=12),
        "engagement_id": uuid.UUID(int=13),
    }
    row.update(over)
    return row


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    seen = _Calls()
    names = {ALICE: "Ana Alvarez", BOB: "Bo Brandt", CARA: "Cara Chen"}

    async def names_of(ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        seen.names.append(list(ids))
        return {i: names[i] for i in ids if i in names}

    async def audit_labels(
        ctx: object, kind: str, ids: list[str], *, tenant: TenantContext
    ) -> dict[str, _Label]:
        assert ctx is None
        seen.labels.append((kind, list(ids), tenant))
        return {i: _Label(f"{kind} {i} label") for i in ids if not i.startswith("unnamed")}

    monkeypatch.setattr(labels, "names_of", names_of)
    monkeypatch.setattr(labels, "audit_labels", audit_labels)

    def audit_noun(kind: str) -> str:
        return f"Noun of {kind}"

    monkeypatch.setattr(labels, "audit_noun", audit_noun)
    return seen


async def test_label_rows_human_actor_and_target(calls: _Calls) -> None:
    [row] = await labels_label_rows(TENANT, [_event()])
    assert row == {
        "tenant_id": TENANT,
        "seq": 1,
        "effective_at": WHEN,
        "actor_label": "Ana Alvarez",
        "target_label": "request_item r-1 label",
        "text": "Ana Alvarez request_item r-1 label request item sent",
        "client_id": uuid.UUID(int=11),
        "office_id": uuid.UUID(int=12),
        "engagement_id": uuid.UUID(int=13),
    }
    assert calls.names == [[ALICE]]
    [(kind, ids, tenant)] = calls.labels
    assert (kind, ids) == ("request_item", ["r-1"])
    assert tenant.tenant_id == TENANT
    assert tenant.actor_id == "system:audit_label_index"


async def test_label_rows_support_actor_is_a_person(calls: _Calls) -> None:
    [row] = await labels_label_rows(TENANT, [_event(actor_kind="support", actor_id=str(BOB))])
    assert row["actor_label"] == "Bo Brandt"


async def test_label_rows_agent_is_labelled_as_the_person_it_acted_for(calls: _Calls) -> None:
    [row] = await labels_label_rows(
        TENANT, [_event(actor_kind="agent", actor_id="agent:accrued", on_behalf_of_user_id=CARA)]
    )
    assert row["actor_label"] == "Cara Chen"
    assert calls.names == [[CARA]]


async def test_label_rows_agent_without_a_person_has_no_actor(calls: _Calls) -> None:
    [row] = await labels_label_rows(TENANT, [_event(actor_kind="agent", actor_id=str(ALICE))])
    assert row["actor_label"] is None
    assert calls.names == []  # nobody to name: identity is not asked


async def test_label_rows_system_actor_has_no_label_even_with_a_uuid_id(calls: _Calls) -> None:
    [row] = await labels_label_rows(TENANT, [_event(actor_kind="system", actor_id=str(ALICE))])
    assert row["actor_label"] is None
    assert row["text"] == "request_item r-1 label request item sent"


async def test_label_rows_names_people_the_refs_point_at_only(calls: _Calls) -> None:
    [row] = await labels_label_rows(
        TENANT,
        [
            _event(
                actor_kind="system",
                actor_id="system:x",
                before_ref={"assignee_user_id": str(BOB), "user_identity": str(ALICE)},
                after_ref={"user_id": str(CARA), "reviewer_user_id": "not-a-uuid"},
            )
        ],
    )
    assert calls.names == [sorted([BOB, CARA], key=str)]
    assert row["text"] == "request_item r-1 label Bo Brandt Cara Chen request item sent"


async def test_label_rows_a_ref_to_an_unknown_person_is_left_out(calls: _Calls) -> None:
    stranger = uuid.UUID(int=99)
    [row] = await labels_label_rows(TENANT, [_event(after_ref={"user_id": str(stranger)})])
    assert row["text"] == "Ana Alvarez request_item r-1 label request item sent"


async def test_label_rows_an_unnamed_target_is_its_noun(calls: _Calls) -> None:
    [row] = await labels_label_rows(TENANT, [_event(target_id="unnamed-1")])
    assert row["target_label"] == "Noun of request_item"


async def test_label_rows_group_targets_by_type_once_each(calls: _Calls) -> None:
    rows = await labels_label_rows(
        TENANT,
        [
            _event(seq=1, target_id="b"),
            _event(seq=2, target_id="a"),
            _event(seq=3, target_type="evidence_file", target_id="f"),
            _event(seq=4, target_id="a", actor_id=str(ALICE)),
        ],
    )
    assert [(k, i) for k, i, _ in calls.labels] == [
        ("request_item", ["a", "b"]),
        ("evidence_file", ["f"]),
    ]
    assert calls.names == [[ALICE]]
    assert [r["seq"] for r in rows] == [1, 2, 3, 4]
    assert rows[2]["target_label"] == "evidence_file f label"


async def test_label_rows_clip_long_labels(calls: _Calls, monkeypatch: pytest.MonkeyPatch) -> None:
    async def long_names(ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {i: "n" * 250 for i in ids}

    async def long_labels(
        ctx: object, kind: str, ids: list[str], *, tenant: TenantContext
    ) -> dict[str, _Label]:
        return {i: _Label("t" * 350) for i in ids}

    monkeypatch.setattr(labels, "names_of", long_names)
    monkeypatch.setattr(labels, "audit_labels", long_labels)
    [row] = await labels_label_rows(TENANT, [_event()])
    assert row["actor_label"] == "n" * 200
    assert row["target_label"] == "t" * 300


# --- the back-fill and the catch-up --------------------------------------------------------------


async def test_backfill_runs_batches_until_a_short_one(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, int | None]] = []
    answers = iter([(3, 30), (3, 60), (1, 61)])

    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        assert tenant_id == TENANT
        seen.append((limit, after))
        return next(answers)

    monkeypatch.setattr(labels, "index_batch", index_batch)
    assert await labels.backfill(TENANT, batch=3) == 7
    assert seen == [(3, 0), (3, 30), (3, 60)]


async def test_backfill_stops_when_nothing_is_left(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([(2, 5), (0, None)])

    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        return next(answers)

    monkeypatch.setattr(labels, "index_batch", index_batch)
    assert await labels.backfill(TENANT, batch=2) == 2


async def test_backfill_full_batch_with_no_last_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        return limit, None

    monkeypatch.setattr(labels, "index_batch", index_batch)
    assert await labels.backfill(TENANT, batch=4) == 4


async def test_backfill_waits_out_a_busy_indexer(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int | None] = []
    sleeps: list[float] = []

    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        attempts.append(after)
        if len(attempts) < 3:
            raise labels.IndexBusy(tenant_id)
        return 1, 9

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(labels, "index_batch", index_batch)
    monkeypatch.setattr(labels.asyncio, "sleep", sleep)
    assert await labels.backfill(TENANT, batch=5, retries=2, pause=0.5) == 1
    assert attempts == [0, 0, 0]
    assert sleeps == [0.5, 0.5]


async def test_backfill_raises_after_its_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        attempts.append(1)
        raise labels.IndexBusy(tenant_id)

    async def sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(labels, "index_batch", index_batch)
    monkeypatch.setattr(labels.asyncio, "sleep", sleep)
    with pytest.raises(labels.IndexBusy):
        await labels.backfill(TENANT, retries=3)
    assert len(attempts) == 4


async def test_backfill_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    async def index_batch(
        tenant_id: uuid.UUID, limit: int, *, after: int | None
    ) -> tuple[int, int | None]:
        seen.append(limit)
        return 0, None

    monkeypatch.setattr(labels, "index_batch", index_batch)
    assert await labels.backfill(TENANT) == 0
    assert seen == [labels.BATCH]


async def test_catch_up_runs_one_default_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    async def index_batch(*args: object, **kwargs: object) -> tuple[int, int | None]:
        seen.append((args[0], args[1:], kwargs))
        return 0, None

    monkeypatch.setattr(labels, "index_batch", index_batch)
    await labels.catch_up(TENANT)
    assert seen == [(TENANT, (), {})]


async def test_catch_up_does_not_wait_for_a_busy_indexer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def index_batch(tenant_id: uuid.UUID) -> tuple[int, int | None]:
        raise labels.IndexBusy(tenant_id)

    monkeypatch.setattr(labels, "index_batch", index_batch)
    await labels.catch_up(TENANT)  # suppressed: another indexer is catching the firm up


async def test_catch_up_lets_other_errors_through(monkeypatch: pytest.MonkeyPatch) -> None:
    async def index_batch(tenant_id: uuid.UUID) -> tuple[int, int | None]:
        raise RuntimeError("database gone")

    monkeypatch.setattr(labels, "index_batch", index_batch)
    with pytest.raises(RuntimeError, match="database gone"):
        await labels.catch_up(TENANT)
