"""The QuickBooks Online ledger adapter (A-02-T26; DEC-70, DEC-709; C20 v1; AC-49).

Metadata only, read-only by construction: its key, category, connection provider, read scopes
and hosts, which must match the write-capability registry's read connector entry. The connection
itself runs through `connections` (the connector contract). Registered only in an environment
that holds the QuickBooks app registration (`settings.qbo_client_id` and secret), so a catalogue
row reads Available only where a client could really connect (catalogue honesty, fail closed).
"""

from __future__ import annotations

from typing import Final, Literal

from abacus.modules.integrations.adapters import register_adapter, registered_adapter

KEY: Final = "quickbooks_online"
_HOSTS: Final = (
    "appcenter.intuit.com",
    "oauth.platform.intuit.com",
    "developer.api.intuit.com",
    "sandbox-quickbooks.api.intuit.com",
    "quickbooks.api.intuit.com",
)


class QuickBooksOnlineAdapter:
    read_methods: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return KEY

    @property
    def category(self) -> Literal["ledger"]:
        return "ledger"

    @property
    def connector_provider(self) -> str | None:
        return KEY

    def read_scopes(self) -> tuple[str, ...]:
        return ("ledger.trial_balance", "ledger.company_info")

    def egress_hosts(self) -> tuple[str, ...]:
        return _HOSTS


def register_if_configured(configured: bool) -> None:
    """At import, from `integrations.api`: once, and only with the app registration present."""
    if configured and registered_adapter(KEY) is None:
        register_adapter(QuickBooksOnlineAdapter())
