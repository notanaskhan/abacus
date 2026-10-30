"""IRS transcripts as pure functions (T-01-T45; T-01 §3.6; CLI-05 a): parse the text of a Wage &
Income or Account transcript and compare it with the return as filed, by code (ADR-050).

A practitioner pulls the transcript from IRS e-Services under the 8821 on file and uploads it;
the agent never logs in to an IRS system and never does this arithmetic. The text is client-
system content and therefore hostile (ADR-052): it is bounded in size, read line by line with
anchored patterns, and anything this module does not recognise is reported as a problem rather
than guessed at. Nothing here reads a clock, a database or the network, so the same text and the
same return give the same comparison every time.

- **Wage & Income** (`wage_income`): one block per information return, opened by a line
  `Form <code> <title>`. Inside it, `Payer:`, `Employer:`, `Lender:` or `Filer:` names who issued
  it (on the same line or the next), and `<Label>: $1,234.00` lines carry the money fields, dot
  leaders allowed. Each form's comparable figure is one named field (`COMPARED_FIELD`); a form
  this module does not compare keeps its fields and is reported, never dropped.
- **Account** and **Record of Account** (`account`, `record_of_account`): the transaction table's
  rows `<TC> <explanation> [<cycle>] MM-DD-YYYY <amount>` and `Account balance: <amount>`. TC 922
  is the IRS review of unreported income, not an assessment (CLI-05 acceptance).
- **Comparison**: each comparable information return is matched to at most one filed item of the
  same form by payer name (normalised; the IRS truncates names, so a prefix of four characters or
  more matches): first every pair whose amounts are equal, then the rest in order. A line
  agrees when the amounts are equal; otherwise its difference is transcript minus return (the
  return amount is absent, "Not on return", when nothing matched). The result is `agrees` only
  when every compared line agrees. All figures are exact `Decimal`s; nothing is rounded.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final, Literal, cast

TranscriptKind = Literal["wage_income", "account", "record_of_account"]
LineStatus = Literal["agrees", "differs", "not_on_return"]
ComparisonResult = Literal["agrees", "differences"]
ProblemCode = Literal[
    "too_large",
    "no_tax_year",
    "kind_mismatch",
    "unreadable_amount",
    "form_without_payer",
    "form_without_amount",
    "form_not_compared",
    "duplicate_field",
    "unreadable_transaction",
    "transcript_not_parsed",
    "tax_year_mismatch",
    "not_wage_income",
]

# The comparison library's version, stored with every `transcript_comparisons` row so a later
# change to the matching rules never silently re-reads an old comparison.
COMPARE_VERSION: Final = "transcripts-v1"

# Hostile-content bounds (ADR-052): a real transcript is a few hundred lines.
MAX_TEXT_CHARS: Final = 400_000
MAX_LINES: Final = 20_000
MAX_ENTRIES: Final = 2_000

# The field each form is compared on, as the transcript labels it. Everything else on the form is
# kept in `fields` (withholding, for instance) but does not decide agreement.
COMPARED_FIELD: Final[dict[str, str]] = {
    "W-2": "wages, tips and other compensation",
    "W-2G": "gross winnings",
    "1098": "mortgage interest received from payer(s)/borrower(s)",
    "1098-E": "student loan interest received by lender",
    "1098-T": "payments received for qualified tuition and related expenses",
    "1099-INT": "interest",
    "1099-DIV": "total ordinary dividends",
    "1099-G": "unemployment compensation",
    "1099-MISC": "other income",
    "1099-NEC": "non-employee compensation",
    "1099-R": "gross distribution",
    "1099-K": "gross amount of payment card/third party network transactions",
    "1099-B": "proceeds",
    "SSA-1099": "benefits paid",
}

_PAYER_LABELS: Final = ("payer", "employer", "lender", "filer", "trustee")


def _amount(prefix: str = "") -> str:
    """`-$1,234.56`, `($1,234.56)` or `1234.56`: two decimals always, at most 15 integer digits;
    a parenthesis opens only with one that closes."""
    return (
        rf"(?P<{prefix}neg>-)?(?P<{prefix}open>\()?\$?"
        rf"(?P<{prefix}int>\d{{1,3}}(?:,\d{{3}}){{0,4}}|\d{{1,15}})\.(?P<{prefix}cents>\d{{2}})"
        rf"(?({prefix}open)\))"
    )


_AMOUNT_RE: Final = re.compile(rf"^{_amount()}$")
_FORM_RE: Final = re.compile(
    r"^Form (?P<code>[A-Z0-9]{1,4}(?:-[A-Z0-9]{1,4})?)(?: (?P<title>.*))?$"
)
_LABEL_VALUE_RE: Final = re.compile(r"^(?P<label>[A-Za-z][^:]{0,119}?):[ .]*(?P<value>.*)$")
_TAX_YEAR_RE: Final = re.compile(
    r"^(?:Tax Period Requested|Report for Tax Period Ending):[ .]*"
    r"(?:(?:December|12)[ ,/-]+(?:31[ ,/-]+)?(?P<year>\d{4})|12-31-(?P<year2>\d{4}))$"
)
_KIND_HEADERS: Final[dict[str, TranscriptKind]] = {
    "wage and income transcript": "wage_income",
    "account transcript": "account",
    "record of account": "record_of_account",
}
_TRANSACTION_RE: Final = re.compile(
    rf"^(?P<tc>\d{{3}})\s+(?P<explanation>\S.*?)\s+(?:(?P<cycle>\d{{8}})\s+)?"
    rf"(?P<date>\d{{2}}-\d{{2}}-\d{{4}})\s+(?P<amount>{_amount('a_')})$"
)
_BALANCE_RE: Final = re.compile(rf"^Account balance:[ .]*(?P<amount>{_amount()})$", re.IGNORECASE)
_NAME_NOISE_RE: Final = re.compile(r"[^a-z0-9 ]+")
_NAME_SUFFIXES: Final = frozenset(
    {"inc", "llc", "pllc", "lp", "ltd", "pc", "na", "co", "corp", "fsb"}
)
_MIN_PREFIX: Final = 4


@dataclass(frozen=True)
class Problem:
    """Something in the text this module would not guess at. `line_no` is 1-based (0: the whole
    text); the transcript's own words are never echoed (they are TRI)."""

    line_no: int
    code: ProblemCode


