"""Public interface of the portal module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). The C5 v1.1 portal-half stub (P-08-T01) adds the home and
preferences routes; branding, the home read model and preferences land with P-08-T05 and T13.
The branding and host writers are for provisioning and the scenario loader (P-08-T14), inside the
caller's unit of work.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.portal.approval_emails import SUBSCRIPTIONS as _APPROVAL_EMAILS
from abacus.modules.portal.approvals_contract import approvals_router
from abacus.modules.portal.branding import (
    BrandingSlots,
    activate_portal_host,
    add_portal_host,
    register_branding_settings,
    set_branding,
)
from abacus.modules.portal.contract import router
from abacus.modules.portal.deliverables_contract import deliverables_router, governance_router
from abacus.modules.portal.documents_routes import documents_router
from abacus.modules.portal.intake_contract import intake_router
from abacus.modules.portal.notices import SUBSCRIPTIONS as _NOTICES
from abacus.modules.portal.pbc_contract import pbc_router
from abacus.modules.portal.rooms_routes import rooms_router
from abacus.modules.portal.settings_contract import settings_router

# The worker's subscriptions: third-party upload notices (R-01-T13) and the approval email
# (R-02-T14).
SUBSCRIPTIONS = {**_NOTICES, **_APPROVAL_EMAILS}

# The routers the API mounts, in order (P-39; F-03-T07). C5 portal-pbc: the documents reads
# (R-01-T07), the third-party room (R-01-T13), then the drop poll (R-01-T09) and the stubs
# still waiting for their tasks.
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    documents_router,
    rooms_router,
    pbc_router,
    deliverables_router,
    governance_router,
    approvals_router,
    settings_router,  # C16 v1.1 stub (R-01-T16): portal settings and preview
    intake_router,  # C5 v1.2 intake half stub (N-01-T02): "Upload something else"
)

# R-01-T13: the request owner hears of a third party's upload (`third_party.uploaded`).
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# G-01-T04 (AC1.9): the display name and the footer are the portal's; settings write them here.
register_branding_settings()

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "BrandingSlots",
    "activate_portal_host",
    "add_portal_host",
    "set_branding",
]

# P-10-T27 (DEC-3117): the portal topics of the invalidation stream.
from abacus.modules.portal.realtime_topics import register as _register_topics  # noqa: E402

_register_topics()

# R-02-T22: the portal's comment anchors (POR-08 questions, POR-09 page comments, POR-15 "Ask the
# auditor…"); the governance letter's client readers are its authors only (AC-33).
from abacus.modules.collaboration.api import register_anchor, register_client_policy  # noqa: E402
from abacus.modules.portal import thread_anchors as _anchors  # noqa: E402

register_anchor(_anchors.APPROVAL, _anchors.APPROVAL_ANCHORS)
register_anchor(_anchors.PAGE, _anchors.PAGE_ANCHORS)
register_anchor(_anchors.LETTER, _anchors.LETTER_ANCHORS)
register_client_policy(_anchors.LETTER, "author_only")
