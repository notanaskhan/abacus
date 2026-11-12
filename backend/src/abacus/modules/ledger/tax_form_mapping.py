"""C9's tax form-line taxonomy (T-05-T26; T-05 §4.2 M5, F3; TXP-02; DEC-4518). RED: the ledger's
mapping tables.

A partnership's trial balance carries two mapping sets side by side: the financial-statement set
(`fs_line`, A-03) and the tax set (`tax_form_line`), which maps each account to a Form 1065 line
key from the C21 `tax_form_lines` set version it names (`reference_set_version_id`, T-05-T21).

- **Suggestions are code's** (`suggest_form_lines`): the prior year's tax set first
  (carry-forward from the prior workbook, when the key is still in this year's set), then the
  firm's number-range rules, then its description rules; a key outside the version's mappable
  keys is never suggested. Rules are firm content (database rows passed in by the caller, never
  constants here).
- **A mapping is a person's.** `record_form_line` writes one insert-only `mapping_set_edits` row
  as a human (`actor_kind = 'human'`, 0079); the agent's judgments arrive as a
  `tax_account_mapping` proposal that the tax reviewer approves (T-05-T23's mapper; the tax
  module's adapter checks the approver's function and calls this).
- `form_line_rows` reads the set's current key per account (the latest edit wins); `unmapped`
  counts what still has no key (the export gate, T-05-T60).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork

TAXONOMY: Final = "tax_form_line"
Method = Literal["prior_year", "range", "description"]
Confidence = Literal["high", "medium", "low"]


class FormLineKeyUnknown(DomainInvalid):
    """The key is not a mappable line of the set version the mapping set names."""

    code = "form_line_key_unknown"


@dataclass(frozen=True)
class RangeRule:
    """Accounts `start` to `end` (by code, inclusive, compared as numbers when both are) map to
    `key` (a firm rule: "4000-4999 → L1a")."""

    start: str
    end: str
    key: str


@dataclass(frozen=True)
class DescriptionRule:
    """An account whose name contains `phrase` (case-insensitive) maps to `key`."""

    phrase: str
    key: str


@dataclass(frozen=True)
class Suggestion:
    account_code: str
    form_line_key: str | None
    method: Method | None
    confidence: Confidence | None


def _in_range(code: str, rule: RangeRule) -> bool:
    digits = code.split("-")[0]
    if digits.isdigit() and rule.start.isdigit() and rule.end.isdigit():
        return int(rule.start) <= int(digits) <= int(rule.end)
    return rule.start <= code <= rule.end


def suggest_form_lines(
    accounts: Sequence[tuple[str, str]],
    *,
    keys: frozenset[str],
    prior: Mapping[str, str],
    ranges: Sequence[RangeRule] = (),
    descriptions: Sequence[DescriptionRule] = (),
) -> tuple[Suggestion, ...]:
    """Code's suggestion per account, in the accounts' order: prior year (high), then a range
    rule (medium), then a description rule (low); none when nothing applies. Only `keys`."""
    out: list[Suggestion] = []
    for code, name in accounts:
        carried = prior.get(code)
        if carried is not None and carried in keys:
            out.append(Suggestion(code, carried, "prior_year", "high"))
            continue
        ranged = next((r.key for r in ranges if r.key in keys and _in_range(code, r)), None)
        if ranged is not None:
            out.append(Suggestion(code, ranged, "range", "medium"))
            continue
        lowered = name.lower()
        described = next(
            (d.key for d in descriptions if d.key in keys and d.phrase.lower() in lowered), None
        )
        if described is not None:
            out.append(Suggestion(code, described, "description", "low"))
            continue
        out.append(Suggestion(code, None, None, None))
    return tuple(out)


def unmapped_form_lines(accounts: Sequence[str], rows: Mapping[str, str | None]) -> int:
    """Accounts with no key yet (the entity export waits while this is above zero)."""
    return sum(1 for code in accounts if not rows.get(code))


_TAX_SET = text(
    "SELECT id FROM mapping_sets WHERE trial_balance_id = :tb AND taxonomy_kind = 'tax_form_line'"
)


async def tax_mapping_set(tenant: TenantContext, trial_balance_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(_TAX_SET, {"tb": trial_balance_id})
    return None if found is None else UUID(str(found))


async def ensure_tax_mapping_set(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    trial_balance_id: UUID,
    reference_set_version_id: UUID,
    created_by: UUID,
) -> UUID:
    """The TB's tax set, created on first use with the C21 version it maps to."""
    found = await tx.session.scalar(_TAX_SET, {"tb": trial_balance_id})
    if found is not None:
        return UUID(str(found))
    set_id = await tx.session.scalar(
        text(
            "INSERT INTO mapping_sets (tenant_id, engagement_id, trial_balance_id, created_by, "
            "taxonomy_kind, reference_set_version_id) VALUES (:t, :e, :tb, :by, 'tax_form_line', "
            ":v) RETURNING id"
        ),
        {
            "t": tenant_id,
            "e": engagement_id,
            "tb": trial_balance_id,
            "by": created_by,
            "v": reference_set_version_id,
        },
    )
    tx.record(
        "mapping_set.created",
        target=Target("mapping_set", UUID(str(set_id))),
        after=Ref(reference_set_version=reference_set_version_id),
        scope=Scope(engagement_id=engagement_id),
    )
    return UUID(str(set_id))


async def record_form_line(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    mapping_set_id: UUID,
    engagement_id: UUID,
    account_code: str,
    form_line_key: str,
    keys: frozenset[str],
    edited_by: UUID,
) -> None:
    """A person's mapping of one account (insert-only; the latest row is the mapping). A key
    outside the version's mappable keys answers 422 `form_line_key_unknown`."""
    if form_line_key not in keys:
        raise FormLineKeyUnknown(facts={"account_code": account_code})
    await tx.session.execute(
        text(
            "INSERT INTO mapping_set_edits (tenant_id, mapping_set_id, account_code, "
            "form_line_key, edited_by, actor_kind) VALUES (:t, :m, :code, :key, :by, 'human')"
        ),
        {
            "t": tenant_id,
            "m": mapping_set_id,
            "code": account_code,
            "key": form_line_key,
            "by": edited_by,
        },
    )
    tx.record(
        "account_mapping.edited",
        target=Target("mapping_set", mapping_set_id),
        after=Ref(accounts=1),  # the account and key are on the row, never in the trail
        scope=Scope(engagement_id=engagement_id),
    )


async def form_line_rows(tenant: TenantContext, mapping_set_id: UUID) -> dict[str, str | None]:
    """Each mapped account's current key (the latest edit wins)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT DISTINCT ON (account_code) account_code, form_line_key "
                "FROM mapping_set_edits WHERE mapping_set_id = :m "
                "ORDER BY account_code, created_at DESC, id DESC"
            ),
            {"m": mapping_set_id},
        )
        return {str(r.account_code): r.form_line_key for r in rows}
