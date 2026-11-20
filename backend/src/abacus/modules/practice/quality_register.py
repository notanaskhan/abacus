"""The SQMS register: objectives, risks and responses; register imports; the risk-assessment
review (Q-05-T08 remainder, built in the S52 Q-05 sweep; SPEC-711 AC-1, AC-5; DEC-5829). Amber.

The register is firm content loaded by import (a dry run, then a publish), never a commit
(AGENTS.md #16). The import file is a CSV with the columns `level,component,ref,parent_ref,title,
frequency` (`level` objective, risk or response); the dry run counts what it would write and
refuses an unknown component, a duplicate ref or a missing parent (422); the publish writes it
(new refs only; an existing ref keeps its row). The QM owner patches an objective's owner and
health flag with a note (version-checked).
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise

_FINGERPRINT: Final = "practice.qm_register"
COMPONENTS: Final = frozenset(
    {"governance_leadership", "ethical_requirements", "acceptance_continuance",
     "engagement_performance", "resources", "information_communication"}
)  # fmt: skip
LEVELS: Final = ("objective", "risk", "response")


class ImportInvalid(DomainInvalid):
    code = "register_import_invalid"
    message = "The register file has rows that cannot be loaded."


def parse(content: bytes) -> list[dict[str, str]]:
    """The register rows, checked (pure)."""
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]
    except (UnicodeDecodeError, csv.Error):
        raise ImportInvalid(facts={"reason": "unreadable"}) from None
    refs = Counter(r.get("ref", "") for r in rows)
    objectives = {r["ref"] for r in rows if r.get("level") == "objective"}
    for n, r in enumerate(rows, start=2):
        if r.get("level") not in LEVELS or not r.get("ref") or not r.get("title"):
            raise ImportInvalid(facts={"line": str(n)})
        if refs[r["ref"]] > 1:
            raise ImportInvalid(facts={"line": str(n), "reason": "duplicate_ref"})
        if r["level"] == "objective" and r.get("component") not in COMPONENTS:
            raise ImportInvalid(facts={"line": str(n), "reason": "unknown_component"})
        if r["level"] != "objective" and r.get("parent_ref") not in objectives:
            raise ImportInvalid(facts={"line": str(n), "reason": "missing_parent"})
    return rows


async def dry_run(ctx: AuthContext, kind: str, source_evidence_version_id: UUID) -> UUID:
    from abacus.modules.evidence.api import version_content

    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    rows = parse(await version_content(ctx.tenant, source_evidence_version_id))
    counts = dict(Counter(r["level"] for r in rows))
    async with uow(ctx.tenant) as tx:
        import_id = cast(UUID, await tx.session.scalar(text(
            "INSERT INTO qm_register_imports (tenant_id, kind, source_evidence_version_id, counts, "
            "status) VALUES (:t, :k, :v, CAST(:c AS jsonb), 'dry_run') RETURNING id"
        ), {"t": ctx.tenant_id, "k": kind, "v": source_evidence_version_id,
            "c": json.dumps(counts, sort_keys=True)}))  # fmt: skip
        tx.record("quality_import.dry_run", target=Target("qm_register_import", import_id))
    return import_id


async def publish(ctx: AuthContext, import_id: UUID) -> UUID:
    from abacus.modules.evidence.api import version_content

    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(text(
            "SELECT kind, source_evidence_version_id, status FROM qm_register_imports WHERE id = :i"
        ), {"i": import_id})).first()  # fmt: skip
    if found is None:
        raise NotFound("qm_register_import")
    if found.status != "dry_run":
        raise DomainConflict(facts={"reason": "already_published"})
    rows = parse(await version_content(ctx.tenant, found.source_evidence_version_id))
    async with uow(ctx.tenant) as tx:
        objectives: dict[str, UUID] = {}
        for r in (r for r in rows if r["level"] == "objective"):
            oid = await tx.session.scalar(text(
                "INSERT INTO qm_objectives (tenant_id, component, ref, title) VALUES (:t, :c, :r, :ti) "
                "ON CONFLICT (tenant_id, ref) DO NOTHING RETURNING id"
            ), {"t": ctx.tenant_id, "c": r["component"], "r": r["ref"], "ti": r["title"][:300]})  # fmt: skip
            if oid is None:
                oid = await tx.session.scalar(text("SELECT id FROM qm_objectives WHERE ref = :r"), {"r": r["ref"]})
            objectives[r["ref"]] = cast(UUID, oid)
        for r in (r for r in rows if r["level"] in ("risk", "response")):
            table = "qm_risks" if r["level"] == "risk" else "qm_responses"
            extra = "" if r["level"] == "risk" else ", frequency"
            value = "" if r["level"] == "risk" else ", :f"
            await tx.session.execute(text(
                f"INSERT INTO {table} (tenant_id, objective_id, ref, title{extra}) VALUES "
                f"(:t, :o, :r, :ti{value}) ON CONFLICT (tenant_id, ref) DO NOTHING"
            ), {"t": ctx.tenant_id, "o": objectives[r["parent_ref"]], "r": r["ref"],
                "ti": r["title"][:300], "f": r.get("frequency") or None})  # fmt: skip
        new_id = cast(UUID, await tx.session.scalar(text(
            "INSERT INTO qm_register_imports (tenant_id, kind, source_evidence_version_id, counts, "
            "status, published_by) VALUES (:t, :k, :v, CAST(:c AS jsonb), 'published', :u) RETURNING id"
        ), {"t": ctx.tenant_id, "k": found.kind, "v": found.source_evidence_version_id,
            "c": json.dumps(dict(Counter(r["level"] for r in rows)), sort_keys=True), "u": ctx.user_id}))  # fmt: skip
        tx.record("quality_import.published", target=Target("qm_register_import", new_id))
    return new_id


async def import_row(tenant: TenantContext, import_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        row = (await session.execute(text(
            "SELECT id, kind, status, counts FROM qm_register_imports WHERE id = :i"
        ), {"i": import_id})).mappings().first()  # fmt: skip
    if row is None:
        raise NotFound("qm_register_import")
    return dict(row)


async def register(tenant: TenantContext, component: str | None) -> dict[str, list[dict[str, object]]]:
    async with tenant_session(tenant) as session:
        objectives = [dict(r) for r in (await session.execute(text(
            "SELECT id, component, ref, title, owner_user_id, health_flag, version FROM qm_objectives "
            "WHERE active AND (CAST(:c AS text) IS NULL OR component = :c) ORDER BY ref"
        ), {"c": component})).mappings()]  # fmt: skip
        ids = [o["id"] for o in objectives]
        risks = [dict(r) for r in (await session.execute(text(
            "SELECT id, objective_id, ref, title FROM qm_risks WHERE objective_id = ANY(:ids) ORDER BY ref"
        ), {"ids": ids})).mappings()]  # fmt: skip
        responses = [dict(r) for r in (await session.execute(text(
            "SELECT id, objective_id, ref, title, owner_user_id, frequency FROM qm_responses "
            "WHERE objective_id = ANY(:ids) ORDER BY ref"
        ), {"ids": ids})).mappings()]  # fmt: skip
    return {"objectives": objectives, "risks": risks, "responses": responses}


async def patch_objective(
    ctx: AuthContext, objective_id: UUID, *, owner_user_id: UUID | None, health_flag: str | None,
    note: str | None, version: int,
) -> None:
    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    sealed = None if note is None else await seal(ctx.tenant_id, note.encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(text(
            "UPDATE qm_objectives SET owner_user_id = coalesce(:o, owner_user_id), health_flag = :h, "
            "note_sealed = coalesce(:n, note_sealed), version = version + 1 WHERE id = :id AND "
            "version = :v RETURNING id"
        ), {"o": owner_user_id, "h": health_flag, "n": sealed, "id": objective_id, "v": version})  # fmt: skip
        if done is None:
            raise DomainConflict(facts={"reason": "stale_objective"})
        tx.record("qm_objective.updated", target=Target("qm_objective", objective_id), after=Ref(at_risk=int(health_flag == "at_risk")))


async def record_review(ctx: AuthContext, reviewed_on: object, note: str | None) -> UUID:
    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    sealed = None if note is None else await seal(ctx.tenant_id, note.encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        review_id = cast(UUID, await tx.session.scalar(text(
            "INSERT INTO qm_risk_assessment_reviews (tenant_id, reviewed_on, note_sealed, reviewed_by) "
            "VALUES (:t, :d, :n, :u) RETURNING id"
        ), {"t": ctx.tenant_id, "d": reviewed_on, "n": sealed, "u": ctx.user_id}))  # fmt: skip
        tx.record("qm_risk_review.recorded", target=Target("qm_risk_review", review_id))
    return review_id


__all__ = ["COMPONENTS", "ImportInvalid", "dry_run", "import_row", "parse", "patch_objective",
           "publish", "record_review", "register"]  # fmt: skip
