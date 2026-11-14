"""The entity return's preparer memo service (T-05-T54; TASK-7906; T-05 F9; TXP-01; ADR-005,
ADR-050, ADR-090, P-24; DEC-4909, DEC-4910). Amber; the drafting capability is T-05-T48's
(`memo_drafter`).

- **Facts (code).** `memo_facts` reads the workbook's cells into the figures the memo may state,
  each with its section and the cells it cites: capital (each partner's ending capital, the
  partners' totals, M-2 line 9 "ending capital"), distributions, Schedule K lines (06), states and
  PTET (08), the book-to-tax bridge (03's mapped lines) and the year's structural events (interest
  transfers). Each cited cell is a source with its verified quote (`<sheet>!<cell> = <value>`).
  The figure fingerprint is T-05-T48's `fingerprint_of` over these facts.
- **Draft and regenerate.** `start_draft` opens the person's run of `tax.memo_drafter` and
  dispatches `MemoDraftWorkflow` (ADR-090 versioned; identifiers in and out). Without both §7216
  consents it is 409 `consent_required` before anything starts. With no sections named, a stale
  memo regenerates only its affected sections (those with a changed fact); a person's sections are
  always carried over by the drafter (P-24).
- **Edit.** A person's section edit (`expected_version` = the memo's version, 409
  `memo_version_conflict` otherwise) writes the next version with that section `human_owned`
  (cause `edit`, `created_by_kind` human).
- **Adopt (L1) and approve (L2).** Both are P-04 sign-offs on the `preparer_memo` reviewable (its
  content hash, `seen_hash`), then the memo's own `adopted` / `approved` event (0830's CHECK: a
  person's). The preparer never approves: the L1 signer and the person a draft acted for are the
  reviewable's preparers (P-04 refuses them L2; this service refuses first, 403
  `preparer_cannot_approve`). Approval writes the opportunities section's segments as
  `planning_opportunities` rows.
- **Staleness.** After a run ends, a fix is applied or a cell is edited, `check_stale` compares
  the facts now with the fingerprint the memo was drafted from; an adopted or approved memo whose
  figures moved gets one `went_stale` event (system) and `tax_memo.went_stale` (C16). The read
  names each moved figure: "ending capital 6,860,000 → 6,866,200" (values then from review's
  versions as of the memo version's time).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
    from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
    from abacus.kernel.uow import Ref, Scope, Target, uow
    from abacus.modules.identity.api import AuthContext
    from abacus.modules.tax.memo_drafter import (
        CAPABILITY,
        SECTION_KEYS,
        DraftMemoInput,
        MemoFact,
        MemoSource,
        fingerprint_of,
    )
    from abacus.modules.tax.workbook_service import WORKBOOK, sheets_of

TARGET: Final = "preparer_memo"
Status = Literal["drafting", "adopted", "approved", "stale"]
SECTION_TITLES: Final[Mapping[str, str]] = {
    "overview": "Facts",
    "structural_events": "Structural events",
    "balance_sheet": "Balance sheet",
    "book_to_tax": "Book-to-tax bridge",
    "depreciation": "Depreciation",
    "liabilities_752": "§752 liabilities",
    "states_ptet": "States and PTET",
    "distributions": "Distributions",
    "capital": "Capital",
    "open_items": "Open items",
    "opportunities": "Opportunities",
}
Values = Mapping[str, Mapping[str, object]]


class ConsentRequired(DomainConflict):
    code = "consent_required"


class MemoVersionConflict(DomainConflict):
    code = "memo_version_conflict"


class MemoNotDrafted(DomainConflict):
    code = "memo_not_drafted"


class PreparerCannotApprove(DomainForbidden):
    code = "preparer_cannot_approve"


# --- facts (code) --------------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionFact:
    fact: MemoFact
    section: str
    cells: tuple[str, ...]


def _dec(values: Values, key: str) -> Decimal | None:
    raw = values.get(key, {}).get("v")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except ArithmeticError:
        return None


def _text(values: Values, key: str) -> str:
    raw = values.get(key, {}).get("v")
    return "" if raw is None else str(raw)


def money(amount: Decimal) -> str:
    return f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"


def handle_of(cell: str) -> str:
    """`cell:05_f2` for `05!F2` (a source handle the drafter accepts)."""
    return "cell:" + cell.replace("!", "_").lower()


def _slug(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")[:40] or "x"


def memo_facts(values: Values, transfers: Sequence[str] = ()) -> list[SectionFact]:
    """The memo's figures from the workbook's cells (module docstring), in a fixed order."""
    out: list[SectionFact] = []

    def add(section: str, handle: str, label: str, amount: Decimal | None, cells: Sequence[str]):  # noqa: ANN202 -- a local adder
        if amount is None:
            return
        out.append(
            SectionFact(MemoFact(handle=handle, label=label, value=money(amount)), section,
                        tuple(cells))
        )  # fmt: skip

    n = 2
    partners: list[int] = []
    while _text(values, f"05!A{n}"):
        partners.append(n)
        name = _text(values, f"05!A{n}")
        add("capital", f"capital_{_slug(name)}", f"{name} ending capital",
            _dec(values, f"05!F{n}"), [f"05!F{n}"])  # fmt: skip
        n += 1
    if partners:
        for col, key, label, section in (
            ("C", "contributions", "contributions", "capital"),
            ("D", "distributions", "distributions", "distributions"),
            ("E", "income", "income allocated to the partners", "capital"),
            ("F", "partners_ending", "partners' ending capital", "capital"),
        ):
            cells = [f"05!{col}{r}" for r in partners]
            amounts = [_dec(values, c) for c in cells]
            total = sum((a for a in amounts if a is not None), Decimal(0))
            add(section, key, label, total, cells)
    add("capital", "m2_ending", "ending capital", _dec(values, "07!B9"), ["07!B9"])
    n = 2
    while f"06!A{n}" in values:
        line = _text(values, f"06!A{n}")
        add("overview", f"k_{_slug(line)}", f"Schedule K line {line}",
            _dec(values, f"06!C{n}"), [f"06!C{n}"])  # fmt: skip
        n += 1
    n = 2
    while f"08!A{n}" in values:
        label = f"{_text(values, f'08!A{n}')} {_text(values, f'08!B{n}')}".strip()
        add("states_ptet", f"state_{n}", label, _dec(values, f"08!C{n}"), [f"08!C{n}"])
        n += 1
    n = 2
    while f"03!A{n}" in values:
        add("book_to_tax", f"line_{_slug(_text(values, f'03!A{n}'))}",
            _text(values, f"03!B{n}") or _text(values, f"03!A{n}"),
            _dec(values, f"03!C{n}"), [f"03!C{n}"])  # fmt: skip
        n += 1
    for i, day in enumerate(transfers, start=1):
        out.append(
            SectionFact(MemoFact(handle=f"transfer_{i}", label="interest transfer", value=day),
                        "structural_events", ())
        )  # fmt: skip
    return out[:120]


def sources_of(form: str, values: Values, facts: Sequence[SectionFact]) -> list[MemoSource]:
    titles = dict(sheets_of(form))
    seen: dict[str, MemoSource] = {}
    for f in facts:
        for cell in f.cells:
            if cell in seen:
                continue
            sheet, a1 = cell.split("!", 1)
            label = f"{sheet} {titles.get(sheet, '')}".strip() + f"!{a1}"
            amount = _dec(values, cell)
            quote = f"{label} = {money(amount) if amount is not None else _text(values, cell)}"
            seen[cell] = MemoSource(handle=handle_of(cell), label=label[:120], quote=quote[:600])
    return list(seen.values())[:80]


def moved(
    then: Sequence[SectionFact], now: Sequence[SectionFact]
) -> list[tuple[SectionFact, str]]:
    """Each fact whose value moved, with the stale line "ending capital 6,860,000 → 6,866,200"."""
    before = {f.fact.handle: f for f in then}
    out: list[tuple[SectionFact, str]] = []
    for f in now:
        old = before.get(f.fact.handle)
        if old is not None and old.fact.value != f.fact.value:
            out.append((f, f"{f.fact.label} {old.fact.value} → {f.fact.value}"))
    return out


def affected_sections(then: Sequence[SectionFact], now: Sequence[SectionFact]) -> list[str]:
    keys = {f.section for f, _ in moved(then, now)}
    return [k for k in SECTION_KEYS if k in keys]


# --- reads ---------------------------------------------------------------------------------------

_MEMO: Final = text(
    "SELECT id, engagement_id, current_version_no, figure_fingerprint, content_hash, updated_at "
    "FROM preparer_memos WHERE work_item_id = :r"
)
_VERSION_ROW: Final = text(
    "SELECT version_no, sections, created_at, on_behalf_of_user_id FROM preparer_memo_versions "
    "WHERE memo_id = :m AND version_no = :v"
)
_LAST_EVENT: Final = text(
    "SELECT event FROM preparer_memo_events WHERE memo_id = :m AND event IN "
    "('drafted', 'regenerated', 'section_edited', 'adopted', 'approved', 'went_stale') "
    "ORDER BY created_at DESC, id DESC LIMIT 1"
)
_PREPARERS: Final = text(
    "SELECT DISTINCT on_behalf_of_user_id FROM preparer_memo_versions WHERE memo_id = :m "
    "AND on_behalf_of_user_id IS NOT NULL"
)
_EVENT: Final = text(
    "INSERT INTO preparer_memo_events (tenant_id, engagement_id, work_item_id, memo_id, event, "
    "version_no, ref) VALUES (:t, :e, :r, :m, :event, :v, CAST(:ref AS jsonb))"
)


@dataclass(frozen=True)
class MemoRow:
    id: UUID
    engagement_id: UUID
    version: int
    fingerprint: str | None
    content_hash: str | None


@dataclass(frozen=True)
class MemoSectionView:
    key: str
    title: str
    body: str
    human_owned: bool


@dataclass(frozen=True)
class MemoView:
    status: Status
    sections: list[MemoSectionView]
    seen_hash: str
    stale_fields: list[str]
    version: int


async def memo_row(tenant: TenantContext, return_id: UUID) -> MemoRow | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_MEMO, {"r": return_id})).first()
    if r is None:
        return None
    return MemoRow(UUID(str(r.id)), UUID(str(r.engagement_id)), int(r.current_version_no),
                   r.figure_fingerprint, r.content_hash)  # fmt: skip


async def _version(
    tenant: TenantContext, memo: MemoRow
) -> tuple[list[dict[str, object]], datetime]:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_VERSION_ROW, {"m": memo.id, "v": memo.version})).first()
    if r is None:
        raise MemoNotDrafted
    return cast(list[dict[str, object]], r.sections or []), cast(datetime, r.created_at)


async def _last_event(tenant: TenantContext, memo_id: UUID) -> str | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(_LAST_EVENT, {"m": memo_id})
    return None if found is None else str(found)


async def facts_now(
    tenant: TenantContext, return_id: UUID
) -> tuple[str, Values, list[SectionFact]]:
    from abacus.modules.review.api import current_values
    from abacus.modules.tax.entity_decisions import year_transfers

    form = await _form(tenant, return_id)
    values = await current_values(tenant, WORKBOOK, return_id)
    transfers, _ = await year_transfers(tenant, return_id)
    return form, values, memo_facts(values, [f"{d.month}/{d.day}/{d.year}" for d in transfers])


async def facts_then(tenant: TenantContext, return_id: UUID, at: datetime) -> list[SectionFact]:
    from abacus.modules.review.api import values_as_of
    from abacus.modules.tax.entity_decisions import year_transfers

    then = (await values_as_of(tenant, WORKBOOK, [return_id], at)).get(return_id, {})
    transfers, _ = await year_transfers(tenant, return_id)
    return memo_facts(then, [f"{d.month}/{d.day}/{d.year}" for d in transfers])


async def _form(tenant: TenantContext, return_id: UUID) -> str:
    async with tenant_session(tenant) as session:
        form = await session.scalar(
            text("SELECT form FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
    if form is None:
        raise NotFound("tax_return")
    return str(form)


def body_of(section: Mapping[str, object]) -> str:
    segments = cast(list[Mapping[str, object]], section.get("segments") or [])
    return " ".join(str(s.get("text", "")) for s in segments).strip()


async def read_memo(ctx: AuthContext, return_id: UUID) -> MemoView:
    """TXP-01's memo (the route authorised `tax_memo.read`)."""
    memo = await memo_row(ctx.tenant, return_id)
    if memo is None or memo.version == 0:
        return MemoView("drafting", [], "", [], 0)
    sections, drafted_at = await _version(ctx.tenant, memo)
    last = await _last_event(ctx.tenant, memo.id)
    _, _, now = await facts_now(ctx.tenant, return_id)
    stale_lines: list[str] = []
    status: Status = "drafting"
    if last in ("adopted", "approved", "went_stale"):
        if (
            memo.fingerprint is not None
            and fingerprint_of([f.fact for f in now]) != memo.fingerprint
        ):
            status = "stale"
            then = await facts_then(ctx.tenant, return_id, drafted_at)
            stale_lines = [line for _, line in moved(then, now)]
        else:
            status = "approved" if last == "approved" else "adopted"
    return MemoView(
        status=status,
        sections=[
            MemoSectionView(
                str(s["key"]),
                SECTION_TITLES.get(str(s["key"]), str(s["key"])),
                body_of(s),
                bool(s.get("human_owned")),
            )
            for s in sections
        ],
        seen_hash=memo.content_hash or "",
        stale_fields=stale_lines,
        version=memo.version,
    )


