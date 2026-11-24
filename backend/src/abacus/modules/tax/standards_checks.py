"""The 1065 Review Checklist v4 check library (T-08-T23; TASK-8916; T-08 AC4.2; TAX-14; ADR-050;
OQ-3; DEC-5918; amber). No model anywhere: every check is a pure function of one return's facts
snapshot (`Facts`), gathered once per return by code (`gather`) and registered to the standards
run's slot (`standards_runs.register_check`) under a check code the firm's checklist items name.

The eight named checks (TAX-14's inline list; the UI keeps "C-17", code keys `1065-v4/C-17`):

- C-04 `check.k1_count_item_i`: Item I equals the partners on the return (`check:k1_count`).
- C-09 `check.schedule_k_k1_sum`: each Schedule K line equals its K-1 columns' sum, 09 against
  06 (`tie_out:k1_sum_k`).
- C-12 `check.m3_required`: Schedule M-3 is on the return exactly when total assets reach
  10,000,000 (`check:m3_required`).
- C-15 `check.tb_balanced_mapped`: the trial balance foots and no account is unmapped
  (`tie_out:tb_foots`, `check:tb_unmapped`).
- C-17 `check.m2_line9_schedule_l21`: M-2 line 9 equals Schedule L line 21, assets less
  liabilities (`tie_out:item_l_m2`).
- C-22 `check.partnership_representative`: a partnership representative is designated
  (`check:partnership_representative`).
- C-31 `check.section_754_documented`: a year with a transfer of interest has its §754 position
  decided (`decision:section_754`).
- C-38 `check.ptet_recorded`: every apportioned state has its PTET election, and an elected one a
  payment (`check:ptet_recorded`).

The reference in brackets is the one an exception links (an open issue raised under it) or
raises under.

C-17's off 6,200 is the tax-exempt interest the capital rollforward omits: the same gap the
workbook's `item_l_m2` tie-out raised its open issue for, so the run links that issue (Ridgeline's
count stays 11). C-31 links the §754 decision's issue under `decision:section_754`.

The data-presence checks (`presence.*`) bind the checklist's other items: each passes when the
datum the item reviews is on the return (a workbook sheet populated, the engine summary, partner
TINs, the profile's facts, the due date …) and otherwise raises under `presence:<what>`. An item
whose datum does not apply to the return (no states: the state sheet) is not applicable.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.tax.standards_runs import TieOutResult

ZERO: Final = Decimal(0)
M3_ASSETS: Final = Decimal("10000000")
Values = Mapping[str, Mapping[str, object] | None]


@dataclass(frozen=True)
class Facts:
    """One return's facts for the checks, read by code (`gather`), never by a model."""

    form: str
    values: Values = field(default_factory=dict[str, Mapping[str, object] | None])
    partners: int = 0
    partners_missing_tin: int = 0
    k1_recipients: int = 0
    engine_lines: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])
    has_engine_summary: bool = False
    profile: Mapping[str, object] = field(default_factory=dict[str, object])
    unmapped: int | None = None
    transfers: int = 0
    section_754: str = "none"  # none | open | sent_to_client | decided
    states: tuple[str, ...] = ()
    ptet_elections: Mapping[str, str] = field(default_factory=dict[str, str])
    ptet_paid: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])
    original_due_on: date | None = None
    ownership_periods: int = 0
    assets_registered: int = 0


# --- helpers -------------------------------------------------------------------------------------


def _dec(values: Values, key: str) -> Decimal | None:
    cell = values.get(key)
    if cell is None or cell.get("v") in (None, ""):
        return None
    try:
        return Decimal(str(cell["v"]))
    except (InvalidOperation, ArithmeticError):
        return None


def _rows(values: Values, sheet: str, col: str = "A") -> list[int]:
    out: list[int] = []
    n = 2
    while f"{sheet}!{col}{n}" in values:
        out.append(n)
        n += 1
    return out


def _form_lines(values: Values) -> dict[str, Decimal]:
    lines: dict[str, Decimal] = {}
    for n in _rows(values, "03"):
        cell = values.get(f"03!A{n}")
        key = None if cell is None else cell.get("v")
        amount = _dec(values, f"03!C{n}")
        if key not in (None, "") and amount is not None:
            lines[str(key)] = lines.get(str(key), ZERO) + amount
    return lines


