"""Account mapping and the financial statements built from it (SPEC-316; TASK-345; A-03, AUD-20).

A firm's grouping set (its taxonomy) is content: imported as CSV into a draft version with any
problems listed, then published by a person. A trial balance's mapping set uses one published
version. Each account maps to an FS line by a person's edit (the newest counts) or else by the
version's account-number ranges (first rule wins), computed on read, so a new trial balance
version maps without writing anything. Code computes every amount, total and check (ADR-050).

Statements: each FS line's amount is its accounts' net (debit - credit) presented on the line's
normal side; groupings and classes total; net income is revenue - expenses; the balance sheet
balances when assets = liabilities + equity + net income (a pre-closing trial balance).
Ledger stays dependency-free: callers authorise and pass identifiers.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import pairwise
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork

# The rules moved to the pure compute package (A-03-T08); re-exported for this module's callers.
from abacus.modules.ledger.compute.mapping import Method as Method
from abacus.modules.ledger.compute.mapping import account_key as account_key
from abacus.modules.ledger.compute.mapping import normalised_code as normalised_code
from abacus.modules.ledger.compute.mapping import resolve_line as resolve_line
from abacus.modules.ledger.compute.mapping import rule_line as rule_line
from abacus.modules.ledger.mapping_repository import (
    catalogue_rows,
    discard_drafts,
    edits_of,
    get_mapping_set,
    get_version,
    grouping_sets,
    insert_edits,
    insert_fs_line,
    insert_grouping,
    insert_mapping_set,
    insert_rules,
    insert_set,
    insert_version,
    mapping_editors,
    mapping_set_for,
    newest_edits,
    next_version_no,
    publish,
    recent_fs_lines,
    set_by_key,
    version_by_number,
    versions_of_sets,
)
from abacus.modules.ledger.models import MappingSet, MappingSetEdit
from abacus.modules.ledger.trial_balances import trial_balance_view

CLASSES: Final = ("assets", "liabilities", "equity", "revenue", "expenses")
HEADER: Final = (
    "grouping_key",
    "grouping_label",
    "class",
    "fs_line_key",
    "fs_line_label",
    "normal_balance",
    "account_from",
    "account_to",
)
MAX_ROWS: Final = 2000
_ZERO: Final = Decimal("0.00")
Class = Literal["assets", "liabilities", "equity", "revenue", "expenses"]


class GroupingSetInvalid(DomainInvalid):
    code = "grouping_set_invalid"


class VersionHasProblems(DomainConflict):
    code = "grouping_set_has_problems"


class AlreadyPublished(DomainConflict):
    code = "grouping_set_published"


class VersionNotDraft(DomainConflict):
    code = "grouping_set_not_draft"  # A-03-T06: a discarded version is never published


class MappingExists(DomainConflict):
    code = "mapping_set_exists"


class MappingInvalid(DomainInvalid):
    code = "mapping_invalid"


# --- the taxonomy (pure) ----------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedLine:
    key: str
    label: str
    grouping: str
    normal_balance: str


@dataclass(frozen=True)
class ParsedGrouping:
    key: str
    label: str
    class_: str


@dataclass(frozen=True)
class Problem:
    row: int
    code: str
    detail: str
    sheet: str = ""  # A-03-T06: the workbook sheet ("" for a CSV)


@dataclass(frozen=True)
class ParsedGroupingSet:
    groupings: list[ParsedGrouping]
    lines: list[ParsedLine]
    ranges: list[tuple[str, str, str]]  # from, to, fs line key
    problems: list[Problem]
    payload_hash: str


def parse_grouping_set(text: str) -> ParsedGroupingSet:
    """A grouping set from CSV: one row per FS line, or per extra range of a line."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    problems: list[Problem] = []
    if not rows or tuple(c.strip().lower() for c in rows[0][: len(HEADER)]) != HEADER:
        return ParsedGroupingSet([], [], [], [Problem(1, "header", ",".join(HEADER))], "0" * 64)
    groupings: dict[str, ParsedGrouping] = {}
    lines: dict[str, ParsedLine] = {}
    ranges: list[tuple[str, str, str]] = []
    range_rows: list[int] = []
    for number, raw in enumerate(rows[1 : MAX_ROWS + 1], start=2):
        cells = [c.strip() for c in raw] + [""] * (len(HEADER) - len(raw))
        g_key, g_label, cls, l_key, l_label, normal, a_from, a_to = cells[: len(HEADER)]
        if not any(cells):
            continue
        if not g_key or not l_key:
            problems.append(Problem(number, "missing_key", "grouping_key and fs_line_key"))
            continue
        cls = cls.lower()
        if cls not in CLASSES:
            problems.append(Problem(number, "class_invalid", cls))
            continue
        if normal.lower() not in ("debit", "credit"):
            problems.append(Problem(number, "normal_balance_invalid", normal))
            continue
        seen = groupings.get(g_key)
        if seen is not None and (seen.class_ != cls or (g_label and seen.label != g_label)):
            problems.append(Problem(number, "duplicate_key", g_key))
            continue
        groupings.setdefault(g_key, ParsedGrouping(g_key, g_label or g_key, cls))
        line = lines.get(l_key)
        if line is not None and (line.grouping != g_key or (l_label and line.label != l_label)):
            problems.append(Problem(number, "duplicate_key", l_key))
            continue
        lines.setdefault(l_key, ParsedLine(l_key, l_label or l_key, g_key, normal.lower()))
        if a_from or a_to:
            low, high = a_from or a_to, a_to or a_from
            if account_key(low) > account_key(high):
                problems.append(Problem(number, "range_invalid", f"{low}-{high}"))
                continue
            ranges.append((low, high, l_key))
            range_rows.append(number)
    if len(rows) - 1 > MAX_ROWS:
        problems.append(Problem(MAX_ROWS + 2, "too_many_rows", str(MAX_ROWS)))
    return finish_grouping_set(
        list(groupings.values()), list(lines.values()), ranges, range_rows, problems
    )


