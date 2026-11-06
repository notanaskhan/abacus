"""The statements service (A-06-T25; A-06 F7; AUD-20; DEC-80; DEC-2304).

`draft` builds a new insert-only version from the ledger's final layer over the C9 taxonomy
(`compute.fs_draft`); `tie_out` proves it (`compute.tie_out`) and records an insert-only run. A
version is out of date when the current trial balance version or the recorded entries differ from
the ones it was drafted from; it is computed on read, never stored. Lineage returns only
C4-verified citations. Checklist answers go through `review.api.record_value`, so every answer has
a field history, and an agent's suggestion stays a suggestion until a person adopts it (INV-1).
The routes have authorised the action and the flag; this module re-reads the row's engagement and
authorises against it wherever the route only had a version or document id.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.evidence.api import verified_citation_ids
from abacus.modules.adjustments.api import recorded_entries
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.ledger.api import (
    EntrySet,
    Statements,
    engagement_trial_balances,
    mapping_view,
    statements_for,
    trial_balance_view,
)
from abacus.modules.reporting.compute import fs_draft, tie_out
from abacus.modules.review.api import FieldOwner, record_value, register_field_owner

JsonRow = dict[str, Any]  # Any: rows and JSON columns from the database
FRAMEWORK: Final = "us_gaap"
_ANSWER_TARGET: Final = "disclosure_checklist_answer"
_ZERO: Final = Decimal(0)


class NoFinalTrialBalance(DomainConflict):
    """Statements draft from a mapped, balanced final layer; there is none yet."""

    code = "final_tb_unavailable"


class ReasonRequired(DomainInvalid):
    """N/A needs a reason line (the database refuses it too)."""

    code = "reason_required"


class StaleAnswer(DomainConflict):
    """The answer changed since it was read (`If-Match`)."""

    code = "version_conflict"


class NoSuggestion(DomainConflict):
    """Only an agent's suggested answer can be adopted."""

    code = "nothing_to_adopt"


class NotAnswered(DomainConflict):
    """Only an answered or adopted item can be reviewed (`facts.item_key`)."""

    code = "not_answered"


@dataclass(frozen=True)
class Source:
    tb_id: UUID
    version_id: UUID
    period_end: date
    statements: Statements
    entries: EntrySet
    accounts_of: dict[str, tuple[str, ...]]


async def _source(tenant: TenantContext, engagement_id: UUID) -> Source:
    tbs = await engagement_trial_balances(tenant, engagement_id)
    if not tbs:
        raise NoFinalTrialBalance
    current = max(tbs, key=lambda t: t.period_end)
    found = await statements_for(tenant, engagement_id, current.id, "final")
    mapped = await mapping_view(tenant, engagement_id, current.id)
    if found is None or mapped is None or not found.balanced:
        raise NoFinalTrialBalance
    view = await trial_balance_view(tenant, engagement_id, current.id)
    keys = mapped.fs_line_keys or {}
    accounts: defaultdict[str, list[str]] = defaultdict(list)
    for account in mapped.accounts:
        if account.fs_line_id is not None and account.fs_line_id in keys:
            accounts[keys[account.fs_line_id]].append(account.account_code)
    return Source(
        current.id,
        view.version.id,
        current.period_end,
        found,
        await recorded_entries(tenant, engagement_id),
        {k: tuple(sorted(v)) for k, v in accounts.items()},
    )