# --- draft (the person's run) -------------------------------------------------------------------


async def start_draft(ctx: AuthContext, return_id: UUID, sections: Sequence[str]) -> UUID:
    """The person's run of `tax.memo_drafter` (module docstring); answers the run."""
    from abacus.modules.agents.api import open_capability_run
    from abacus.modules.tax.entity_run_plan import consent_in_force

    if not await consent_in_force(ctx.tenant, return_id):
        raise ConsentRequired(facts={"return_id": str(return_id)})
    async with tenant_session(ctx.tenant) as session:
        engagement = await session.scalar(
            text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
    if engagement is None:
        raise NotFound("tax_return")
    keys = [k for k in sections if k in SECTION_KEYS]
    run_id = await open_capability_run(
        ctx,
        agent_id=CAPABILITY,
        engagement_id=UUID(str(engagement)),
        inputs={"return_id": str(return_id), "sections": keys},
        work_item_ref=f"memo:{return_id}",
    )
    await dispatch(
        MemoDraftWorkflow,
        MemoDraftInput(str(ctx.tenant_id), str(run_id), str(return_id), keys),
        id=f"memo-draft:{ctx.tenant_id}:{run_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


async def draft_now(tenant_id: UUID, run_id: UUID, return_id: UUID, keys: Sequence[str]) -> str:
    """The run's step, as the agent: code's facts in, T-05-T48's drafter, the version stored."""
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context
    from abacus.modules.tax.memo_drafter import draft_memo
    from abacus.modules.tax.overview import tax_year_of

    try:
        agent = await load_run_v2_context(tenant_id, run_id)
    except AgentRunNotRunning:
        return "run_ended"
    if agent.engagement_id is None:
        return "refused"
    form, values, now = await facts_now(agent.tenant, return_id)
    memo = await memo_row(agent.tenant, return_id)
    affected: list[str] | None = list(keys) or None
    if affected is None and memo is not None and memo.version:
        _, drafted_at = await _version(agent.tenant, memo)
        changed = affected_sections(await facts_then(agent.tenant, return_id, drafted_at), now)
        affected = changed or None
    name = await _entity_name(agent.tenant, return_id)
    given = DraftMemoInput(
        entity_name=str(name or "The partnership")[:200],
        tax_year=await tax_year_of(agent.tenant, return_id),
        sections=list(affected or SECTION_KEYS),
        facts=[f.fact for f in now],
        sources=sources_of(form, values, now),
    )
    done = await draft_memo(
        agent, return_id=return_id, engagement_id=agent.engagement_id,
        on_behalf_of=agent.initiator.user_id, given=given, affected=affected,
    )  # fmt: skip
    return done.outcome


async def _entity_name(tenant: TenantContext, return_id: UUID) -> str | None:
    """The filing entity's name, through its owners (never their tables)."""
    from abacus.modules.engagements.api import work_item_tri_subject
    from abacus.modules.organisations.api import client_names

    subject = await work_item_tri_subject(tenant, return_id)
    if subject is None or subject.entity_id is None:
        return None
    async with tenant_session(tenant) as session:
        found = await client_names(session, [subject.entity_id])
    names = found.get(subject.entity_id)
    return None if names is None else names.client_entity_name


@dataclass(frozen=True)
class MemoDraftInput:
    tenant_id: str
    run_id: str
    return_id: str
    sections: list[str]


_SHORT: Final = timedelta(seconds=30)
_TIMEOUT: Final = timedelta(minutes=5)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="MemoDraftWorkflow")
class MemoDraftWorkflow:
    """Orchestration only: running, the draft activity, then succeeded or failed."""

    async def _state(self, p: MemoDraftInput, state: str, reason: str | None) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, None],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: MemoDraftInput) -> str:
        await self._state(p, "running", None)
        outcome = await workflow.execute_activity(
            "tax.memo.draft",
            p,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if outcome != "drafted":
            await self._state(p, "failed", outcome)
            return "failed"
        await self._state(p, "succeeded", None)
        return outcome


@activity.defn(name="tax.memo.draft")
async def draft_activity(p: MemoDraftInput) -> str:
    return await draft_now(UUID(p.tenant_id), UUID(p.run_id), UUID(p.return_id), p.sections)


WORKFLOWS: dict[type, WorkClass] = {MemoDraftWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (draft_activity,)


# --- a person's section edit --------------------------------------------------------------------

_INSERT_VERSION: Final = text(
    "INSERT INTO preparer_memo_versions (tenant_id, engagement_id, work_item_id, memo_id, "
    "version_no, sections, cause, created_by_kind, content_hash, figure_fingerprint) "
    "VALUES (:t, :e, :r, :m, :v, CAST(:sections AS jsonb), 'edit', 'human', :hash, :fp)"
)
_MOVE: Final = text(
    "UPDATE preparer_memos SET current_version_no = :v, content_hash = :hash, "
    "updated_at = clock_timestamp() WHERE id = :m AND current_version_no = :seen"
)


async def edit_section(
    ctx: AuthContext, return_id: UUID, key: str, *, expected_version: int, body: str
) -> MemoSectionView:
    """The person's words replace the section (human-owned from now on, P-24)."""
    from abacus.modules.tax.memo_drafter import Stored, content_hash_of

    if key not in SECTION_KEYS:
        raise NotFound("memo_section")
    memo = await memo_row(ctx.tenant, return_id)
    if memo is None or memo.version == 0:
        raise MemoNotDrafted
    if expected_version != memo.version:
        raise MemoVersionConflict(facts={"current_version": memo.version})
    sections, _ = await _version(ctx.tenant, memo)
    edited: dict[str, object] = {
        "key": key,
        "segments": [{"text": body.strip(), "citations": []}],
        "human_owned": True,
    }
    out: list[dict[str, object]] = [edited if str(s.get("key")) == key else s for s in sections]
    if not any(str(s.get("key")) == key for s in sections):
        out.append(edited)
    stored = [
        Stored(str(s["key"]), tuple(cast(list[dict[str, object]], s.get("segments") or [])),
               bool(s.get("human_owned")), bool(s.get("unsupported", False)))
        for s in out
    ]  # fmt: skip
    digest = content_hash_of(stored)
    version = memo.version + 1
    scope = {"t": ctx.tenant_id, "e": memo.engagement_id, "r": return_id, "m": memo.id}
    async with uow(ctx.tenant) as tx:
        moved_row = await tx.session.execute(
            _MOVE, {"m": memo.id, "v": version, "hash": digest, "seen": memo.version}
        )
        if moved_row.rowcount != 1:  # type: ignore[attr-defined] -- an UPDATE's CursorResult
            raise MemoVersionConflict(facts={"current_version": memo.version})
        await tx.session.execute(
            _INSERT_VERSION,
            {**scope, "v": version, "sections": json.dumps([s.as_json() for s in stored]),
             "hash": digest, "fp": memo.fingerprint},
        )  # fmt: skip
        await tx.session.execute(
            _EVENT, {**scope, "event": "section_edited", "v": version,
                     "ref": json.dumps({"section": key})},
        )  # fmt: skip
        tx.record(
            "tax_memo.section_edited",
            target=Target(TARGET, memo.id),
            after=Ref(version_no=version, content_hash=digest),  # the section is the version row's
            scope=Scope(engagement_id=memo.engagement_id, work_item_id=return_id),
        )
    return MemoSectionView(key, SECTION_TITLES[key], body.strip(), True)


# --- L1 adopt and L2 approve (P-04 sign-offs) ------------------------------------------------


async def preparers(tenant: TenantContext, memo_id: UUID) -> frozenset[UUID]:
    """Whoever a draft acted for and whoever adopted it (L1): never the L2 approver."""
    from abacus.modules.review.api import sign_off_states

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PREPARERS, {"m": memo_id})).all()
    acted = {UUID(str(r[0])) for r in rows}
    memo_hash = await _hash_of(tenant, memo_id)
    states = (await sign_off_states(tenant, TARGET, [memo_id], {memo_id: memo_hash}))[memo_id]
    adopters = {s.signed_by for s in states if s.level == 1 and s.signed_by is not None}
    return frozenset(acted | adopters)


