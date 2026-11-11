"""A-07-T19: the live-path registrations bundle (A-07 §4.10, §8.1; DEC-83; DF-11), inert until the
A-07 flags.

Merged before the Fri Dec 24, 2027 freeze so nothing on the live path moves in the window. Since
A-07-T33 (DEC-3106) each provider reads its firm's flag: `audits.completion`, `audits.letters`,
`audits.report_release`, `audits.archive` (boolean, per firm, default off). Off, every provider
below answers as if it were not there (a rail row or tag provider returns nothing, a source
refuses with 404, a decision card cannot be raised, the seal section writes no file, the envelope
consumer does nothing), so with every flag off AUD-02, ENG-02, SIG-01 and HOME-02 answer exactly
as before (row acceptance).

What registers here:
- **C7 envelope sources** `rep_letter` (gate G7; signed by management with the provider's email
  code, DF-11; dated as of the report date) and `governance_letter` (the acknowledgement envelope
  where POR-15 is off, DEC-83), and the `envelope.completed` consumer that records them.
- **C11 document kinds** `representation_letter`, `governance_letter`, `audit_report` (its final
  is the same kind rendered in `final` mode, which needs the EP's approval: C11 has no separate
  `audit_report_final` kind; DEC-2706).
- **Decision kinds** `going_concern` and `opinion`, reserved to the engagement partner, options
  computed by code (AU-C 570; AU-C 700/705), and the reviewable `audit_report_version`.
- **A-01 rail rows** for AUD-18 to AUD-25 and index tags `report_released`, `archived`.
- **The engagement export's `archive_seal` section** (P-43: the seal travels in the export).
- **C16 notification kinds** of A-07 §4.8 are registered with the notification catalogue's kinds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import (
    AUDITS_ARCHIVE,
    AUDITS_COMPLETION,
    AUDITS_LETTERS,
    AUDITS_REPORT_RELEASE,
)
from abacus.kernel.clock import FIRM_ZONE
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag as FlagDef
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance.eqr_service import TemplateItem, register_eqr_checklist_template
from abacus.modules.assurance.release import report_release_approval
from abacus.modules.assurance.sections import (
    Band,
    IndexTag,
    SectionState,
    SectionStateProvider,
    register_audit_section,
    register_index_tag,
)
from abacus.modules.evidence.api import SectionFile, SectionRequest, register_export_section
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import api as c11
from abacus.modules.review.api import (
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    Reviewable,
    ReviewableFacts,
    register_decision_kind,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.signatures.api import EnvelopeSource, register_envelope_source

Flag = Literal["audits.completion", "audits.letters", "audits.report_release", "audits.archive"]
# A-07-T33 (DEC-3106): the per-firm flags (ADR-089), boolean and default off, replace the S27
# `LIVE` table and `completion_dark.COMPLETION_LIVE`: nothing here is live for a firm until its
# flag flips in a Tuesday slot (P-29).
FLAGS: Final[dict[Flag, FlagDef]] = {
    "audits.completion": AUDITS_COMPLETION,
    "audits.letters": AUDITS_LETTERS,
    "audits.report_release": AUDITS_REPORT_RELEASE,
    "audits.archive": AUDITS_ARCHIVE,
}
REP_LETTER: Final = "rep_letter"
GOVERNANCE_LETTER: Final = "governance_letter"
RECORD_TYPE: Final = "audit_documentation"  # AU-C 230 (the audit file's record type)
SEAL_SECTION: Final = "archive_seal"
REPORT_VERSION: Final = "audit_report_version"


async def live(tenant: TenantContext, flag: Flag) -> bool:
    """The firm's flag (a read error falls back to the default, off)."""
    return await flag_enabled(tenant, FLAGS[flag])


async def require_live(tenant: TenantContext, flag: Flag) -> None:
    """A path behind an off flag answers as if it did not exist (404)."""
    if not await live(tenant, flag):
        raise NotLive(flag)


class NotLive(NotFound):
    """An A-07 path whose flag is off answers as if it did not exist (404)."""


# --- A-01 rail rows and index tags -----------------------------------------------------------

