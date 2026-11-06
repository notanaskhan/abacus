"""Public interface of the notices module; other modules import only this (ADR-008).

Pre-registered (F-03-T08; ADR-140). N-04-T02 (DEC-2051): the notices v1 contract stub
(`docs/contracts/notices.md`).
"""

from abacus.kernel.audit_owners import register_client_owners, register_engagement_owners
from abacus.modules.engagements.api import register_work_item_kind
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.notices.audit_targets import (
    CLIENT_KINDS,
    ENGAGEMENT_KINDS,
    intake_clients,
    notice_engagements,
)
from abacus.modules.notices.contract import router
from abacus.modules.notices.kind import NoticeKind

# DEC-2264: the trail places a notice on its engagement and an intake on its client.
register_engagement_owners(ENGAGEMENT_KINDS, notice_engagements)
register_client_owners(CLIENT_KINDS, intake_clients)

# F-03-T22: the `notice` work-item kind.
register_work_item_kind("notice", NoticeKind())

# N-04-T06: HOME-01's notices tile from the same visible rows NOT-01 tallies.
from abacus.modules.notices.home_counts import register_home_counts  # noqa: E402

register_home_counts()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

from abacus.modules.notices.analysis import register_position_kind  # noqa: E402

register_position_kind()  # N-04-T11 (DEC-2239): the `notice_position` card, reserved to the signer

from abacus.modules.notices import response as _response  # noqa: E402
from abacus.modules.review.api import (  # noqa: E402
    register_gate_kind,
    register_reviewable,
    register_reviewable_facts,
)

# N-04-T12 (DEC-2240): the response is a reviewable whose facts refuse sign-off with
# decision_pending, position_mismatch or explanation_required; the three gate kinds read it.
register_reviewable(_response.TARGET, _response.reviewables)
register_reviewable_facts(_response.TARGET, _response.facts)
register_gate_kind("notice_position_decision", _response.position_decided)
register_gate_kind("notice_response_signoff", _response.signoff_ready)
register_gate_kind("notice_response_send", _response.send_ready)

from abacus.modules.notices.intake_sources import register as _register_sources  # noqa: E402

_register_sources()  # N-04-T13 (DEC-2245): the answer effect and the two triage destinations

# N-04-T16 (DEC-2311): the response's C11 kind, C7 source, workflow and consumer.
from abacus.modules.notices import sending as _sending  # noqa: E402
from abacus.modules.notices.response_activities import ACTIVITIES as ACTIVITIES  # noqa: E402
from abacus.modules.notices.response_workflow import NoticeResponseWorkflow  # noqa: E402

_sending.register()
SUBSCRIPTIONS = _sending.SUBSCRIPTIONS
WORKFLOWS: dict[type, str] = {NoticeResponseWorkflow: "time_sensitive"}