async def _hash_of(tenant: TenantContext, memo_id: UUID) -> str:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT content_hash FROM preparer_memos WHERE id = :m"), {"m": memo_id}
        )
    return str(found or "")


async def sign_memo(
    ctx: AuthContext, return_id: UUID, *, level: Literal[1, 2], seen_hash: str
) -> UUID:
    """L1 adopt or L2 approve (module docstring); answers P-04's sign-off id."""
    from abacus.modules.review.api import STATEMENTS, sign_target

    memo = await memo_row(ctx.tenant, return_id)
    if memo is None or memo.version == 0:
        raise MemoNotDrafted
    if level == 2 and ctx.user_id in await preparers(ctx.tenant, memo.id):
        raise PreparerCannotApprove(facts={"return_id": str(return_id)})
    signed = await sign_target(ctx, TARGET, memo.id, level, seen_hash, STATEMENTS[level].version)
    event = "adopted" if level == 1 else "approved"
    scope = {"t": ctx.tenant_id, "e": memo.engagement_id, "r": return_id, "m": memo.id}
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _EVENT, {**scope, "event": event, "v": memo.version,
                     "ref": json.dumps({"sign_off": str(signed.id)})},
        )  # fmt: skip
        if level == 2:
            await _write_opportunities(tx, ctx, memo, return_id)
        tx.record(
            f"tax_memo.{event}",
            target=Target(TARGET, memo.id),
            after=Ref(version_no=memo.version, sign_off=signed.id),
            scope=Scope(engagement_id=memo.engagement_id, work_item_id=return_id),
        )
    return signed.id


