"""The fiduciary computation service (T-07-T16; T-07 §4, F6, F7; SPEC-656 AC-6.1 to AC-7.2, AC-9.2;
ADR-050, ADR-004, DEC-84; amber). TXT-02's workpaper over the engine (`compute/fiduciary.py`).

- **Inputs** are insert-only versions: an FAI line, a trust expense or a distribution is edited by
  writing its next version (`*_versions.seq`), each with who set it (a person) and why (sealed).
  FAI lines and expenses carry at least one citation to the custodial statement or the governing
  instrument (`document_text`, `instrument_clause`; INV-2); a distribution names its clause basis
  when the instrument governs it. Only a person edits (an agent proposes elsewhere).
- **Recompute** is synchronous: every edit, and the interpretation's approval, recomputes into a
  new insert-only `fai_dni_computations` version with its prior's id, its `inputs_hash`, its
  outputs and its beneficiary allocations, unless the inputs hash matches the current version
  (idempotent). Before the interpretation is approved the service refuses: 409
  `interpretation_not_approved` (no figure is computed on an unapproved reading).
- **Review**: the computation is a reviewable for L2 (`fiduciary_computation`, DEC-84); a new
  version changes its content hash, so the L2 sign-off goes stale and TXT-02 shows Changed rows
  with the struck prior values from the last signed version and the Re-approve banner.
- **K-1 box provenance**: each allocation box is recorded through `review.api.record_value` on the
  computation (engine-sourced), so SHL-09 shows where a box came from.
- **Export** is a deterministic workbook of one version (`kernel.safe_xlsx`): two exports of the
  same version are byte-identical.

Every figure is the engine's; the browser never sums (TXT-02). TRI amounts stay classified `Tri`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, names_of
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    record_value,
    register_reviewable,
    register_reviewable_facts,
    sign_off_states,
    stale_of,
)
from abacus.modules.tax.compute import fiduciary as engine
from abacus.modules.tax.fiduciary_contract import (
    FaiLineEditIn,
    FaiLineIn,
    FaiLineOut,
    FaiLinesOut,
    FiduciaryCharacterAmountOut,
    FiduciaryCharacterRowOut,
    FiduciaryComputationOut,
    FiduciaryRecomputeOut,
    FiduciaryTallyOut,
    FiduciaryTreeNodeOut,
    InterpretationNotApproved,
    TrustDistributionEditIn,
    TrustDistributionIn,
    TrustDistributionOut,
    TrustDistributionsOut,
    TrustExpenseEditIn,
    TrustExpenseIn,
    TrustExpenseOut,
    TrustExpensesOut,
)
from abacus.modules.tax.instruments.service import _authorised, _return

TARGET: Final = "fiduciary_computation"
LEVELS: Final = (2,)
READ: Final = "fiduciary_computation.read"
_AAD: Final = "tax.fiduciary.reason"
_ENTITY: Final = {"complex": "complex_trust", "simple": "simple_trust", "estate": "estate"}
_CHARACTER: Final[dict[str, engine.Character]] = {
    "interest": "interest",
    "ordinary_dividends": "ordinary_dividends",
    "tax_exempt_interest": "tax_exempt_interest",
    "capital_gain": "capital_gains",
    "rents": "other",
    "other_income": "other",
}


class VersionConflict(DomainConflict):
    code = "version_conflict"


class StatementTablesMissing(DomainConflict):
    """Import from statement needs P-11's extracted tables for the document (T-07 cut 4)."""

    code = "statement_tables_missing"


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _scope(ctx: AuthContext, return_id: UUID, action: str) -> tuple[UUID, UUID, int]:
    r = await _return(ctx.tenant, return_id)
    await _authorised(ctx, r.engagement_id, action)
    return r.engagement_id, r.client_entity_id, r.tax_year


# --- inputs, newest version each -----------------------------------------------------------------

