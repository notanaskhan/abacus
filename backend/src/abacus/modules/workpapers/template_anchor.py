"""The `template_version` comment anchor (K-03-T17; TASK-9010; KNW-06; DEC-6016).

A KNW-06 thread sits on a template version. Methodology owns the version and imports no
collaboration host, so this provider lives here (workpapers already imports both): the label is
methodology's (`template_version_label`), the resource is the firm's (template comments are firm
work, read under `template.read` like the template itself).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.modules.collaboration.api import AnchorFacts, Locator
from abacus.modules.identity.api import AuthContext

KIND: Final = "template_version"


class TemplateVersionAnchors:
    locator_keys: frozenset[str] = frozenset({"component"})

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        from abacus.modules.methodology.api import template_version_label

        del locator
        label = await template_version_label(ctx, anchor_id)
        if label is None:
            return None
        return AnchorFacts(tenant_id=ctx.tenant_id, engagement_id=None, client_id=None,
                           label=f"Template {label}"[:200])  # fmt: skip


ANCHORS: Final = TemplateVersionAnchors()

__all__ = ["ANCHORS", "KIND", "TemplateVersionAnchors"]