@dataclass(frozen=True)
class InformationReturn:
    """One information return on a Wage & Income transcript."""

    line_no: int
    form: str
    payer_name: str | None
    amount: Decimal | None  # the compared field; None when the form is not compared or lacks it
    fields: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class Transaction:
    """One row of an Account transcript's transaction table."""

    line_no: int
    code: str
    explanation: str
    cycle: str | None
    posted_on: date
    amount: Decimal


@dataclass(frozen=True)
class ParsedTranscript:
    kind: TranscriptKind
    tax_year: int | None
    information_returns: tuple[InformationReturn, ...] = ()
    transactions: tuple[Transaction, ...] = ()
    account_balance: Decimal | None = None
    problems: tuple[Problem, ...] = ()

    @property
    def parsed(self) -> bool:
        """Parsed when the tax year is known and nothing was too large to read."""
        return self.tax_year is not None and not any(
            p.code in ("too_large", "no_tax_year", "kind_mismatch") for p in self.problems
        )


@dataclass(frozen=True)
class FiledItem:
    """An information return as the return as filed reports it (the caller maps the approved
    engine import's values to these; T-01-T43)."""

    form: str
    payer_name: str
    amount: Decimal


@dataclass(frozen=True)
class ComparedLine:
    line_no: int
    form: str
    payer_name: str | None
    transcript_amount: Decimal
    return_amount: Decimal | None  # None: "Not on return"
    difference: Decimal  # transcript minus return; 0 when it agrees
    status: LineStatus


@dataclass(frozen=True)
class Comparison:
    result: ComparisonResult
    lines: tuple[ComparedLine, ...]
    difference_total: Decimal
    agreeing: tuple[tuple[str, int], ...]  # (form, count) in transcript order
    not_on_transcript: tuple[FiledItem, ...]  # filed but absent from the transcript (not a diff)
    not_compared: tuple[int, ...]  # line numbers of information returns with no compared amount
    version: str = COMPARE_VERSION
    problems: tuple[Problem, ...] = field(default=())

    @property
    def differing(self) -> tuple[ComparedLine, ...]:
        return tuple(line for line in self.lines if line.status != "agrees")


def parse_amount(text: str) -> Decimal | None:
    """`$1,870.00`, `-$9,812.00`, `($12.00)` or `0.00` to an exact Decimal; anything else None."""
    match = _AMOUNT_RE.match(text.strip())
    return None if match is None else _matched_amount(match)


def _matched_amount(match: re.Match[str], prefix: str = "") -> Decimal:
    value = Decimal(f"{match[prefix + 'int'].replace(',', '')}.{match[prefix + 'cents']}")
    negative = match[prefix + "neg"] is not None or match[prefix + "open"] is not None
    return -value if negative else value


def normalise_payer(name: str) -> str:
    """Casefold, drop punctuation and the corporate suffixes the IRS and the engine spell
    differently (`Inc.`, `LLC`, `N.A.`), collapse spaces."""
    words = _NAME_NOISE_RE.sub(" ", name.casefold().replace(".", "")).split()
    while words and words[-1] in _NAME_SUFFIXES:
        words.pop()
    while words and words[0] == "the":
        words.pop(0)
    return " ".join(words)