_LINES: Final = text(
    "SELECT l.id, l.kind, l.parent_line_id, l.description, v.seq, v.amount, v.citation_ids "
    "FROM fai_lines l JOIN LATERAL (SELECT * FROM fai_line_versions x WHERE x.line_id = l.id "
    "ORDER BY x.seq DESC LIMIT 1) v ON true WHERE l.work_item_id = :r ORDER BY l.created_at, l.id"
)
_EXPENSES: Final = text(
    "SELECT e.id, e.kind, v.seq, v.charged_to, v.amount, v.deductible, v.clause_id, v.citation_ids "
    "FROM trust_expenses e JOIN LATERAL (SELECT * FROM trust_expense_versions x "
    "WHERE x.expense_id = e.id ORDER BY x.seq DESC LIMIT 1) v ON true "
    "WHERE e.work_item_id = :r ORDER BY e.created_at, e.id"
)
_DISTRIBUTIONS: Final = text(
    "SELECT d.id, d.beneficiary_contact_id, v.seq, v.paid_on, v.amount, v.form, v.source, "
    "v.clause_id, v.sixty_five_day_election_id FROM trust_distributions d JOIN LATERAL "
    "(SELECT * FROM trust_distribution_versions x WHERE x.distribution_id = d.id "
    "ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.work_item_id = :r "
    "ORDER BY v.paid_on, d.created_at, d.id"
)
_INTERPRETATION: Final = text(
    "SELECT id, status, content_hash FROM instrument_interpretations WHERE work_item_id = :r "
    "AND superseded_at IS NULL"
)
_DETERMINATION_CODES: Final = text(
    "SELECT d.key, v.value_code FROM instrument_determinations d JOIN LATERAL (SELECT * FROM "
    "instrument_determination_versions x WHERE x.determination_id = d.id ORDER BY x.seq DESC "
    "LIMIT 1) v ON true WHERE d.interpretation_id = :i"
)
_CURRENT: Final = text(
    "SELECT id, version_no, inputs_hash, outputs, content_hash, computed_at, engine_version, "
    "parameter_set, prior_computation_id FROM fai_dni_computations WHERE work_item_id = :r "
    "ORDER BY version_no DESC LIMIT 1"
)
_BY_HASH: Final = text(
    "SELECT outputs FROM fai_dni_computations WHERE work_item_id = :r AND content_hash = :h "
    "ORDER BY version_no DESC LIMIT 1"
)
_CONTACTS: Final = text("SELECT id, display_name FROM contacts WHERE id = ANY(:ids)")


async def _contact_names(session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    rows = (await session.execute(_CONTACTS, {"ids": list(ids)})).all()
    return {r[0]: str(r[1]) for r in rows}


def _lines_out(rows: Sequence[object]) -> list[FaiLineOut]:
    return [
        FaiLineOut(
            id=r[0], kind=r[1], parent_line_id=r[2], description=r[3], amount=Decimal(r[5]),
            citation_ids=list(r[6] or ()), version=int(r[4]),
        )  # fmt: skip
        for r in cast(Sequence[Sequence[object]], rows)  # pyright: ignore[reportArgumentType,reportUnknownArgumentType]
    ]


async def fai_lines(ctx: AuthContext, return_id: UUID) -> FaiLinesOut:
    await _scope(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_LINES, {"r": return_id})).all()
    return FaiLinesOut(lines=_lines_out(rows))


async def trust_expenses(ctx: AuthContext, return_id: UUID) -> TrustExpensesOut:
    await _scope(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_EXPENSES, {"r": return_id})).all()
    return TrustExpensesOut(
        expenses=[
            TrustExpenseOut(
                id=r[0], kind=r[1], charged_to=r[3], amount=Decimal(r[4]), deductible=bool(r[5]),
                clause_id=r[6], citation_ids=list(r[7] or ()), version=int(r[2]),
            )  # fmt: skip
            for r in rows
        ]
    )


async def trust_distributions(ctx: AuthContext, return_id: UUID) -> TrustDistributionsOut:
    await _scope(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_DISTRIBUTIONS, {"r": return_id})).all()
        names = await _contact_names(session, sorted({r[1] for r in rows}, key=str))
        prior = await _signed_outputs(ctx.tenant, session, return_id)
    struck = cast(dict[str, str], (prior or {}).get("distributions_by_id", {}))
    return TrustDistributionsOut(
        distributions=[
            TrustDistributionOut(
                id=r[0], beneficiary_contact_id=r[1], beneficiary_name=names.get(r[1], ""),
                paid_on=r[3], amount=Decimal(r[4]), form=r[5], source=r[6], clause_id=r[7],
                sixty_five_day_election_id=r[8], version=int(r[2]),
                prior_amount=(
                    Decimal(struck[str(r[0])])
                    if str(r[0]) in struck and Decimal(struck[str(r[0])]) != Decimal(r[4])
                    else None
                ),
            )  # fmt: skip
            for r in rows
        ]
    )


# --- edits (a person's; each recomputes) ---------------------------------------------------------


async def _sealed(ctx: AuthContext, reason: str | None, row_id: UUID) -> bytes | None:
    if reason is None:
        return None
    del row_id
    return await seal(ctx.tenant_id, reason.encode(), _AAD)


