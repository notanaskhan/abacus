"""Public interface of the identity module; other modules import only this (ADR-008)."""

from abacus.modules.identity.authz import (
    MFA_RECENT,
    Forbidden,
    Resource,
    UnknownAction,
    authorise,
    visible,
)
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import EngagementRole
from abacus.modules.identity.routes import router
from abacus.modules.identity.routing import (
    ACTION_KEY,
    SELF,
    AbacusRoute,
    AbacusRouter,
    current_context,
    current_signed_in,
    declared_action,
)
from abacus.modules.identity.service import TeamMember, add_engagement_member, engagement_team
from abacus.modules.identity.tokens import (
    InvalidToken,
    JwtVerifier,
    TokenVerifier,
    VerifiedIdentity,
    configure_verifier,
    reset_verifier,
    token_verifier,
)

__all__ = [
    "ACTION_KEY",
    "MFA_RECENT",
    "SELF",
    "AbacusRoute",
    "AbacusRouter",
    "AuthContext",
    "EngagementRole",
    "Forbidden",
    "InvalidToken",
    "JwtVerifier",
    "Resource",
    "TeamMember",
    "TokenVerifier",
    "UnknownAction",
    "VerifiedIdentity",
    "add_engagement_member",
    "authorise",
    "configure_verifier",
    "current_context",
    "current_signed_in",
    "declared_action",
    "engagement_team",
    "reset_verifier",
    "router",
    "token_verifier",
    "visible",
]
