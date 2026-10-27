"""One A-01 engagement export package per engagement inside the firm export (Q-02-T47; Q-02 §4.2
`FirmExportWorkflow`; compliance-kernel §3; DEC-640). PROTECTED (evidence, red).

The firm export acts as the system on behalf of its approver (INV-5), so each package is the
engagement as the approver may read it now: the same planner, section providers and builder as an
AUD-03 binder export (`export_selection.plan_selection`, `export_activities.section_files`,
`export_builder.build_package`), every asked PBC binder of the engagement's assurance work item,
accepted and unaccepted versions, no audit-trail section (the audit export is G-02-T17's).

Nothing is widened for the firm: an engagement the approver may not read (a wall, a role or
independence), one with no assurance work item and one with no asked PBC binder are left out and named in the firm index's
`omitted` list with their reason, never silently dropped (DEC-640). A file whose bytes no longer
match their fingerprint fails the whole export (RB-29), as it fails a binder export.

Each package is written to its own scratch file and returned with its digests; the firm archive
(`firm_export_activities.write_archive`) stores it at `packages/<engagement_id>.zip` and its
manifest hashes the stored bytes.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import IO, Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.modules.engagements.api import (
    all_engagement_ids,
    assurance_item_id,
    engagement_metadata,
    get_ref,
)
from abacus.modules.evidence.export_activities import evidence_files, section_files
from abacus.modules.evidence.export_builder import (
    PackageFacts,
    PackageIntegrityError,
    PackageInvalid,
    build_package,
)
from abacus.modules.evidence.export_manifest import (
    ManifestClient,
    ManifestEngagement,
    ManifestPerson,
    ManifestScope,
)
from abacus.modules.evidence.export_package import ExportSectionInvalid, SectionRequest
from abacus.modules.evidence.export_sections import acting_person
from abacus.modules.evidence.export_selection import plan_in_use, plan_selection
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, firm_name, names_of
from abacus.modules.requests.api import pbc_binders

PACKAGE_DIR: Final = "packages"
PACKAGE_KIND: Final = "binder"

Omission = Literal["not_readable", "not_an_audit", "no_binders", "unsafe_contents"]

_log = get_logger(__name__)


class FirmPackageIntegrityError(Exception):
    """A stored file no longer matches its fingerprint (RB-29): the firm export fails."""


@dataclass(frozen=True, slots=True)
class EngagementPackage:
    """One built package, open in worker scratch until the firm archive has copied it."""

    engagement_id: UUID
    work_item_id: UUID
    path: str
    handle: IO[bytes]
    bundle_sha256: str
    manifest_sha256: str
    bytes: int
    file_count: int
    request_count: int


@dataclass(frozen=True, slots=True)
class Omitted:
    engagement_id: UUID
    reason: Omission


@dataclass(slots=True)
class FirmPackages:
    packages: list[EngagementPackage]
    omitted: list[Omitted]

    def close(self) -> None:
        for package in self.packages:
            package.handle.close()

    def __enter__(self) -> FirmPackages:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def package_path(engagement_id: UUID) -> str:
    return f"{PACKAGE_DIR}/{engagement_id}.zip"


async def _readable(ctx: AuthContext, engagement_id: UUID) -> bool:
    try:
        engagement = await get_ref(ctx, engagement_id)
        await authorise(ctx, "evidence.read", engagement.resource())
    except (Forbidden, NotFound):
        return False
    return True


async def _one(
    ctx: AuthContext,
    system: TenantContext,
    *,
    export_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    as_of_seq: int,
    built_at: datetime,
    firm: str,
    approver: ManifestPerson,
    heartbeat: Callable[[], None],
) -> EngagementPackage | Omitted:
    binders = tuple(await pbc_binders(ctx, work_item_id))
    if not binders:  # a package's scope names at least one binder (SPEC-344)
        return Omitted(engagement_id, "no_binders")
    request = SectionRequest(
        export_id=export_id,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        binder_ids=binders,
        as_of_seq=as_of_seq,
        include_unaccepted=True,
        requested_by_user_id=ctx.user_id,
        membership_id=ctx.membership_id,
    )
    try:
        plan = await plan_selection(ctx, request)
        with plan_in_use(plan):
            sections, extra = await section_files(system, request)
    except ExportSectionInvalid:
        # The approver lost the engagement between the check and the plan, or a name was unsafe.
        return Omitted(engagement_id, "unsafe_contents")
    meta = await engagement_metadata(ctx, engagement_id)
    facts = PackageFacts(
        export_id=export_id,
        kind=PACKAGE_KIND,
        generated_at=built_at,
        as_of_seq=as_of_seq,
        tenant_id=system.tenant_id,
        firm_name=firm,
        client=ManifestClient(
            client_id=meta.engagement.client_id, display_name=meta.engagement.client_name
        ),
        engagement=ManifestEngagement(
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            display_name=meta.engagement.name,
            period_end=meta.engagement.fiscal_period_end,
        ),
        requested_by=approver,
        requested_at=built_at,
        scope=ManifestScope(
            binder_ids=list(binders), include_unaccepted=True, include_audit_trail=False
        ),
        request_count=len(plan.requests),
        requests_without_file=sum(1 for r in plan.requests if not r.files),
        sections=tuple(extra),
    )
    evidence = evidence_files(system.tenant_id, plan, asyncio.get_running_loop(), heartbeat)
    handle = tempfile.TemporaryFile()  # noqa: SIM115 -- closed by FirmPackages.close
    try:
        built = await asyncio.to_thread(build_package, facts, [*sections, *evidence], handle)
    except PackageInvalid:
        handle.close()
        return Omitted(engagement_id, "unsafe_contents")
    except PackageIntegrityError as mismatch:
        handle.close()
        version_id = next(
            (f.evidence_version_id for f in plan.files if f.path == mismatch.path), None
        )
        # RB-29: the integrity alarm reads this event. Identifiers only.
        _log.error(
            "evidence.integrity_mismatch",
            tenant_id=system.tenant_id,
            evidence_version_id=version_id,
            export_id=export_id,
        )
        raise FirmPackageIntegrityError(str(engagement_id)) from None
    handle.seek(0)
    heartbeat()
    return EngagementPackage(
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        path=package_path(engagement_id),
        handle=handle,
        bundle_sha256=built.bundle_sha256,
        manifest_sha256=built.manifest_sha256,
        bytes=built.bytes,
        file_count=built.file_count,
        request_count=len(plan.requests),
    )


async def engagement_packages(
    system: TenantContext,
    *,
    export_id: UUID,
    approver_id: UUID,
    as_of_seq: int,
    built_at: datetime,
    heartbeat: Callable[[], None] = lambda: None,
) -> FirmPackages:
    """Every engagement of the firm, in creation order: a package, or its reason for omission. The
    caller closes the result once the firm archive has copied the packages."""
    ctx = await acting_person(system, approver_id)
    firm = await firm_name(system.tenant_id)
    names = await names_of([approver_id])
    approver = ManifestPerson(
        user_id=approver_id, display_name=names.get(approver_id) or "Unknown person"
    )
    found = FirmPackages(packages=[], omitted=[])
    try:
        for engagement_id in await all_engagement_ids(system):
            if not await _readable(ctx, engagement_id):
                found.omitted.append(Omitted(engagement_id, "not_readable"))
                continue
            work_item_id = await assurance_item_id(ctx.tenant, engagement_id)
            if work_item_id is None:
                found.omitted.append(Omitted(engagement_id, "not_an_audit"))
                continue
            made = await _one(
                ctx,
                system,
                export_id=export_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                as_of_seq=as_of_seq,
                built_at=built_at,
                firm=firm,
                approver=approver,
                heartbeat=heartbeat,
            )
            if isinstance(made, Omitted):
                found.omitted.append(made)
            else:
                found.packages.append(made)
    except BaseException:
        found.close()
        raise
    return found