async def add_fai_line(ctx: AuthContext, return_id: UUID, body: FaiLineIn) -> FaiLineOut:
    _person(ctx, "fai_line.edit")
    engagement, _, _ = await _scope(ctx, return_id, "fai_line.edit")
    async with uow(ctx.tenant) as tx:
        line_id = await tx.session.scalar(
            text(
                "INSERT INTO fai_lines (tenant_id, engagement_id, work_item_id, kind, "
                "parent_line_id, description, created_by) VALUES (:t, :e, :w, :k, :p, :d, :u) "
                "RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "k": body.kind,
             "p": body.parent_line_id, "d": body.description, "u": ctx.user_id},
        )  # fmt: skip
        await _line_version(tx, ctx, line_id, 1, body.amount, body.citation_ids, None)
        tx.record(
            "fai_line.created", target=Target("fai_line", line_id),
            after=Ref(work_item_id=return_id), scope=Scope(engagement_id=engagement),
        )  # fmt: skip
        await recompute_in(tx, return_id, engagement)
    return FaiLineOut(
        id=line_id, kind=body.kind, parent_line_id=body.parent_line_id,
        description=body.description, amount=body.amount, citation_ids=body.citation_ids,
        version=1,
    )  # fmt: skip


async def _line_version(
    tx: UnitOfWork, ctx: AuthContext, line_id: UUID, seq: int, amount: Decimal,
    citations: Sequence[UUID], reason: str | None,
) -> None:  # fmt: skip
    vid = uuid4()
    await tx.session.execute(
        text(
            "INSERT INTO fai_line_versions (tenant_id, line_id, seq, amount, citation_ids, "
            "set_by_kind, set_by_id, reason_sealed) VALUES (:t, :l, :s, :a, :c, 'human', :u, :r)"
        ),
        {"t": ctx.tenant_id, "l": line_id, "s": seq, "a": amount,
         "c": list(citations), "u": ctx.user_id, "r": await _sealed(ctx, reason, vid)},
    )  # fmt: skip


async def edit_fai_line(ctx: AuthContext, line_id: UUID, body: FaiLineEditIn) -> FaiLineOut:
    _person(ctx, "fai_line.edit")
    async with tenant_session(ctx.tenant) as session:
        head = (
            await session.execute(
                text("SELECT work_item_id, engagement_id FROM fai_lines WHERE id = :l"), {"l": line_id}
            )
        ).first()
    if head is None:
        raise NotFound("fai_line")
    return_id, engagement = head[0], head[1]
    await _scope(ctx, return_id, "fai_line.edit")
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(
            text("SELECT max(seq) FROM fai_line_versions WHERE line_id = :l"), {"l": line_id}
        )
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await _line_version(
            tx, ctx, line_id, body.expected_version + 1, body.amount, body.citation_ids, body.reason
        )
        tx.record(
            "fai_line.changed", target=Target("fai_line", line_id),
            after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=engagement),
        )  # fmt: skip
        await recompute_in(tx, return_id, engagement)
    lines = (await fai_lines(ctx, return_id)).lines
    return next(x for x in lines if x.id == line_id)


async def add_trust_expense(ctx: AuthContext, return_id: UUID, body: TrustExpenseIn) -> TrustExpenseOut:
    _person(ctx, "fai_line.edit")
    engagement, _, _ = await _scope(ctx, return_id, "fai_line.edit")
    async with uow(ctx.tenant) as tx:
        expense_id = await tx.session.scalar(
            text(
                "INSERT INTO trust_expenses (tenant_id, engagement_id, work_item_id, kind, "
                "created_by) VALUES (:t, :e, :w, :k, :u) RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "k": body.kind, "u": ctx.user_id},
        )  # fmt: skip
        await _expense_version(tx, ctx, expense_id, 1, body.charged_to, body.amount, body.deductible, body.clause_id, body.citation_ids, None)
        tx.record(
            "trust_expense.created", target=Target("trust_expense", expense_id),
            after=Ref(work_item_id=return_id), scope=Scope(engagement_id=engagement),
        )  # fmt: skip
        await recompute_in(tx, return_id, engagement)
    return TrustExpenseOut(
        id=expense_id, kind=body.kind, charged_to=body.charged_to, amount=body.amount,
        deductible=body.deductible, clause_id=body.clause_id, citation_ids=body.citation_ids,
        version=1,
    )  # fmt: skip


async def _expense_version(
    tx: UnitOfWork, ctx: AuthContext, expense_id: UUID, seq: int, charged_to: str,
    amount: Decimal, deductible: bool, clause_id: UUID | None, citations: Sequence[UUID],
    reason: str | None,
) -> None:  # fmt: skip
    vid = uuid4()
    await tx.session.execute(
        text(
            "INSERT INTO trust_expense_versions (tenant_id, expense_id, seq, charged_to, amount, "
            "deductible, clause_id, citation_ids, set_by_kind, set_by_id, reason_sealed) VALUES "
            "(:t, :x, :s, :c, :a, :d, :cl, :ci, 'human', :u, :r)"
        ),
        {"t": ctx.tenant_id, "x": expense_id, "s": seq, "c": charged_to, "a": amount,
         "d": deductible, "cl": clause_id, "ci": list(citations), "u": ctx.user_id,
         "r": await _sealed(ctx, reason, vid)},
    )  # fmt: skip


async def edit_trust_expense(ctx: AuthContext, expense_id: UUID, body: TrustExpenseEditIn) -> TrustExpenseOut:
    _person(ctx, "fai_line.edit")
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(text("SELECT work_item_id, engagement_id FROM trust_expenses WHERE id = :x"), {"x": expense_id})).first()
    if head is None:
        raise NotFound("trust_expense")
    await _scope(ctx, head[0], "fai_line.edit")
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(text("SELECT max(seq) FROM trust_expense_versions WHERE expense_id = :x"), {"x": expense_id})
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await _expense_version(tx, ctx, expense_id, body.expected_version + 1, body.charged_to, body.amount, body.deductible, body.clause_id, body.citation_ids, body.reason)
        tx.record(
            "trust_expense.changed", target=Target("trust_expense", expense_id),
            after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=head[1]),
        )  # fmt: skip
        await recompute_in(tx, head[0], head[1])
    return next(x for x in (await trust_expenses(ctx, head[0])).expenses if x.id == expense_id)


