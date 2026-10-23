"""P-01-T12: C16 v1 is recorded frozen (`docs/contracts/notifications.md` §10). The snapshot
holds the v2 feed, the per-kind preferences and the email half's template import; today's
schemas break none of it, and preferences carry no Restricted field."""

from __future__ import annotations

import json
from pathlib import Path

from abacus_tools import contracts

SNAPSHOT = Path(__file__).resolve().parent / "v1.json"


def test_c16_is_frozen_at_v1_and_today_breaks_nothing() -> None:
    assert [p.stem for p in contracts.snapshots()["c16_notifications"]] == ["v1"]
    frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert contracts.breaking(frozen, contracts.current("c16_notifications")) == []


def test_c16_v1_holds_the_preferences_and_template_import_models() -> None:
    frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert {
        "NotificationFeedOut",
        "NotificationPreferencesOut",
        "NotificationPreferencesIn",
        "EmailTemplateImportIn",
    } <= set(frozen)
    preference = frozen["NotificationPreferenceOut"]["properties"]
    assert set(preference) == {"kind", "in_app", "email"}
    assert {p.get("cls") for p in preference.values()} == {"internal"}