def finish_grouping_set(
    groupings: list[ParsedGrouping],
    lines: list[ParsedLine],
    ranges: list[tuple[str, str, str]],
    range_rows: list[int],
    problems: list[Problem],
    sheet: str = "",
) -> ParsedGroupingSet:
    """Overlapping ranges, each reported on the later range's own row (A-03-T06), and the
    payload hash of the canonical content."""
    order = sorted(range(len(ranges)), key=lambda i: account_key(ranges[i][0]))
    for i, j in pairwise(order):
        a, b = ranges[i], ranges[j]
        if account_key(b[0]) <= account_key(a[1]):
            detail = f"{a[0]}-{a[1]} and {b[0]}-{b[1]}"
            problems.append(Problem(range_rows[j], "overlapping_range", detail, sheet))
    canonical = "\n".join(
        [f"g|{g.key}|{g.label}|{g.class_}" for g in groupings]
        + [f"l|{v.key}|{v.label}|{v.grouping}|{v.normal_balance}" for v in lines]
        + [f"r|{a}|{b}|{k}" for a, b, k in ranges]
    )
    return ParsedGroupingSet(
        groupings, lines, ranges, problems, hashlib.sha256(canonical.encode()).hexdigest()
    )


# --- views ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FsLineView:
    id: UUID
    key: str
    label: str
    normal_balance: str
    grouping_key: str


@dataclass(frozen=True)
class GroupingView:
    id: UUID
    key: str
    label: str
    class_: str
    lines: list[FsLineView]


@dataclass(frozen=True)
class VersionView:
    id: UUID
    set_key: str
    set_name: str
    version: int
    status: str
    problems: list[Problem]
    created_at: datetime
    published_at: datetime | None
    # A-03-T06 (C9 v2 catalogue): additive, defaulted so v0's callers are unchanged.
    set_id: UUID | None = None
    effective_from: date | None = None
    published_by: UUID | None = None


