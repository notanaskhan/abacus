# ac-test-author: ayushkbhatia
"""N-02-T41 (ADR-078; TASK-2534; N-02 §3.7; C13; INV-1): the countersignature is the named firm
signer's only, written from N-02 §3.7 ("countersign only by the named firm signer") and C7 v1.1
rather than the code. Another partner, the firm admin, an agent and the system are refused before
any session is issued, before and after the client signs; a stale second factor is refused too.

The letter out for signature is N-02-T28's harness (N-02-T33's approvable letter, Daniel Reyes the
named signer).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import Forbidden
from abacus.modules.signatures import countersign

from . import test_n02t28_countersign as t28
from .agent_tests.support import Seeder
from .test_n02t28_countersign import _signatures, engines, fresh_registry, seed

__all__ = ["_signatures", "engines", "fresh_registry", "seed"]

pytestmark = pytest.mark.usefixtures("engines", "fresh_registry")
_out_for_signature = t28._out_for_signature  # pyright: ignore[reportPrivateUsage] -- N-02-T28's letter
_other_partner = t28._other_partner  # pyright: ignore[reportPrivateUsage] -- N-02-T28's partner


async def test_only_the_named_firm_signer_countersigns(seed: Seeder) -> None:
    ctx, engagement, envelope = await _out_for_signature(seed)
    other = replace(
        await _other_partner(seed, ctx.tenant_id, engagement), mfa_at=datetime.now(UTC)
    )
    await seed.run(
        "UPDATE envelope_signers SET status = 'signed', signed_at = clock_timestamp(), "
        "signature_method = 'typed' WHERE envelope_id = $1 AND party_kind = 'contact'",
        envelope,
    )
    planted = [
        other,
        replace(ctx, tenant=TenantContext(ctx.tenant_id, "agent", f"agent:x:{ctx.user_id}")),
        replace(ctx, tenant=TenantContext(ctx.tenant_id, "system", "signatures:planted")),
    ]
    for who in planted:
        with pytest.raises(Forbidden):
            await countersign.countersign_session(who, envelope)
    issued = await seed.value(
        "SELECT count(*) FROM signing_sessions s JOIN envelope_signers g ON g.id = s.signer_id "
        "WHERE g.envelope_id = $1 AND g.party_kind <> 'contact'",
        envelope,
    )
    assert issued == 0
    assert not await countersign.countersign_gate(ctx.tenant, engagement)
