"""N-04-T11: a notice's analysis (N-04 §3 US-4.3; NOT-02; DEC-2239).

- **Return as filed.** A person records the return-as-filed snapshot: from the approved engine
  (CCH) import or as a cited preparer entry, every line cited (`notice_return_snapshots`,
  insert-only; the newest is current).
- **Proposed items.** The notice's proposed line changes and payer items, from the form map
  (`code_map`) or a person's cited entry (`notice_proposed_items`; a correction supersedes).
- **Run.** Code compares them (`compute.underreporter`, `compute.bracket`) and writes an
  insert-only `notice_analyses` version, **idempotent on `inputs_hash`** (the same inputs answer
  the existing version). The agent step is a registered hook that fails closed: no hook, or a
  hook that refuses, leaves the stage `off` or `refused` and no recommendation; a recommendation
  is recorded only from a `live` stage (0650's CHECK), and only then is the card's option
  preselected.
- **Position.** `notice_position` is a C3 card with code options (agree, partially agree,
  disagree), reserved to the notice's **signer**; its applier records the position on the notice.
  Decision requests and their notes are insert-only (`notice_notes`, sealed text).

Whitley (CP2000): interest 412.00 → 3,532.00, explained by two cited 1099-INTs not on the return
(Front Range Bank 1,870.00, Lakeview Credit Union 1,250.00), and the bracket check agrees.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices.compute import bracket, underreporter
from abacus.modules.notices.service import notice
from abacus.modules.review.api import (
    AppliedDecision,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    raise_decision_card,
    register_decision_kind,
)

POSITION_KIND: Final = "notice_position"
POSITIONS: Final = {
    "agree": "Agree with the notice",
    "partially_agree": "Partially agree",
    "disagree": "Disagree",
}
ENGINE_NAME: Final = "notices.analysis"
ENGINE_VERSION: Final = "1"


class NothingToAnalyze(DomainConflict):
    """The notice has no proposed items yet: record them first."""

    code = "nothing_to_analyze"


class LineUncited(DomainInvalid):
    """Every entered line carries its citation (identifiers only in facts)."""

    code = "line_uncited"


@dataclass(frozen=True)
class AgentStep:
    stage: str  # off, shadow, live, refused
    run_id: UUID | None
    recommended_position: str | None


# The agent step's hook (N-04-T16 registers it). None, or a refusal, means no recommendation.
AgentHook = Callable[
    [TenantContext, UUID, dict[str, Any]], Awaitable[AgentStep]  # Any: JSON from the database
]  # Any: JSON from the database or the document
_AGENT_HOOK: list[AgentHook] = []


def register_agent_step(hook: AgentHook) -> None:
    _AGENT_HOOK[:] = [hook]


async def _agent_step(
    tenant: TenantContext,
    notice_id: UUID,
    facts: dict[str, Any],  # Any: JSON from the database
) -> AgentStep:  # Any: JSON from the database or the document
    if not _AGENT_HOOK:
        return AgentStep("off", None, None)
    try:
        step = await _AGENT_HOOK[0](tenant, notice_id, facts)
    except Exception:  # a failing hook fails closed: no recommendation, never a guess
        return AgentStep("refused", None, None)
    if step.stage != "live":
        return AgentStep(step.stage, step.run_id, None)
    return step


def _hash(payload: object) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def record_return_as_filed(
    ctx: AuthContext,
    notice_id: UUID,
    *,
    source: str,
    filing_status: str | None,
    filed_on: date | None,
    lines: Sequence[tuple[str, str | None, Decimal, UUID | None]],
) -> None:
    """A person records the return as filed; each line `(key, label, value, citation_id)`."""
    if any(c is None for *_, c in lines):
        raise LineUncited
    found = await notice(ctx, notice_id)
    payload = [
        {"key": k, "label": label, "value": str(v), "citation_id": str(c)}
        for k, label, v, c in lines
    ]
    digest = _hash({"source": source, "filing_status": filing_status, "lines": payload})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO notice_return_snapshots (tenant_id, work_item_id, source, "
                "filing_status, filed_on, lines, recorded_actor_kind, recorded_by, inputs_hash) "
                "VALUES (:t, :w, :source, :fs, :filed_on, CAST(:lines AS jsonb), 'human', :by, :h)"
            ),
            {
                "t": ctx.tenant_id,
                "w": found.id,
                "source": source,
                "fs": filing_status,
                "filed_on": filed_on,
                "lines": json.dumps(payload),
                "by": ctx.user_id,
                "h": digest,
            },
        )
        tx.record(
            "notice.return_as_filed_recorded",
            target=Target("notice", found.id),
            after=Ref(lines=len(payload), inputs_hash=digest),
        )


async def record_proposed_items(
    ctx: AuthContext,
    notice_id: UUID,
    items: Sequence[dict[str, Any]],  # Any: JSON from the database or the document
) -> None:
    """A person's cited entry of the notice's proposed items (origin `human`)."""
    found = await notice(ctx, notice_id)
    async with uow(ctx.tenant) as tx:
        for item in items:
            if item.get("citation_id") is None:
                raise LineUncited
            await tx.session.execute(
                text(
                    "INSERT INTO notice_proposed_items (tenant_id, work_item_id, kind, line_key, "
                    "label, payer_name, info_form, amount_shown, amount_irs, origin, citation_id, "
                    "recorded_actor_kind, recorded_by) VALUES (:t, :w, :kind, :line_key, :label, "
                    ":payer, :form, :shown, :irs, 'human', :cite, 'human', :by)"
                ),
                {
                    "t": ctx.tenant_id,
                    "w": found.id,
                    "kind": item["kind"],
                    "line_key": item["line_key"],
                    "label": item["label"],
                    "payer": item.get("payer_name"),
                    "form": item.get("info_form"),
                    "shown": item.get("amount_shown"),
                    "irs": item.get("amount_irs"),
                    "cite": item["citation_id"],
                    "by": ctx.user_id,
                },
            )
        tx.record(
            "notice.proposed_items_recorded",
            target=Target("notice", found.id),
            after=Ref(items=len(items)),
        )


async def _inputs(
    tenant: TenantContext, notice_id: UUID
) -> tuple[dict[str, Any] | None, list[Any]]:  # Any: JSON from the database or the document
    async with tenant_session(tenant) as session:
        snapshot = (
            (
                await session.execute(
                    text(
                        "SELECT filing_status, lines FROM notice_return_snapshots "
                        "WHERE work_item_id = :w ORDER BY created_at DESC, id DESC LIMIT 1"
                    ),
                    {"w": notice_id},
                )
            )
            .mappings()
            .first()
        )
        items = list(
            (
                await session.execute(
                    text(
                        "SELECT p.* FROM notice_proposed_items p WHERE p.work_item_id = :w "
                        "AND NOT EXISTS (SELECT 1 FROM notice_proposed_items s "
                        "WHERE s.supersedes_id = p.id) ORDER BY p.created_at, p.id"
                    ),
                    {"w": notice_id},
                )
            ).mappings()
        )
    return (dict(snapshot) if snapshot else None), items


def compare(
    snapshot: dict[str, Any] | None,  # Any: JSON from the database
    items: Sequence[Any],  # Any: JSON from the database
    *,
    tax_year: int | None,  # Any: JSON from the database or the document
) -> dict[str, Any]:  # Any: JSON from the database or the document
    """Code's comparison as stored rows (pure over its inputs)."""
    as_filed = {line["key"]: Decimal(line["value"]) for line in (snapshot or {}).get("lines", [])}
    proposed = [
        underreporter.ProposedLine(
            i["line_key"],
            i["label"],
            i["amount_shown"],
            Decimal(i["amount_irs"] or 0),
        )
        for i in items
        if i["kind"] == "line_change"
    ]
    payers = [
        underreporter.InformationReturn(
            i["payer_name"] or "",
            i["info_form"] or "",
            Decimal(i["amount_irs"] or 0),
            on_return=False,
            line_key=i["line_key"],
        )
        for i in items
        if i["kind"] == "payer_item"
    ]
    result = underreporter.compare(as_filed, proposed, payers)
    checks: dict[str, Any] = {  # Any: JSON from the database or the document
        "difference_explained": result.difference_explained,
        "total_foots": True,
        "bracket_check": None,
    }
    status = (snapshot or {}).get("filing_status")
    tax_line = next((i for i in items if i["line_key"] == "tax"), None)
    ti_before = as_filed.get("taxable_income")
    if status and tax_year and tax_line is not None and ti_before is not None:
        check = bracket.check(
            status,
            tax_year,
            ti_before,
            ti_before + result.income_difference,
            Decimal(tax_line["amount_irs"] or 0) - Decimal(tax_line["amount_shown"] or 0),
        )
        checks["bracket_check"] = {
            "rate": str(check.rate) if check.rate is not None else None,
            "expected": str(check.expected) if check.expected is not None else None,
            "notice": str(check.notice),
            "agrees": check.agrees,
            "reason": check.reason,
        }
    rows: list[dict[str, Any]] = [  # Any: JSON from the database or the document
        {
            "key": r.key,
            "label": r.label,
            "as_filed": None if r.as_filed is None else str(r.as_filed),
            "irs": str(r.irs),
            "difference": str(r.difference),
            "citation_ids": [],
        }
        for r in result.rows
    ]
    infos = [
        {
            "payer_name": r.payer_name,
            "form": r.form,
            "amount": str(r.amount),
            "on_return": r.on_return,
            "issued_after_filing": False,
            "document_id": None,
            "citation_id": None,
        }
        for r in result.information_returns
    ]
    return {
        "analysis_kind": "underreporter_comparison" if proposed else "none",
        "rows": rows,
        "information_returns": infos,
        "checks": checks,
        "inputs_hash": result.stamp.inputs_hash,
    }