_OPPORTUNITY: Final = text(
    "INSERT INTO planning_opportunities (tenant_id, engagement_id, work_item_id, memo_id, "
    "source_kind, title, body) VALUES (:t, :e, :r, :m, 'memo', :title, CAST(:body AS jsonb))"
)


async def _write_opportunities(
    tx: object, ctx: AuthContext, memo: MemoRow, return_id: UUID
) -> int:
    """The approved memo's opportunities section, one row per segment (title: its first
    sentence)."""
    from abacus.kernel.uow import UnitOfWork

    if not isinstance(tx, UnitOfWork):
        return 0
    sections, _ = await _version(ctx.tenant, memo)
    found = next((s for s in sections if s.get("key") == "opportunities"), None)
    if found is None:
        return 0
    n = 0
    for segment in cast(list[Mapping[str, object]], found.get("segments") or []):
        body = str(segment.get("text", "")).strip()
        if not body or body == "Unsupported":
            continue
        title = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0][:200]
        await tx.session.execute(
            _OPPORTUNITY,
            {"t": ctx.tenant_id, "e": memo.engagement_id, "r": return_id, "m": memo.id,
             "title": title, "body": json.dumps([dict(segment)])},
        )  # fmt: skip
        n += 1
    return n


async def opportunities(ctx: AuthContext, return_id: UUID) -> list[tuple[UUID, str]]:
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            text(
                "SELECT id, title FROM planning_opportunities WHERE work_item_id = :r "
                "AND status = 'open' ORDER BY created_at, id"
            ),
            {"r": return_id},
        )
        return [(UUID(str(r.id)), str(r.title)) for r in rows]


