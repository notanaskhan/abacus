"""The CAS package's figures (C-02-T21; TASK-8706; SPEC-701; CLS-08; ADR-050), pure.

Code computes; nothing here reads a database, the clock or a model. The service hands in the
posted trial balance (C9's adjusted TB, final layer, with only posted or recorded entries) and the
C9 mapping (account → FS line and its grouping class), and gets back:

- `statement_lines`: one line per FS line in catalogue order, its amount in presentation sign
  (assets and expenses debit-positive; liabilities, equity and revenue credit-positive) and the
  accounts it came from (`account_refs`, the per-figure lineage CLS-08 opens).
- `balance_sheet` and `income_statement` (current and prior month) with their totals; the balance
  sheet carries the year's net income as a derived line when no account maps to it.
- `cash_flows_ytd`: the indirect method from the opening and closing posted TBs, tied to the change
  in cash.
- `aging`: AR or AP open items by bucket, tied to the GL balance of the control account.
- `preconditions`: CLS-08c's blockers (accounts reconciled, open issues, unposted entries).
- `route`: K-02's SSARS framework for the period end and the CAS answer → the package route and
  its legend key ("No assurance is provided." for AR-C 70 preparation).
- `commentary`: the firm's commentary template filled from accepted flux explanations only.
- `content_hash`: SHA-256 of the canonical figures (a regenerated package with the same posted TB
  hashes the same).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Final, Literal

GroupingClass = Literal["assets", "liabilities", "equity", "revenue", "expenses"]
Route = Literal["ar_c_70_preparation", "cas_by_product", "standalone_letter"]
Blocker = Literal["accounts_unreconciled", "issues_open", "entries_unposted"]
Bucket = Literal["current", "1_30", "31_60", "61_90", "over_90"]

ZERO: Final = Decimal("0.00")
CENT: Final = Decimal("0.01")
BUCKETS: Final[tuple[Bucket, ...]] = ("current", "1_30", "31_60", "61_90", "over_90")
CREDIT_NORMAL: Final = frozenset({"liabilities", "equity", "revenue"})
NET_INCOME_KEY: Final = "net_income_ytd"
NO_ASSURANCE: Final = "ar_c_70.no_assurance"  # the legend's key; its words are the copy's
POSTED: Final = frozenset({"posted", "recorded"})


@dataclass(frozen=True, slots=True)
class LedgerAccount:
    """One account of the posted TB: its net balance, debit positive."""

    ref: str
    name: str
    balance: Decimal


@dataclass(frozen=True, slots=True)
class EntryLine:
    account_ref: str
    debit: Decimal
    credit: Decimal
    status: str  # an entry's status: only `posted` (written to QBO) or `recorded` count


@dataclass(frozen=True, slots=True)
class FsLine:
    """C9's FS line an account maps to, with its grouping, in catalogue order."""

    key: str
    label: str
    grouping_key: str
    grouping_label: str
    grouping_class: GroupingClass
    order: int


@dataclass(frozen=True, slots=True)
class StatementLine:
    key: str
    label: str
    grouping_key: str
    grouping_class: GroupingClass
    amount: Decimal
    account_refs: tuple[str, ...]
    prior: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    lines: tuple[StatementLine, ...]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal

    @property
    def balanced(self) -> bool:
        return self.total_assets == self.total_liabilities + self.total_equity


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    lines: tuple[StatementLine, ...]
    revenue: Decimal
    expenses: Decimal
    net_income: Decimal
    prior_net_income: Decimal | None


@dataclass(frozen=True, slots=True)
class CashFlows:
    operating: tuple[StatementLine, ...]
    investing: tuple[StatementLine, ...]
    financing: tuple[StatementLine, ...]
    net_change: Decimal
    opening_cash: Decimal
    closing_cash: Decimal

    @property
    def ties(self) -> bool:
        return self.opening_cash + self.net_change == self.closing_cash


@dataclass(frozen=True, slots=True)
class AgingItem:
    party: str
    bucket: Bucket
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Aging:
    buckets: tuple[tuple[Bucket, Decimal], ...]
    total: Decimal
    gl_balance: Decimal
    account_refs: tuple[str, ...]

    @property
    def ties(self) -> bool:
        return self.total == self.gl_balance


