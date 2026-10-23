"""The Reminder template the follow-up tests import (P-06-T14). Test data, imported through the
platform import path as staff would: the product holds no template text (AGENTS 16). One
content for every test, so importing it again writes nothing."""

from __future__ import annotations

from typing import Final

from abacus.modules.communications.api import REMINDER_TEMPLATE
from abacus.modules.communications.templates import import_platform_version

SUBJECT: Final = "{{firm_name}} is still waiting on {{engagement_display_name}}"
BODY: Final = (
    "Hi {{recipient_first_name}},\n\n{{firm_name}} is still waiting for the following:\n\n"
    "{{request_list}}\n\nOpen your list: {{app_link}}\n"
)
VARIABLES: Final = [
    "app_link",
    "engagement_display_name",
    "firm_name",
    "recipient_first_name",
    "request_list",
]


async def import_reminder_template() -> None:
    await import_platform_version(
        "staff-p06t14", REMINDER_TEMPLATE, "en-US", SUBJECT, BODY, VARIABLES
    )
