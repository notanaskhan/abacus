"""Scoping rules on a template version (K-03-T18; TASK-9011; K-03 F3; SHT-03 a-f; KNW-06;
ADR-050; DEC-6017; amber).

- **Read** (`rules`, `template.read`): the version's rules in position order, with the draft's
  ETag.
- **Save** (`save_rules`, `scoping_rule.edit`, the QM owner; DEC-5803): the whole list at the
  ETag the editor saw (412 when it moved; 409 `not_draft` on a published version). Refused with
  422 `unknown_source` when a condition reads a source no provider knows, and 422
  `rule_conflict` when two rules show and hide the same target (the facts name both positions
  and the target). A rule keeps its id across saves, a removed rule is deleted (a request it
  showed keeps its row; 1010's `ON DELETE SET NULL`), and each request in a shown request group
  is re-linked to the first rule showing it (`shown_by_rule_id`, so "41 + 6 by rule" counts).
  One `scoping_rule.changed` event per save, the person's.
- **Sources** (`sources`): the catalogue the providers registered (`register_scoping_source`:
  engagements, assurance); methodology reads no engagement data itself.
- **Preview** (`preview`): the rules evaluated by code over one engagement's answers (the
  providers authorise the reader on that engagement) or over none (a blank engagement). No
  model is called; nothing is written.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, DomainPreconditionFailed, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.methodology import scoping as engine
from abacus.modules.methodology.template_drafts import (
    RELINK_REQUESTS,
    TARGET,
    ComponentInvalid,
    NotDraft,
    etag_of,
    require_human,
    version_row,
)

SourceKind = Literal["planning_form", "risk", "assertion", "engagement_fact"]
_IDENT: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


class RuleConflict(DomainInvalid):
    code = "rule_conflict"


class UnknownSource(DomainInvalid):
    code = "unknown_source"


@dataclass(frozen=True)
class Source:
    key: str
    label: str
    kind: SourceKind
    options: tuple[str, ...] = ()


class SourceProvider(Protocol):
    """A module that answers scoping sources for an engagement (registered at import)."""

    def knows(self, key: str) -> bool: ...

    async def catalogue(self, ctx: AuthContext) -> Sequence[Source]: ...

    async def answers(
        self, ctx: AuthContext, engagement_id: UUID
    ) -> Mapping[str, engine.Answer]: ...


_PROVIDERS: dict[str, SourceProvider] = {}


def register_scoping_source(name: str, provider: SourceProvider) -> None:
    _PROVIDERS[name] = provider


def known(key: str) -> bool:
    return any(p.knows(key) for p in _PROVIDERS.values())


async def sources(ctx: AuthContext, version_id: UUID) -> list[Source]:
    await version_row(ctx, version_id, "template.read")
    out: dict[str, Source] = {}
    for name in sorted(_PROVIDERS):
        for s in await _PROVIDERS[name].catalogue(ctx):
            out.setdefault(s.key, s)
    return sorted(out.values(), key=lambda s: s.label)


async def answers_for(ctx: AuthContext, engagement_id: UUID) -> dict[str, engine.Answer]:
    found: dict[str, engine.Answer] = {}
    for name in sorted(_PROVIDERS):
        found.update(await _PROVIDERS[name].answers(ctx, engagement_id))
    return found


# --- reading -------------------------------------------------------------------------------------

_RULES: Final = text(
    "SELECT id, position, label, group_op, conditions, effect, target_kind, target_ref "
    "FROM scoping_rules WHERE template_version_id = :v ORDER BY position, id"
)
_SHEETS: Final = text(
    "SELECT step_key, sheet_key FROM template_sheet_definitions "
    "WHERE template_version_id = :v AND step_key IS NOT NULL"
)
_GROUPS: Final = text(
    "SELECT group_key, count(*) AS n FROM template_requests WHERE template_version_id = :v "
    "AND group_key IS NOT NULL GROUP BY group_key"
)


def _rule(row: Any) -> engine.Rule:  # noqa: ANN401 -- a result row
    """A stored rule as the engine's (its label is the editor's, read beside it)."""
    stored: object = row.conditions
    loaded: object = cast(object, stored) if isinstance(stored, list) else json.loads(str(stored))
    raw = cast(list[dict[str, Any]], loaded)  # Any: a condition's JSON, read field by field
    conditions = tuple(
        engine.Condition(
            str(c["source_path"]), cast(engine.Operator, c["operator"]), c.get("value")
        )
        for c in raw
    )
    return engine.Rule(
        str(row.id), int(row.position), row.group_op, conditions, row.effect, row.target_kind,
        str(row.target_ref),
    )  # fmt: skip


async def _rules(session: AsyncSession, version_id: UUID) -> list[engine.Rule]:
    return [_rule(r) for r in await session.execute(_RULES, {"v": version_id})]


async def _shape(session: AsyncSession, version_id: UUID) -> engine.Shape:
    by_step: dict[str, set[str]] = {}
    for r in await session.execute(_SHEETS, {"v": version_id}):
        by_step.setdefault(str(r.step_key), set()).add(str(r.sheet_key))
    groups = {
        str(r.group_key): int(r.n) for r in await session.execute(_GROUPS, {"v": version_id})
    }
    return engine.Shape({k: frozenset(v) for k, v in by_step.items()}, groups)


Labelled = tuple[engine.Rule, str | None]


async def rules(ctx: AuthContext, version_id: UUID) -> tuple[int, list[Labelled]]:
    row = await version_row(ctx, version_id, "template.read")
    async with tenant_session(ctx.tenant) as session:
        found = [
            (_rule(r), None if r.label is None else str(r.label))
            for r in await session.execute(_RULES, {"v": version_id})
        ]
    return int(row.draft_etag), found


# --- saving --------------------------------------------------------------------------------------


def check(items: Sequence[engine.Rule]) -> None:
    """422 `unknown_source`, then 422 `rule_conflict` (code's checks, before any write)."""
    positions = [r.position for r in items]
    if len(set(positions)) != len(positions) or len({r.key for r in items}) != len(items):
        raise ComponentInvalid(facts={"table": "scoping_rules"})
    for rule in items:
        if not rule.conditions or rule.target_kind not in engine.TARGET_KINDS:
            raise ComponentInvalid(facts={"table": "scoping_rules", "rule": rule.position})
        for c in rule.conditions:
            if c.operator not in engine.OPERATORS:
                raise ComponentInvalid(facts={"table": "scoping_rules", "rule": rule.position})
            if not known(c.source):
                raise UnknownSource(facts={"rule": rule.position})
    found = engine.conflicts(items)
    if found:
        first = found[0]
        facts: dict[str, object] = {
            "first": first.first,
            "second": first.second,
            "target_kind": first.target_kind,
            "conflicts": len(found),
        }
        if _IDENT.fullmatch(first.target_ref):
            facts["target"] = first.target_ref
        raise RuleConflict(facts=facts)


_BUMP: Final = text(
    "UPDATE template_versions SET draft_etag = draft_etag + 1 WHERE id = :v AND status = 'draft' "
    "AND draft_etag = :seen RETURNING draft_etag"
)
_IDS: Final = text("SELECT id FROM scoping_rules WHERE template_version_id = :v")
_DELETE: Final = text("DELETE FROM scoping_rules WHERE template_version_id = :v AND id = :id")
_UPDATE: Final = text(
    "UPDATE scoping_rules SET position = :position, label = :label, group_op = :group_op, "
    "conditions = CAST(:conditions AS jsonb), effect = :effect, target_kind = :target_kind, "
    "target_ref = :target_ref WHERE template_version_id = :v AND id = :id"
)
_INSERT: Final = text(
    "INSERT INTO scoping_rules (id, tenant_id, template_version_id, position, label, group_op, "
    "conditions, effect, target_kind, target_ref) VALUES (:id, :t, :v, :position, :label, "
    ":group_op, CAST(:conditions AS jsonb), :effect, :target_kind, :target_ref)"
)


def _values(rule: engine.Rule, label: str | None) -> dict[str, object]:
    conditions = [
        {"source_path": c.source, "operator": c.operator}
        | ({} if c.value is None else {"value": c.value})
        for c in rule.conditions
    ]
    return {
        "id": UUID(rule.key), "position": rule.position, "label": label,
        "group_op": rule.group_op, "conditions": json.dumps(conditions), "effect": rule.effect,
        "target_kind": rule.target_kind, "target_ref": rule.target_ref,
    }  # fmt: skip


async def save_rules(
    ctx: AuthContext,
    version_id: UUID,
    items: Sequence[Labelled],
    if_match: str,
) -> tuple[int, list[Labelled]]:
    require_human(ctx, "scoping_rule.edit")
    row = await version_row(ctx, version_id, "scoping_rule.edit")
    if row.status != "draft":
        raise NotDraft(facts={"status": str(row.status)})
    seen = etag_of(if_match)
    if seen != int(row.draft_etag):
        raise DomainPreconditionFailed(facts={"etag": int(row.draft_etag)})
    check([r for r, _ in items])
    async with uow(ctx.tenant) as tx:
        etag = await tx.session.scalar(_BUMP, {"v": version_id, "seen": seen})
        if etag is None:  # another save landed between the read and the write
            raise DomainPreconditionFailed(facts={"etag": seen + 1})
        existing = {r.id for r in await tx.session.execute(_IDS, {"v": version_id})}
        wanted = {UUID(r.key) for r, _ in items}
        for gone in existing - wanted:
            await tx.session.execute(_DELETE, {"v": version_id, "id": gone})
        for rule, label in items:
            values = _values(rule, label) | {"v": version_id, "t": ctx.tenant_id}
            await tx.session.execute(_UPDATE if values["id"] in existing else _INSERT, values)
        await tx.session.execute(RELINK_REQUESTS, {"v": version_id})
        tx.record(
            "scoping_rule.changed",
            target=Target(TARGET, version_id),
            after=Ref(rules=len(items), etag=int(etag)),
        )
    return await rules(ctx, version_id)


# --- evaluating ----------------------------------------------------------------------------------


async def evaluate(
    ctx: AuthContext, version_id: UUID, engagement_id: UUID | None
) -> engine.Evaluation:
    """Code's evaluation over one engagement's answers, or over none (a blank engagement)."""
    answers = {} if engagement_id is None else await answers_for(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        if (
            await session.scalar(
                text("SELECT 1 FROM template_versions WHERE id = :v"), {"v": version_id}
            )
            is None
        ):
            raise NotFound(TARGET)
        found = await _rules(session, version_id)
        shape = await _shape(session, version_id)
    return engine.evaluate_scoping_rules(found, answers, shape)


async def preview(
    ctx: AuthContext, version_id: UUID, engagement_id: UUID | None
) -> engine.Evaluation:
    await authorise(ctx, "template.read", Resource.firm(ctx.tenant_id))
    return await evaluate(ctx, version_id, engagement_id)


__all__ = [
    "Labelled",
    "RuleConflict",
    "Source",
    "SourceProvider",
    "UnknownSource",
    "answers_for",
    "check",
    "evaluate",
    "known",
    "preview",
    "register_scoping_source",
    "rules",
    "save_rules",
    "sources",
]