@dataclass(frozen=True, slots=True)
class Precondition:
    blocker: Blocker
    done: int | None = None
    of: int | None = None


@dataclass(frozen=True, slots=True)
class AcceptedFlux:
    """One flux explanation a Manager or Partner accepted (CLS-10); drafts never count."""

    label: str
    change: Decimal
    pct: Decimal | None
    explanation: str


@dataclass(frozen=True, slots=True)
class PackageRoute:
    route: Route
    legend_key: str | None


@dataclass(frozen=True, slots=True)
class Lineage:
    """Which accounts made each figure, by FS line key (CLS-08's per-figure lineage)."""

    by_line: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT)


def posted_tb(
    accounts: Iterable[LedgerAccount], entries: Iterable[EntryLine]
) -> list[LedgerAccount]:
    """The adjusted TB with only posted or recorded entries applied (a proposed or held entry
    never reaches a statement)."""
    out = {a.ref: a for a in accounts}
    for e in entries:
        if e.status not in POSTED:
            continue
        found = out.get(e.account_ref)
        base = found.balance if found is not None else ZERO
        name = found.name if found is not None else e.account_ref
        out[e.account_ref] = LedgerAccount(e.account_ref, name, _q(base + e.debit - e.credit))
    return list(out.values())


def _sign(cls: GroupingClass, debit_positive: Decimal) -> Decimal:
    return -debit_positive if cls in CREDIT_NORMAL else debit_positive


def statement_lines(
    accounts: Iterable[LedgerAccount],
    mapping: Mapping[str, FsLine],
    classes: frozenset[GroupingClass],
    prior: Iterable[LedgerAccount] | None = None,
) -> list[StatementLine]:
    """One line per mapped FS line of the given classes, in catalogue order, with lineage. An
    unmapped account is the mapping's open item (C9), never placed here by guess."""
    sums: dict[str, Decimal] = {}
    refs: dict[str, list[str]] = {}
    lines: dict[str, FsLine] = {}
    for a in accounts:
        fs = mapping.get(a.ref)
        if fs is None or fs.grouping_class not in classes:
            continue
        lines[fs.key] = fs
        sums[fs.key] = sums.get(fs.key, ZERO) + a.balance
        refs.setdefault(fs.key, []).append(a.ref)
    before: dict[str, Decimal] | None = None
    if prior is not None:
        before = {}
        for a in prior:
            fs = mapping.get(a.ref)
            if fs is None or fs.grouping_class not in classes:
                continue
            lines.setdefault(fs.key, fs)
            refs.setdefault(fs.key, [])
            before[fs.key] = before.get(fs.key, ZERO) + a.balance
    ordered = sorted(lines.values(), key=lambda f: (f.order, f.key))
    return [
        StatementLine(
            fs.key,
            fs.label,
            fs.grouping_key,
            fs.grouping_class,
            _q(_sign(fs.grouping_class, sums.get(fs.key, ZERO))),
            tuple(sorted(refs.get(fs.key, []))),
            None if before is None else _q(_sign(fs.grouping_class, before.get(fs.key, ZERO))),
        )
        for fs in ordered
    ]


def _total(lines: Iterable[StatementLine], cls: GroupingClass) -> Decimal:
    return _q(sum((ln.amount for ln in lines if ln.grouping_class == cls), ZERO))


def income_statement(
    accounts: Sequence[LedgerAccount],
    mapping: Mapping[str, FsLine],
    prior: Sequence[LedgerAccount] | None = None,
) -> IncomeStatement:
    """The month's income statement (CLS-08a), against the prior month when given."""
    lines = tuple(statement_lines(accounts, mapping, frozenset({"revenue", "expenses"}), prior))
    revenue, expenses = _total(lines, "revenue"), _total(lines, "expenses")
    prior_ni = None
    if prior is not None:
        prior_ni = _q(
            sum((ln.prior or ZERO for ln in lines if ln.grouping_class == "revenue"), ZERO)
            - sum((ln.prior or ZERO for ln in lines if ln.grouping_class == "expenses"), ZERO)
        )
    return IncomeStatement(lines, revenue, expenses, _q(revenue - expenses), prior_ni)


