"""Minimal skills: imported database content (K-03-T21; TASK-9015; K-03 F10; KNW-06 c; SHT-04;
DEC-6021; amber). No editor and no eval gate (K-05).

- **Import** (`import_skills`, `POST /v1/skills/import`, `skill.import`, the QM owner with fresh
  MFA): a content pack of skills and their versions. A version is immutable once imported (an
  equal body re-imported is a no-op; a different body under the same number answers 409
  `skill_version_exists`). Each body must pass the sanitised-markdown schema (`unsafe_reason`):
  anything outside it is refused with 422 `skill_markdown_unsafe`, never stripped. A `published`
  version records the importer as publisher.
- **Read** (`skills`, `skill_version`, `knowledge.read`): each skill's versions with status.
- **Pins** (`pin_warnings`): a template version's skill pins and, for a pin to a draft version, the
  KNW-06c warning ("Skill BH-SK-430 v2 is a draft"), a warning that never blocks publish.
- **Runs** (`published_body`): the body an agent-column run uses, published versions only.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise

Status = Literal["draft", "published"]
_KEY: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$")
_STEP: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
MAX_BODY: Final = 60_000


class SkillMarkdownUnsafe(DomainInvalid):
    """A skill body uses markdown outside the sanitised schema (refused, never stripped)."""

    code = "skill_markdown_unsafe"


class SkillVersionExists(DomainConflict):
    """That skill version is already imported with another body: versions never change."""

    code = "skill_version_exists"


class SkillPackInvalid(DomainInvalid):
    """The content pack is not a list of skills with numbered versions."""

    code = "skill_pack_invalid"


# --- the sanitised-markdown schema ---------------------------------------------------------------

_UNSAFE: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("html", re.compile(r"<\s*/?\s*[A-Za-z!?]")),  # any tag, comment or doctype
    ("html_entity", re.compile(r"&#?[A-Za-z0-9]+;")),
    ("image", re.compile(r"!\[")),
    ("script_url", re.compile(r"(?i)\b(javascript|vbscript|data|file)\s*:")),
    ("autolink", re.compile(r"(?i)<\s*(https?|mailto):")),
    ("control", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‪-‮⁦-⁩]")),
    ("reference_definition", re.compile(r"(?m)^\s{0,3}\[[^\]]+\]:\s")),
)
_LINK: Final = re.compile(r"\]\(([^)\s]*)")


def unsafe_reason(body: str) -> str | None:
    """Why the body falls outside the schema (headings, paragraphs, lists, emphasis, code, block
    quotes, tables and links to https or relative targets), or None when it fits."""
    if not body.strip() or len(body) > MAX_BODY:
        return "length"
    for reason, pattern in _UNSAFE:
        if pattern.search(body):
            return reason
    for target in _LINK.findall(body):
        if target and not (target.startswith("https://") or target.startswith("#")
                           or target.startswith("/")):  # fmt: skip
            return "link_target"
    return None


# --- import --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionIn:
    version: int
    status: Status
    body_md: str
    linked_step_keys: tuple[str, ...]


@dataclass(frozen=True)
class SkillIn:
    key: str
    name: str
    group: str | None
    versions: tuple[VersionIn, ...]


@dataclass(frozen=True)
class SkillVersionView:
    skill_id: UUID
    key: str
    name: str
    version_id: UUID
    version: int
    status: Status
    linked_step_keys: tuple[str, ...]


def parse_pack(raw: Mapping[str, object]) -> list[SkillIn]:
    """The pack's skills, checked for shape and the markdown schema (422 before any write)."""
    items = raw.get("skills")
    if not isinstance(items, list) or not items or len(cast(list[object], items)) > 200:
        raise SkillPackInvalid(facts={"field": "skills"})
    out: list[SkillIn] = []
    for item in cast(list[object], items):
        if not isinstance(item, dict):
            raise SkillPackInvalid(facts={"field": "skill"})
        s = cast(dict[str, object], item)
        key, name, group = s.get("key"), s.get("name"), s.get("group")
        versions = s.get("versions")
        if not (isinstance(key, str) and _KEY.fullmatch(key) and isinstance(name, str)
                and name.strip() and isinstance(versions, list) and versions):  # fmt: skip
            raise SkillPackInvalid(facts={"field": "skill"})
        parsed: list[VersionIn] = []
        for v in cast(list[object], versions):
            if not isinstance(v, dict):
                raise SkillPackInvalid(facts={"field": "version"})
            d = cast(dict[str, object], v)
            number, status, body = d.get("version"), d.get("status", "draft"), d.get("body_md")
            steps = d.get("linked_step_keys", [])
            if not (isinstance(number, int) and number >= 1 and status in ("draft", "published")
                    and isinstance(body, str) and isinstance(steps, list)
                    and all(isinstance(x, str) and _STEP.fullmatch(x)
                            for x in cast(list[object], steps))):  # fmt: skip
                raise SkillPackInvalid(facts={"field": "version"})
            reason = unsafe_reason(body)
            if reason is not None:
                raise SkillMarkdownUnsafe(
                    facts={"skill": key, "version": number, "reason": reason}
                )
            parsed.append(VersionIn(number, status, body,
                                    tuple(cast(list[str], steps))))  # fmt: skip
        out.append(SkillIn(key, name.strip()[:200],
                           group.strip()[:120] if isinstance(group, str) and group.strip()
                           else None, tuple(parsed)))  # fmt: skip
    return out