def total_assets(values: Values) -> Decimal | None:
    """Schedule L total assets from sheet 03's signed nets (asset lines and their contra lines;
    `entity_tb.group_of`), None without a Schedule L line."""
    from abacus.modules.tax.entity_tb import group_of

    lines = _form_lines(values)
    assets = [v for k, v in lines.items() if k.startswith("L") and group_of(k) == "assets"]
    return sum(assets, ZERO) if assets else None


def _tie(values: Values, key: str) -> object | None:
    from abacus.modules.tax.entity_sections import tie_outs

    return next(
        (t for t in tie_outs(cast("dict[str, dict[str, object]]", values)) if t.key == key), None
    )


def _tie_result(values: Values, key: str, title: str) -> TieOutResult:
    found = _tie(values, key)
    if found is None or getattr(found, "state", "pending") == "pending":
        return TieOutResult("not_applicable")
    links = cast("tuple[Mapping[str, str], ...]", getattr(found, "links", ()))
    anchor = dict(links[0]) if links else None
    difference = cast("Decimal | None", getattr(found, "difference", None))
    if getattr(found, "state", "") == "tie":
        return TieOutResult("pass", difference, anchor)
    return TieOutResult(
        "exception", difference, anchor, f"tie_out:{key}",
        f"{title}: off {abs(difference or ZERO):,.0f}",
    )  # fmt: skip


# --- the eight named checks ----------------------------------------------------------------------


def c04_k1_count(f: Facts) -> TieOutResult:
    """Item I (the engine's, else 09's recipient columns) equals the partners on the return."""
    if not f.partners:
        return TieOutResult("not_applicable")
    columns = 0
    while f"09!{chr(ord('B') + columns)}1" in f.values:
        columns += 1
    item_i = f.engine_lines.get("1065.item_i")
    reported = int(item_i) if item_i is not None else columns
    anchor = {"sheet": "09", "range": "B1"}
    if reported == f.partners:
        return TieOutResult("pass", ZERO, anchor)
    return TieOutResult(
        "exception", Decimal(reported - f.partners), anchor, "check:k1_count",
        f"Item I reads {reported} K-1s for {f.partners} partners",
    )  # fmt: skip


def c09_schedule_k_k1_sum(f: Facts) -> TieOutResult:
    return _tie_result(f.values, "k1_sum_k", "Schedule K equals Σ K-1s")


def c12_m3_required(f: Facts) -> TieOutResult:
    """Schedule M-3 is required from total assets of 10,000,000 (Form 1065 instructions); it is
    on the return when sheet 03 maps an M-3 line or the engine reports one."""
    assets = total_assets(f.values)
    if assets is None:
        return TieOutResult("not_applicable")
    required = assets >= M3_ASSETS
    lines = _form_lines(f.values)
    applied = any(k.startswith("M-3") for k in lines) or bool(f.engine_lines.get("1065.m3"))
    anchor = {"sheet": "03", "range": "A2"}
    if required == applied:
        return TieOutResult("pass", None, anchor)
    title = (
        f"Schedule M-3 required: total assets {assets:,.0f} reach 10,000,000"
        if required
        else "Schedule M-3 attached below the 10,000,000 threshold"
    )
    return TieOutResult("exception", assets, anchor, "check:m3_required", title)


def c15_tb_balanced_mapped(f: Facts) -> TieOutResult:
    foots = _tie_result(f.values, "tb_foots", "Trial balance foots")
    if foots.outcome == "exception":
        return foots
    if f.unmapped:
        return TieOutResult(
            "exception", Decimal(f.unmapped), {"sheet": "03", "range": "A2"},
            "check:tb_unmapped", f"{f.unmapped} accounts unmapped",
        )  # fmt: skip
    if foots.outcome == "not_applicable" and f.unmapped is None:
        return TieOutResult("not_applicable")
    return TieOutResult("pass", ZERO, foots.anchor)


def c17_m2_line9_schedule_l21(f: Facts) -> TieOutResult:
    """M-2 line 9 (07!B9) equals Schedule L line 21: total assets less total liabilities from
    sheet 03's form lines (`form_preview_blockers.schedule_l_line_21`)."""
    from abacus.modules.tax.form_preview_blockers import schedule_l_line_21

    line_9 = _dec(f.values, "07!B9")
    line_21 = schedule_l_line_21(cast("dict[str, dict[str, object]]", f.values))
    if line_9 is None or line_21 is None:
        return TieOutResult("not_applicable")
    difference = line_9 - line_21
    anchor = {"sheet": "07", "range": "B9"}
    if difference == ZERO:
        return TieOutResult("pass", ZERO, anchor)
    return TieOutResult(
        "exception", difference, anchor, "tie_out:item_l_m2",
        f"Schedule M-2 line 9 equals Schedule L line 21: off {abs(difference):,.0f}",
    )  # fmt: skip


