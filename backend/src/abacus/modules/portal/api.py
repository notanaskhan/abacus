"""Public interface of the portal module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). The C5 v1.1 portal-half stub (P-08-T01) adds the home and
preferences routes; branding, the home read model and preferences land with P-08-T05 and T13.
The branding and host writers are for provisioning and the scenario loader (P-08-T14), inside the
caller's unit of work.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.portal.branding import (
    BrandingSlots,
    activate_portal_host,
    add_portal_host,
    register_branding_settings,
    set_branding,
)
from abacus.modules.portal.contract import router

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# G-01-T04 (AC1.9): the display name and the footer are the portal's; settings write them here.
register_branding_settings()

__all__ = [
    "ROUTERS",
    "BrandingSlots",
    "activate_portal_host",
    "add_portal_host",
    "set_branding",
]