@dataclass(frozen=True)
class MappedAccount:
    account_code: str
    account_name: str
    eoy: Decimal
    final: Decimal | None
    boy: Decimal | None
    fs_line_id: UUID | None
    method: Literal["manual", "prior_year", "number_range"] | None
    edited_by: UUID | None
    edited_at: datetime | None


@dataclass(frozen=True)
class MappingView:
    mapping_set_id: UUID
    version: VersionView
    groupings: list[GroupingView]
    accounts: list[MappedAccount]
    mapped: int
    unmapped: int
    manual: int
    content_hash: str
    # A-03-T08 tallies, computed on read.
    prior_year: int = 0
    number_range: int = 0
    tb_balanced: bool = True
    fs_line_keys: dict[UUID, str] | None = None


@dataclass(frozen=True)
class StatementLine:
    key: str
    label: str
    cy: Decimal
    py: Decimal | None


@dataclass(frozen=True)
class StatementGroup:
    key: str
    label: str
    class_: str
    lines: list[StatementLine]
    cy: Decimal
    py: Decimal | None


@dataclass(frozen=True)
class Statements:
    layer: str
    groups: list[StatementGroup]
    totals: dict[str, Decimal]  # per class, presented
    py_totals: dict[str, Decimal] | None
    net_income: Decimal
    py_net_income: Decimal | None
    difference: Decimal  # assets - (liabilities + equity + net income)
    balanced: bool
    unmapped: int


def presented(net: Decimal, normal_balance: str) -> Decimal:
    return net if normal_balance == "debit" else -net


def content_hash(version_id: UUID, mapping: Sequence[tuple[str, UUID | None]]) -> str:
    text = (
        str(version_id)
        + "|"
        + "|".join(f"{c}={f}" for c, f in sorted(mapping, key=lambda m: m[0]))
    )
    return hashlib.sha256(text.encode()).hexdigest()


def build_statements(
    groupings: Sequence[GroupingView],
    accounts: Sequence[MappedAccount],
    layer: str,
) -> Statements:
    """By code: FS line amounts, grouping and class totals, net income, the balance check."""
    has_prior = any(a.boy is not None for a in accounts)
    line_of = {line.id: line for g in groupings for line in g.lines}
    cy: dict[UUID, Decimal] = {}
    py: dict[UUID, Decimal] = {}
    for a in accounts:
        if a.fs_line_id is None or a.fs_line_id not in line_of:
            continue
        normal = line_of[a.fs_line_id].normal_balance
        net = a.final if layer == "final" and a.final is not None else a.eoy
        cy[a.fs_line_id] = cy.get(a.fs_line_id, _ZERO) + presented(net, normal)
        if a.boy is not None:
            py[a.fs_line_id] = py.get(a.fs_line_id, _ZERO) + presented(a.boy, normal)
    groups: list[StatementGroup] = []
    totals: dict[str, Decimal] = dict.fromkeys(CLASSES, _ZERO)
    py_totals: dict[str, Decimal] | None = dict.fromkeys(CLASSES, _ZERO) if has_prior else None
    for g in groupings:
        lines = [
            StatementLine(
                line.key,
                line.label,
                cy.get(line.id, _ZERO),
                py.get(line.id, _ZERO) if has_prior else None,
            )
            for line in g.lines
        ]
        g_cy = sum((line.cy for line in lines), _ZERO)
        g_py = sum((line.py or _ZERO for line in lines), _ZERO) if has_prior else None
        groups.append(StatementGroup(g.key, g.label, g.class_, lines, g_cy, g_py))
        totals[g.class_] += g_cy
        if py_totals is not None and g_py is not None:
            py_totals[g.class_] += g_py
    net_income = totals["revenue"] - totals["expenses"]
    py_net = py_totals["revenue"] - py_totals["expenses"] if py_totals is not None else None
    difference = totals["assets"] - (totals["liabilities"] + totals["equity"] + net_income)
    return Statements(
        layer,
        groups,
        totals,
        py_totals,
        net_income,
        py_net,
        difference,
        difference == 0,
        sum(1 for a in accounts if a.fs_line_id is None),
    )


