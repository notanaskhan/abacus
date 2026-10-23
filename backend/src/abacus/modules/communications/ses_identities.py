"""Per-firm SES sender identities (Q-01-T47; platform-ops contract section 3.8; ADR-142). For
R-01's ADM-10 "Sender domain". PROTECTED.

`SesIdentityPort` creates a domain identity with Easy DKIM and a custom MAIL FROM domain, reads
its state and deletes it. The SES adapter calls SES v2 in the configured region only (a US
region; settings refuse any other) through the client `kernel.storage` makes (STORE-001); local
runs and tests use `InMemorySesIdentities`. The port returns machine states (`pending`,
`verified`, `failed`); the words a person reads belong to ADM-10 and the status registry (R-01).
Which firm owns a domain is R-01's record, not SES's: no tag or name here carries a tenant.

boto3 is synchronous: callers run these methods in `asyncio.to_thread`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, Protocol

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.storage import AwsError, error_code, sesv2_client

if TYPE_CHECKING:
    from types_boto3_sesv2 import SESV2Client
    from types_boto3_sesv2.type_defs import DkimSigningAttributesTypeDef

State = Literal["pending", "verified", "failed"]
RecordType = Literal["CNAME", "MX", "TXT"]
_LABEL: Final = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN: Final = re.compile(rf"(?:{_LABEL}\.)+[a-z]{{2,63}}")
_SUBDOMAIN: Final = re.compile(_LABEL)
_SPF: Final = "v=spf1 include:amazonses.com ~all"
_DKIM_RSA: Final = "RSA_2048_BIT"  # the Easy DKIM signing length (SES-managed keys)
# SES states -> the port's. A temporary failure or a check not yet started is still pending.
_STATES: Final[Mapping[str, State]] = {
    "SUCCESS": "verified",
    "FAILED": "failed",
    "PENDING": "pending",
    "TEMPORARY_FAILURE": "pending",
    "NOT_STARTED": "pending",
}


class SesIdentityInvalid(ValueError):
    """The domain or MAIL FROM subdomain is not a plain lower-case host name."""


class SesIdentityNotFound(LookupError):
    """SES has no identity for the domain."""


class SesIdentityUnavailable(Exception):
    """SES refused or could not be reached; carries the error code only, never the domain."""


@dataclass(frozen=True)
class DnsRecord:
    type: RecordType
    name: str
    value: str


@dataclass(frozen=True)
class IdentitySetup:
    domain: str
    dns_records: tuple[DnsRecord, ...]


@dataclass(frozen=True)
class IdentityStatus:
    domain: str
    verification: State
    dkim: State
    mail_from: State


class SesIdentityPort(Protocol):
    def create_identity(self, *, domain: str, mail_from_subdomain: str) -> IdentitySetup: ...

    def identity_status(self, *, domain: str) -> IdentityStatus: ...

    def delete_identity(self, *, domain: str) -> None: ...


def _domain(domain: str) -> str:
    if len(domain) > 253 or not _DOMAIN.fullmatch(domain):
        raise SesIdentityInvalid("domain")
    return domain


def _mail_from(domain: str, subdomain: str) -> str:
    if not _SUBDOMAIN.fullmatch(subdomain):
        raise SesIdentityInvalid("mail_from_subdomain")
    return f"{subdomain}.{domain}"


def _records(domain: str, tokens: tuple[str, ...], mail_from: str, region: str) -> IdentitySetup:
    """Easy DKIM's three CNAMEs, then the custom MAIL FROM domain's MX and SPF records."""
    dkim = tuple(
        DnsRecord("CNAME", f"{t}._domainkey.{domain}", f"{t}.dkim.amazonses.com") for t in tokens
    )
    return IdentitySetup(
        domain,
        (
            *dkim,
            DnsRecord("MX", mail_from, f"10 feedback-smtp.{region}.amazonses.com"),
            DnsRecord("TXT", mail_from, _SPF),
        ),
    )


class SesIdentities:
    """The SES v2 adapter. `create_identity` is idempotent for the same domain."""

    def __init__(
        self, client: SESV2Client, *, region: str, configuration_set: str | None = None
    ) -> None:
        self._client = client
        self._region = region
        self._configuration_set = configuration_set

    def create_identity(self, *, domain: str, mail_from_subdomain: str) -> IdentitySetup:
        domain = _domain(domain)
        mail_from = _mail_from(domain, mail_from_subdomain)
        try:
            try:
                # Easy DKIM (SES-managed keys), sending through the environment's configuration
                # set so delivery events reach the drain (Q-01-T46).
                dkim: DkimSigningAttributesTypeDef = {"NextSigningKeyLength": _DKIM_RSA}
                if self._configuration_set is None:
                    created = self._client.create_email_identity(
                        EmailIdentity=domain, DkimSigningAttributes=dkim
                    )
                else:
                    created = self._client.create_email_identity(
                        EmailIdentity=domain,
                        DkimSigningAttributes=dkim,
                        ConfigurationSetName=self._configuration_set,
                    )
                tokens = tuple(created.get("DkimAttributes", {}).get("Tokens", []))
            except AwsError as exc:
                if error_code(exc) != "AlreadyExistsException":
                    raise
                found = self._client.get_email_identity(EmailIdentity=domain)
                tokens = tuple(found.get("DkimAttributes", {}).get("Tokens", []))
            self._client.put_email_identity_mail_from_attributes(
                EmailIdentity=domain,
                MailFromDomain=mail_from,
                BehaviorOnMxFailure="USE_DEFAULT_VALUE",
            )
        except AwsError as exc:
            raise SesIdentityUnavailable(error_code(exc) or "unreachable") from None
        return _records(domain, tokens, mail_from, self._region)

    def identity_status(self, *, domain: str) -> IdentityStatus:
        domain = _domain(domain)
        try:
            found = self._client.get_email_identity(EmailIdentity=domain)
        except AwsError as exc:
            if error_code(exc) == "NotFoundException":
                raise SesIdentityNotFound("domain") from None
            raise SesIdentityUnavailable(error_code(exc) or "unreachable") from None
        if "VerificationStatus" in found:
            verification = _STATES.get(found["VerificationStatus"], "pending")
        else:
            verification = "verified" if found.get("VerifiedForSendingStatus") else "pending"
        dkim = _STATES.get(str(found.get("DkimAttributes", {}).get("Status", "")), "pending")
        mail_from_status = found.get("MailFromAttributes", {}).get("MailFromDomainStatus")
        mail_from = _STATES.get(str(mail_from_status), "pending")
        return IdentityStatus(domain, verification, dkim, mail_from)

    def delete_identity(self, *, domain: str) -> None:
        """Deleting an identity SES doesn't have is not an error."""
        domain = _domain(domain)
        try:
            self._client.delete_email_identity(EmailIdentity=domain)
        except AwsError as exc:
            if error_code(exc) != "NotFoundException":
                raise SesIdentityUnavailable(error_code(exc) or "unreachable") from None