async def _resource_of_document(tenant: TenantContext, document_id: UUID) -> JsonRow:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT id, engagement_id, work_item_id, framework_key, status, "
                        "management_approval, checklist_template_version_id, current_version_no "
                        "FROM statement_documents WHERE id = :d"
                    ),
                    {"d": document_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound("statement_document")
    return dict(row)


async def _version_row(tenant: TenantContext, version_id: UUID) -> JsonRow:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT v.id, v.engagement_id, v.work_item_id, v.statement_document_id, "
                        "v.version_no, v.source_snapshot_id, v.adjustments_hash, "
                        "v.drafted_by_kind, v.content_hash, v.created_at "
                        "FROM statement_versions v WHERE v.id = :v"
                    ),
                    {"v": version_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound("statement_version")
    return dict(row)


async def _authorise(ctx: AuthContext, action: str, engagement_id: UUID) -> None:
    await authorise(ctx, action, (await get_ref(ctx, engagement_id)).resource())


async def authorise_version(ctx: AuthContext, action: str, version_id: UUID) -> None:
    """The version's own engagement: a version id alone never reaches another engagement."""
    await _authorise(ctx, action, (await _version_row(ctx.tenant, version_id))["engagement_id"])


async def authorise_document(ctx: AuthContext, action: str, document_id: UUID) -> None:
    row = await _resource_of_document(ctx.tenant, document_id)
    await _authorise(ctx, action, row["engagement_id"])


# --- draft ------------------------------------------------------------------------------------


async def draft(ctx: AuthContext, engagement_id: UUID, work_item_id: UUID) -> tuple[UUID, int]:
    """A new version from the final layer. Deterministic: the same TB and entries hash the same."""
    source = await _source(ctx.tenant, engagement_id)
    refs = tuple(sorted(e.ref for e in source.entries.recorded))
    lines = fs_draft.draft(
        source.statements.groups, source.period_end.year, source.accounts_of, refs, {}
    )
    async with uow(ctx.tenant, ctx.actor) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO statement_documents (tenant_id, engagement_id, work_item_id, "
                "framework_key) VALUES (:t, :e, :w, :f) "
                "ON CONFLICT (tenant_id, work_item_id, kind, framework_key) DO NOTHING"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "w": work_item_id, "f": FRAMEWORK},
        )
        document = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, current_version_no, row_version FROM statement_documents "
                        "WHERE work_item_id = :w AND framework_key = :f FOR UPDATE"
                    ),
                    {"w": work_item_id, "f": FRAMEWORK},
                )
            )
            .mappings()
            .one()
        )
        version_no = int(document["current_version_no"]) + 1
        version_id = cast(
            UUID,
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO statement_versions (tenant_id, engagement_id, work_item_id, "
                        "statement_document_id, version_no, source_snapshot_id, adjustments_hash, "
                        "drafted_by_kind, initiator_user_id, engine_version, content_hash) "
                        "VALUES (:t, :e, :w, :d, :n, :s, :a, 'human', :u, :engine, :c) "
                        "RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "e": engagement_id,
                        "w": work_item_id,
                        "d": document["id"],
                        "n": version_no,
                        "s": source.version_id,
                        "a": fs_draft.adjustments_hash(refs),
                        "u": ctx.user_id,
                        "engine": fs_draft.ENGINE_VERSION,
                        "c": fs_draft.content_hash(lines),
                    },
                )
            ).scalar_one(),
        )
        for line in lines:
            line_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO line_items (tenant_id, statement_version_id, statement_key, "
                        "section_key, line_key, label, position, note_ref) VALUES "
                        "(:t, :v, :st, :se, :l, :label, :p, :n) RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "v": version_id,
                        "st": line.statement_key,
                        "se": line.section_key,
                        "l": line.line_key,
                        "label": line.label,
                        "p": line.position,
                        "n": line.note_ref,
                    },
                )
            ).scalar_one()
            for value in line.values:
                await tx.session.execute(
                    text(
                        "INSERT INTO linked_values (tenant_id, line_item_id, year, value, source, "
                        "source_ref) VALUES (:t, :l, :y, :v, :s, CAST(:r AS jsonb))"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "l": line_id,
                        "y": value.year,
                        "v": value.value,
                        "s": value.source,
                        "r": _source_ref(value),
                    },
                )
        await tx.session.execute(
            text(
                "UPDATE statement_documents SET current_version_no = :n, "
                "row_version = row_version + 1, updated_at = clock_timestamp() WHERE id = :d"
            ),
            {"n": version_no, "d": document["id"]},
        )
        tx.record(
            "statement.drafted",
            target=Target("statement_version", version_id),
            after=Ref(version=version_no),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return version_id, version_no


def _source_ref(value: fs_draft.DraftValue) -> str:
    return json.dumps(
        {"accounts": list(value.accounts), "entries": list(value.entries),
         "terms": list(value.terms)},
        sort_keys=True,
    )  # fmt: skip


# --- reads ------------------------------------------------------------------------------------


async def _lines(tenant: TenantContext, version_id: UUID) -> list[JsonRow]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT l.id AS line_id, l.statement_key, l.section_key, l.line_key, "
                        "l.label, l.position, l.note_ref, v.id AS value_id, v.year, v.value, "
                        "v.source, v.source_ref, v.citation_ids, v.override_reason "
                        "FROM line_items l JOIN linked_values v ON v.tenant_id = l.tenant_id "
                        "AND v.line_item_id = l.id WHERE l.statement_version_id = :v "
                        "ORDER BY l.position, v.year DESC"
                    ),
                    {"v": version_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


async def is_out_of_date(tenant: TenantContext, version: JsonRow) -> bool:
    """A new TB version or a newly recorded entry makes the version out of date."""
    try:
        source = await _source(tenant, version["engagement_id"])
    except NoFinalTrialBalance:
        return True
    refs = [e.ref for e in source.entries.recorded]
    return (
        source.version_id != version["source_snapshot_id"]
        or fs_draft.adjustments_hash(refs) != version["adjustments_hash"]
    )


@dataclass(frozen=True)
class VersionView:
    row: JsonRow
    lines: list[JsonRow]
    out_of_date: bool
    tie_out: JsonRow | None


@dataclass(frozen=True)
class DocumentView:
    document: JsonRow | None
    current: VersionView | None


async def _last_tie_out(tenant: TenantContext, version_id: UUID) -> JsonRow | None:
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT total, tied, off, engine_version, inputs_hash, created_at "
                        "FROM tie_out_runs WHERE statement_version_id = :v "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"v": version_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row else None


async def current_of(tenant: TenantContext, work_item_id: UUID) -> DocumentView:
    async with tenant_session(tenant) as session:
        document = (
            (
                await session.execute(
                    text(
                        "SELECT id, framework_key, status, management_approval, "
                        "current_version_no, engagement_id FROM statement_documents "
                        "WHERE work_item_id = :w ORDER BY framework_key LIMIT 1"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if document is None:
            return DocumentView(None, None)
        version_id = (
            await session.execute(
                text(
                    "SELECT id FROM statement_versions WHERE statement_document_id = :d "
                    "AND version_no = :n"
                ),
                {"d": document["id"], "n": document["current_version_no"]},
            )
        ).scalar_one_or_none()
    if version_id is None:
        return DocumentView(dict(document), None)
    row = await _version_row(tenant, version_id)
    return DocumentView(
        dict(document),
        VersionView(
            row,
            await _lines(tenant, version_id),
            await is_out_of_date(tenant, row),
            await _last_tie_out(tenant, version_id),
        ),
    )


# --- tie-out ----------------------------------------------------------------------------------


def _effects(entries: EntrySet) -> list[tie_out.EntryEffect]:
    return [
        tie_out.EntryEffect(entry.ref, line.account_code, line.debit - line.credit)
        for entry in entries.recorded
        for line in entry.lines
    ]


def _expected(statements: Statements, year: int) -> dict[tuple[str, int], Decimal]:
    expected: dict[tuple[str, int], Decimal] = {}
    for group in statements.groups:
        for line in group.lines:
            key = fs_draft.line_key(line.key)
            expected[(key, year)] = line.cy
            if line.py is not None:
                expected[(key, year - 1)] = line.py
    return expected


async def run_tie_out(ctx: AuthContext, version_id: UUID) -> JsonRow:
    """Code foots, cross-foots and ties the version, and records an insert-only run."""
    version = await _version_row(ctx.tenant, version_id)
    source = await _source(ctx.tenant, version["engagement_id"])
    values = [
        tie_out.Value(
            r["line_key"],
            r["label"],
            int(r["year"]),
            r["value"],
            r["source"],
            tuple(r["source_ref"].get("terms", ())),
            tuple(r["source_ref"].get("accounts", ())),
            tuple(r["source_ref"].get("entries", ())),
        )
        for r in await _lines(ctx.tenant, version_id)
    ]
    result = tie_out.tie_out(
        values,
        _expected(source.statements, source.period_end.year),
        _effects(source.entries),
    )
    off = [
        {
            "line_key": o.line_key,
            "label": o.label,
            "year": str(o.year),
            "value": str(o.value),
            "expected": str(o.expected),
            "off_by": str(o.off_by),
            "cause": o.cause or "",
        }
        for o in result.off
    ]
    async with uow(ctx.tenant, ctx.actor) as tx:
            row = (
            (
                await tx.session.execute(
                    text(
                        "INSERT INTO tie_out_runs (tenant_id, statement_version_id, "
                        "engine_version, inputs_hash, total, tied, off) VALUES "
                        "(:t, :v, :e, :h, :total, :tied, CAST(:off AS jsonb)) "
                        "RETURNING id, total, tied, off, engine_version, inputs_hash, created_at"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "v": version_id,
                        "e": tie_out.ENGINE_VERSION,
                        "h": result.inputs_hash,
                        "total": result.total,
                        "tied": result.tied,
                        "off": json.dumps(off, sort_keys=True),
                    },
                )
            )
            .mappings()
            .one()
        )
        tx.record(
            "statement.tie_out_run",
            target=Target("statement_version", version_id),
            after=Ref(run=row["id"], tied=result.tied, total=result.total),
            scope=Scope(
                engagement_id=version["engagement_id"], work_item_id=version["work_item_id"]
            ),
        )
    return dict(row)


async def last_tie_out(tenant: TenantContext, version_id: UUID) -> JsonRow:
    found = await _last_tie_out(tenant, version_id)
    if found is None:
        raise NotFound("tie_out_run")
    return found


# --- lineage ----------------------------------------------------------------------------------


async def lineage(
    tenant: TenantContext, version_id: UUID, line_id: UUID
) -> tuple[list[dict[str, str]], list[UUID]]:
    """A line's sources and its C4-verified citations only (INV-2)."""
    rows = [r for r in await _lines(tenant, version_id) if r["line_id"] == line_id]
    if not rows:
        raise NotFound("line_item")
    sources: list[dict[str, str]] = []
    for r in rows:
        ref = r["source_ref"]
        sources.extend(
            {"kind": "tb_account", "year": str(r["year"]), "ref": a} for a in ref.get("accounts", ())
        )
        sources.extend(
            {"kind": "entry", "year": str(r["year"]), "ref": e} for e in ref.get("entries", ())
        )
        sources.extend(
            {"kind": "formula", "year": str(r["year"]), "ref": t} for t in ref.get("terms", ())
        )
    value_ids = [r["value_id"] for r in rows]
    verified = await verified_citation_ids(tenant, "linked_value", value_ids)
    return sources, [c for ids in verified.values() for c in ids]


# --- the disclosure checklist -----------------------------------------------------------------


async def _answer_value(
    tenant: TenantContext, answer_id: UUID, field_key: str
) -> dict[str, object] | None:
    del field_key
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text("SELECT answer FROM disclosure_checklist_answers WHERE id = :a"),
                {"a": answer_id},
            )
        ).scalar_one_or_none()
    return None if found is None else {"t": "text", "v": found}


register_field_owner(FieldOwner(_ANSWER_TARGET, _answer_value, frozenset()))


@dataclass(frozen=True)
class ChecklistView:
    document_id: UUID
    template_version_id: UUID | None
    items: list[JsonRow]
    answered: int
    total: int


async def checklist(tenant: TenantContext, document_id: UUID) -> ChecklistView:
    """The template's items with their answers, in template order; counts by code (142)."""
    document = await _resource_of_document(tenant, document_id)
    template = document["checklist_template_version_id"]
    if template is None:
        return ChecklistView(document_id, None, [], 0, 0)
    async with tenant_session(tenant) as session:
        template_items = (
            await session.execute(
                text(
                    "SELECT items FROM disclosure_checklist_template_versions WHERE id = :t"
                ),
                {"t": template},
            )
        ).scalar_one()
        answers = (
            (
                await session.execute(
                    text(
                        "SELECT item_key, answer, reason, note_ref, state, suggestion_id, version "
                        "FROM disclosure_checklist_answers WHERE statement_document_id = :d"
                    ),
                    {"d": document_id},
                )
            )
            .mappings()
            .all()
        )
    by_key = {a["item_key"]: dict(a) for a in answers}
    items: list[JsonRow] = [
        {
            "item_key": item["key"],
            "section": item.get("section", ""),
            "text": item.get("text", ""),
            "answer": by_key.get(item["key"], {}).get("answer"),
            "reason": by_key.get(item["key"], {}).get("reason"),
            "note_ref": by_key.get(item["key"], {}).get("note_ref"),
            "state": by_key.get(item["key"], {}).get("state", "empty"),
            "suggestion_id": by_key.get(item["key"], {}).get("suggestion_id"),
            "version": by_key.get(item["key"], {}).get("version", 1),
        }
        for item in cast(list[JsonRow], template_items)
    ]
    answered = sum(1 for i in items if i["answer"] is not None and i["state"] != "suggested")
    return ChecklistView(document_id, template, items, answered, len(items))


async def _existing(tx_session: AsyncSession, document_id: UUID, item_key: str) -> JsonRow | None:
    row = (
        (
            await tx_session.execute(
                text(
                    "SELECT id, answer, state, version, suggestion_id "
                    "FROM disclosure_checklist_answers "
                    "WHERE statement_document_id = :d AND item_key = :k FOR UPDATE"
                ),
                {"d": document_id, "k": item_key},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def answer_item(
    ctx: AuthContext,
    document_id: UUID,
    item_key: str,
    answer: str,
    reason: str | None,
    note_ref: str | None,
    if_match: int,
) -> JsonRow:
    """A person's answer: N/A needs its reason; every change has a field history."""
    if answer == "na" and not (reason or "").strip():
        raise ReasonRequired
    document = await _resource_of_document(ctx.tenant, document_id)
    template = document["checklist_template_version_id"]
    if template is None:
        raise NotFound("disclosure_checklist")
    async with uow(ctx.tenant, ctx.actor) as tx:
        existing = await _existing(tx.session, document_id, item_key)
        if existing is not None and int(existing["version"]) != if_match:
            raise StaleAnswer
        scope = {"d": document_id, "k": item_key, "ans": answer, "reason": reason,
                 "n": note_ref, "u": ctx.user_id}  # fmt: skip
        if existing is None:
            answer_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO disclosure_checklist_answers (tenant_id, engagement_id, "
                        "work_item_id, statement_document_id, template_version_id, item_key, "
                        "answer, reason, note_ref, state, answered_by) VALUES (:t, :e, :w, :d, "
                        ":tv, :k, :ans, :reason, :n, 'answered', :u) RETURNING id"
                    ),
                    {
                        **scope,
                        "t": ctx.tenant_id,
                        "e": document["engagement_id"],
                        "w": document["work_item_id"],
                        "tv": template,
                    },
                )
            ).scalar_one()
        else:
            answer_id = existing["id"]
            await tx.session.execute(
                text(
                    "UPDATE disclosure_checklist_answers SET answer = :ans, reason = :reason, "
                    "note_ref = :n, state = 'answered', answered_by = :u, reviewed_by = NULL, "
                    "version = version + 1, updated_at = clock_timestamp() "
                    "WHERE statement_document_id = :d AND item_key = :k"
                ),
                scope,
            )
        await record_value(
            tx,
            engagement_id=document["engagement_id"],
            target_type=_ANSWER_TARGET,
            target_id=answer_id,
            field_key="answer",
            value={"t": "text", "v": answer},
            value_source="human",
            cause="edit",
            citation_note=note_ref or reason or answer,
        )
        tx.record(
            "disclosure_checklist.answered",
            target=Target(_ANSWER_TARGET, answer_id),
            after=Ref(item=item_key),
            scope=Scope(
                engagement_id=document["engagement_id"], work_item_id=document["work_item_id"]
            ),
        )
    return await _one_item(ctx.tenant, document_id, item_key)


async def adopt_item(
    ctx: AuthContext, document_id: UUID, item_key: str, if_match: int
) -> JsonRow:
    """A person adopts the agent's suggested answer: it becomes theirs (INV-1)."""
    document = await _resource_of_document(ctx.tenant, document_id)
    async with uow(ctx.tenant, ctx.actor) as tx:
        existing = await _existing(tx.session, document_id, item_key)
        if existing is None or existing["state"] != "suggested" or existing["answer"] is None:
            raise NoSuggestion
        if int(existing["version"]) != if_match:
            raise StaleAnswer
        await tx.session.execute(
            text(
                "UPDATE disclosure_checklist_answers SET state = 'adopted', adopted_by = :u, "
                "version = version + 1, updated_at = clock_timestamp() "
                "WHERE statement_document_id = :d AND item_key = :k"
            ),
            {"u": ctx.user_id, "d": document_id, "k": item_key},
        )
        await record_value(
            tx,
            engagement_id=document["engagement_id"],
            target_type=_ANSWER_TARGET,
            target_id=existing["id"],
            field_key="answer",
            value={"t": "text", "v": existing["answer"]},
            value_source="human",
            cause="suggestion_adopted",
            suggestion_id=existing["suggestion_id"],
            citation_note="adopted",
        )
        tx.record(
            "disclosure_checklist.adopted",
            target=Target(_ANSWER_TARGET, existing["id"]),
            after=Ref(item=item_key),
            scope=Scope(
                engagement_id=document["engagement_id"], work_item_id=document["work_item_id"]
            ),
        )
    return await _one_item(ctx.tenant, document_id, item_key)


async def review_items(ctx: AuthContext, document_id: UUID, item_keys: Sequence[str]) -> None:
    """A reviewer marks answered or adopted items reviewed; a suggestion cannot be reviewed."""
    document = await _resource_of_document(ctx.tenant, document_id)
    async with uow(ctx.tenant, ctx.actor) as tx:
        for key in item_keys:
            existing = await _existing(tx.session, document_id, key)
            if existing is None or existing["state"] not in ("answered", "adopted"):
                raise NotAnswered(facts={"item_key": key})
            await tx.session.execute(
                text(
                    "UPDATE disclosure_checklist_answers SET state = 'reviewed', "
                    "reviewed_by = :u, version = version + 1, updated_at = clock_timestamp() "
                    "WHERE statement_document_id = :d AND item_key = :k"
                ),
                {"u": ctx.user_id, "d": document_id, "k": key},
            )
            tx.record(
                "disclosure_checklist.reviewed",
                target=Target(_ANSWER_TARGET, existing["id"]),
                after=Ref(item=key),
                scope=Scope(
                    engagement_id=document["engagement_id"],
                    work_item_id=document["work_item_id"],
                ),
            )


async def _one_item(tenant: TenantContext, document_id: UUID, item_key: str) -> JsonRow:
    view = await checklist(tenant, document_id)
    found = next((i for i in view.items if i["item_key"] == item_key), None)
    if found is None:
        raise NotFound("disclosure_checklist_item")
    return found


AUDIT_KINDS: Final = frozenset({"statement_version", _ANSWER_TARGET})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For a statement version or checklist answer an audit event names: id -> its engagement."""
    table = "statement_versions" if kind == "statement_version" else "disclosure_checklist_answers"
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(f"SELECT id, engagement_id FROM {table} WHERE id = ANY(:ids)"),  # noqa: S608
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}