_SKILL: Final = text("SELECT id FROM agent_skills WHERE skill_key = :k")
_NEW_SKILL: Final = text(
    "INSERT INTO agent_skills (id, tenant_id, skill_key, name, skill_group, created_by) "
    "VALUES (:id, :t, :k, :name, :g, :by)"
)
_VERSION: Final = text(
    "SELECT id, body_sha256 FROM agent_skill_versions WHERE skill_id = :s AND version = :v"
)
_NEW_VERSION: Final = text(
    "INSERT INTO agent_skill_versions (id, tenant_id, skill_id, version, status, body_md, "
    "body_sha256, linked_step_keys, source, created_by, published_by, published_at) VALUES (:id, "
    ":t, :s, :v, :status, :body, :sha, :steps, 'imported', :by, :pub, "
    "CASE WHEN :status = 'published' THEN abacus_now() END)"
)


async def import_skills(ctx: AuthContext, pack: Mapping[str, object]) -> list[UUID]:
    """The pack's new versions (an identical re-import adds none); one event per new version."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("skill.import", "role")
    await authorise(ctx, "skill.import", Resource.firm(ctx.tenant_id))  # fresh MFA (matrix)
    skills = parse_pack(pack)
    added: list[UUID] = []
    try:
        await _write(ctx, skills, added)
    except MissingAuditEvent:
        if added:  # a write without its event is a bug; an identical re-import writes nothing
            raise
    return added


async def _write(ctx: AuthContext, skills: Sequence[SkillIn], added: list[UUID]) -> None:
    async with uow(ctx.tenant) as tx:
        for skill in skills:
            skill_id = await tx.session.scalar(_SKILL, {"k": skill.key})
            if skill_id is None:
                skill_id = uuid4()
                await tx.session.execute(
                    _NEW_SKILL,
                    {"id": skill_id, "t": ctx.tenant_id, "k": skill.key, "name": skill.name,
                     "g": skill.group, "by": ctx.user_id},
                )  # fmt: skip
            for v in skill.versions:
                sha = hashlib.sha256(v.body_md.encode("utf-8")).hexdigest()
                found = (
                    await tx.session.execute(_VERSION, {"s": skill_id, "v": v.version})
                ).first()
                if found is not None:
                    if str(found.body_sha256) != sha:
                        raise SkillVersionExists(facts={"skill": skill.key, "version": v.version})
                    continue
                version_id = uuid4()
                await tx.session.execute(
                    _NEW_VERSION,
                    {"id": version_id, "t": ctx.tenant_id, "s": skill_id, "v": v.version,
                     "status": v.status, "body": v.body_md, "sha": sha,
                     "steps": list(v.linked_step_keys), "by": ctx.user_id,
                     "pub": ctx.user_id if v.status == "published" else None},
                )  # fmt: skip
                tx.record(
                    "skill_version.imported",
                    target=Target("agent_skill", cast(UUID, skill_id)),
                    after=Ref(
                        version=v.version, published=int(v.status == "published"), sha256=sha
                    ),
                )
                added.append(version_id)


# --- reading -------------------------------------------------------------------------------------

_VERSIONS: Final = text(
    "SELECT s.id AS skill_id, s.skill_key, s.name, v.id, v.version, v.status, v.linked_step_keys "
    "FROM agent_skills s JOIN agent_skill_versions v ON v.skill_id = s.id "
    "WHERE (CAST(:v AS uuid) IS NULL OR v.id = CAST(:v AS uuid)) ORDER BY s.skill_key, v.version"
)


def _view(r: object) -> SkillVersionView:
    row = cast(Mapping[str, object], r)
    return SkillVersionView(
        cast(UUID, row["skill_id"]), str(row["skill_key"]), str(row["name"]),
        cast(UUID, row["id"]), int(cast(int, row["version"])), cast(Status, row["status"]),
        tuple(cast(Sequence[str], row["linked_step_keys"] or ())),
    )  # fmt: skip


async def skills(ctx: AuthContext) -> list[SkillVersionView]:
    await authorise(ctx, "knowledge.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_VERSIONS, {"v": None})).mappings()
        return [_view(r) for r in found]


async def skill_version(ctx: AuthContext, version_id: UUID) -> SkillVersionView:
    await authorise(ctx, "knowledge.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_VERSIONS, {"v": version_id})).mappings().first()
    if found is None:
        raise NotFound("skill_version")
    return _view(found)


@dataclass(frozen=True)
class PinWarning:
    skill_key: str
    version: int
    severity: Literal["warning"]
    text: str


_PINS: Final = text(
    "SELECT p.skill_key, v.version, v.status FROM template_skill_pins p "
    "JOIN agent_skill_versions v ON v.id = p.skill_version_id "
    "WHERE p.template_version_id = :t ORDER BY p.skill_key"
)


async def pin_warnings(tenant: TenantContext, template_version_id: UUID) -> list[PinWarning]:
    """KNW-06c: a pin to a draft skill version is a warning (it never blocks publish)."""
    async with tenant_session(tenant) as session:
        found = list(await session.execute(_PINS, {"t": template_version_id}))
    return [
        PinWarning(str(r.skill_key), int(r.version), "warning",
                   f"Skill {r.skill_key} v{r.version} is a draft")
        for r in found
        if r.status == "draft"
    ]  # fmt: skip


async def published_body(tenant: TenantContext, skill_version_id: UUID) -> str | None:
    """The body an agent-column run uses: a published version's only."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT body_md FROM agent_skill_versions WHERE id = :v "
                 "AND status = 'published'"),
            {"v": skill_version_id},
        )  # fmt: skip
    return None if found is None else str(found)


__all__ = [
    "PinWarning",
    "SkillMarkdownUnsafe",
    "SkillPackInvalid",
    "SkillVersionExists",
    "SkillVersionView",
    "import_skills",
    "parse_pack",
    "pin_warnings",
    "published_body",
    "skill_version",
    "skills",
    "unsafe_reason",
]