# (key, band, order, route, title, flag): AUD-18 to AUD-25 (A-07 §2.1).
SECTIONS: Final[tuple[tuple[str, Band, int, str, str, Flag], ...]] = (
    ("eqr", "completion", 20, "AUD-18", "Engagement quality review", "audits.completion"),
    ("completion_checklist", "completion", 21, "AUD-19", "Completion", "audits.completion"),
    (
        "representation_letter",
        "completion",
        22,
        "AUD-21",
        "Representation letter",
        "audits.letters",
    ),
    (
        "governance_communications",
        "completion",
        23,
        "AUD-22",
        "Governance communications",
        "audits.letters",
    ),
    ("auditors_report", "reporting", 0, "AUD-23", "Auditor's report", "audits.report_release"),
    ("release", "reporting", 1, "AUD-24", "Release", "audits.report_release"),
    ("archive", "reporting", 2, "AUD-25", "Archive", "audits.archive"),
)
_SECTION_FLAG: Final[dict[str, Flag]] = {key: flag for key, *_, flag in SECTIONS}
_STATE_PROVIDERS: dict[str, SectionStateProvider] = {}
# Live before its service: still no row (never a made-up state, A-01 DV-1).
_NO_SERVICE_YET: Final[SectionState | None] = None


def _section_provider(key: str) -> SectionStateProvider:
    async def state(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
        """None leaves the row out (A-01 DV-1). Off, the row never shows; the live states
        arrive with the A-07 service behind each screen (T24 to T32) and T33's flag checks."""
        del work_item_id
        return None if not await live(tenant, _SECTION_FLAG[key]) else _NO_SERVICE_YET

    return state


async def report_released_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    """A-07-T30: "Released Oct 9" on an AUD-01 row once G8 is recorded in Accrued; nothing while
    `audits.report_release` is off."""
    if not work_item_ids or not await live(tenant, "audits.report_release"):
        return {}
    from abacus.modules.assurance.providers import month_day

    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT work_item_id, released_at FROM report_releases "
                    "WHERE kind = 'original' AND work_item_id = ANY(:ids)"
                ),
                {"ids": list(work_item_ids)},
            )
        ).all()
    return {
        r.work_item_id: [
            IndexTag(
                "report_released",
                f"Released {month_day(r.released_at.astimezone(FIRM_ZONE).date())}",
            )
        ]
        for r in rows
    }


async def archived_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    del tenant, work_item_ids
    return {}  # off: no tag; the archive service (A-07-T31) supplies "Archived"


# --- C7 envelope sources ---------------------------------------------------------------------


