"""The onboarding import of a firm's email templates (R-01-T23; C16 v1.1; R-01 Story 7.4;
DEC-561).

A counsel-approved bundle (F-09-T115 pattern) becomes database rows, never a commit (AGENTS 16).
`email_template.import` is the firm admin's, with a fresh second factor for the dry run as well
(the matrix); it is never behind `portal.settings_editor` (the contract).

- Each entry is checked as the editor checks a draft (`check_content`) and linted as publish
  lints it (`lint_template`). An unregistered or platform-locked key, an invalid entry, a key
  named twice or any lint finding makes the entry `refused`; otherwise its change is `add`
  (the firm has neither a draft nor a version in use), `unchanged` (the same content is already
  the draft, or published when the entry publishes) or `update`.
- **Dry run** (the default): the report only. Nothing is written and nothing is audited.
- **Apply**: all or nothing. Any refused entry answers 422 (`template_invalid` for an invalid or
  unknown entry, else `template_lint_failed` with identifier-only facts) and nothing is written.
  Otherwise one unit of work: each changed entry replaces the firm's draft (`publish: false`) or
  is published as version n+1 with source `import` (`publish: true`, the same insert-only
  function the editor's publish uses; a draft the firm had stays, based on the older version).
  Audited `email_template.imported` per template (and `email_template.published` with its
  outbox event for a published one).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications import template_store
from abacus.modules.communications.events import EmailTemplatePublished
from abacus.modules.communications.lint import LintFinding, lint_template
from abacus.modules.communications.render import TemplateContent
from abacus.modules.communications.template_registry import registration_of
from abacus.modules.communications.template_service import (
    TemplateDraftStale,
    TemplateLintFailed,
    check_content,
)
from abacus.modules.communications.templates import TemplateInvalid
from abacus.modules.identity.api import AuthContext, Resource, authorise

Change = Literal["add", "update", "unchanged", "refused"]
_SERIALIZATION = "40001"


@dataclass(frozen=True)
class BundleEntry:
    key: str
    content: TemplateContent
    publish: bool


@dataclass(frozen=True)
class ImportResult:
    key: str
    change: Change
    findings: tuple[LintFinding, ...] = ()
    invalid: bool = False


async def _current(
    ctx: AuthContext, key: str
) -> tuple[TemplateContent | None, TemplateContent | None]:
    """The firm's draft and the version in use, as content."""
    async with tenant_session(ctx.tenant) as session:
        firm_id = await template_store.firm_template_id(session, key)
        draft = (
            None
            if firm_id is None
            else await template_store.draft_of(session, ctx.tenant_id, firm_id)
        )
        published = await template_store.resolve(session, ctx.tenant_id, key)
    return (
        None if draft is None else draft.content,
        None if published is None else published.content,
    )


async def _assess(ctx: AuthContext, entry: BundleEntry, repeated: bool) -> ImportResult:
    registration = registration_of(entry.key)
    if repeated or registration is None or not registration.firm_editable:
        return ImportResult(entry.key, "refused", invalid=True)
    try:
        check_content(entry.content, registration)
    except TemplateInvalid:
        return ImportResult(entry.key, "refused", invalid=True)
    findings = lint_template(entry.content, registration)
    if findings:
        return ImportResult(entry.key, "refused", tuple(findings))
    draft, published = await _current(ctx, entry.key)
    same = published if entry.publish else (draft if draft is not None else published)
    if same == entry.content:
        return ImportResult(entry.key, "unchanged")
    return ImportResult(entry.key, "add" if draft is None and published is None else "update")


async def assess(ctx: AuthContext, bundle: list[BundleEntry]) -> list[ImportResult]:
    counts = Counter(e.key for e in bundle)
    return [await _assess(ctx, e, counts[e.key] > 1) for e in bundle]


async def import_bundle(
    ctx: AuthContext, bundle: list[BundleEntry], *, dry_run: bool
) -> list[ImportResult]:
    await authorise(ctx, "email_template.import", Resource.firm(ctx.tenant_id))
    results = await assess(ctx, bundle)
    if dry_run:
        return results
    refused = [r for r in results if r.change == "refused"]
    if any(r.invalid for r in refused):
        raise TemplateInvalid
    if refused:
        raise TemplateLintFailed(
            [LintFinding(f.code, f"{r.key}.{f.where}") for r in refused for f in r.findings]
        )
    changed = [(e, r) for e, r in zip(bundle, results, strict=True) if r.change != "unchanged"]
    if changed:
        await _apply(ctx, [e for e, _ in changed])
    return results


async def _apply(ctx: AuthContext, entries: list[BundleEntry]) -> None:
    async with uow(ctx.tenant) as tx:
        for entry in entries:
            template_id = await template_store.ensure_firm_template(tx.session, entry.key)
            current = await template_store.resolve(tx.session, ctx.tenant_id, entry.key)
            if entry.publish:
                version = (current.version if current is not None else 0) + 1
                try:
                    version_id, sha = await template_store.publish_version(
                        tx.session,
                        ctx.tenant_id,
                        entry.key,
                        template_id,
                        version,
                        entry.content,
                        source="import",
                    )
                except DBAPIError as exc:
                    if getattr(exc.orig, "sqlstate", None) == _SERIALIZATION:
                        raise TemplateDraftStale(facts={"draft_version": 0}) from None
                    raise
                after = Ref(version_id=version_id, version=version, sha256=sha)
                tx.record(
                    "email_template.published",
                    target=Target("email_template", template_id),
                    before=Ref(version_id=current.version_id) if current is not None else None,
                    after=after,
                )
                tx.emit(EmailTemplatePublished(key=entry.key, version=version))
                tx.record(
                    "email_template.imported",
                    target=Target("email_template", template_id),
                    after=after,
                )
                continue
            draft = await template_store.draft_of(
                tx.session, ctx.tenant_id, template_id, lock=True
            )
            have = draft.draft_version if draft is not None else 0
            # The draft's counter keeps rising, so an editor's stale `expected_version` is 409.
            await template_store.put_draft(
                tx.session,
                ctx.tenant_id,
                template_id,
                base_version_id=current.version_id if current is not None else None,
                draft_version=have + 1,
                content=entry.content,
                updated_by=ctx.user_id,
            )
            tx.record(
                "email_template.imported",
                target=Target("email_template", template_id),
                before=Ref(draft_version=have) if have else None,
                after=Ref(draft_version=have + 1),
            )
