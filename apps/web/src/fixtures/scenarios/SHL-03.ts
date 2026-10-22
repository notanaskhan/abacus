// SHL-03 firm switcher and profile menu: one fixture scenario per artboard (P-01-T07). Viewers and
// the clock come from the README's artboard table (Mon 14 Sep 2026, 9:24 AM CT for all six); the
// data from fixtures/seed/shell.ts. The tray, submenu and toast are local state (epic §5.1), so
// e and f differ from a only in the data they need: the sandbox membership and the office list.
//
// They live under fixtures/ (dev and test only, inside the L10 scan); src/screens/SHL-03/scenarios.ts
// re-exports them for the screen's tests and the gallery (P-01-T08).

import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { OFFICE_REFS, capabilitiesFor, meV3For } from "../seed/shell";
import type { PreferencesIn, PreferencesOut, SignedOutOut } from "@abacus/api-client";

const E0 = seedScenario();
const seed = getSeed();

/** `sandbox: false` holds back Grace's second membership: only frame e lists two firms. */
function shellHandlers(options: { sandbox?: boolean } = {}): Record<string, FixtureHandler> {
  let defaults: Record<string, string | null> = {};
  return {
    ...E0.handlers,
    "GET /v1/me": ({ persona }) => {
      const slug = persona ?? "";
      const me = meV3For(seed, slug, {
        ...(slug in defaults ? { defaultOfficeId: defaults[slug] ?? null } : {}),
        ...(options.sandbox === undefined ? {} : { sandbox: options.sandbox }),
      });
      return me === undefined ? json({ detail: "unknown_persona" }, 404) : json(me);
    },
    "GET /v1/me/capabilities": ({ persona }) => json(capabilitiesFor(seed, persona ?? "")),
    // AC 2.1.3: the office must be one of the active tenant's; offices filter, never restrict.
    "PUT /v1/me/preferences": ({ persona, body }) => {
      const wanted = (body as Partial<PreferencesIn> | null)?.default_office_id ?? null;
      if (wanted !== null && !OFFICE_REFS.some((o) => o.id === wanted)) {
        return json({ detail: "not_found" }, 404);
      }
      defaults = { ...defaults, [persona ?? ""]: wanted };
      const answer: PreferencesOut = { default_office_id: wanted };
      return json(answer);
    },
    // AC 2.1.6: the staff session ends (P-01-T09); the browser then goes to sign-in.
    "POST /v1/auth/sign-out": () => {
      const ended: SignedOutOut = { ended: true };
      return json(ended);
    },
  };
}

const at = (state: string, persona: string, options: { sandbox?: boolean } = {}): Scenario => ({
  state,
  persona,
  clock: E0.clock ?? "2026-09-14T09:24:00-05:00",
  handlers: shellHandlers(options),
});

export const scenarios = defineScenarios({
  /** Admin: Firm settings, Users & roles, Audit log; "All offices ⇕". */
  a: at("a", "grace-holloway", { sandbox: false }),
  /** Non-admin: no admin section; "Chicago ⇕". */
  b: at("b", "hannah-leclerc"),
  /** Partner: Firm settings (View only) and Audit log. */
  c: at("c", "daniel-reyes"),
  /** IT / Security: Security center, Developer & API (fixture only) and Audit log. */
  d: at("d", "felix-andersen"),
  /** Multi-firm: Grace's second membership, the training sandbox. */
  e: at("e", "grace-holloway"),
  /** Office submenu: All offices ✓ · Chicago · Denver · New York. */
  f: at("f", "grace-holloway", { sandbox: false }),
});