@dataclass
class _Held:
    tokens: tuple[str, ...]
    mail_from: str
    verification: State = "pending"
    dkim: State = "pending"
    mail_from_state: State = "pending"


class InMemorySesIdentities:
    """Local runs and tests: the same rules, no SES. `set_states` stands in for DNS checks."""

    def __init__(self, *, region: str = "us-east-2") -> None:
        self._region = region
        self._held: dict[str, _Held] = {}

    def create_identity(self, *, domain: str, mail_from_subdomain: str) -> IdentitySetup:
        domain = _domain(domain)
        mail_from = _mail_from(domain, mail_from_subdomain)
        held = self._held.get(domain)
        if held is None:
            digest = hashlib.sha256(domain.encode()).hexdigest()
            tokens = tuple(digest[i : i + 32] for i in (0, 16, 32))
            held = self._held[domain] = _Held(tokens, mail_from)
        else:
            held.mail_from = mail_from
        return _records(domain, held.tokens, mail_from, self._region)

    def identity_status(self, *, domain: str) -> IdentityStatus:
        held = self._held.get(_domain(domain))
        if held is None:
            raise SesIdentityNotFound("domain")
        return IdentityStatus(domain, held.verification, held.dkim, held.mail_from_state)

    def delete_identity(self, *, domain: str) -> None:
        self._held.pop(_domain(domain), None)

    def set_states(
        self, domain: str, *, verification: State, dkim: State, mail_from: State
    ) -> None:
        held = self._held[_domain(domain)]
        held.verification, held.dkim, held.mail_from_state = verification, dkim, mail_from


_identities: SesIdentityPort | None = None


def configure_ses_identities(port: SesIdentityPort | None) -> None:
    global _identities
    _identities = port


def ses_identities() -> SesIdentityPort:
    """SES where the mail settings are set, the in-memory port on local and test runs."""
    global _identities
    if _identities is None:
        s = settings()
        if s.ses_configuration_set is not None:
            _identities = SesIdentities(
                sesv2_client(region=s.ses_region),
                region=s.ses_region,
                configuration_set=s.ses_configuration_set,
            )
        elif s.environment in SYNTHETIC_ENVIRONMENTS:
            _identities = InMemorySesIdentities(region=s.ses_region)
        else:
            raise RuntimeError("no SES identity port configured (set the SES settings)")
    return _identities
