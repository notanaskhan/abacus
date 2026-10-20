# Every product module, once, sorted (P-39; F-03-T07): the quality gate, the API and the worker
# collect each module's registry.py and api.py from this tuple. A static check keeps it in step
# with the packages on disk.
MODULES: tuple[str, ...] = (
    "agents",
    "audit_trail",
    "communications",
    "connections",
    "engagements",
    "evidence",
    "fieldwork",
    "identity",
    "ledger",
    "notifications",
    "organisations",
    "platform",
    "requests",
    "sampling",
)