async def _distribution_version(
    tx: UnitOfWork, ctx: AuthContext, distribution_id: UUID, seq: int, paid_on: date,
    amount: Decimal, form: str, source: str, clause_id: UUID | None, reason: str | None,
) -> None:  # fmt: skip
    vid = uuid4()
    await tx.session.execute(
        text(
            "INSERT INTO trust_distribution_versions (tenant_id, distribution_id, seq, paid_on, "
            "amount, form, source, clause_id, set_by_kind, set_by_id, reason_sealed) VALUES (:t, "
            ":d, :s, :p, :a, :f, :src, :c, 'human', :u, :r)"
        ),
        {"t": ctx.tenant_id, "d": distribution_id, "s": seq, "p": paid_on, "a": amount,
         "f": form, "src": source, "c": clause_id, "u": ctx.user_id,
         "r": await _sealed(ctx, reason, vid)},
    )  # fmt: skip


async def add_trust_distribution(ctx: AuthContext, return_id: UUID, body: TrustDistributionIn) -> TrustDistributionOut:
    _person(ctx, "trust_distribution.edit")
    engagement, _, _ = await _scope(ctx, return_id, "trust_distribution.edit")
    async with uow(ctx.tenant) as tx:
        distribution_id = await tx.session.scalar(
            text(
                "INSERT INTO trust_distributions (tenant_id, engagement_id, work_item_id, "
                "beneficiary_contact_id, created_by) VALUES (:t, :e, :w, :b, :u) RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "b": body.beneficiary_contact_id, "u": ctx.user_id},
        )  # fmt: skip
        await _distribution_version(tx, ctx, distribution_id, 1, body.paid_on, body.amount, body.form, body.source, body.clause_id, None)
        tx.record(
            "trust_distribution.created", target=Target("trust_distribution", distribution_id),
            after=Ref(work_item_id=return_id), scope=Scope(engagement_id=engagement),
        )  # fmt: skip
        await recompute_in(tx, return_id, engagement)
    return next(x for x in (await trust_distributions(ctx, return_id)).distributions if x.id == distribution_id)


async def edit_trust_distribution(ctx: AuthContext, distribution_id: UUID, body: TrustDistributionEditIn) -> TrustDistributionOut:
    """AC-7.1: editing Theo's Dec 15 distribution writes its next version and recomputes."""
    _person(ctx, "trust_distribution.edit")
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(text("SELECT d.work_item_id, d.engagement_id, v.form FROM trust_distributions d JOIN LATERAL (SELECT form FROM trust_distribution_versions x WHERE x.distribution_id = d.id ORDER BY seq DESC LIMIT 1) v ON true WHERE d.id = :d"), {"d": distribution_id})).first()
    if head is None:
        raise NotFound("trust_distribution")
    await _scope(ctx, head[0], "trust_distribution.edit")
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(text("SELECT max(seq) FROM trust_distribution_versions WHERE distribution_id = :d"), {"d": distribution_id})
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await _distribution_version(tx, ctx, distribution_id, body.expected_version + 1, body.paid_on, body.amount, head[2], body.source, body.clause_id, body.reason)
        tx.record(
            "trust_distribution.changed", target=Target("trust_distribution", distribution_id),
            after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=head[1]),
        )  # fmt: skip
        await recompute_in(tx, head[0], head[1])
    return next(x for x in (await trust_distributions(ctx, head[0])).distributions if x.id == distribution_id)


