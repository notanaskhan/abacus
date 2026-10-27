"""GENERATED from docs/architecture/write-capabilities.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.write_capabilities
"""

from typing import Final

VERSION: Final = 1
# The read connectors and the only hosts each may reach (ADR-040).
READ_CONNECTORS: Final[tuple[dict[str, object], ...]] = ()
# Reserved writes: none is enabled (ADR-150); every execute_write is refused.
WRITES: Final[tuple[dict[str, object], ...]] = (
    {
        "adapter_key": "docusign",
        "decision": "ADR-149",
        "enabled": False,
        "key": "esignature_envelope_send",
        "owner_epic": "N-02",
        "shape": "W7",
    },
    {
        "adapter_key": "quickbooks_online",
        "decision": "P-16",
        "enabled": False,
        "key": "ledger_post_journal_entries",
        "owner_epic": "C-02",
        "shape": "W1",
    },
    {
        "adapter_key": "cch_file_bridge",
        "decision": "P-18",
        "enabled": False,
        "key": "tax_engine_file_bridge",
        "owner_epic": "T-01",
        "shape": "W2",
    },
)
# Q-01's DNS Firewall allowlist: every declared egress host.
EGRESS_HOSTS: Final[frozenset[str]] = frozenset()
