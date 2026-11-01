"""N-02-T37's live read (TASK-2540; ENG-04 d, e; DEC-1581) against Postgres: once Send drafted
the letter's envelope, the composer reads when it went out and the day each side signed from
C7's own rows, in the firm's time zone; nothing before C7 records it."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from abacus.modules.engagements import letter_flow, letters
from abacus.modules.signatures import api as _signatures  # registers the source and its ports

from .agent_tests.support import Seeder
from .test_n02t32_letter_composer import engines, fresh_registry, seed
from .test_n02t33_letter_approval import (
    _approvable,  # pyright: ignore[reportPrivateUsage] -- N-02-T33's harness
)

__all__ = ["_signatures", "engines", "fresh_registry", "seed"]

pytestmark = pytest.mark.usefixtures("engines", "fresh_registry")


async def test_the_composer_reads_sent_and_each_sides_signed_day_from_the_envelope(
    seed: Seeder,
) -> None:
    ctx, engagement, _template = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    await letter_flow.approve_letter(ctx, engagement, '"1"')
    envelope = await letter_flow.send_letter(ctx, engagement)
    drafted = await letters.composed_letter(ctx, engagement)
    assert drafted.sent_at is None
    assert all(s.signed_on is None and not s.signed for s in drafted.signers)

    sent = datetime(2026, 3, 1, 15, 0, tzinfo=UTC)
    await seed.as_actor(  # the database binds a send to the person who sends
        ctx.tenant_id,
        ("human", str(ctx.user_id)),
        "UPDATE envelopes SET status = 'sent', provider = 'docuseal', "
        "provider_envelope_id = 'ds-1', sent_at = $2, sent_by = $3 WHERE id = $1",
        envelope,
        sent,
        ctx.user_id,
    )
    await seed.run(
        "UPDATE envelope_signers SET status = 'signed', signed_at = $2, "
        "signature_method = 'provider_adopted' "
        "WHERE envelope_id = $1 AND role = 'signer'",
        envelope,
        datetime(2026, 3, 2, 18, 0, tzinfo=UTC),
    )
    composed = await letters.composed_letter(ctx, engagement)
    assert composed.sent_at == sent
    by_role = {s.role: s for s in composed.signers}
    assert (by_role["client"].signed, by_role["client"].signed_on) == (True, date(2026, 3, 2))
    assert (by_role["firm"].signed, by_role["firm"].signed_on) == (False, None)
