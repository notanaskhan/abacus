"""The e-signature provider an envelope is sent through (N-02-T14; N-02 §3.5; ADR-149, ADR-342).

EnvelopeWorkflow's activities talk to one `EsignProvider`, configured at startup: the fake
(`abacus_tools.fakes.esign`, synthetic environments only) until the DocuSeal adapter lands
through W7 (N-02-T18: `provider_for` builds the firm's own adapter only when its kill switch,
W7 and a connected install allow). With none, a send is recorded as not sent and nothing
leaves. The webhook is a hint and the poll is the truth (ADR-041's pattern): state comes
only from `status`, never from a signal's payload. The provider sees identifiers, routing,
identity methods and document hashes; document bytes stay in our stores.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Final, Protocol
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.errors import ServiceUnavailable


class ProviderUnavailable(ServiceUnavailable):
    """No e-signature provider is configured here: nothing is sent."""

    code = "provider_unavailable"


# N-02-T47: a 429's wait, bounded by EnvelopeWorkflow's five-minute retry ceiling.
RATE_LIMIT_DEFAULT_SECONDS: Final = 30.0
RATE_LIMIT_MAX_SECONDS: Final = 300.0


class ProviderRateLimited(ServiceUnavailable):
    """The provider answered 429 (N-02-T47): the activity retries no sooner than `retry_after`
    seconds, never in a tight loop; nothing is half-recorded."""

    code = "provider_unavailable"

    def __init__(self, retry_after: float) -> None:
        super().__init__("rate_limited")
        self.retry_after = retry_after


def retry_after_seconds(header: str | None, now: datetime | None = None) -> float:
    """`Retry-After` as seconds (delta-seconds or an HTTP date), clamped to 1..300; absent or
    unreadable is 30."""
    if header is None or not header.strip():
        return RATE_LIMIT_DEFAULT_SECONDS
    value = header.strip()
    if value.isdigit():
        wait = float(value)
    else:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return RATE_LIMIT_DEFAULT_SECONDS
        if when.tzinfo is None:
            return RATE_LIMIT_DEFAULT_SECONDS
        wait = (when - (now or datetime.now(UTC))).total_seconds()
    return min(max(wait, 1.0), RATE_LIMIT_MAX_SECONDS)


@dataclass(frozen=True)
class SignerSpec:
    signer_id: str  # our `envelope_signers.id`, the provider's client user id
    order: int
    routing_group: int
    identity_method: str


@dataclass(frozen=True)
class EnvelopeSpec:
    envelope_id: str
    idempotency_key: str  # a retried create reads back by this, never creates twice
    document_sha256s: tuple[str, ...]
    signers: tuple[SignerSpec, ...]
    # N-02-T23 (DEC-1283): where the provider sends a signer once they finish, POR-06's return
    # route; it shows nothing until our poll confirms (the provider's redirect is never trusted).
    return_url: str | None = None


@dataclass(frozen=True)
class Created:
    provider_envelope_id: str
    recipients: dict[str, str]  # our signer id -> the provider's recipient id
    response_sha256: str


@dataclass(frozen=True)
class SignerState:
    signer_id: str
    status: str  # pending | viewed | signed | declined | verification_failed
    viewed_at: datetime | None
    signed_at: datetime | None
    kba_failures: int
    decline_reason: str | None


@dataclass(frozen=True)
class SignerEvidence:
    """The five IRS items for a remote signature (R-05; chapter 06 §6.3), as the provider
    recorded them: the signed image, the date and time, the IP address and login ID, the
    identity-verification result and the signature method; plus the device."""

    signer_id: str
    signed_image: bytes
    signed_at: datetime
    ip: str
    login_ref: str
    identity_result: str
    signature_method: str
    user_agent_family: str | None
    device_label: str | None


@dataclass(frozen=True)
class Completed:
    combined_document: bytes
    certificate: bytes
    signers: tuple[SignerEvidence, ...]


class EsignProvider(Protocol):
    name: str

    async def create_and_send(self, spec: EnvelopeSpec) -> Created: ...

    async def status(self, provider_envelope_id: str) -> tuple[SignerState, ...]: ...

    async def completed(self, provider_envelope_id: str) -> Completed: ...

    async def remind(self, provider_envelope_id: str, signer_id: str) -> None: ...

    async def void(self, provider_envelope_id: str, reason: str) -> None: ...

    async def signing_url(self, provider_envelope_id: str, signer_id: str) -> str:
        """N-02-T23: the signer's own provider view, a bearer link handed only to that signer's
        authenticated portal session and never stored."""
        ...


_provider: EsignProvider | None = None
FirmProvider = Callable[[UUID], Awaitable[EsignProvider]]
_firm_provider: FirmProvider | None = None


def configure_provider(provider: EsignProvider | None) -> None:
    """Startup and tests: the provider every envelope uses; None removes it."""
    global _provider
    _provider = provider


def provider() -> EsignProvider:
    if _provider is None:
        raise ProviderUnavailable
    return _provider


def register_firm_provider(resolver: FirmProvider | None) -> None:
    """N-02-T18: how a firm's own provider (DocuSeal, ADR-342) is built when no provider is
    configured for the whole process; None removes it."""
    global _firm_provider
    _firm_provider = resolver


async def provider_for(tenant_id: UUID) -> EsignProvider:
    """The provider for one firm's call: the process-wide one (the fake, synthetic environments
    and tests), else the firm's own when every switch is on, else `ProviderUnavailable`."""
    if _provider is not None:
        return _provider
    if _firm_provider is None:
        raise ProviderUnavailable
    return await _firm_provider(tenant_id)


def sign_return_url(envelope_id: UUID) -> str:
    """N-02-T23 (DEC-1283): POR-06's return route for an envelope, where the provider sends each
    signer once they finish (`/portal/sign/$envelopeId/return`, DF-12). It carries nothing: the
    page asks the server, which polls the provider before answering."""
    return f"{settings().app_base_url.rstrip('/')}/portal/sign/{envelope_id}/return"