async def run(ctx: AuthContext, notice_id: UUID) -> tuple[int, bool]:
    """Compute and record a version; the same inputs return the existing version (reused)."""
    found = await notice(ctx, notice_id)
    snapshot, items = await _inputs(ctx.tenant, found.id)
    if not items:
        raise NothingToAnalyze
    computed = compare(snapshot, items, tax_year=found.tax_year)
    async with tenant_session(ctx.tenant) as session:
        existing = (
            await session.execute(
                text(
                    "SELECT version FROM notice_analyses WHERE work_item_id = :w "
                    "AND inputs_hash = :h AND status = 'ready' ORDER BY version DESC LIMIT 1"
                ),
                {"w": found.id, "h": computed["inputs_hash"]},
            )
        ).scalar()
    if existing is not None:
        return int(existing), True
    step = await _agent_step(
        ctx.tenant,
        found.id,
        {
            "inputs_hash": computed["inputs_hash"],
            "initiator": ctx.user_id,
            "rows": computed["rows"],
            "checks": computed["checks"],
            "information_returns": computed["information_returns"],
        },
    )
    async with uow(ctx.tenant) as tx:
        version = int(
            (
                await tx.session.execute(
                    text(
                        "SELECT coalesce(max(version), 0) + 1 FROM notice_analyses "
                        "WHERE work_item_id = :w"
                    ),
                    {"w": found.id},
                )
            ).scalar_one()
        )
        await tx.session.execute(
            text(
                "INSERT INTO notice_analyses (tenant_id, work_item_id, version, status, "
                "analysis_kind, rows, information_returns, checks, sources, engine_name, "
                "engine_version, inputs_hash, agent_run_id, agent_stage, recommended_position) "
                "VALUES (:t, :w, :v, 'ready', :kind, CAST(:rows AS jsonb), CAST(:infos AS jsonb), "
                "CAST(:checks AS jsonb), '[]'::jsonb, :en, :ev, :h, :run, :stage, :rec)"
            ),
            {
                "t": ctx.tenant_id,
                "w": found.id,
                "v": version,
                "kind": computed["analysis_kind"],
                "rows": json.dumps(computed["rows"]),
                "infos": json.dumps(computed["information_returns"]),
                "checks": json.dumps(computed["checks"]),
                "en": ENGINE_NAME,
                "ev": ENGINE_VERSION,
                "h": computed["inputs_hash"],
                "run": step.run_id,
                "stage": step.stage,
                "rec": step.recommended_position,
            },
        )
        tx.record(
            "notice.analysis_recorded",
            target=Target("notice", found.id),
            after=Ref(version=version, inputs_hash=computed["inputs_hash"]),
        )
    return version, False


