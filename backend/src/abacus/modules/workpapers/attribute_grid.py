"""The shared attribute-test grid (A-05-T22; A-05 §3 F4, §4.2 M2; EBP-03, EBP-04 Testing,
EBP-05; A-08 reuses it for AUD-12; DEC-2212).

A test is drawn from an **approved** A-03 sample set (409 `sample_not_approved` otherwise): one
row per sampled item in sample order, one column per attribute. Each cell's history is
insert-only (`test_attribute_results`, newest `seq` wins):
- the agent writes `agent_tested` (with the value it read, its citations and code's trace) or
  `needs_human`; it never concludes (the database refuses an agent `pass`, `exception` or
  `no_effect`, INV-1);
- a person marks `pass`, `exception` or `no_effect` (a sealed note for no effect and
  exceptions).

A person's mark is a new version of the test (`version_no`, `content_hash`) and announces
`attribute_test.version_created`, so an L1/L2 sign-off on the test goes stale (P-04). Adoption is
C3's own sign-off on the `attribute_test` reviewable (SHL-12). An exception row prefills SHL-15's
issue draft with its anchor.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import Reviewable, ReviewableFacts, seal_text
from abacus.modules.sampling.api import approved_items

TARGET: Final = "attribute_test"
Variant = Literal[
    "ebp_eligibility", "ebp_contribution_recalc", "ebp_distribution", "aud12_tod", "aud12_toc"
]
HumanResult = Literal["pass", "exception", "no_effect"]
AgentResult = Literal["agent_tested", "needs_human"]
_HUMAN: Final = frozenset({"pass", "exception", "no_effect"})
_ANCHOR: Final[dict[str, str]] = {
    "ebp_eligibility": "EBP-03",
    "ebp_contribution_recalc": "EBP-04",
    "ebp_distribution": "EBP-05",
    "aud12_tod": "AUD-12",
    "aud12_toc": "AUD-12",
}


class UnknownAttribute(DomainInvalid):
    code = "unknown_attribute"


class NoteRequired(DomainInvalid):
    """An exception or a no-effect mark carries the person's note."""

    code = "note_required"


class TestMoved(DomainConflict):
    code = "version_conflict"


class AttributeTestVersionCreated(DomainEvent):
    """A person's mark changed the test: its sign-offs go stale (review.stale)."""

    event_type: ClassVar[str] = "attribute_test.version_created"

    test_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]


@dataclass(frozen=True)
class Attribute:
    key: str
    label: str


@dataclass(frozen=True)
class Cell:
    attribute_key: str
    result: str
    seq: int
    value: Mapping[str, object] | None
    citation_ids: tuple[UUID, ...]
    trace: Mapping[str, object] | None
    actor_kind: str


@dataclass(frozen=True)
class Row:
    position: int
    item_id: UUID
    record_key: str
    cells: tuple[Cell, ...]

    @property
    def state(self) -> str:
        """A row's state: exception if any cell is, then needs human, then the rest."""
        results = {c.result for c in self.cells}
        for state in ("exception", "needs_human", "agent_tested", "no_effect", "pass"):
            if state in results:
                return state
        return "not_started"


@dataclass(frozen=True)
class Grid:
    test_id: UUID
    variant: str
    workpaper_id: UUID
    attributes: tuple[Attribute, ...]
    rows: tuple[Row, ...]
    version_no: int
    content_hash: str
    counts: Mapping[str, int] = field(default_factory=dict[str, int])


def _hash(test_id: UUID, cells: Sequence[tuple[object, ...]]) -> str:
    body = json.dumps([str(test_id), *[[str(x) for x in c] for c in cells]], separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


async def create_test(
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    workpaper_id: UUID,
    variant: Variant,
    sample_set_id: UUID,
    sample_version: int,
    attributes: Sequence[Attribute],
) -> UUID:
    """A test over the approved sample's items; 409 `sample_not_approved` otherwise."""
    await approved_items(ctx, sample_set_id, sample_version)  # refuses an unapproved sample
    if not attributes or len({a.key for a in attributes}) != len(attributes):
        raise DomainInvalid(facts={"field": "attributes"})
    async with uow(ctx.tenant) as tx:
        test_id = cast(
            UUID,
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO attribute_tests (tenant_id, engagement_id, work_item_id, "
                        "workpaper_id, variant, sample_set_id, sample_set_version, attributes, "
                        "content_hash) VALUES (:t, :e, :w, :wp, :variant, :set, :v, "
                        "CAST(:attrs AS jsonb), :hash) RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "e": engagement_id,
                        "w": work_item_id,
                        "wp": workpaper_id,
                        "variant": variant,
                        "set": sample_set_id,
                        "v": sample_version,
                        "attrs": json.dumps(
                            [{"key": a.key, "label": a.label} for a in attributes]
                        ),
                        "hash": hashlib.sha256(str(sample_set_id).encode()).hexdigest(),
                    },
                )
            ).scalar_one(),
        )
        tx.record("attribute_test.created", target=Target(TARGET, test_id))
    return test_id