# --- staleness ---------------------------------------------------------------------------------


async def check_stale(tenant_id: UUID, return_id: UUID) -> bool:
    """An adopted or approved memo whose figures moved gets one `went_stale` (as the system)."""
    from abacus.modules.engagements.api import function_holders
    from abacus.modules.tax.entity_decisions import TaxMemoWentStale

    system = TenantContext(tenant_id, "system", f"memo_stale:{return_id}")
    memo = await memo_row(system, return_id)
    if memo is None or memo.version == 0 or memo.fingerprint is None:
        return False
    if await _last_event(system, memo.id) not in ("adopted", "approved"):
        return False
    _, _, now = await facts_now(system, return_id)
    if fingerprint_of([f.fact for f in now]) == memo.fingerprint:
        return False
    _, drafted_at = await _version(system, memo)
    lines = [line for _, line in moved(await facts_then(system, return_id, drafted_at), now)]
    holders = await function_holders(system, return_id)
    scope = {"t": tenant_id, "e": memo.engagement_id, "r": return_id, "m": memo.id}
    async with uow(system) as tx:
        await tx.session.execute(
            _EVENT, {**scope, "event": "went_stale", "v": memo.version,
                     "ref": json.dumps({"figures": len(lines)})},
        )  # fmt: skip
        tx.emit(
            TaxMemoWentStale(
                work_item_id=return_id, engagement_id=memo.engagement_id, memo_id=memo.id,
                recipient_user_ids=sorted({u for users in holders.values() for u in users}),
            )
        )  # fmt: skip
        tx.record(
            "tax_memo.went_stale",
            target=Target(TARGET, memo.id),
            after=Ref(version_no=memo.version, figures=len(lines)),
            scope=Scope(engagement_id=memo.engagement_id, work_item_id=return_id),
        )
    return True


