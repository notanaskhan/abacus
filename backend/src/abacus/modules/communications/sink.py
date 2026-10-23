"""The synthetic mail sink (F-04-T22; F-04.22; SPEC-307 AC-5; DEC-59, P-11).

No email from a synthetic firm (`firms.synthetic`) leaves the sink, on any transport. Before the
transport sees a synthetic firm's message, `send_email` routes its recipient here:
- an address already on the sink domain is kept (the scenario's people are seeded there);
- any other address, `@brightwaterhale.com` included (it may be a real domain), is rewritten to
  `<local-part>+<tenant-short>@<sink domain>`, so staging's SES receipt rule stores it in S3;
- with no sink domain (an environment that set none and isn't local, test or evaluation), or
  when the result is not on the sink, the send is refused.

A refusal is logged with the tenant and message IDs only: never the address, before or after.
Real firms' mail is untouched.
"""

from __future__ import annotations

import re
from typing import Final
from uuid import UUID

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings

# The Brightwater Hale scenario's sink (SPEC-307 AC-5): a reserved `.test` name, never delivered.
LOCAL_SINK_DOMAIN: Final = "sink.brightwaterhale.test"
_LOCAL_PART: Final = re.compile(r"[^A-Za-z0-9._-]")
_MAX_LOCAL: Final = 64


def sink_domain() -> str | None:
    """The sink this environment delivers synthetic mail to, or None (refuse every send)."""
    configured = settings().mail_sink_domain
    if configured is not None:
        return configured.lower()
    return LOCAL_SINK_DOMAIN if settings().environment in SYNTHETIC_ENVIRONMENTS else None


def _domain_of(address: str) -> str | None:
    local, at, domain = address.strip().rpartition("@")
    return domain.lower() if at and local and domain else None


def on_sink(address: str) -> bool:
    """Whether the address is delivered to the sink, exactly (no subdomain or look-alike)."""
    sink = sink_domain()
    return sink is not None and _domain_of(address) == sink


def sink_address(address: str, tenant_id: UUID) -> str | None:
    """Where a synthetic firm's message to `address` goes, or None: refuse it."""
    sink = sink_domain()
    if sink is None:
        return None
    if on_sink(address):
        return address.strip()
    if _domain_of(address) is None:
        return None  # not an address: no local part or no domain
    local = address.strip().rpartition("@")[0]
    tag = f"+{tenant_id.hex[:8]}"
    safe = _LOCAL_PART.sub("-", local)[: _MAX_LOCAL - len(tag)]
    routed = f"{safe}{tag}@{sink}"
    return routed if on_sink(routed) else None