# --- service (callers authorise first) --------------------------------------------------------


async def import_grouping_set(
    tx: UnitOfWork, *, tenant_id: UUID, key: str, name: str, text: str, user_id: UUID
) -> UUID:
    """A draft version from CSV, with its problems; rows are written only when there are none."""
    return await import_parsed_grouping_set(
        tx,
        tenant_id=tenant_id,
        key=key,
        name=name,
        parsed=parse_grouping_set(text),
        user_id=user_id,
    )


async def import_parsed_grouping_set(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    key: str,
    name: str,
    parsed: ParsedGroupingSet,
    user_id: UUID,
) -> UUID:
    """A draft version from a parsed CSV or workbook (A-03-T06). The set's earlier draft is
    discarded in the same unit, so a set holds one live draft (0521)."""
    key, name = key.strip().lower(), name.strip()
    if not key or not 1 <= len(name) <= 120:
        raise GroupingSetInvalid("name")
    found = await set_by_key(tx.session, key)
    set_id = (
        found.id
        if found is not None
        else await insert_set(
            tx.session, tenant_id=tenant_id, key=key, name=name, created_by=user_id
        )
    )
    discarded = await discard_drafts(tx.session, set_id) if found is not None else 0
    version_id = await insert_version(
        tx.session,
        tenant_id=tenant_id,
        grouping_set_id=set_id,
        version=await next_version_no(tx.session, set_id),
        payload_hash=parsed.payload_hash,
        problems=[
            {"row": p.row, "code": p.code, "detail": p.detail, "sheet": p.sheet}
            for p in parsed.problems
        ],
        created_by=user_id,
    )
    if not parsed.problems:
        grouping_ids: dict[str, UUID] = {}
        for position, g in enumerate(parsed.groupings):
            grouping_ids[g.key] = await insert_grouping(
                tx.session,
                tenant_id=tenant_id,
                version_id=version_id,
                key=g.key,
                label=g.label,
                class_=g.class_,
                position=position,
            )
        line_ids: dict[str, UUID] = {}
        for position, line in enumerate(parsed.lines):
            line_ids[line.key] = await insert_fs_line(
                tx.session,
                tenant_id=tenant_id,
                version_id=version_id,
                grouping_id=grouping_ids[line.grouping],
                key=line.key,
                label=line.label,
                normal_balance=line.normal_balance,
                position=position,
            )
        await insert_rules(
            tx.session,
            [
                {
                    "tenant_id": tenant_id,
                    "version_id": version_id,
                    "position": position,
                    "account_from": low,
                    "account_to": high,
                    "fs_line_id": line_ids[line_key],
                }
                for position, (low, high, line_key) in enumerate(parsed.ranges)
            ],
        )
    tx.record(
        "grouping_set.imported",
        target=Target("grouping_set_version", version_id),
        after=Ref(problems=len(parsed.problems), discarded=discarded),
    )
    return version_id


async def publish_version(
    tx: UnitOfWork,
    *,
    version_id: UUID,
    user_id: UUID,
    actor_kind: str,
    effective_from: date,
) -> None:
    """A person publishes a clean draft with its effective date; it freezes (0079, 0521)."""
    found = await get_version(tx.session, version_id)
    if found is None:
        raise NotFound("grouping_set_version")
    if found.status == "published":
        raise AlreadyPublished(str(version_id))
    if found.status != "draft":
        raise VersionNotDraft(str(version_id))
    if found.problems:
        raise VersionHasProblems(str(len(found.problems)))
    await publish(
        tx.session,
        version_id,
        status="published",
        published_by=user_id,
        published_actor_kind=actor_kind,
        effective_from=effective_from,
    )
    tx.record("grouping_set.published", target=Target("grouping_set_version", version_id))