async def _rep_letter_documents(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    del ctx, version_id
    raise NotLive  # off; A-07-T24 builds the letter's documents


async def _rep_letter_signers(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    del ctx, version_id
    raise NotLive  # off; A-07-T24: management signs with the provider's email code (DF-11)


async def rep_letter_dated_as_of_report(ctx: AuthContext, version_id: UUID) -> Sequence[str]:
    """The date rule (A-07 §3.3): a representation letter is dated as of the auditor's report
    date. While the letters flag is off, every send is refused with the flag's problem."""
    del version_id
    return ["letters_not_live"] if not await live(ctx.tenant, "audits.letters") else []


async def governance_acknowledgement_only(ctx: AuthContext, version_id: UUID) -> Sequence[str]:
    """DEC-83: a governance letter goes by envelope only as an acknowledgement, and only where the
    POR-15 room is off for the firm; refused while the letters flag is off."""
    del version_id
    return ["letters_not_live"] if not await live(ctx.tenant, "audits.letters") else []


async def on_letter_envelope_completed(event: OutboxEvent) -> None:
    """`envelope.completed` for a rep letter (G7 with the date check, A-07-T24) or a governance
    acknowledgement (A-07-T26). Inert while the letters flag is off: the event is left to the
    other consumers (signatures' own record is unchanged)."""
    if event.payload.get("source_kind") not in (REP_LETTER, GOVERNANCE_LETTER):
        return
    if not await live(TenantContext(event.tenant_id, "system", "a07_letters"), "audits.letters"):
        return
    if event.payload.get("source_kind") == REP_LETTER:
        # A-07-T24 (DEC-2808): G7 with the date check, on the client signer's signing instant in
        # the firm's zone. A-07-T26 records the governance acknowledgement.
        from abacus.modules.assurance.rep_letters import record_signature
        from abacus.modules.signatures.api import envelope_signing

        envelope_id = UUID(str(event.payload["envelope_id"]))
        tenant = TenantContext(event.tenant_id, "system", "rep_letter_g7")
        signing = await envelope_signing(tenant, envelope_id)
        signed_at = None if signing is None else signing.signed_at.get("client")
        if signed_at is None:
            return
        await record_signature(
            tenant, envelope_id, signed_at, signed_at.astimezone(FIRM_ZONE).date()
        )


# --- C11 document kinds ----------------------------------------------------------------------


async def _no_variables(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
    """The kinds declare no variables. Regenerate and the out-of-date read reach only documents
    a live render made, so they need no flag here."""
    del owner, scope
    return {}


async def _live_variables(
    tenant: TenantContext, owner: c11.OwnerRef, scope: c11.RenderScope
) -> Mapping[str, str]:
    """A new render: refused (404) while both the letters and the report flags are off."""
    del owner, scope
    if not await live(tenant, "audits.letters") and not await live(
        tenant, "audits.report_release"
    ):
        raise NotLive("audits.letters")
    return {}


async def _no_approval(ref: c11.ApprovalRef) -> tuple[UUID, str] | None:
    """No final is approved while the flags are off (C11 refuses `final_requires_approval`)."""
    del ref
    return None


_DOCUMENT_KINDS: Final[tuple[tuple[c11.GeneratedDocumentKind, c11.KindLayout], ...]] = (
    ("representation_letter", "letter"),
    ("governance_letter", "letter"),
    ("audit_report", "report"),
)


# --- Decision kinds --------------------------------------------------------------------------

# AU-C 570.24 to .27 and AU-C 700/705: the options are fixed copy; nothing computes a figure.
_GOING_CONCERN: Final = (
    ("no_substantial_doubt", "No substantial doubt"),
    ("doubt_alleviated", "Substantial doubt alleviated by management's plans; disclosed"),
    ("doubt_exists_disclosed", "Substantial doubt exists; adequately disclosed"),
    ("doubt_exists_inadequate", "Substantial doubt exists; disclosure inadequate"),
)
_OPINION: Final = (
    ("unmodified", "Unmodified"),
    ("qualified", "Qualified"),
    ("adverse", "Adverse"),
    ("disclaimer", "Disclaimer of opinion"),
)


async def _going_concern_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    del subject
    await require_live(tenant, "audits.completion")
    return ComputedCard(options=tuple(CardOption(k, label) for k, label in _GOING_CONCERN))


async def _opinion_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    del subject
    await require_live(tenant, "audits.report_release")
    return ComputedCard(options=tuple(CardOption(k, label) for k, label in _OPINION))


async def report_version_reviewables(
    tenant: TenantContext, work_item_id: UUID
) -> list[Reviewable]:
    """The report versions a sign-off may cite (A-07-T27 builds them); none while off."""
    del tenant, work_item_id
    return []  # off: nothing to cite; A-07-T27 lists the versions


async def report_version_facts(tenant: TenantContext, version_id: UUID) -> ReviewableFacts | None:
    """AUD-23 b's approval: the EP's L4 on one report version's content hash (A-07-T27). Its
    preparer is the person who wrote the version, so they cannot approve their own (R-SO-2).
    S35 round 2 end pass: the sign-off refused an unregistered kind, so no report was approved."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT engagement_id, version_no, content_hash, created_by "
                    "FROM audit_report_versions WHERE id = :v"
                ),
                {"v": version_id},
            )
        ).first()
    if row is None:
        return None
    return ReviewableFacts(
        target_type=REPORT_VERSION,
        target_id=version_id,
        engagement_id=row.engagement_id,
        content_hash=str(row.content_hash),
        version_no=int(row.version_no),
        preparer_user_ids=frozenset({row.created_by}),
        required_levels=(1, 4),  # the preparer's L1, then the EP's approval
    )


# --- The export's seal section ---------------------------------------------------------------


async def archive_seal_section(
    tenant: TenantContext, request: SectionRequest
) -> Sequence[SectionFile]:
    """The archive's seal (P-43): manifest id and SHA-256 once locked; no file while off."""
    del tenant, request
    return []  # off: no file; A-07-T31 writes the manifest id and seal SHA-256


# --- Registration ----------------------------------------------------------------------------


async def eqr_checklist_items(tenant: TenantContext, engagement_id: UUID) -> list[TemplateItem]:
    """The firm's published EQR checklist for the engagement's type (A-07-T22's import), in
    order; none until one is published (the review then cannot open, 409 `template_missing`).
    S35 round 2 end pass: nothing registered this provider, so no review ever opened."""
    from abacus.modules.engagements.api import engagement_type_of
    from abacus.modules.methodology.api import published_checklist

    engagement_type = await engagement_type_of(tenant, engagement_id)
    if engagement_type is None:
        return []
    found = await published_checklist(tenant, "eqr", engagement_type)
    return [] if found is None else [TemplateItem(i.key, i.text) for i in found.items]


def register() -> None:
    """At import (assurance/api.py), once; a reload replaces itself."""
    register_eqr_checklist_template(eqr_checklist_items)
    for key, band, order, route, title, _flag in SECTIONS:
        provider = _STATE_PROVIDERS.setdefault(key, _section_provider(key))
        register_audit_section(key, band, order, route, provider, title=title, link="planned")
    register_index_tag("report_released", report_released_tags, "metadata")
    register_index_tag("archived", archived_tags, "metadata")
    register_envelope_source(
        EnvelopeSource(
            kind=REP_LETTER,
            documents=_rep_letter_documents,
            signers=_rep_letter_signers,
            retention_record_type=RECORD_TYPE,
            gate="G7",
            checks=(rep_letter_dated_as_of_report,),
            completed_label="Signed",
        )
    )
    # TASK-6543 (DEC-3145): the governance letter's source drafts from a sent version's final
    # document, the recipients signing to acknowledge.
    from abacus.modules.assurance import governance_comms as gc

    register_envelope_source(
        EnvelopeSource(
            kind=GOVERNANCE_LETTER,
            documents=gc.governance_documents,
            signers=gc.governance_signers,
            retention_record_type=RECORD_TYPE,
            checks=(governance_acknowledgement_only,),
            completed_label="Acknowledged",
            draft=gc.governance_draft,  # type: ignore[arg-type] -- returns C7's SourceDraft
        )
    )
    for kind, layout in _DOCUMENT_KINDS:
        try:
            c11.document_kind(kind)
        except c11.UnknownDocumentKind:
            c11.register_document_kind(
                c11.DocumentKind(
                    kind=kind,
                    layout=layout,
                    variables_provider=_no_variables,
                    # A-07-T30: the report's final render is approved by the consumed release
                    # grant (the EP's decision); the letters' finals stay with their services.
                    approval_provider=report_release_approval
                    if kind == "audit_report"
                    else gc.send_approval
                    if kind == GOVERNANCE_LETTER
                    else _no_approval,
                    # The governance letter's body is its version's sections (DEC-3145).
                    body_provider=gc.letter_body if kind == GOVERNANCE_LETTER else None,
                    retention_record_type=RECORD_TYPE,
                    formats=("pdf", "docx"),
                    tenant_variables_provider=_live_variables,
                )
            )
    register_decision_kind(
        DecisionKind(
            code="going_concern",
            reserved_role="engagement_partner",
            options=_going_concern_card,
            questions={"going_concern": "Going concern (AU-C 570)"},
        )
    )
    register_decision_kind(
        DecisionKind(
            code="opinion",
            reserved_role="engagement_partner",
            options=_opinion_card,
            questions={"opinion": "Opinion on the financial statements"},
        )
    )
    register_reviewable(REPORT_VERSION, report_version_reviewables)
    register_reviewable_facts(REPORT_VERSION, report_version_facts)
    register_export_section(SEAL_SECTION, archive_seal_section)


SUBSCRIPTIONS: Final = {"envelope.completed": on_letter_envelope_completed}