async def import_from_statement(ctx: AuthContext, return_id: UUID, evidence_version_id: UUID) -> FaiLinesOut:
    """Import from statement: P-11's extracted tables become FAI lines a person then reviews. With
    no tables for the document the cut-4 fallback holds: manual entry with citations (409)."""
    _person(ctx, "fai_line.edit")
    await _scope(ctx, return_id, "fai_line.edit")
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT count(*) FROM extracted_tables WHERE evidence_version_id = :v"),
            {"v": evidence_version_id},
        )
    if not found:
        raise StatementTablesMissing(facts={"evidence_version_id": str(evidence_version_id)})
    # The statement's tables land as lines through the same path as manual entry, once the
    # custodial statement layout map exists (T-07 §4, P-11-T36); until then the fallback holds.
    raise StatementTablesMissing(facts={"layout": "custodial_statement_unmapped"})


# --- recompute -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Inputs:
    inputs: engine.FiduciaryInputs
    interpretation_hash: str
    distribution_amounts: dict[str, str]


async def _inputs(session: AsyncSession, return_id: UUID, tax_year: int, entity_kind: str) -> _Inputs:
    interp = (await session.execute(_INTERPRETATION, {"r": return_id})).first()
    if interp is None or interp[1] != "approved":
        raise InterpretationNotApproved(facts={"return_id": str(return_id)})
    codes = {k: v for k, v in (await session.execute(_DETERMINATION_CODES, {"i": interp[0]})).all()}
    entity_type = cast(
        engine.EntityType,
        "estate" if entity_kind == "estate" else _ENTITY.get(str(codes.get("trust_type", "complex")), "complex_trust"),
    )
    gains_in_dni = str(codes.get("fai_definition", "")).startswith("gains_to_income")
    determinations = engine.Determinations(entity_type, gains_in_dni=gains_in_dni)
    rows = (await session.execute(_LINES, {"r": return_id})).all()
    qualified: dict[UUID, Decimal] = {}
    for r in rows:
        if r[1] == "qualified_dividends" and r[2] is not None:
            qualified[r[2]] = qualified.get(r[2], Decimal(0)) + Decimal(r[5])
    lines = tuple(
        engine.FaiLine(
            key=str(r[0]), character=_CHARACTER[r[1]], amount=Decimal(r[5]),
            qualified=qualified.get(r[0], engine.ZERO),
            to_principal=r[1] == "capital_gain" and not gains_in_dni,
        )  # fmt: skip
        for r in rows
        if r[1] != "qualified_dividends"
    )
    expenses = tuple(
        engine.TrustExpense(str(r[0]), Decimal(r[4]), r[3], bool(r[5]))
        for r in (await session.execute(_EXPENSES, {"r": return_id})).all()
    )
    drows = (await session.execute(_DISTRIBUTIONS, {"r": return_id})).all()
    names = await _contact_names(session, sorted({r[1] for r in drows}, key=str))
    distributions = tuple(
        engine.Distribution(str(r[1]), names.get(r[1], ""), r[3], Decimal(r[4]), r[6])
        for r in drows
    )
    return _Inputs(
        engine.FiduciaryInputs(tax_year, determinations, lines, expenses, distributions),
        str(interp[2] or "0" * 64),
        {str(r[0]): f"{Decimal(r[4]):.2f}" for r in drows},
    )


def _outputs(result: engine.FiduciaryResult, distributions: dict[str, str]) -> dict[str, object]:
    def tree(rows: Sequence[engine.TreeRow]) -> list[dict[str, object]]:
        return [
            {"key": r.key, "label": r.label, "amount": f"{r.amount:.2f}", "clause": r.clause_ref,
             "children": tree(r.children)}  # fmt: skip
            for r in rows
        ]

    return {
        "fai": f"{result.fai:.2f}", "dni": f"{result.dni:.2f}", "idd": f"{result.idd:.2f}",
        "distributions": f"{result.distributions:.2f}",
        "retained_dni": f"{result.retained_dni:.2f}",
        "taxable_income": f"{result.taxable_income:.2f}", "exemption": f"{result.exemption:.2f}",
        "dni_by_character": {k: f"{v:.2f}" for k, v in result.dni_by_character.items()},
        "dni_qualified": f"{result.dni_qualified:.2f}", "tie": result.tie,
        "notes": list(result.notes), "tree": tree(result.tree),
        "allocations": [
            {"beneficiary": a.beneficiary, "name": a.name, "distributions": f"{a.distributions:.2f}",
             "share": str(a.share), "box_1": f"{a.box_1:.2f}", "box_2a": f"{a.box_2a:.2f}",
             "box_2b": f"{a.box_2b:.2f}", "box_other": {k: f"{v:.2f}" for k, v in a.box_other.items()}}
            for a in result.allocations
        ],
        "distributions_by_id": distributions,
    }  # fmt: skip