def balance_sheet(
    accounts: Sequence[LedgerAccount],
    mapping: Mapping[str, FsLine],
    *,
    net_income_label: str,
    equity_grouping_key: str,
) -> BalanceSheet:
    """The balance sheet at period end. The year's net income (income statement accounts not yet
    closed to retained earnings) is a derived equity line with every I/S account as its lineage,
    unless an equity account already carries it."""
    lines = statement_lines(accounts, mapping, frozenset({"assets", "liabilities", "equity"}))
    is_accounts = [
        a for a in accounts
        if (fs := mapping.get(a.ref)) is not None and fs.grouping_class in ("revenue", "expenses")
    ]  # fmt: skip
    if is_accounts and not any(ln.key == NET_INCOME_KEY for ln in lines):
        ni = _q(-sum((a.balance for a in is_accounts), ZERO))
        lines.append(
            StatementLine(
                NET_INCOME_KEY,
                net_income_label,
                equity_grouping_key,
                "equity",
                ni,
                tuple(sorted(a.ref for a in is_accounts)),
            )
        )
    return BalanceSheet(
        tuple(lines),
        _total(lines, "assets"),
        _total(lines, "liabilities"),
        _total(lines, "equity"),
    )


def cash_flows_ytd(
    opening: Sequence[LedgerAccount],
    closing: Sequence[LedgerAccount],
    mapping: Mapping[str, FsLine],
    *,
    cash_groupings: frozenset[str],
    noncash_expense_lines: frozenset[str],
    noncash_contra_lines: frozenset[str] = frozenset(),
    investing_groupings: frozenset[str],
    financing_groupings: frozenset[str],
) -> CashFlows:
    """The indirect method, year to date: net income, add back non-cash expenses, then the change
    in every other balance-sheet line by section. A contra line the non-cash expense moves
    (accumulated depreciation) is left out, its change being the add-back. A grouping not named as
    investing or financing is operating. Ties when opening cash + the net change equals closing
    cash."""
    open_bal = {a.ref: a.balance for a in opening}
    close_bal = {a.ref: a.balance for a in closing}
    refs = set(open_bal) | set(close_bal)

    def delta(ref: str) -> Decimal:
        return close_bal.get(ref, ZERO) - open_bal.get(ref, ZERO)

    by_line: dict[str, tuple[FsLine, Decimal, list[str]]] = {}
    ni = ZERO
    noncash = ZERO
    noncash_refs: list[str] = []
    cash_open = cash_close = ZERO
    for ref in sorted(refs):
        fs = mapping.get(ref)
        if fs is None:
            continue
        if fs.grouping_class in ("revenue", "expenses"):
            ni -= delta(ref)
            if fs.key in noncash_expense_lines:
                noncash += delta(ref)
                noncash_refs.append(ref)
            continue
        if fs.grouping_key in cash_groupings:
            cash_open += open_bal.get(ref, ZERO)
            cash_close += close_bal.get(ref, ZERO)
            continue
        line, amount, rs = by_line.get(fs.key, (fs, ZERO, []))
        # A debit-balance increase uses cash; a credit-balance increase provides it.
        by_line[fs.key] = (line, amount - delta(ref), [*rs, ref])
    operating = [
        StatementLine(NET_INCOME_KEY, "Net income", "operating", "equity", _q(ni), ()),
    ]
    if noncash_refs:
        operating.append(
            StatementLine("noncash", "Non-cash expenses", "operating", "expenses", _q(noncash),
                          tuple(noncash_refs))
        )  # fmt: skip
    investing: list[StatementLine] = []
    financing: list[StatementLine] = []
    for fs, amount, rs in sorted(by_line.values(), key=lambda t: (t[0].order, t[0].key)):
        if fs.key == NET_INCOME_KEY:
            continue
        if fs.key in noncash_expense_lines or fs.key in noncash_contra_lines:
            continue
        line = StatementLine(
            fs.key, fs.label, fs.grouping_key, fs.grouping_class, _q(amount), tuple(sorted(rs))
        )
        if fs.grouping_key in investing_groupings:
            investing.append(line)
        elif fs.grouping_key in financing_groupings:
            financing.append(line)
        else:
            operating.append(line)
    net = _q(sum((ln.amount for ln in (*operating, *investing, *financing)), ZERO))
    return CashFlows(
        tuple(operating), tuple(investing), tuple(financing), net, _q(cash_open), _q(cash_close)
    )