# --- the reviewable -----------------------------------------------------------------------------


async def _reviewable_facts(tenant: TenantContext, memo_id: UUID) -> object | None:
    from abacus.modules.review.api import ReviewableFacts

    async with tenant_session(tenant) as session:
        r = (
            await session.execute(
                text(
                    "SELECT engagement_id, work_item_id, content_hash, current_version_no "
                    "FROM preparer_memos WHERE id = :m"
                ),
                {"m": memo_id},
            )
        ).first()
    if r is None or not r.current_version_no:
        return None
    return ReviewableFacts(
        target_type=TARGET,
        target_id=memo_id,
        engagement_id=r.engagement_id,
        content_hash=str(r.content_hash or ""),
        version_no=int(r.current_version_no),
        preparer_user_ids=await preparers(tenant, memo_id),
        required_levels=(1, 2),
        label="Preparer memo",
        context_label="Entity return",
        work_item_id=r.work_item_id,
    )


def register() -> None:
    """At the tax api's import: the memo as a P-04 reviewable."""
    from abacus.modules.review.api import register_reviewable_facts

    register_reviewable_facts(TARGET, _reviewable_facts)  # type: ignore[arg-type] -- ReviewableFacts, typed loosely for the lazy import


__all__ = [
    "ACTIVITIES",
    "SECTION_TITLES",
    "TARGET",
    "WORKFLOWS",
    "ConsentRequired",
    "MemoDraftWorkflow",
    "MemoNotDrafted",
    "MemoSectionView",
    "MemoVersionConflict",
    "MemoView",
    "PreparerCannotApprove",
    "SectionFact",
    "affected_sections",
    "check_stale",
    "edit_section",
    "handle_of",
    "memo_facts",
    "money",
    "moved",
    "opportunities",
    "read_memo",
    "register",
    "sign_memo",
    "sources_of",
    "start_draft",
]