async def latest(
    ctx: AuthContext, notice_id: UUID
) -> dict[str, Any] | None:  # Any: JSON from the database or the document
    found = await notice(ctx, notice_id)
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM notice_analyses WHERE work_item_id = :w "
                        "ORDER BY version DESC LIMIT 1"
                    ),
                    {"w": found.id},
                )
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


async def request_decision(ctx: AuthContext, notice_id: UUID, note: str | None) -> UUID:
    """Raise the signer's `notice_position` card; an optional note rides as an insert-only
    notice note. Deciding is C3's `POST /v1/decision-cards/{id}/decide`."""
    found = await notice(ctx, notice_id)
    if await latest(ctx, notice_id) is None:
        raise NothingToAnalyze
    card_id = await raise_decision_card(
        ctx,
        engagement_id=found.engagement_id,
        kind=POSITION_KIND,
        question_key=f"notice.{found.id.hex}",
        work_item_id=found.id,
    )
    if note:
        await add_note(ctx, notice_id, note, card_id)
    return card_id


async def add_note(
    ctx: AuthContext, notice_id: UUID, body: str, decision_card_id: UUID | None
) -> UUID:
    found = await notice(ctx, notice_id)
    async with uow(ctx.tenant) as tx:
        note_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO notice_notes (tenant_id, work_item_id, body_sealed, author_id, "
                    "decision_card_id) VALUES (:t, :w, :body, :by, :card) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "w": found.id,
                    "body": await seal(
                        ctx.tenant_id, body.encode("utf-8"), f"notice_note:{found.id}"
                    ),
                    "by": ctx.user_id,
                    "card": decision_card_id,
                },
            )
        ).scalar_one()
        tx.record("notice.note_added", target=Target("notice", found.id), after=Ref(note=note_id))
    return UUID(str(note_id))