_TEST = text(
    "SELECT id, engagement_id, workpaper_id, variant, sample_set_id, sample_set_version, "
    "attributes, version_no, content_hash FROM attribute_tests WHERE id = :id"
)
_CELLS = text(
    "SELECT DISTINCT ON (sample_item_id, attribute_key) sample_item_id, attribute_key, result, "
    "seq, value, citation_ids, trace, actor_kind FROM test_attribute_results "
    "WHERE test_id = :id ORDER BY sample_item_id, attribute_key, seq DESC"
)


async def _test(tenant: TenantContext, test_id: UUID) -> Mapping[str, object]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_TEST, {"id": test_id})).mappings().one_or_none()
    if found is None:
        raise NotFound(TARGET)
    return dict(found)


async def grid(ctx: AuthContext, engagement_id: UUID, test_id: UUID) -> Grid:
    """Rows in sample order with each attribute's newest result and the counts EBP-03 shows."""
    test = await _test(ctx.tenant, test_id)
    if test["engagement_id"] != engagement_id:
        raise NotFound(TARGET)
    items = await approved_items(
        ctx, cast(UUID, test["sample_set_id"]), int(cast(int, test["sample_set_version"]))
    )
    async with tenant_session(ctx.tenant) as session:
        latest = (await session.execute(_CELLS, {"id": test_id})).mappings().all()
    by_item: dict[UUID, list[Cell]] = {}
    for r in latest:
        by_item.setdefault(cast(UUID, r["sample_item_id"]), []).append(
            Cell(
                attribute_key=cast(str, r["attribute_key"]),
                result=cast(str, r["result"]),
                seq=cast(int, r["seq"]),
                value=cast(Mapping[str, object] | None, r["value"]),
                citation_ids=tuple(cast(Sequence[UUID], r["citation_ids"] or ())),
                trace=cast(Mapping[str, object] | None, r["trace"]),
                actor_kind=cast(str, r["actor_kind"]),
            )
        )
    rows = tuple(Row(i.position, i.id, i.record_key, tuple(by_item.get(i.id, ()))) for i in items)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    attrs = tuple(
        Attribute(str(a["key"]), str(a["label"]))
        for a in cast(list[Mapping[str, object]], test["attributes"])
    )
    return Grid(
        test_id,
        cast(str, test["variant"]),
        cast(UUID, test["workpaper_id"]),
        attrs,
        rows,
        int(cast(int, test["version_no"])),
        cast(str, test["content_hash"]),
        counts,
    )


async def _next_seq(tenant: TenantContext, test_id: UUID, item_id: UUID, key: str) -> int:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT coalesce(max(seq), 0) FROM test_attribute_results WHERE test_id = :t "
                "AND sample_item_id = :i AND attribute_key = :k"
            ),
            {"t": test_id, "i": item_id, "k": key},
        )
    return int(cast(int, found)) + 1


async def record_agent_result(
    tenant: TenantContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    test_id: UUID,
    item_id: UUID,
    attribute_key: str,
    result: AgentResult,
    value: Mapping[str, object] | None,
    citation_ids: Sequence[UUID],
    trace: Mapping[str, object] | None,
    suggestion_id: UUID | None = None,
) -> None:
    """The agent's cell: what it read and code's trace; never a conclusion (INV-1)."""
    seq = await _next_seq(tenant, test_id, item_id, attribute_key)
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO test_attribute_results (tenant_id, engagement_id, work_item_id, "
                "test_id, sample_item_id, attribute_key, seq, value, citation_ids, result, trace, "
                "suggestion_id) VALUES (:t, :e, :w, :test, :item, :key, :seq, "
                "CAST(:value AS jsonb), :cites, :result, CAST(:trace AS jsonb), :sugg)"
            ),
            {
                "t": tenant.tenant_id,
                "e": engagement_id,
                "w": work_item_id,
                "test": test_id,
                "item": item_id,
                "key": attribute_key,
                "seq": seq,
                "value": None if value is None else json.dumps(value, default=str),
                "cites": list(citation_ids),
                "result": result,
                "trace": None if trace is None else json.dumps(trace, default=str),
                "sugg": suggestion_id,
            },
        )
        tx.record(
            "attribute_result.recorded",
            target=Target(TARGET, test_id),
            after=Ref(seq=seq),
        )