async def grouping_set_versions(tenant: TenantContext) -> list[VersionView]:
    async with tenant_session(tenant) as session:
        sets = {s.id: s for s in await grouping_sets(session)}
        versions = await versions_of_sets(session, list(sets))
    return [
        VersionView(
            v.id,
            sets[v.grouping_set_id].key,
            sets[v.grouping_set_id].name,
            v.version,
            v.status,
            [
                Problem(int(p["row"]), str(p["code"]), str(p["detail"]), str(p.get("sheet", "")))
                for p in v.problems
            ],
            v.created_at,
            v.published_at,
            set_id=v.grouping_set_id,
            effective_from=v.effective_from,
            published_by=v.published_by,
        )
        for v in versions
    ]


async def grouping_catalogue(tenant: TenantContext, version_id: UUID) -> list[GroupingView]:
    """C9 v2 (A-03-T06): a version's groupings with their FS lines, in order."""
    views, _ = await _catalogue(tenant, version_id)
    return views


async def grouping_version_id(tenant: TenantContext, set_id: UUID, version_no: int) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await version_by_number(session, set_id, version_no)


async def recently_used(
    tenant: TenantContext, version_id: UUID, user_id: UUID, limit: int = 5
) -> list[UUID]:
    """The FS lines of this version the person most recently chose, newest first: their own
    edits only, so no other person's work and no engagement shows through (INV-3)."""
    async with tenant_session(tenant) as session:
        return await recent_fs_lines(session, version_id, user_id, limit)


async def _catalogue(
    tenant: TenantContext, version_id: UUID
) -> tuple[list[GroupingView], list[tuple[str, str, UUID]]]:
    async with tenant_session(tenant) as session:
        groupings, lines, rules = await catalogue_rows(session, version_id)
    by_grouping: dict[UUID, list[FsLineView]] = {}
    keys = {g.id: g.key for g in groupings}
    for line in lines:
        by_grouping.setdefault(line.grouping_id, []).append(
            FsLineView(line.id, line.key, line.label, line.normal_balance, keys[line.grouping_id])
        )
    views = [
        GroupingView(g.id, g.key, g.label, g.class_, by_grouping.get(g.id, [])) for g in groupings
    ]
    return views, [(r.account_from, r.account_to, r.fs_line_id) for r in rules]


async def create_mapping_set(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    tb_id: UUID,
    version_id: UUID,
    user_id: UUID,
) -> UUID:
    version = await get_version(tx.session, version_id)
    if version is None or version.status != "published":
        raise MappingInvalid("version_not_published")
    if await mapping_set_for(tx.session, tb_id) is not None:
        raise MappingExists(str(tb_id))
    mapping_id = await insert_mapping_set(
        tx.session,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        trial_balance_id=tb_id,
        grouping_set_version_id=version_id,
        created_by=user_id,
    )
    tx.record("mapping_set.created", target=Target("mapping_set", mapping_id))
    return mapping_id


async def mapping_set_of(tenant: TenantContext, tb_id: UUID) -> MappingSet | None:
    async with tenant_session(tenant) as session:
        return await mapping_set_for(session, tb_id)


@dataclass(frozen=True)
class MappingAuthors:
    """Who prepared a mapping set, from its own records (P-04-T15): its creator and everyone who
    edited a mapping in it."""

    mapping_set_id: UUID
    engagement_id: UUID
    trial_balance_id: UUID
    authors: frozenset[UUID]


async def mapping_set_authors(
    tenant: TenantContext, mapping_set_id: UUID
) -> MappingAuthors | None:
    """For callers authorised on the mapping set's engagement; None when unknown."""
    async with tenant_session(tenant) as session:
        found = await get_mapping_set(session, mapping_set_id)
        if found is None:
            return None
        editors = await mapping_editors(session, found.id)
    return MappingAuthors(
        found.id,
        found.engagement_id,
        found.trial_balance_id,
        frozenset(editors | {found.created_by}),
    )


