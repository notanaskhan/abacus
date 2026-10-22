"""Display labels for roles (F-03-T30; chapter 03 §4.2; glossary). `/v1/me/capabilities` returns
them so screens never print a role code."""

from __future__ import annotations

from typing import Final

ROLE_LABELS: Final[dict[str, str]] = {
    "firm_admin": "Firm Admin",
    "practice_leader": "Practice Leader",
    "quality_partner": "Quality Partner",
    "security_admin": "IT / Security",
    "firm_partner": "Partner",
    "engagement_partner": "Engagement Partner",
    "manager": "Manager",
    "senior": "Senior",
    "staff": "Staff",
    "reviewer": "Reviewer",
    "eqr_reviewer": "EQR Reviewer",
    "specialist": "Specialist",
    "client_service": "Client Service",
    "client_admin": "Owner",
    "client_contributor": "Contributor",
}