async def _position_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """Code's options over the newest analysis version."""
    notice_id = UUID(hex=subject.question_key.removeprefix("notice."))
    async with tenant_session(tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT version, inputs_hash, recommended_position FROM notice_analyses "
                        "WHERE work_item_id = :w ORDER BY version DESC LIMIT 1"
                    ),
                    {"w": notice_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise NothingToAnalyze
    figures = {"analysis_version": str(row["version"]), "inputs_hash": row["inputs_hash"]}
    # The agent's recommendation (live stage only, 0650's CHECK) rides on the analysis; NOT-02
    # preselects it from there. The card itself carries code's options only.
    return ComputedCard(
        options=tuple(CardOption(key, label, figures) for key, label in POSITIONS.items())
    )


async def _apply_position(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    notice_id = UUID(hex=decided.question_key.removeprefix("notice."))
    await tx.session.execute(
        text(
            "UPDATE notices SET position = :p, decision_id = :d, decided_at = clock_timestamp(), "
            "row_version = row_version + 1 WHERE work_item_id = :w"
        ),
        {"p": decided.option_key, "d": decided.decision_id, "w": notice_id},
    )
    tx.record(
        "notice.position_decided",
        target=Target("notice", notice_id),
        after=Ref(decision=decided.decision_id),
    )


def register_position_kind() -> None:
    register_decision_kind(
        DecisionKind(
            code=POSITION_KIND,
            reserved_role="signer",
            options=_position_card,
            questions={"notice": "The firm's position on the notice"},
            apply=_apply_position,
        )
    )