async def mark(
    ctx: AuthContext,
    engagement_id: UUID,
    test_id: UUID,
    item_id: UUID,
    attribute_key: str,
    result: HumanResult,
    note: str | None,
) -> Grid:
    """A person's pass, exception or no effect: a new result row and a new test version."""
    if result not in _HUMAN:
        raise DomainInvalid(facts={"field": "result"})
    current = await grid(ctx, engagement_id, test_id)
    if attribute_key not in {a.key for a in current.attributes}:
        raise UnknownAttribute(facts={"attribute": attribute_key})
    if item_id not in {r.item_id for r in current.rows}:
        raise NotFound("sample_item")
    if result in ("exception", "no_effect") and not (note and note.strip()):
        raise NoteRequired
    sealed = None
    if note:
        sealed = await seal_text(ctx.tenant, note, "attribute_result", test_id, item_id)
    seq = await _next_seq(ctx.tenant, test_id, item_id, attribute_key)
    work_item = await _work_item(ctx.tenant, test_id)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO test_attribute_results (tenant_id, engagement_id, work_item_id, "
                "test_id, sample_item_id, attribute_key, seq, result, note_sealed) VALUES (:t, "
                ":e, :w, :test, :item, :key, :seq, :result, :note)"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": work_item,
                "test": test_id,
                "item": item_id,
                "key": attribute_key,
                "seq": seq,
                "result": result,
                "note": sealed,
            },
        )
        cells = [
            (r.item_id, c.attribute_key, c.result, c.seq) for r in current.rows for c in r.cells
        ] + [(item_id, attribute_key, result, seq)]
        new_hash = _hash(test_id, sorted(cells, key=str))
        moved = await tx.session.scalar(
            text(
                "UPDATE attribute_tests SET version_no = version_no + 1, content_hash = :hash "
                "WHERE id = :id AND version_no = :v RETURNING version_no"
            ),
            {"hash": new_hash, "id": test_id, "v": current.version_no},
        )
        if moved is None:
            raise TestMoved
        tx.record(
            "attribute_result.marked",
            target=Target(TARGET, test_id),
            after=Ref(version=int(cast(int, moved))),
        )
        tx.emit(
            AttributeTestVersionCreated(
                test_id=test_id, engagement_id=engagement_id, version_no=int(cast(int, moved))
            )
        )
    return await grid(ctx, engagement_id, test_id)


async def _work_item(tenant: TenantContext, test_id: UUID) -> UUID:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM attribute_tests WHERE id = :id"), {"id": test_id}
        )
    if found is None:
        raise NotFound(TARGET)
    return cast(UUID, found)


@dataclass(frozen=True)
class ExceptionPrefill:
    """SHL-15's issue draft for an exception row: title, anchor and the row's citations."""

    title: str
    anchor: str
    record_key: str
    citation_ids: tuple[UUID, ...]


def exception_prefill(found: Grid, item_id: UUID) -> ExceptionPrefill:
    row = next((r for r in found.rows if r.item_id == item_id), None)
    if row is None or row.state != "exception":
        raise NotFound("exception_row")
    failing = [c for c in row.cells if c.result == "exception"]
    labels = {a.key: a.label for a in found.attributes}
    title = "; ".join(labels.get(c.attribute_key, c.attribute_key) for c in failing)
    cites = tuple(dict.fromkeys(x for c in row.cells for x in c.citation_ids))
    anchor = f"{_ANCHOR.get(found.variant, 'TEST')}!row {row.position}"
    return ExceptionPrefill(title, anchor, row.record_key, cites)


async def test_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """C3: each test on the engagement with its content hash; its sign-off is the adoption."""
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, variant, version_no, content_hash FROM attribute_tests "
                        "WHERE engagement_id = :e ORDER BY created_at"
                    ),
                    {"e": engagement_id},
                )
            )
            .mappings()
            .all()
        )
    return [
        Reviewable(
            TARGET,
            cast(UUID, r["id"]),
            f"{_ANCHOR.get(cast(str, r['variant']), 'TEST')} test",
            f"Attribute test v{r['version_no']}",
            cast(str, r["content_hash"]),
            True,
        )
        for r in rows
    ]


async def test_facts(tenant: TenantContext, test_id: UUID) -> ReviewableFacts | None:
    """P-04's sign-off facts for one test: its hash, version and the people who marked it (an L1
    adopter must not be the only preparer when the matrix says so)."""
    async with tenant_session(tenant) as session:
        test = (await session.execute(_TEST, {"id": test_id})).mappings().one_or_none()
        if test is None:
            return None
        markers = (
            await session.execute(
                text(
                    "SELECT DISTINCT actor_id FROM test_attribute_results WHERE test_id = :id "
                    "AND actor_kind = 'human'"
                ),
                {"id": test_id},
            )
        ).scalars()
        people = frozenset(UUID(str(m)) for m in markers if m)
    return ReviewableFacts(
        TARGET,
        test_id,
        cast(UUID, test["engagement_id"]),
        cast(str, test["content_hash"]),
        int(cast(int, test["version_no"])),
        people,
        label=f"{_ANCHOR.get(cast(str, test['variant']), 'TEST')} attribute test",
    )