def aging(
    items: Iterable[AgingItem], *, gl_balance: Decimal, account_refs: Sequence[str]
) -> Aging:
    """AR or AP open items by bucket, tied to the control account's balance (CLS-08's agings)."""
    sums = dict.fromkeys(BUCKETS, ZERO)
    for item in items:
        sums[item.bucket] += item.amount
    total = _q(sum(sums.values(), ZERO))
    return Aging(
        tuple((b, _q(sums[b])) for b in BUCKETS), total, _q(gl_balance), tuple(account_refs)
    )


def preconditions(
    *, reconciled: int, accounts: int, open_issues: int, unposted_entries: int
) -> list[Precondition]:
    """CLS-08c's reasons a package cannot release: every plan account reconciled, no open
    exception, no entry left unposted. Empty when it may."""
    out: list[Precondition] = []
    if reconciled < accounts:
        out.append(Precondition("accounts_unreconciled", reconciled, accounts))
    if open_issues > 0:
        out.append(Precondition("issues_open", open_issues, None))
    if unposted_entries > 0:
        out.append(Precondition("entries_unposted", unposted_entries, None))
    return out


def route(framework: str, *, cas_answer: bool) -> PackageRoute:
    """K-02's `ssars_framework_for` (period end, early adoption) and the package's CAS answer:
    before SSARS 27, AR-C 70 preparation with "No assurance is provided." on every page; after,
    a CAS by-product (no legend) when the firm answers that the statements are a by-product of
    the CAS engagement, else a standalone preparation letter."""
    if framework == "ar_c_70_preparation":
        return PackageRoute("ar_c_70_preparation", NO_ASSURANCE)
    if framework != "cas_by_product":
        raise ValueError(f"unknown SSARS framework {framework!r}")
    return PackageRoute("cas_by_product" if cas_answer else "standalone_letter", None)


def _money(x: Decimal) -> str:
    sign = "-" if x < 0 else "+"
    return f"{sign}{abs(x):,.0f}"


def commentary(template: str, accepted: Sequence[AcceptedFlux]) -> str:
    """The firm's commentary template (content, from the database) with `{flux}` filled by one
    line per accepted explanation, in the order given; a template without the slot is kept as
    written. Draft explanations never appear (the caller passes accepted ones only)."""
    lines = []
    for f in accepted:
        pct = "" if f.pct is None else f" ({f.pct.quantize(Decimal('0.1'))}%)"
        lines.append(f"- {f.label}: {_money(f.change)}{pct}. {f.explanation}")
    return template.replace("{flux}", "\n".join(lines))


def content_hash(*parts: object) -> str:
    """SHA-256 over the canonical JSON of the figures (Decimal as text)."""

    def plain(x: object) -> object:
        if isinstance(x, Decimal):
            return str(x)
        if hasattr(x, "__dataclass_fields__"):
            return plain(asdict(x))  # type: ignore[call-overload]  # a dataclass instance, checked above
        if isinstance(x, Mapping):
            return {str(k): plain(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
        if isinstance(x, (list, tuple)):
            return [plain(v) for v in x]
        return x

    body = json.dumps([plain(p) for p in parts], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


__all__ = [
    "BUCKETS",
    "NET_INCOME_KEY",
    "NO_ASSURANCE",
    "AcceptedFlux",
    "Aging",
    "AgingItem",
    "BalanceSheet",
    "CashFlows",
    "EntryLine",
    "FsLine",
    "IncomeStatement",
    "LedgerAccount",
    "Lineage",
    "PackageRoute",
    "Precondition",
    "StatementLine",
    "aging",
    "balance_sheet",
    "cash_flows_ytd",
    "commentary",
    "content_hash",
    "income_statement",
    "posted_tb",
    "preconditions",
    "route",
    "statement_lines",
]
