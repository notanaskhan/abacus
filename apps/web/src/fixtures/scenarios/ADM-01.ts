// ADM-01 Settings home & firm profile: one fixture scenario per artboard (G-01-T06; G-01 §5.3).
// a, b, c and f are Grace Holloway at E0 (b, c and f are reached by editing a: dirty, the empty
// display name, the save); d is Daniel Reyes (partner, read-only); e is Felix Andersen (security
// admin: read-only, no Plan & seats, Security first in At a glance). Mon Sep 14, 2026, 9:24 AM CT.

import { defineScenarios } from "../../app-core/fixture-mode";
import { firmSettingsHandlers } from "../handlers/firm-settings";
import { seedScenario } from "../scenario";
import { DEMO_INSTANT } from "../seed/clock";
import type { SettingsViewer } from "../seed/firm-people";

const E0 = seedScenario();

function at(state: string, persona: string, viewer: SettingsViewer) {
  return {
    state,
    persona,
    clock: DEMO_INSTANT,
    handlers: { ...firmSettingsHandlers(viewer), ...E0.handlers, ...firmSettingsHandlers(viewer) },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "grace-holloway", "admin"),
  b: at("b", "grace-holloway", "admin"),
  c: at("c", "grace-holloway", "admin"),
  d: at("d", "daniel-reyes", "partner"),
  e: at("e", "felix-andersen", "security"),
  f: at("f", "grace-holloway", "admin"),
});

export type Adm01State = keyof typeof scenarios;