def payers_match(transcript_name: str | None, filed_name: str) -> bool:
    """Equal once normalised, or one a prefix of the other of at least four characters (the IRS
    truncates payer names on transcripts)."""
    if transcript_name is None:
        return False
    left, right = normalise_payer(transcript_name), normalise_payer(filed_name)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= _MIN_PREFIX and longer.startswith(shorter)


def _lines(text: str) -> list[str] | None:
    if len(text) > MAX_TEXT_CHARS:
        return None
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return None if len(lines) > MAX_LINES else lines


def _header(lines: Sequence[str]) -> tuple[TranscriptKind | None, int | None]:
    kind: TranscriptKind | None = None
    year: int | None = None
    for line in lines:
        lowered = line.casefold()
        if kind is None and lowered in _KIND_HEADERS:
            kind = _KIND_HEADERS[lowered]
        if year is None and (match := _TAX_YEAR_RE.match(line)) is not None:
            year = int(match["year"] or match["year2"])
    return kind, year


def parse_transcript(text: str, kind: TranscriptKind) -> ParsedTranscript:
    """Parse one transcript's text. `kind` is what the person said they uploaded; a text whose
    header names another kind is refused (`kind_mismatch`), never re-read as that kind."""
    lines = _lines(text)
    if lines is None:
        return ParsedTranscript(kind=kind, tax_year=None, problems=(Problem(0, "too_large"),))
    header_kind, year = _header(lines)
    problems: list[Problem] = []
    if header_kind is not None and header_kind != kind:
        return ParsedTranscript(kind=kind, tax_year=year, problems=(Problem(0, "kind_mismatch"),))
    if year is None:
        problems.append(Problem(0, "no_tax_year"))
    if kind == "wage_income":
        returns, more = _parse_wage_income(lines)
        return ParsedTranscript(
            kind=kind,
            tax_year=year,
            information_returns=returns,
            problems=(*problems, *more),
        )
    transactions, balance, more = _parse_account(lines)
    return ParsedTranscript(
        kind=kind,
        tax_year=year,
        transactions=transactions,
        account_balance=balance,
        problems=(*problems, *more),
    )


@dataclass
class _Block:
    line_no: int
    form: str
    payer_name: str | None = None
    awaiting_payer: bool = False
    fields: dict[str, tuple[str, Decimal]] = field(default_factory=dict[str, tuple[str, Decimal]])


def _close(block: _Block, problems: list[Problem]) -> InformationReturn:
    if block.payer_name is None:
        problems.append(Problem(block.line_no, "form_without_payer"))
    compared = COMPARED_FIELD.get(block.form)
    amount: Decimal | None = None
    if compared is None:
        problems.append(Problem(block.line_no, "form_not_compared"))
    elif compared in block.fields:
        amount = block.fields[compared][1]
    else:
        problems.append(Problem(block.line_no, "form_without_amount"))
    return InformationReturn(
        line_no=block.line_no,
        form=block.form,
        payer_name=block.payer_name,
        amount=amount,
        fields=tuple(block.fields.values()),
    )


def _parse_wage_income(
    lines: Sequence[str],
) -> tuple[tuple[InformationReturn, ...], tuple[Problem, ...]]:
    problems: list[Problem] = []
    returns: list[InformationReturn] = []
    block: _Block | None = None
    for line_no, line in enumerate(lines, start=1):
        if not line:
            continue
        if (form := _FORM_RE.match(line)) is not None:
            if block is not None:
                returns.append(_close(block, problems))
            if len(returns) >= MAX_ENTRIES:
                problems.append(Problem(line_no, "too_large"))
                block = None
                break
            block = _Block(line_no=line_no, form=form["code"])
            continue
        if block is None:
            continue
        pair = _LABEL_VALUE_RE.match(line)
        if pair is None:
            if block.awaiting_payer:  # the name follows `Payer:` and its identifier line
                block.payer_name, block.awaiting_payer = line[:120], False
            continue
        label, value = pair["label"].strip(), pair["value"].strip()
        if label.casefold() in _PAYER_LABELS:
            if block.payer_name is None:
                if value:
                    block.payer_name = value[:120]
                else:
                    block.awaiting_payer = True
            continue
        if not any(ch.isdigit() for ch in value):
            continue  # identifiers' captions, submission types: not money
        if value.upper().startswith("XX"):
            continue  # masked identifiers (FIN, EIN, SSN): never money, never kept
        amount = parse_amount(value)
        if amount is None:
            problems.append(Problem(line_no, "unreadable_amount"))
            continue
        key = label.casefold()
        if key in block.fields:
            problems.append(Problem(line_no, "duplicate_field"))
            continue
        block.fields[key] = (label, amount)
    if block is not None:
        returns.append(_close(block, problems))
    return tuple(returns), tuple(problems)