async def mapping_view(
    tenant: TenantContext,
    engagement_id: UUID,
    tb_id: UUID,
    prior: Mapping[str, str] | None = None,
) -> MappingView | None:
    """The trial balance's current version mapped (A-03-T08): a person's edit first, then the
    prior year's line for the same normalised code (matched by FS-line key, so a later version
    of the grouping set still matches), then the version's number ranges, else unmapped."""
    async with tenant_session(tenant) as session:
        found = await mapping_set_for(session, tb_id)
        if found is None:
            return None
        edits = {e.account_code: e for e in await newest_edits(session, found.id)}
    tb = await trial_balance_view(tenant, engagement_id, tb_id)
    groupings, ranges = await _catalogue(tenant, found.grouping_set_version_id)
    version = next(
        v for v in await grouping_set_versions(tenant) if v.id == found.grouping_set_version_id
    )
    by_key = {line.key: line.id for g in groupings for line in g.lines}
    accounts: list[MappedAccount] = []
    for line in tb.lines:
        edit = edits.get(line.account_code)
        fs_line, method = resolve_line(
            line.account_code,
            edit.fs_line_id if edit is not None else None,
            prior or {},
            by_key,
            ranges,
        )
        accounts.append(
            MappedAccount(
                line.account_code,
                line.account_name,
                line.eoy,
                line.final,
                line.boy,
                fs_line,
                method,
                edit.edited_by if edit is not None else None,
                edit.created_at if edit is not None else None,
            )
        )
    unmapped = sum(1 for a in accounts if a.fs_line_id is None)
    return MappingView(
        found.id,
        version,
        groupings,
        accounts,
        len(accounts) - unmapped,
        unmapped,
        sum(1 for a in accounts if a.method == "manual"),
        content_hash(
            found.grouping_set_version_id, [(a.account_code, a.fs_line_id) for a in accounts]
        ),
        sum(1 for a in accounts if a.method == "prior_year"),
        sum(1 for a in accounts if a.method == "number_range"),
        sum((a.eoy for a in accounts), Decimal(0)) == 0,
        {v: k for k, v in by_key.items()},
    )


def prior_keys(view: MappingView) -> dict[str, str]:
    """A finished mapping as the next year's prior: normalised code to FS-line key."""
    keys = view.fs_line_keys or {}
    return {
        normalised_code(a.account_code): keys[a.fs_line_id]
        for a in view.accounts
        if a.fs_line_id is not None and a.fs_line_id in keys
    }


async def published_versions(tenant: TenantContext) -> list[VersionView]:
    return [v for v in await grouping_set_versions(tenant) if v.status == "published"]


async def edit_mappings(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    mapping_set_id: UUID,
    version_id: UUID,
    edits: Sequence[tuple[str, UUID | None]],
    user_id: UUID,
    actor_kind: str,
) -> int:
    """People map accounts to FS lines of the set's version, or back to the rules (None)."""
    if not edits or len(edits) > 500:
        raise MappingInvalid("edits")
    _, lines, _ = await catalogue_rows(tx.session, version_id)
    valid = {line.id for line in lines}
    if any(f is not None and f not in valid for _, f in edits):
        raise MappingInvalid("fs_line")
    await insert_edits(
        tx.session,
        [
            {
                "tenant_id": tenant_id,
                "mapping_set_id": mapping_set_id,
                "account_code": code.strip(),
                "fs_line_id": fs_line,
                "edited_by": user_id,
                "actor_kind": actor_kind,
            }
            for code, fs_line in edits
        ],
    )
    tx.record(
        "account_mapping.edited",
        target=Target("mapping_set", mapping_set_id),
        after=Ref(accounts=len(edits)),
    )
    return len(edits)


async def statements_for(
    tenant: TenantContext,
    engagement_id: UUID,
    tb_id: UUID,
    layer: str,
    prior: Mapping[str, str] | None = None,
) -> Statements | None:
    found = await mapping_view(tenant, engagement_id, tb_id, prior)
    if found is None:
        return None
    return build_statements(found.groupings, found.accounts, layer)


