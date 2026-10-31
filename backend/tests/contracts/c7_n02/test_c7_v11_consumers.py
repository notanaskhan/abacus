"""N-02-T25 (TASK-2233; DEC-1285): C7 v1.1's consumer contract for T-01 and T-02, without a
database. `signatures.api` carries the additive surface (`supersede_for_amount_change`,
`extend_retention`, `envelope_summaries_for`, the `efile_authorization` gate, the source
contracts and the signer-level events); the v1 names stay; a contracted source must draft and its
drafts stay inside their purposes; only the system supersedes; every event field is classified.
"""

from __future__ import annotations

import inspect
from uuid import uuid4

import pytest

from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.uow import DomainEvent
from abacus.modules.signatures import api
from abacus.modules.signatures.consumers import SourceContractBroken, check_contract
from abacus.modules.signatures.sources import EnvelopeSource, register_envelope_source

V1 = ("register_envelope_source", "envelope_summary_for", "envelope_gate_facts", "create_draft")
V11 = (
    "supersede_for_amount_change",
    "extend_retention",
    "envelope_summaries_for",
    "EFILE_GATE",
    "CONSENT_SET",
    "TAX_RETURN",
    "SOURCE_CONTRACTS",
    "EnvelopeSignerSigned",
    "EnvelopeSignerVerificationFailed",
    "EnvelopeSuperseded",
)


def test_v1_is_unchanged_and_v11_is_added() -> None:
    for name in (*V1, *V11):
        assert name in api.__all__, name
    assert list(inspect.signature(api.envelope_summary_for).parameters) == [
        "ctx",
        "source_kind",
        "source_id",
    ]
    assert list(inspect.signature(api.supersede_for_amount_change).parameters) == [
        "tenant",
        "envelope_id",
        "binding_id",
    ]
    assert list(inspect.signature(api.extend_retention).parameters) == [
        "tenant",
        "envelope_id",
        "until",
    ]


def test_the_contracted_sources_and_their_floors() -> None:
    assert api.SOURCE_CONTRACTS[api.CONSENT_SET].policy_family == "consent"
    assert api.SOURCE_CONTRACTS[api.TAX_RETURN].policy_family == "efile_authorization"
    check_contract(api.TAX_RETURN, "form_8879_pe", "efile_authorization")
    check_contract("notice_response", "notice_response", "general")  # not contracted
    with pytest.raises(SourceContractBroken):
        check_contract(api.TAX_RETURN, "form_8879", "consent")  # an 8879 under the consent floor
    with pytest.raises(SourceContractBroken):
        check_contract(api.CONSENT_SET, "form_8879", "consent")


def test_a_contracted_source_that_cannot_draft_is_refused_at_registration() -> None:
    async def nothing(_ctx: object, _id: object) -> list[object]:
        return []

    with pytest.raises(RuntimeError, match="must provide a draft"):
        register_envelope_source(
            EnvelopeSource(
                kind=api.TAX_RETURN,
                documents=nothing,
                signers=nothing,
                retention_record_type="signature_evidence",
            )
        )
    assert api.TAX_RETURN not in api.registered_sources()


@pytest.mark.parametrize("kind", ["human", "agent", "support"])
async def test_only_the_system_supersedes(kind: ActorKind) -> None:
    tenant = TenantContext(uuid4(), kind, "someone")
    with pytest.raises(api.SystemOnly):
        await api.supersede_for_amount_change(tenant, uuid4(), "binding")


@pytest.mark.parametrize(
    "event",
    [api.EnvelopeSignerSigned, api.EnvelopeSignerVerificationFailed, api.EnvelopeSuperseded],
)
def test_every_v11_event_field_is_classified(event: type[DomainEvent]) -> None:
    assert unclassified_fields(event) == []
    assert event.event_type.startswith("envelope.")
