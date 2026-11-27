"""TAX-11's diagnostics, computed (T-06-T50; TASK-9008; T-06 F7; SPEC-702 AC-30 to AC-33; ADR-050;
DEC-6014; amber).

`form_diagnostics` holds one row per (return, approved checkpoint, rule). `refresh` writes them
for the return's current approved checkpoint, idempotently (an upsert per rule), as the system:

- **Code's checks** (no model; the 1065 Review Checklist v4's pure checks over one facts snapshot,
  `standards_checks.gather`, plus the form-preview identity of `form_preview_blockers`):
  `item_i_count` (Item I is the partners on the return), `item_j_m3_required` (Schedule M-3
  exactly when total assets reach the threshold), `partnership_representative` (one is
  designated), `m2_line9_schedule_l21` (M-2's ending capital is Schedule L line 21),
  `k1_item_l_schedule_l21` (Σ K-1 Item L is Schedule L line 21), `section_754_statement` (a
  transfer's §754 position is decided) and `k1_sums_schedule_k` (each Schedule K line, box 2
  among them, is its K-1 columns' sum). A check that does not apply to the return reads clear.
- **The engine's diagnostics**: each diagnostic of the newest diagnostics import is a rule
  (`engine.<code>`), an error blocking, a warning a warning, the rest information.
- **Issues**: a failing rule links the open issue already raised under its reference (TXP-10's,
  a standards run's, or this run's) and raises one only when none is open
  (`review.api.record_self_check_issue`, code's title), so a re-run never adds a second.

The read (`GET …/diagnostics`) refreshes first, as the preview caches its rendered pages: the
rows are the checkpoint's, derived and deterministic.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import MissingAuditEvent, Ref, Scope, Target, uow
from abacus.modules.tax import standards_checks as sc
from abacus.modules.tax.form_preview_blockers import item_l_off
from abacus.modules.tax.standards_runs import TieOutResult

Severity = Literal["blocking", "warning", "info"]
ACTOR: Final = "tax:form_diagnostics"
CATEGORY: Final = "form_diagnostics"  # issues.category_path is a code (as standards_runs)


@dataclass(frozen=True)
class Rule:
    key: str
    severity: Severity
    title: str
    check: Callable[[sc.Facts], TieOutResult]


def _item_l(f: sc.Facts) -> TieOutResult:
    off = item_l_off(dict(f.values))  # type: ignore[arg-type] -- the same sheet values
    if off is None:
        return TieOutResult("not_applicable")
    if off == 0:
        return TieOutResult("pass", off)
    return TieOutResult("exception", off, issue_ref="tie_out:item_l_schedule_l21",
                        title="Σ K-1 Item L does not equal Schedule L line 21")  # fmt: skip


RULES: Final[tuple[Rule, ...]] = (
    Rule("item_i_count", "warning", "Item I does not match the partners", sc.c04_k1_count),
    Rule("item_j_m3_required", "blocking", "Schedule M-3 required (Item J)", sc.c12_m3_required),
    Rule("partnership_representative", "warning", "No partnership representative",
         sc.c22_partnership_representative),
    Rule("m2_line9_schedule_l21", "warning", "M-2 line 9 does not equal Schedule L line 21",
         sc.c17_m2_line9_schedule_l21),
    Rule("k1_item_l_schedule_l21", "blocking", "Σ K-1 Item L does not equal Schedule L line 21",
         _item_l),
    Rule("section_754_statement", "blocking", "§754 statement not decided",
         sc.c31_section_754_documented),
    Rule("k1_sums_schedule_k", "blocking", "K-1 boxes do not sum to Schedule K",
         sc.c09_schedule_k_k1_sum),
)  # fmt: skip
_ENGINE_SEVERITY: Final[dict[str, Severity]] = {
    "error": "blocking", "warning": "warning", "informational": "info",
}  # fmt: skip


@dataclass(frozen=True)
class Result:
    rule_key: str
    source: Literal["accrued", "engine"]
    severity: Severity
    failing: bool
    issue_ref: str | None
    title: str
    facts: dict[str, object]
    engine_import_id: UUID | None = None


def evaluate(facts: sc.Facts) -> list[Result]:
    """Code's rules over one facts snapshot (pure)."""
    out: list[Result] = []
    for rule in RULES:
        found = rule.check(facts)
        failing = found.outcome == "exception"
        out.append(
            Result(
                rule.key, "accrued", rule.severity, failing,
                found.issue_ref or f"form_diagnostic:{rule.key}", found.title or rule.title,
                {"difference": None if found.difference is None else str(found.difference)},
            )
        )  # fmt: skip
    return out


