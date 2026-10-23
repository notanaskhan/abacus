// SHL-06 firm sign-in: the states built in the product (P-01-T11; P-01 §5.3). a–f are the hosted
// provider's pages and have no scenario (docs/screens/SHL-06.md, Deviations). g is Hannah Leclerc
// landing from the BFF at Mon 14 Sep 2026, 9:24 AM CT: the refresh answers and `/v1/me` loads.
// `error` is the undesigned sign-in error state: the BFF refused (`?error=<code>`), or the refresh
// found no session. Each scenario names the landing's query string it opens on.

import type { ErrorOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { sessionHandlers } from "../handlers";
import { seedScenario } from "../scenario";

const E0 = seedScenario();

const at = (state: string, handlers: Scenario["handlers"] = {}): Scenario => ({
  state,
  persona: "hannah-leclerc",
  clock: E0.clock ?? "2026-09-14T09:24:00-05:00",
  handlers: { ...E0.handlers, ...sessionHandlers(), ...handlers },
});

const expired: ErrorOut = { detail: "session_expired" };

export const scenarios = defineScenarios({
  /** Signing in: "Signing in…" while the refresh and `/v1/me` answer, then the return path. */
  g: at("g"),
  /** The BFF refused the sign-in: no second factor on the provider's token (AC 5.1.2). */
  error: at("error"),
  /** The callback found no live session: the refresh answers 401 `session_expired`. */
  expired: at("expired", { "POST /v1/auth/refresh": () => json(expired, 401) }),
});

export type Shl06State = keyof typeof scenarios;

/** The landing each state opens on (`/signin/callback` + this). */
export const SEARCH: Readonly<Record<Shl06State, string>> = {
  g: "?to=%2Fengagements",
  error: "?error=mfa_required_at_sign_in",
  expired: "?to=%2Fengagements",
};
