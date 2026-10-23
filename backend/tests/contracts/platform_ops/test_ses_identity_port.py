"""Q-01-T47: the SES sender-identity port (platform-ops contract section 3.8), against a real
botocore SES v2 client under `botocore.stub.Stubber` (every request is checked against the service
model; nothing leaves the process) and against the in-memory port local runs use.

Contract rules: Easy DKIM and a custom MAIL FROM domain are always requested; `create_identity` is
idempotent for the same domain; the port returns machine states (`pending`, `verified`, `failed`).
Synthetic domains only (`.test`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from botocore.stub import Stubber

from abacus.kernel.config import settings
from abacus.modules.communications.api import (
    DnsRecord,
    IdentityStatus,
    InMemorySesIdentities,
    SesIdentities,
    SesIdentityInvalid,
    SesIdentityNotFound,
    SesIdentityPort,
    SesIdentityUnavailable,
    configure_ses_identities,
    ses_identities,
)

if TYPE_CHECKING:
    from types_boto3_sesv2 import SESV2Client

REGION = "us-east-2"
DKIM_RSA = "RSA_2048_BIT"
DOMAIN = "brightwater-hale.example.test"
TOKENS = ("a" * 32, "b" * 32, "c" * 32)
Json = dict[str, Any]  # JSON-shaped SES responses, untyped by botocore's Stubber
STUBBED = "testing"  # a stubbed client never opens a connection or signs a real request


def _client() -> SESV2Client:
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- only some stubs installed
        "sesv2",
        region_name=REGION,
        aws_access_key_id=STUBBED,
        aws_secret_access_key=STUBBED,
    )


@pytest.fixture
def stubbed() -> Iterator[tuple[SesIdentities, Stubber]]:
    client = _client()
    with Stubber(client) as stub:
        yield SesIdentities(client, region=REGION, configuration_set="abacus-staging-fake"), stub
        stub.assert_no_pending_responses()


def _created(tokens: tuple[str, ...] = TOKENS) -> Json:
    return {
        "IdentityType": "DOMAIN",
        "VerifiedForSendingStatus": False,
        "DkimAttributes": {"SigningEnabled": True, "Status": "PENDING", "Tokens": list(tokens)},
    }


def _identity(*, verification: str, dkim: str, mail_from: str | None) -> Json:
    found: Json = {
        "IdentityType": "DOMAIN",
        "VerifiedForSendingStatus": verification == "SUCCESS",
        "VerificationStatus": verification,
        "DkimAttributes": {"SigningEnabled": True, "Status": dkim, "Tokens": list(TOKENS)},
    }
    if mail_from is not None:
        found["MailFromAttributes"] = {
            "MailFromDomain": f"mail.{DOMAIN}",
            "MailFromDomainStatus": mail_from,
            "BehaviorOnMxFailure": "USE_DEFAULT_VALUE",
        }
    return found


MAIL_FROM_REQUEST = {
    "EmailIdentity": DOMAIN,
    "MailFromDomain": f"mail.{DOMAIN}",
    "BehaviorOnMxFailure": "USE_DEFAULT_VALUE",
}
EXPECTED_RECORDS = (
    *(DnsRecord("CNAME", f"{t}._domainkey.{DOMAIN}", f"{t}.dkim.amazonses.com") for t in TOKENS),
    DnsRecord("MX", f"mail.{DOMAIN}", f"10 feedback-smtp.{REGION}.amazonses.com"),
    DnsRecord("TXT", f"mail.{DOMAIN}", "v=spf1 include:amazonses.com ~all"),
)


def test_create_asks_for_easy_dkim_and_a_custom_mail_from_domain(
    stubbed: tuple[SesIdentities, Stubber],
) -> None:
    port, stub = stubbed
    stub.add_response(
        "create_email_identity",
        _created(),
        {
            "EmailIdentity": DOMAIN,
            "DkimSigningAttributes": {"NextSigningKeyLength": DKIM_RSA},
            "ConfigurationSetName": "abacus-staging-fake",
        },
    )
    stub.add_response("put_email_identity_mail_from_attributes", {}, MAIL_FROM_REQUEST)
    setup = port.create_identity(domain=DOMAIN, mail_from_subdomain="mail")
    assert setup.domain == DOMAIN
    assert setup.dns_records == EXPECTED_RECORDS


def test_create_is_idempotent_for_the_same_domain(
    stubbed: tuple[SesIdentities, Stubber],
) -> None:
    port, stub = stubbed
    stub.add_client_error(
        "create_email_identity", service_error_code="AlreadyExistsException", http_status_code=400
    )
    stub.add_response(
        "get_email_identity",
        _identity(verification="PENDING", dkim="PENDING", mail_from="PENDING"),
        {"EmailIdentity": DOMAIN},
    )
    stub.add_response("put_email_identity_mail_from_attributes", {}, MAIL_FROM_REQUEST)
    setup = port.create_identity(domain=DOMAIN, mail_from_subdomain="mail")
    assert setup.dns_records == EXPECTED_RECORDS


@pytest.mark.parametrize(
    ("ses", "expected"),
    [
        (("PENDING", "PENDING", "PENDING"), ("pending", "pending", "pending")),
        (("SUCCESS", "SUCCESS", "SUCCESS"), ("verified", "verified", "verified")),
        (("FAILED", "FAILED", "FAILED"), ("failed", "failed", "failed")),
        (("TEMPORARY_FAILURE", "NOT_STARTED", "TEMPORARY_FAILURE"), ("pending",) * 3),
        (("SUCCESS", "SUCCESS", None), ("verified", "verified", "pending")),
    ],
)
def test_status_returns_machine_states(
    stubbed: tuple[SesIdentities, Stubber],
    ses: tuple[str, str, str | None],
    expected: tuple[str, str, str],
) -> None:
    port, stub = stubbed
    verification, dkim, mail_from = ses
    stub.add_response(
        "get_email_identity",
        _identity(verification=verification, dkim=dkim, mail_from=mail_from),
        {"EmailIdentity": DOMAIN},
    )
    assert port.identity_status(domain=DOMAIN) == IdentityStatus(DOMAIN, *expected)  # pyright: ignore[reportArgumentType] -- literals from the table


def test_status_of_an_unknown_domain_is_not_found(stubbed: tuple[SesIdentities, Stubber]) -> None:
    port, stub = stubbed
    stub.add_client_error(
        "get_email_identity", service_error_code="NotFoundException", http_status_code=404
    )
    with pytest.raises(SesIdentityNotFound):
        port.identity_status(domain=DOMAIN)


def test_delete_is_quiet_for_a_missing_identity(stubbed: tuple[SesIdentities, Stubber]) -> None:
    port, stub = stubbed
    stub.add_response("delete_email_identity", {}, {"EmailIdentity": DOMAIN})
    stub.add_client_error(
        "delete_email_identity", service_error_code="NotFoundException", http_status_code=404
    )
    port.delete_identity(domain=DOMAIN)
    port.delete_identity(domain=DOMAIN)


@pytest.mark.parametrize("method", ["create", "status", "delete"])
def test_an_ses_error_fails_closed_with_the_code_only(
    stubbed: tuple[SesIdentities, Stubber], method: str
) -> None:
    port, stub = stubbed
    operation = {
        "create": "create_email_identity",
        "status": "get_email_identity",
        "delete": "delete_email_identity",
    }[method]
    stub.add_client_error(operation, service_error_code="TooManyRequestsException")
    with pytest.raises(SesIdentityUnavailable) as raised:
        if method == "create":
            port.create_identity(domain=DOMAIN, mail_from_subdomain="mail")
        elif method == "status":
            port.identity_status(domain=DOMAIN)
        else:
            port.delete_identity(domain=DOMAIN)
    assert str(raised.value) == "TooManyRequestsException"
    assert DOMAIN not in str(raised.value)


@pytest.mark.parametrize(
    ("domain", "subdomain"),
    [
        ("Brightwater-Hale.example.test", "mail"),  # not lower case
        ("brightwater hale.test", "mail"),
        ("localhost", "mail"),  # not a domain
        ("brightwater-hale.example.test", "mail.extra"),  # one label only
        ("brightwater-hale.example.test", ""),
    ],
)
def test_a_malformed_domain_never_reaches_ses(domain: str, subdomain: str) -> None:
    client = _client()
    with Stubber(client):  # no responses queued: any call would fail the test
        port = SesIdentities(client, region=REGION)
        with pytest.raises(SesIdentityInvalid):
            port.create_identity(domain=domain, mail_from_subdomain=subdomain)


def test_the_in_memory_port_keeps_the_same_rules() -> None:
    port: SesIdentityPort = InMemorySesIdentities(region=REGION)
    first = port.create_identity(domain=DOMAIN, mail_from_subdomain="mail")
    again = port.create_identity(domain=DOMAIN, mail_from_subdomain="mail")
    assert first == again
    assert [r.type for r in first.dns_records] == ["CNAME", "CNAME", "CNAME", "MX", "TXT"]
    assert port.identity_status(domain=DOMAIN) == IdentityStatus(
        DOMAIN, "pending", "pending", "pending"
    )
    assert isinstance(port, InMemorySesIdentities)
    port.set_states(DOMAIN, verification="verified", dkim="verified", mail_from="verified")
    assert port.identity_status(domain=DOMAIN) == IdentityStatus(
        DOMAIN, "verified", "verified", "verified"
    )
    port.delete_identity(domain=DOMAIN)
    port.delete_identity(domain=DOMAIN)
    with pytest.raises(SesIdentityNotFound):
        port.identity_status(domain=DOMAIN)
    with pytest.raises(SesIdentityInvalid):
        port.create_identity(domain="localhost", mail_from_subdomain="mail")


def test_local_runs_get_the_in_memory_port() -> None:
    configure_ses_identities(None)
    settings.cache_clear()
    try:
        assert settings().environment in ("local", "test")
        assert isinstance(ses_identities(), InMemorySesIdentities)
    finally:
        configure_ses_identities(None)