# --- T-05-T62 (DEC-4937): the synthetic-only memo recorder ---------------------------------------


async def record_synthetic_memo(
    ctx: AuthContext,
    return_id: UUID,
    *,
    run_id: UUID,
    on_behalf_of: UUID,
    sections: Sequence[tuple[str, str, int | None]],
) -> int:
    """The scenario loader's one way to put a drafted memo in place for the Brightwater Hale
    tenant: one agent-drafted version from `sections` (`(key, text, source n)`), its fingerprint
    from code's facts now (so a later figure change turns it Stale by code), and a `drafted` event
    naming the recorded run. Refuses every firm that is not synthetic (404). Idempotent: a memo
    that has a version is left as it is."""
    from abacus.kernel.errors import NotFound
    from abacus.modules.identity.api import is_synthetic_firm
    from abacus.modules.tax.memo_drafter import Stored, content_hash_of

    if not await is_synthetic_firm(ctx.tenant):
        raise NotFound("preparer_memo")
    existing = await memo_row(ctx.tenant, return_id)
    if existing is not None and existing.version:
        return existing.version
    _form_of, _values, now = await facts_now(ctx.tenant, return_id)
    stored = [
        Stored(key, ({"text": body, "citations": (
            [{"n": n, "start": 0, "end": len(body)}] if n is not None else [])},), False)
        for key, body, n in sections
    ]  # fmt: skip
    digest = content_hash_of(stored)
    fp = fingerprint_of([f.fact for f in now])
    from abacus.modules.engagements.api import work_item_engagement

    engagement_id = await work_item_engagement(ctx.tenant, return_id)
    if engagement_id is None:
        raise NotFound("tax_return")
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO preparer_memos (tenant_id, engagement_id, work_item_id) "
                "VALUES (:t, :e, :r) ON CONFLICT (work_item_id) DO NOTHING"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "r": return_id},
        )
        memo_id = await tx.session.scalar(
            text("SELECT id FROM preparer_memos WHERE work_item_id = :r FOR UPDATE"),
            {"r": return_id},
        )
        scope = {"t": ctx.tenant_id, "e": engagement_id, "r": return_id, "m": memo_id}
        await tx.session.execute(
            text(
                "INSERT INTO preparer_memo_versions (tenant_id, engagement_id, work_item_id, "
                "memo_id, version_no, sections, cause, created_by_kind, agent_run_id, "
                "on_behalf_of_user_id, content_hash, figure_fingerprint) VALUES (:t, :e, :r, :m, "
                "1, CAST(:sections AS jsonb), 'draft', 'agent', :run, :by, :hash, :fp)"
            ),
            {**scope, "sections": json.dumps([s.as_json() for s in stored]), "run": run_id,
             "by": on_behalf_of, "hash": digest, "fp": fp},  # fmt: skip
        )
        await tx.session.execute(
            text(
                "UPDATE preparer_memos SET current_version_no = 1, drafted_run_id = :run, "
                "content_hash = :hash, figure_fingerprint = :fp, updated_at = clock_timestamp() "
                "WHERE id = :m"
            ),
            {"m": memo_id, "run": run_id, "hash": digest, "fp": fp},
        )
        await tx.session.execute(
            _EVENT,
            {**scope, "event": "drafted", "v": 1,
             "ref": json.dumps({"dropped": 0, "run": str(run_id)})},  # fmt: skip
        )
        tx.record(
            "tax_memo.drafted",
            target=Target(TARGET, memo_id),
            after=Ref(version_no=1, content_hash=digest, run=run_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return 1