def engine_rules(rows: list[tuple[str, str, str | None, UUID]]) -> list[Result]:
    """The engine's diagnostics (code, severity, field, import) as rules: every one is failing."""
    out: list[Result] = []
    for code, severity, field_key, import_id in rows:
        key = "engine." + "".join(
            ch if ch.isalnum() or ch in "_.-" else "_" for ch in code.lower()
        )
        out.append(
            Result(
                key[:80], "engine", _ENGINE_SEVERITY.get(severity, "info"), True,
                f"engine_diagnostic:{code}"[:120], f"Engine diagnostic {code}"[:200],
                {"field_key": field_key}, import_id,
            )
        )  # fmt: skip
    return out


_ENGINE: Final = text(
    "SELECT d.code, d.severity, d.field_key, d.sync_event_id FROM engine_diagnostics d "
    "WHERE d.return_id = :r AND d.sync_event_id = (SELECT e.id FROM engine_sync_events e "
    "WHERE e.return_id = :r AND e.kind = 'diagnostics' ORDER BY e.at DESC, e.id DESC LIMIT 1) "
    "ORDER BY d.code, d.id"
)
_ENGAGEMENT: Final = text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r")
_UPSERT: Final = text(
    "INSERT INTO form_diagnostics (tenant_id, engagement_id, work_item_id, checkpoint_id, "
    "rule_key, source, severity, status, issue_id, facts, engine_import_id) VALUES (:t, :e, :r, "
    ":c, :k, :src, :sev, :st, :i, CAST(:f AS jsonb), :imp) ON CONFLICT (work_item_id, "
    "checkpoint_id, rule_key) DO UPDATE SET severity = EXCLUDED.severity, status = "
    "EXCLUDED.status, issue_id = EXCLUDED.issue_id, facts = EXCLUDED.facts"
)


async def refresh(tenant: TenantContext, return_id: UUID) -> UUID | None:
    """The current approved checkpoint's rows; None when the return has none yet."""
    from abacus.modules.review.api import (
        approved_checkpoint,
        open_issue_for_ref,
        record_self_check_issue,
    )

    system = TenantContext(tenant.tenant_id, "system", ACTOR)
    checkpoint = await approved_checkpoint(system, "tax_return", return_id)
    async with tenant_session(system) as session:
        engagement = await session.scalar(_ENGAGEMENT, {"r": return_id})
        engine = [
            (str(r.code), str(r.severity), r.field_key, r.sync_event_id)
            for r in await session.execute(_ENGINE, {"r": return_id})
        ]
    if checkpoint is None or engagement is None:
        return None
    results = evaluate(await sc.gather(system, return_id)) + engine_rules(engine)
    issues: dict[str, UUID | None] = {}
    for r in results:
        if not r.failing or r.issue_ref is None:
            issues[r.rule_key] = None
            continue
        linked = await open_issue_for_ref(system, return_id, r.issue_ref)
        if linked is None:
            linked, _ = await record_self_check_issue(
                system, engagement_id=engagement, work_item_id=return_id,
                record_type="tax_return", record_id=return_id, source_ref=r.issue_ref,
                title=r.title, internal_note=f"Form diagnostic {r.rule_key}", links=[],
                blocks=("final_approval",) if r.severity == "blocking" else (),
                category_path=CATEGORY,
            )  # fmt: skip
        issues[r.rule_key] = linked
    try:
        async with uow(system) as tx:
            for r in results:
                await tx.session.execute(
                    _UPSERT,
                    {"t": tenant.tenant_id, "e": engagement, "r": return_id, "c": checkpoint,
                     "k": r.rule_key, "src": r.source, "sev": r.severity,
                     "st": "open" if r.failing else "clear", "i": issues[r.rule_key],
                     "f": json.dumps(r.facts), "imp": r.engine_import_id},
                )  # fmt: skip
            tx.record(
                "form_diagnostics.refreshed",
                target=Target("tax_return", return_id),
                after=Ref(checkpoint=checkpoint, open=sum(1 for r in results if r.failing)),
                scope=Scope(engagement_id=engagement, work_item_id=return_id),
            )
    except MissingAuditEvent:  # pragma: no cover - the record always lands
        pass
    return checkpoint


__all__ = ["RULES", "Result", "engine_rules", "evaluate", "refresh"]