def _parse_account(
    lines: Sequence[str],
) -> tuple[tuple[Transaction, ...], Decimal | None, tuple[Problem, ...]]:
    problems: list[Problem] = []
    transactions: list[Transaction] = []
    balance: Decimal | None = None
    for line_no, line in enumerate(lines, start=1):
        if balance is None and (match := _BALANCE_RE.match(line)) is not None:
            balance = _matched_amount(match)
            continue
        if not line[:3].isdigit() or (len(line) > 3 and not line[3].isspace()):
            continue
        row = _TRANSACTION_RE.match(line)
        posted = _date(row["date"]) if row is not None else None
        if row is None or posted is None:
            problems.append(Problem(line_no, "unreadable_transaction"))
            continue
        if len(transactions) >= MAX_ENTRIES:
            problems.append(Problem(line_no, "too_large"))
            break
        transactions.append(
            Transaction(
                line_no=line_no,
                code=row["tc"],
                explanation=row["explanation"][:200],
                cycle=row["cycle"],
                posted_on=posted,
                amount=_matched_amount(row, "a_"),
            )
        )
    return tuple(transactions), balance, tuple(problems)


def _date(text: str) -> date | None:
    month, day, year = (int(part) for part in text.split("-"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def transactions_with_code(parsed: ParsedTranscript, code: str) -> tuple[Transaction, ...]:
    """TC 150 (return filed) or TC 922 (unreported-income review) rows, in posting order."""
    return tuple(t for t in parsed.transactions if t.code == code)


def compare(parsed: ParsedTranscript, filed: Iterable[FiledItem], tax_year: int) -> Comparison:
    """Compare a parsed Wage & Income transcript with the return as filed for `tax_year`.

    Refuses (no lines, result `differences`, a problem) a transcript that is not Wage & Income,
    was not parsed, or is for another year: a comparison is never computed on a guess."""
    filed_items = list(filed)
    refusal: ProblemCode | None = None
    if parsed.kind != "wage_income":
        refusal = "not_wage_income"
    elif not parsed.parsed:
        refusal = "transcript_not_parsed"
    elif parsed.tax_year != tax_year:
        refusal = "tax_year_mismatch"
    if refusal is not None:
        return Comparison(
            result="differences",
            lines=(),
            difference_total=Decimal("0.00"),
            agreeing=(),
            not_on_transcript=tuple(filed_items),
            not_compared=(),
            problems=(Problem(0, refusal),),
        )
    compared = [info for info in parsed.information_returns if info.amount is not None]
    pairs = _pair(compared, filed_items)
    lines: list[ComparedLine] = []
    for info in compared:
        amount = cast("Decimal", info.amount)
        index = pairs.get(info.line_no)
        on_return = None if index is None else filed_items[index].amount
        difference = amount if on_return is None else amount - on_return
        status: LineStatus = (
            "not_on_return" if on_return is None else "agrees" if difference == 0 else "differs"
        )
        lines.append(
            ComparedLine(
                line_no=info.line_no,
                form=info.form,
                payer_name=info.payer_name,
                transcript_amount=amount,
                return_amount=on_return,
                difference=difference,
                status=status,
            )
        )
    used = set(pairs.values())
    not_compared = [i.line_no for i in parsed.information_returns if i.amount is None]
    differing = [line for line in lines if line.status != "agrees"]
    agreeing: dict[str, int] = {}
    for line in lines:
        if line.status == "agrees":
            agreeing[line.form] = agreeing.get(line.form, 0) + 1
    total = sum((line.difference for line in differing), Decimal("0.00"))
    return Comparison(
        result="differences" if differing else "agrees",
        lines=tuple(lines),
        difference_total=total,
        agreeing=tuple(agreeing.items()),
        not_on_transcript=tuple(f for i, f in enumerate(filed_items) if i not in used),
        not_compared=tuple(not_compared),
        problems=parsed.problems,
    )


def _pair(compared: Sequence[InformationReturn], filed: Sequence[FiledItem]) -> dict[int, int]:
    """Transcript line number to filed index. First every pair with the same form, payer and
    amount (so an exact pair is never taken by an earlier line), then the rest of each form and
    payer in transcript and filing order; each filed item pairs once."""
    unused = list(range(len(filed)))
    pairs: dict[int, int] = {}
    for exact in (True, False):
        for info in compared:
            if info.line_no in pairs:
                continue
            for i in unused:
                same = filed[i].form == info.form and payers_match(
                    info.payer_name, filed[i].payer_name
                )
                if same and (not exact or filed[i].amount == info.amount):
                    pairs[info.line_no] = i
                    unused.remove(i)
                    break
    return pairs