def _hash(outputs: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def recompute_in(tx: UnitOfWork, return_id: UUID, engagement_id: UUID) -> FiduciaryRecomputeOut:
    """Inside the caller's unit of work: a new version unless the inputs hash is the current's."""
    head = (await tx.session.execute(text("SELECT r.tax_year, t.fiduciary_kind FROM tax_returns r LEFT JOIN trust_profiles t ON t.client_entity_id = r.client_entity_id WHERE r.work_item_id = :r"), {"r": return_id})).first()
    if head is None:
        raise NotFound("tax_return")
    built = await _inputs(tx.session, return_id, int(head[0]), str(head[1] or "trust"))
    result = engine.compute(built.inputs)
    current = (await tx.session.execute(_CURRENT, {"r": return_id})).first()
    if current is not None and current[2] == result.inputs_hash:
        return FiduciaryRecomputeOut(computation_id=current[0], version_no=int(current[1]), created=False)
    outputs = _outputs(result, built.distribution_amounts)
    content = _hash(outputs)
    version_no = 1 if current is None else int(current[1]) + 1
    params = engine.parameters(result.tax_year)
    tenant_id = (await transaction_context(tx.session)).tenant_id
    computation_id = await tx.session.scalar(
        text(
            "INSERT INTO fai_dni_computations (tenant_id, engagement_id, work_item_id, "
            "version_no, interpretation_hash, inputs_hash, engine_name, engine_version, "
            "parameter_set, income_distribution_deduction, outputs, prior_computation_id, "
            "content_hash) VALUES (:t, :e, :w, :v, :ih, :inp, :en, :ev, :ps, :idd, "
            "CAST(:o AS jsonb), :prior, :ch) RETURNING id"
        ),
        {"t": tenant_id, "e": engagement_id, "w": return_id, "v": version_no,
         "ih": built.interpretation_hash, "inp": result.inputs_hash, "en": result.engine_name,
         "ev": result.engine_version, "ps": f"ty{params.tax_year}.v{params.version}",
         "idd": result.idd, "o": json.dumps(outputs, sort_keys=True),
         "prior": None if current is None else current[0], "ch": content},
    )  # fmt: skip
    for a in result.allocations:
        await tx.session.execute(
            text(
                "INSERT INTO beneficiary_allocations (tenant_id, computation_id, "
                "beneficiary_contact_id, distributions, share, dni_allocated, box_1, box_2a, box_2b, "
                "box_other) VALUES (:t, :c, :b, :d, :s, :dni, :b1, :b2a, :b2b, CAST(:o AS jsonb))"
            ),
            {"t": tenant_id, "c": computation_id, "b": UUID(a.beneficiary),
             "d": a.distributions, "s": a.share, "dni": a.dni_allocated, "b1": a.box_1,
             "b2a": a.box_2a, "b2b": a.box_2b,
             "o": json.dumps({k: f"{v:.2f}" for k, v in a.box_other.items()}, sort_keys=True)},
        )  # fmt: skip
        for box, value in (("box_1", a.box_1), ("box_2a", a.box_2a), ("box_2b", a.box_2b)):
            await record_value(
                tx, engagement_id=engagement_id, target_type=TARGET, target_id=return_id,
                field_key=f"k1_1041.{a.beneficiary}.{box}", value={"t": "decimal", "v": f"{value:.2f}"},
                value_source="formula", cause="recompute",
            )  # fmt: skip
    tx.record(
        "fiduciary_computation.computed", target=Target(TARGET, computation_id),
        after=Ref(version=version_no, inputs_hash=result.inputs_hash),
        scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
    )  # fmt: skip
    return FiduciaryRecomputeOut(computation_id=computation_id, version_no=version_no, created=True)


async def recompute(ctx: AuthContext, return_id: UUID) -> FiduciaryRecomputeOut:
    _person(ctx, "fiduciary_computation.recompute")
    engagement, _, _ = await _scope(ctx, return_id, "fiduciary_computation.recompute")
    async with uow(ctx.tenant) as tx:
        out = await recompute_in(tx, return_id, engagement)
        if not out.created:
            tx.record("fiduciary_computation.unchanged", target=Target(TARGET, out.computation_id))
    return out


async def recompute_after_approval(tenant_id: UUID, interpretation_id: UUID) -> None:
    """The instrument's L3 lock approved the reading: its return's workpaper recomputes."""
    tenant = TenantContext(tenant_id, "system", "tax:fiduciary_recompute")
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM instrument_interpretations WHERE id = :i AND status = 'approved'"),
            {"i": interpretation_id},
        )
    if found is not None:
        await recompute_system(tenant, cast(UUID, found))


