"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import (
    register_draft_request_copy,
    register_open_requests,
    register_roll_forward_items,
)
from abacus.modules.identity.api import (
    AbacusRouter,
    register_contact_delegations,
    register_scope_resolver,
    register_scopes_resolver,
)
from abacus.modules.platform.api import register_audit_value_resolver
from abacus.modules.requests.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.requests.audit_values import request_item_values
from abacus.modules.requests.availability import register_available_datasets
from abacus.modules.requests.binder_index import register_binder_tag
from abacus.modules.requests.binders import (
    SUBSCRIPTIONS,
    DropBinder,
    drop_binder,
    drop_binder_open,
    register_binder_close_rule,
)
from abacus.modules.requests.classification import classify, document_kind
from abacus.modules.requests.closed_binders import (
    BinderClosed,
    refuse_closed_item,
    refuse_closed_item_in,
)
from abacus.modules.requests.comments import (
    check_return_comment,
    insert_return_comment,
    register_comment_scope_check,
)
from abacus.modules.requests.consent import third_party_consented
from abacus.modules.requests.contract import (
    RequestLatestUploadOut,
    RequestOwedByOut,
    binders_router,
    items_router,
    portal_router,
)
from abacus.modules.requests.events import (
    DueDatesChanged,
    RequestItemClassified,
    RequestItemCreated,
    RequestItemDocumentKindChanged,
)
from abacus.modules.requests.follow_up_reads import (
    FollowUpCandidate,
    follow_up_candidates,
    live_files,
    selection_engagements,
)
from abacus.modules.requests.home_counts import register_home_counts
from abacus.modules.requests.lifecycle import (
    ConsentRequired,
    ItemPatch,
    contact_delegations,
    end_contact_delegations,
    record_contact_delegations,
    register_live_facts,
    request_item_scope,
    request_item_scopes,
    update_item,
)
from abacus.modules.requests.pbc_contract import pbc_portal_router
from abacus.modules.requests.portal_documents import (
    PortalBinder,
    PortalBinderRef,
    PortalCategory,
    PortalItem,
    PortalLink,
    portal_binder_ref,
    portal_binder_refs,
    portal_binder_view,
    portal_item_binder,
    portal_item_view,
    prior_year_link,
)
from abacus.modules.requests.portal_home import BinderProgress, ClientHome, client_home
from abacus.modules.requests.portal_room import (
    DelegateUpload,
    RoomItem,
    delegate_upload,
    room_items,
)
from abacus.modules.requests.repository import open_requests_by_engagement
from abacus.modules.requests.roll_forward import (
    copy_items,
    copy_items_as_draft,
    count_prior_items,
    proposed_items,
)
from abacus.modules.requests.routes import firm_router, methodology_router, router
from abacus.modules.requests.service import (
    FulfilledVersion,
    FulfilmentRef,
    ItemKind,
    ItemNotFulfillable,
    NewRequestItem,
    OverdueItem,
    RequestItemRef,
    RequestItemSummary,
    RequestItemView,
    ReviewHost,
    ReviewTarget,
    ScreeningSubject,
    VoidedRuleLink,
    add_request_item,
    apply_drafted_guidance,
    awaiting_review,
    awaiting_review_count,
    drop_items,
    drop_target,
    fulfil_by_rule,
    fulfil_by_upload,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    item_versions,
    items_of_version,
    latest_version_of,
    lock_rule_link,
    move_after_review,
    overdue_for,
    read_item,
    read_item_versions,
    reopen_after_undo,
    request_items_for,
    review_hosts,
    review_targets,
    screening_subject,
    upload_item_of,
    void_rule_link_in,
    withdraw_upload,
)
from abacus.modules.requests.source_documents import (
    SourceDocuments,
    UploadFacts,
    pbc_binders,
    pbc_counts,
    pbc_counts_of,
    register_upload_facts,
    source_documents,
)