def c22_partnership_representative(f: Facts) -> TieOutResult:
    anchor = {"tab": "general_information"}
    if f.profile.get("partnership_representative_contact_id"):
        return TieOutResult("pass", None, anchor)
    return TieOutResult(
        "exception", None, anchor, "check:partnership_representative",
        "Partnership representative not designated",
    )  # fmt: skip


def c31_section_754_documented(f: Facts) -> TieOutResult:
    """A year with a transfer of interest documents its §743(b)/§754 position: the C3 §754
    decision is decided (open or out with the client is not)."""
    if not f.transfers:
        return TieOutResult("not_applicable")
    anchor = {"tab": "basis"}
    if f.section_754 == "decided":
        return TieOutResult("pass", None, anchor)
    return TieOutResult(
        "exception", None, anchor, "decision:section_754",
        "Transfer of interest: §743(b)/§754 position not documented",
    )  # fmt: skip


def c38_ptet_recorded(f: Facts) -> TieOutResult:
    if not f.states:
        return TieOutResult("not_applicable")
    anchor = {"sheet": "08", "range": "A2"}
    missing = [s for s in f.states if s not in f.ptet_elections]
    unpaid = [
        s for s, e in f.ptet_elections.items()
        if e == "elected" and f.ptet_paid.get(s, ZERO) <= ZERO
    ]  # fmt: skip
    if not missing and not unpaid:
        return TieOutResult("pass", None, anchor)
    parts: list[str] = []
    if missing:
        parts.append("no election for " + ", ".join(sorted(missing)))
    if unpaid:
        parts.append("no payment for " + ", ".join(sorted(unpaid)))
    return TieOutResult(
        "exception", Decimal(len(missing) + len(unpaid)), anchor, "check:ptet_recorded",
        "PTET elections and payments: " + "; ".join(parts),
    )  # fmt: skip


NAMED: Final[dict[str, tuple[str, Callable[[Facts], TieOutResult]]]] = {
    "check.k1_count_item_i": ("K-1 count equals Item I", c04_k1_count),
    "check.schedule_k_k1_sum": ("Schedule K equals Σ K-1s", c09_schedule_k_k1_sum),
    "check.m3_required": ("Schedule M-3 required test applied", c12_m3_required),
    "check.tb_balanced_mapped": ("TB balanced and Unmapped 0", c15_tb_balanced_mapped),
    "check.m2_line9_schedule_l21": (
        "Schedule M-2 line 9 equals Schedule L line 21", c17_m2_line9_schedule_l21,
    ),
    "check.partnership_representative": (
        "Partnership representative designated", c22_partnership_representative,
    ),
    "check.section_754_documented": (
        "Transfer of interest: §743(b)/§754 position documented", c31_section_754_documented,
    ),
    "check.ptet_recorded": ("PTET elections and payments recorded", c38_ptet_recorded),
}  # fmt: skip


# --- data presence -------------------------------------------------------------------------------


def _sheet(sheet: str, col: str = "A") -> Callable[[Facts], bool | None]:
    return lambda f: bool(_rows(f.values, sheet, col))


def _profile(key: str) -> Callable[[Facts], bool | None]:
    return lambda f: f.profile.get(key) not in (None, "")


def _m2(f: Facts) -> bool | None:
    return all(f"07!B{n}" in f.values for n in (1, 9))


def _states(f: Facts) -> bool | None:
    return None if not f.states else bool(_rows(f.values, "08", "J") or _rows(f.values, "08"))


def _k1_columns(f: Facts) -> bool | None:
    return None if not f.partners else "09!B1" in f.values


def _tins(f: Facts) -> bool | None:
    return None if not f.partners else f.partners_missing_tin == 0