async def recompute_system(tenant: TenantContext, return_id: UUID) -> None:
    """On the interpretation's approval (the instrument lock's subscriber)."""
    async with tenant_session(tenant) as session:
        head = (await session.execute(text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"), {"r": return_id})).first()
    if head is None:
        return
    async with uow(tenant) as tx:
        out = await recompute_in(tx, return_id, head[0])
        if not out.created:
            tx.record("fiduciary_computation.unchanged", target=Target(TARGET, out.computation_id))


# --- reads -----------------------------------------------------------------------------------------


async def _signed_outputs(tenant: TenantContext, session: AsyncSession, return_id: UUID) -> dict[str, object] | None:
    """The outputs of the version the L2 sign-off was given on, when it is now stale."""
    current = (await session.execute(_CURRENT, {"r": return_id})).first()
    if current is None:
        return None
    stale = [s for s in await stale_of(tenant, TARGET, {return_id: str(current[4])}) if s.level == 2]
    if not stale:
        return None
    found = (await session.execute(_BY_HASH, {"r": return_id, "h": stale[0].signed_hash})).first()
    return None if found is None else cast(dict[str, object], found[0])


def _flatten(
    rows: Sequence[dict[str, object]], parent: str | None, level: int, prior: dict[str, str],
) -> list[FiduciaryTreeNodeOut]:  # fmt: skip
    out: list[FiduciaryTreeNodeOut] = []
    for r in rows:
        key, amount = str(r["key"]), Decimal(str(r["amount"]))
        was = prior.get(key)
        changed = was is not None and Decimal(was) != amount
        clause = r.get("clause")
        out.append(
            FiduciaryTreeNodeOut(
                key=key, parent_key=parent, level=level, label=str(r["label"]), value=amount,
                box_label=None, clause_labels=[str(clause)] if clause else [], provenance_id=None,
                changed=changed, prior_value=Decimal(was) if changed and was is not None else None,
                highlighted=changed,
            )
        )  # fmt: skip
        out.extend(_flatten(cast(list[dict[str, object]], r.get("children") or []), key, level + 1, prior))
    return out


def _prior_amounts(rows: Sequence[dict[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        out[str(r["key"])] = str(r["amount"])
        out |= _prior_amounts(cast(list[dict[str, object]], r.get("children") or []))
    return out


async def computation(ctx: AuthContext, return_id: UUID, view: str = "tree") -> FiduciaryComputationOut:
    await _scope(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        current = (await session.execute(_CURRENT, {"r": return_id})).first()
        if current is None:
            interp = (await session.execute(_INTERPRETATION, {"r": return_id})).first()
            if interp is None or interp[1] != "approved":
                raise InterpretationNotApproved(facts={"return_id": str(return_id)})
            raise NotFound("fiduciary_computation")
        prior = await _signed_outputs(ctx.tenant, session, return_id)
    outputs = cast(dict[str, object], current[3])
    prior_rows = _prior_amounts(cast(list[dict[str, object]], (prior or {}).get("tree", [])))
    nodes = _flatten(cast(list[dict[str, object]], outputs.get("tree", [])), None, 0, prior_rows)
    allocations = cast(list[dict[str, object]], outputs.get("allocations", []))
    by_character = [
        FiduciaryCharacterRowOut(
            kind=kind,  # pyright: ignore[reportArgumentType] -- a FiduciaryCharacterRowOut kind
            total=sum((Decimal(str(a[box])) for a in allocations), Decimal(0)),
            by_party=[FiduciaryCharacterAmountOut(party=str(a["beneficiary"]), amount=Decimal(str(a[box]))) for a in allocations],
        )
        for kind, box in (("interest", "box_1"), ("ordinary_dividends", "box_2a"), ("qualified_dividends", "box_2b"))
    ]
    states = await sign_off_states(ctx.tenant, TARGET, [return_id], {return_id: str(current[4])})
    l2 = next((s for s in states.get(return_id, []) if s.level == 2), None)
    signer = None if l2 is None or l2.signed_by is None else (await names_of([l2.signed_by])).get(l2.signed_by)
    stale = l2 is not None and l2.stale
    tallies = [
        FiduciaryTallyOut(key="idd", label="Income distribution deduction", value=Decimal(str(outputs["idd"])), state="tie" if outputs.get("tie") else "off"),  # pyright: ignore[reportArgumentType] -- a tally word
        FiduciaryTallyOut(key="dni", label="Distributable net income", value=Decimal(str(outputs["dni"])), state=None),
        FiduciaryTallyOut(key="taxable_income", label="Taxable income", value=Decimal(str(outputs["taxable_income"])), state=None),
    ]
    return FiduciaryComputationOut(
        return_id=return_id, computation_id=current[0], version_no=int(current[1]),
        view="character" if view == "character" else "tree", engine_name="fiduciary",
        engine_version=str(current[6]), inputs_hash=str(current[2]), parameter_set=str(current[7]),
        computed_at=current[5], nodes=nodes, by_character=by_character, tallies=tallies,
        notes=[str(n) for n in cast(list[object], outputs.get("notes", []))],
        banner="Changed since the last sign-off · re-approval needed" if stale else None,
        signed_by_initials=None if signer is None else "".join(w[0] for w in signer.split()[:2]).upper(),
        sign_off_stale=stale,
        allowed_actions=["fai_line.edit", "trust_distribution.edit", "fiduciary_computation.recompute", "fiduciary_computation.export", "sign_off.l2"],
    )  # fmt: skip


async def export_xlsx(ctx: AuthContext, return_id: UUID, version_no: int | None = None) -> bytes:
    """One version as a deterministic workbook (no $; numbers as numbers): byte-identical twice."""
    await _scope(ctx, return_id, "fiduciary_computation.export")
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT version_no, outputs FROM fai_dni_computations WHERE work_item_id = :r "
                    "AND (:v IS NULL OR version_no = :v) ORDER BY version_no DESC LIMIT 1"
                ),
                {"r": return_id, "v": version_no},
            )
        ).first()
    if row is None:
        raise NotFound("fiduciary_computation")
    return workbook_of(int(row[0]), cast(dict[str, object], row[1]))


def workbook_of(version_no: int, outputs: dict[str, object]) -> bytes:
    """A version's outputs as the deterministic workbook (pure: the same outputs, the same bytes)."""
    tree_rows: list[list[str | Decimal | None]] = [["Row", "Label", "Amount", "Clause"]]

    def walk(rows: Sequence[dict[str, object]], depth: int) -> None:
        for r in rows:
            tree_rows.append([str(r["key"]), "  " * depth + str(r["label"]), Decimal(str(r["amount"])), cast(str | None, r.get("clause"))])
            walk(cast(list[dict[str, object]], r.get("children") or []), depth + 1)

    walk(cast(list[dict[str, object]], outputs.get("tree", [])), 0)
    alloc: list[list[str | Decimal | None]] = [["Beneficiary", "Distributions", "Share", "Box 1", "Box 2a", "Box 2b"]]
    for a in cast(list[dict[str, object]], outputs.get("allocations", [])):
        alloc.append([str(a["name"]), Decimal(str(a["distributions"])), Decimal(str(a["share"])), Decimal(str(a["box_1"])), Decimal(str(a["box_2a"])), Decimal(str(a["box_2b"]))])
    return workbook([Sheet(f"Computation v{version_no}", tree_rows), Sheet("Allocation", alloc)])


# --- the reviewable (DEC-84: L2) --------------------------------------------------------------------


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (work_item_id) work_item_id, content_hash FROM "
                    "fai_dni_computations WHERE engagement_id = :e ORDER BY work_item_id, version_no DESC"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [Reviewable(TARGET, r[0], f"fiduciary:{r[0]}", "Fiduciary computation", r[1], True) for r in rows]


async def facts(tenant: TenantContext, target_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        r = (
            await session.execute(
                text(
                    "SELECT c.engagement_id, c.content_hash, c.version_no, "
                    "(SELECT array_agg(DISTINCT v.set_by_id) FROM trust_distributions d JOIN "
                    "trust_distribution_versions v ON v.distribution_id = d.id WHERE d.work_item_id = "
                    "c.work_item_id) FROM fai_dni_computations c WHERE c.work_item_id = :r "
                    "ORDER BY c.version_no DESC LIMIT 1"
                ),
                {"r": target_id},
            )
        ).first()
    if r is None:
        return None
    return ReviewableFacts(
        target_type=TARGET, target_id=target_id, engagement_id=r[0], content_hash=r[1],
        version_no=int(r[2]), preparer_user_ids=frozenset(r[3] or ()), required_levels=LEVELS,
        label="Fiduciary computation", work_item_id=target_id,
    )  # fmt: skip


def register() -> None:
    register_reviewable(TARGET, reviewables)
    register_reviewable_facts(TARGET, facts)