# P-07-T25 (C5): CLI-04 records, ends and counts a contact's delegated requests through this.
register_contact_delegations(
    record_contact_delegations, end_contact_delegations, contact_delegations
)
# SPEC-025 (TASK-048 D1): last year's items for a roll-forward, and copying the confirmed ones.
register_roll_forward_items(proposed_items, copy_items)
# P-07-T55 (ENG-13 v2): the whole request list into next year's engagement, as Draft.
register_draft_request_copy(count_prior_items, copy_items_as_draft)

# P-06-T07: binders close when C1 says their work is finished (the subscriber is in binders.py).
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    methodology_router,
    binders_router,  # C5 v1 stub (P-06-T01)
    items_router,
    portal_router,
    pbc_portal_router,  # C5 portal-pbc (R-01-T08): undo an Ignore, undo Mark as Done
)

# P-07-T08: the clients index's open-request count.
register_open_requests(open_requests_by_engagement)
# P-06-T10: a delegate's `request_item` grant resolves to its request's engagement and client.
register_scope_resolver("request_item", request_item_scope)
# R-01-T13 (security review L2): many at once, for the third-party role's lookup.
register_scopes_resolver("request_item", request_item_scopes)
# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)
# G-02-T09 gap (DEC-459): ADM-07's values for requests.
register_audit_value_resolver("request_item", request_item_values)

# I-01-T08: this module's HOME-01 tile or pill (platform.register_home_count).
register_home_counts()

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "BinderClosed",
    "BinderProgress",
    "ClientHome",
    "ConsentRequired",
    "DelegateUpload",
    "DropBinder",
    "DueDatesChanged",
    "FollowUpCandidate",
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemKind",
    "ItemNotFulfillable",
    "ItemPatch",
    "NewRequestItem",
    "OverdueItem",
    "PortalBinder",
    "PortalBinderRef",
    "PortalCategory",
    "PortalItem",
    "PortalLink",
    "RequestItemClassified",
    "RequestItemCreated",
    "RequestItemDocumentKindChanged",
    "RequestItemRef",
    "RequestItemSummary",
    "RequestItemView",
    "RequestLatestUploadOut",
    "RequestOwedByOut",
    "ReviewHost",
    "ReviewTarget",
    "RoomItem",
    "ScreeningSubject",
    "SourceDocuments",
    "UploadFacts",
    "VoidedRuleLink",
    "add_request_item",
    "apply_drafted_guidance",
    "awaiting_review",
    "awaiting_review_count",
    "check_return_comment",
    "classify",
    "client_home",
    "delegate_upload",
    "document_kind",
    "drop_binder",
    "drop_binder_open",
    "drop_items",
    "drop_target",
    "firm_router",
    "follow_up_candidates",
    "fulfil_by_rule",
    "fulfil_by_upload",
    "fulfilled_items",
    "fulfilled_versions",
    "insert_return_comment",
    "item_ref",
    "item_versions",
    "items_of_version",
    "latest_version_of",
    "live_files",
    "lock_rule_link",
    "methodology_router",
    "move_after_review",
    "overdue_for",
    "pbc_binders",
    "pbc_counts",
    "pbc_counts_of",
    "portal_binder_ref",
    "portal_binder_refs",
    "portal_binder_view",
    "portal_item_binder",
    "portal_item_view",
    "prior_year_link",
    "read_item",
    "read_item_versions",
    "refuse_closed_item",
    "refuse_closed_item_in",
    "register_available_datasets",
    "register_binder_close_rule",
    "register_binder_tag",
    "register_comment_scope_check",
    "register_live_facts",
    "register_upload_facts",
    "reopen_after_undo",
    "request_items_for",
    "review_hosts",
    "review_targets",
    "room_items",
    "router",
    "screening_subject",
    "selection_engagements",
    "source_documents",
    "third_party_consented",
    "update_item",
    "upload_item_of",
    "void_rule_link_in",
    "withdraw_upload",
]