# (code, description, predicate, anchor): None from a predicate = not applicable.
PRESENCE: Final[tuple[tuple[str, str, Callable[[Facts], bool | None], dict[str, str]], ...]] = (
    ("presence.trial_balance", "Trial balance loaded", _sheet("01"), {"sheet": "01"}),
    ("presence.form_lines", "Form lines mapped", _sheet("03"), {"sheet": "03"}),
    ("presence.allocation", "Allocation sheet populated", _sheet("04"), {"sheet": "04"}),
    ("presence.capital_accounts", "Capital accounts per partner", _sheet("05"), {"sheet": "05"}),
    ("presence.schedule_k", "Schedule K lines", _sheet("06"), {"sheet": "06"}),
    ("presence.schedule_m2", "Schedule M-2 populated", _m2, {"sheet": "07"}),
    ("presence.state_sheet", "State apportionment sheet", _states, {"sheet": "08"}),
    ("presence.k1_columns", "K-1 columns per partner", _k1_columns, {"sheet": "09"}),
    ("presence.engine_summary", "Engine summary imported", lambda f: f.has_engine_summary,
     {"tab": "overview"}),
    ("presence.partners", "Partners on the return", lambda f: f.partners > 0,
     {"tab": "partners"}),
    ("presence.partner_tins", "Partner TINs on file", _tins, {"tab": "partners"}),
    ("presence.ownership_periods", "Ownership periods recorded",
     lambda f: None if not f.partners else f.ownership_periods > 0, {"tab": "partners"}),
    ("presence.k1_recipients", "K-1 recipients imported",
     lambda f: None if not f.partners else f.k1_recipients > 0, {"tab": "k1s"}),
    ("presence.accounting_method", "Accounting method (Item H)", _profile("accounting_method"),
     {"tab": "general_information"}),
    ("presence.business_code", "Business code (Item C)", _profile("business_code"),
     {"tab": "general_information"}),
    ("presence.principal_activity", "Principal business activity (Item A)",
     _profile("principal_activity"), {"tab": "general_information"}),
    ("presence.books_basis", "Books basis recorded", _profile("books_basis"),
     {"tab": "general_information"}),
    ("presence.prior_year_return", "Prior-year return linked", _profile("prior_year_return_id"),
     {"tab": "overview"}),
    ("presence.due_date", "Due date computed", lambda f: f.original_due_on is not None,
     {"tab": "overview"}),
    ("presence.fixed_assets", "Fixed-asset register", lambda f: f.assets_registered > 0,
     {"tab": "fixed_assets"}),
)  # fmt: skip


def presence_check(
    code: str, predicate: Callable[[Facts], bool | None], anchor: dict[str, str], label: str
) -> Callable[[Facts], TieOutResult]:
    what = code.removeprefix("presence.")

    def run(f: Facts) -> TieOutResult:
        found = predicate(f)
        if found is None:
            return TieOutResult("not_applicable")
        if found:
            return TieOutResult("pass", None, anchor)
        return TieOutResult("exception", None, anchor, f"presence:{what}", f"{label}: missing")

    return run


# --- gathering (code; the only I/O) --------------------------------------------------------------

_PARTNERS: Final = text(
    "SELECT count(*) AS n, count(*) FILTER (WHERE tin_last4 IS NULL) AS no_tin FROM partners "
    "WHERE work_item_id = :r AND withdrawn_on IS NULL"
)
_K1S: Final = text("SELECT count(*) FROM k1_recipients WHERE work_item_id = :r")
_SUMMARY: Final = text(
    "SELECT lines FROM return_engine_summaries WHERE work_item_id = :r AND kind <> 'pro_forma' "
    "ORDER BY approved_at DESC LIMIT 1"
)
_PROFILE: Final = text(
    "SELECT principal_activity, business_code, accounting_method, books_basis, "
    "partnership_representative_contact_id, designated_individual_contact_id, "
    "prior_year_return_id FROM entity_return_profiles WHERE work_item_id = :r"
)
_RETURN: Final = text(
    "SELECT form, engagement_id, original_due_on FROM tax_returns WHERE work_item_id = :r"
)
_TRANSFERS: Final = text("SELECT count(*) FROM interest_transfers WHERE work_item_id = :r")
_PERIODS: Final = text("SELECT count(*) FROM ownership_periods WHERE work_item_id = :r")
_STATES: Final = text(
    "SELECT DISTINCT state FROM state_apportionments WHERE work_item_id = :r ORDER BY state"
)
_ELECTIONS: Final = text("SELECT state, election FROM ptet_elections WHERE work_item_id = :r")
_PAID: Final = text(
    "SELECT state, sum(amount) AS paid FROM ptet_payments WHERE work_item_id = :r GROUP BY state"
)
_ASSETS: Final = text("SELECT count(*) FROM fixed_assets WHERE work_item_id = :r")

# One snapshot per return for the length of one run item (the checks run back to back).
_CACHE: dict[tuple[UUID, UUID], tuple[float, Facts]] = {}
_TTL: Final = 30.0