# --- A-03-T08: the C9 v2 reads ----------------------------------------------------------------


async def mapping_set_by_id(tenant: TenantContext, mapping_set_id: UUID) -> MappingSet | None:
    """A mapping set by its id (the caller then authorises on its engagement)."""
    async with tenant_session(tenant) as session:
        return await get_mapping_set(session, mapping_set_id)


@dataclass(frozen=True)
class AccountEdits:
    """An account's edits: how many (the `seen_version` an edit must name), the FS line before
    the newest edit (the "was …"), and who made the newest and when."""

    count: int
    was_fs_line_id: UUID | None
    rule_before: bool  # the newest edit replaced the rules' line (no earlier edit)
    edited_by: UUID
    edited_at: datetime


async def account_edits(tenant: TenantContext, mapping_set_id: UUID) -> dict[str, AccountEdits]:
    async with tenant_session(tenant) as session:
        rows = await edits_of(session, mapping_set_id)
    out: dict[str, AccountEdits] = {}
    by_code: dict[str, list[MappingSetEdit]] = {}
    for row in rows:
        by_code.setdefault(row.account_code, []).append(row)
    for code, edits in by_code.items():
        newest = edits[-1]
        before = edits[-2] if len(edits) > 1 else None
        out[code] = AccountEdits(
            len(edits),
            before.fs_line_id if before is not None else None,
            before is None,
            newest.edited_by,
            newest.created_at,
        )
    return out


@dataclass(frozen=True)
class MappedLine:
    """One FS line of a mapped trial balance: its accounts' debits, credits and net."""

    grouping_key: str
    grouping_label: str
    grouping_class: str
    fs_line_id: UUID
    fs_line_key: str
    fs_line_label: str
    normal_balance: str
    debit: Decimal
    credit: Decimal
    net: Decimal


@dataclass(frozen=True)
class MappedTrialBalance:
    mapping_set_id: UUID
    trial_balance_id: UUID
    trial_balance_version_no: int
    grouping_set_version_id: UUID
    content_hash: str
    lines: list[MappedLine]
    debit: Decimal
    credit: Decimal
    unmapped: int


async def mapped_trial_balance(
    tenant: TenantContext,
    engagement_id: UUID,
    tb_id: UUID,
    prior: Mapping[str, str] | None = None,
) -> MappedTrialBalance | None:
    """C9 v2's one structure (US-6.4): debits, credits and net per FS line, in the catalogue's
    order, by code from the snapshot's lines (ADR-050), with the version and content hash."""
    view = await mapping_view(tenant, engagement_id, tb_id, prior)
    if view is None:
        return None
    tb = await trial_balance_view(tenant, engagement_id, tb_id)
    found = await mapping_set_by_id(tenant, view.mapping_set_id)
    if found is None:
        return None
    sides = {line.account_code: (line.debit, line.credit) for line in tb.lines}
    sums: dict[UUID, tuple[Decimal, Decimal]] = {}
    for account in view.accounts:
        if account.fs_line_id is None:
            continue
        debit, credit = sides.get(account.account_code, (_ZERO, _ZERO))
        d, c = sums.get(account.fs_line_id, (_ZERO, _ZERO))
        sums[account.fs_line_id] = (d + debit, c + credit)
    lines = [
        MappedLine(
            g.key,
            g.label,
            g.class_,
            line.id,
            line.key,
            line.label,
            line.normal_balance,
            sums[line.id][0],
            sums[line.id][1],
            sums[line.id][0] - sums[line.id][1],
        )
        for g in view.groupings
        for line in g.lines
        if line.id in sums
    ]
    return MappedTrialBalance(
        view.mapping_set_id,
        tb_id,
        tb.version.version_no,
        found.grouping_set_version_id,
        view.content_hash,
        lines,
        sum((x.debit for x in lines), _ZERO),
        sum((x.credit for x in lines), _ZERO),
        view.unmapped,
    )