def _lines(raw: object) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for entry in cast("list[object]", raw or []):
        if not isinstance(entry, dict):
            continue
        e = cast("dict[str, object]", entry)
        key, amount = e.get("line_key"), e.get("amount")
        if isinstance(key, str) and amount is not None:
            try:
                out[key] = Decimal(str(amount))
            except InvalidOperation:
                continue
    return out


async def _unmapped(tenant: TenantContext, engagement_id: UUID) -> int | None:
    from abacus.modules.ledger.api import engagement_trial_balances, mapped_trial_balance

    balances = await engagement_trial_balances(tenant, engagement_id)
    if not balances:
        return None
    newest = max(balances, key=lambda b: (b.period_end, b.current_version_no))
    mapped = await mapped_trial_balance(tenant, engagement_id, newest.id)
    return None if mapped is None else int(mapped.unmapped)


async def gather(tenant: TenantContext, return_id: UUID) -> Facts:
    """The return's facts (cached for one run item)."""
    key = (tenant.tenant_id, return_id)
    hit = _CACHE.get(key)
    if hit is not None and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    from abacus.modules.review.api import current_values
    from abacus.modules.tax.basis_service import section_754_state
    from abacus.modules.tax.workbook_service import WORKBOOK

    async with tenant_session(tenant) as session:
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
        partners = (await session.execute(_PARTNERS, {"r": return_id})).first()
        k1s = int(await session.scalar(_K1S, {"r": return_id}) or 0)
        summary = await session.scalar(_SUMMARY, {"r": return_id})
        profile = (await session.execute(_PROFILE, {"r": return_id})).mappings().first()
        transfers = int(await session.scalar(_TRANSFERS, {"r": return_id}) or 0)
        periods = int(await session.scalar(_PERIODS, {"r": return_id}) or 0)
        states = tuple(str(s) for s in await session.scalars(_STATES, {"r": return_id}))
        elections = {
            str(r.state): str(r.election)
            for r in await session.execute(_ELECTIONS, {"r": return_id})
        }
        paid = {
            str(r.state): Decimal(r.paid) for r in await session.execute(_PAID, {"r": return_id})
        }
        assets = int(await session.scalar(_ASSETS, {"r": return_id}) or 0)
    if ret is None:
        return Facts(form="")
    facts = Facts(
        form=str(ret.form),
        values=await current_values(tenant, WORKBOOK, return_id),
        partners=0 if partners is None else int(partners.n),
        partners_missing_tin=0 if partners is None else int(partners.no_tin),
        k1_recipients=k1s,
        engine_lines=_lines(summary),
        has_engine_summary=summary is not None,
        profile={} if profile is None else dict(profile),
        unmapped=await _unmapped(tenant, cast(UUID, ret.engagement_id)),
        transfers=transfers,
        section_754=await section_754_state(tenant, return_id) if transfers else "none",
        states=states,
        ptet_elections=elections,
        ptet_paid=paid,
        original_due_on=cast("date | None", ret.original_due_on),
        ownership_periods=periods,
        assets_registered=assets,
    )
    _CACHE[key] = (time.monotonic(), facts)
    if len(_CACHE) > 512:
        for stale in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:256]:
            _CACHE.pop(stale, None)
    return facts


def _registered(check: Callable[[Facts], TieOutResult]) -> object:
    async def run(
        tenant: TenantContext, return_id: UUID, _threshold: Decimal | None
    ) -> TieOutResult:
        return check(await gather(tenant, return_id))

    return run


def register() -> None:
    """At the tax api's import: the named checks and the data-presence checks."""
    from abacus.modules.tax.standards_runs import Check, register_check

    for code, (label, check) in NAMED.items():
        register_check(code, label, cast(Check, _registered(check)))
    for code, label, predicate, anchor in PRESENCE:
        register_check(
            code, label, cast(Check, _registered(presence_check(code, predicate, anchor, label)))
        )


__all__ = [
    "M3_ASSETS",
    "NAMED",
    "PRESENCE",
    "Facts",
    "c04_k1_count",
    "c09_schedule_k_k1_sum",
    "c12_m3_required",
    "c15_tb_balanced_mapped",
    "c17_m2_line9_schedule_l21",
    "c22_partnership_representative",
    "c31_section_754_documented",
    "c38_ptet_recorded",
    "gather",
    "presence_check",
    "register",
    "total_assets",
]
